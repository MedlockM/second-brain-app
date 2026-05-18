import UIKit
import Social
import MobileCoreServices
import UniformTypeIdentifiers

/// iOS Share Extension view controller.
/// Receives shared URLs from the system share sheet and passes them to the main app
/// via App Groups shared UserDefaults and a custom URL scheme redirect.
///
/// The extension writes the shared URL to the App Groups container, then opens
/// the main app with the media-summarizer://share?url=... scheme.
class ShareViewController: UIViewController {

    private let appGroupIdentifier = "group.com.mediasummarizer.app"
    private let sharedUrlKey = "SharedURL"
    private let appScheme = "media-summarizer"

    override func viewDidLoad() {
        super.viewDidLoad()
        handleShare()
    }

    private func handleShare() {
        guard let extensionItems = extensionContext?.inputItems as? [NSExtensionItem] else {
            completeWithError()
            return
        }

        for item in extensionItems {
            guard let attachments = item.attachments else { continue }

            for attachment in attachments {
                if attachment.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                    attachment.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { [weak self] data, error in
                        guard let self = self else { return }
                        if let url = data as? URL {
                            self.processSharedUrl(url.absoluteString)
                        } else if let urlData = data as? Data, let urlString = String(data: urlData, encoding: .utf8) {
                            self.processSharedUrl(urlString)
                        } else {
                            self.completeWithError()
                        }
                    }
                    return
                } else if attachment.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
                    attachment.loadItem(forTypeIdentifier: UTType.plainText.identifier, options: nil) { [weak self] data, error in
                        guard let self = self else { return }
                        if let text = data as? String {
                            self.processSharedUrl(text)
                        } else {
                            self.completeWithError()
                        }
                    }
                    return
                }
            }
        }

        // No supported content found
        completeWithError()
    }

    private func processSharedUrl(_ urlString: String) {
        // Save to shared UserDefaults (App Groups)
        let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier)
        sharedDefaults?.set(urlString, forKey: sharedUrlKey)
        sharedDefaults?.set(Date().timeIntervalSince1970, forKey: "SharedURLTimestamp")
        sharedDefaults?.synchronize()

        // Open the main app via custom URL scheme
        let encodedUrl = urlString.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? urlString
        let appUrl = URL(string: "\(appScheme)://share?url=\(encodedUrl)")!

        openURL(appUrl)

        // Complete the extension
        DispatchQueue.main.async {
            self.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
        }
    }

    private func completeWithError() {
        DispatchQueue.main.async {
            let error = NSError(domain: "com.mediasummarizer.share", code: 0, userInfo: [
                NSLocalizedDescriptionKey: "Unable to process shared content"
            ])
            self.extensionContext?.cancelRequest(withError: error)
        }
    }

    /// Opens a URL from the share extension context.
    /// Uses the responder chain to access UIApplication.open since
    /// share extensions don't have direct access to UIApplication.shared.
    @objc private func openURL(_ url: URL) {
        var responder: UIResponder? = self as UIResponder
        let selector = sel_registerName("openURL:")
        while responder != nil {
            if responder!.responds(to: selector) {
                responder!.perform(selector, with: url)
                return
            }
            responder = responder?.next
        }
    }
}
