import UIKit
import Social
import MobileCoreServices
import UniformTypeIdentifiers

/// iOS Share Extension view controller.
/// Receives shared content from the system share sheet and passes it to the main app
/// via App Groups shared UserDefaults and a custom URL scheme redirect.
///
/// Supported content types:
/// - URLs (existing flow)
/// - Plain text (WhatsApp text messages without URL)
/// - Audio files (WhatsApp voice messages: .opus, .m4a, .ogg, .mp4 audio)
///
/// The extension writes the shared content metadata to the App Groups container,
/// then opens the main app with the appropriate media-summarizer:// scheme parameters.
class ShareViewController: UIViewController {

    private let appGroupIdentifier = "group.com.mediasummarizer.app"
    private let sharedUrlKey = "SharedURL"
    private let appScheme = "media-summarizer"

    /// Audio UTTypes that WhatsApp may share
    private let audioTypes: [UTType] = [
        .audio,
        .mpeg4Audio,
        UTType("public.mp3")!,
        UTType("org.xiph.opus")!,
        UTType("org.xiph.ogg")!,
        UTType("com.apple.m4a-audio") ?? .mpeg4Audio
    ].compactMap { $0 }

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
                // Priority 1: Audio file (WhatsApp voice messages)
                if attachment.hasItemConformingToTypeIdentifier(UTType.audio.identifier) {
                    handleAudioAttachment(attachment)
                    return
                }

                // Priority 2: URL
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
                }

                // Priority 3: Plain text (may contain URL or be raw text)
                if attachment.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
                    attachment.loadItem(forTypeIdentifier: UTType.plainText.identifier, options: nil) { [weak self] data, error in
                        guard let self = self else { return }
                        if let text = data as? String {
                            self.processSharedText(text)
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

    /// Handle an audio file attachment (WhatsApp voice message).
    /// Copies the file to the App Group shared container and opens the main app.
    private func handleAudioAttachment(_ attachment: NSItemProvider) {
        // Try loading as file URL first (most common for audio)
        attachment.loadFileRepresentation(forTypeIdentifier: UTType.audio.identifier) { [weak self] url, error in
            guard let self = self, let sourceUrl = url else {
                // Fallback: try loading as data
                self?.handleAudioAsData(attachment)
                return
            }

            // Copy file to shared App Group container
            let fileManager = FileManager.default
            guard let containerUrl = fileManager.containerURL(
                forSecurityApplicationGroupIdentifier: self.appGroupIdentifier
            ) else {
                self.completeWithError()
                return
            }

            let fileName = sourceUrl.lastPathComponent
            let destinationUrl = containerUrl.appendingPathComponent("SharedAudio_\(fileName)")

            // Remove existing file if present
            try? fileManager.removeItem(at: destinationUrl)

            do {
                try fileManager.copyItem(at: sourceUrl, to: destinationUrl)

                // Determine MIME type
                let mimeType = self.mimeTypeForExtension(destinationUrl.pathExtension)

                // Get file size
                let attributes = try? fileManager.attributesOfItem(atPath: destinationUrl.path)
                let fileSize = attributes?[.size] as? Int ?? 0

                self.processSharedAudio(
                    fileUri: destinationUrl.absoluteString,
                    mimeType: mimeType,
                    fileName: fileName,
                    fileSize: fileSize
                )
            } catch {
                self.completeWithError()
            }
        }
    }

    /// Fallback: load audio attachment as raw data.
    private func handleAudioAsData(_ attachment: NSItemProvider) {
        attachment.loadItem(forTypeIdentifier: UTType.audio.identifier, options: nil) { [weak self] data, error in
            guard let self = self else { return }

            if let url = data as? URL {
                // Got a file URL after all
                let fileManager = FileManager.default
                guard let containerUrl = fileManager.containerURL(
                    forSecurityApplicationGroupIdentifier: self.appGroupIdentifier
                ) else {
                    self.completeWithError()
                    return
                }

                let fileName = url.lastPathComponent
                let destinationUrl = containerUrl.appendingPathComponent("SharedAudio_\(fileName)")
                try? fileManager.removeItem(at: destinationUrl)

                do {
                    try fileManager.copyItem(at: url, to: destinationUrl)
                    let mimeType = self.mimeTypeForExtension(destinationUrl.pathExtension)
                    let attributes = try? fileManager.attributesOfItem(atPath: destinationUrl.path)
                    let fileSize = attributes?[.size] as? Int ?? 0

                    self.processSharedAudio(
                        fileUri: destinationUrl.absoluteString,
                        mimeType: mimeType,
                        fileName: fileName,
                        fileSize: fileSize
                    )
                } catch {
                    self.completeWithError()
                }
            } else if let audioData = data as? Data {
                // Raw data: write to container
                let fileManager = FileManager.default
                guard let containerUrl = fileManager.containerURL(
                    forSecurityApplicationGroupIdentifier: self.appGroupIdentifier
                ) else {
                    self.completeWithError()
                    return
                }

                let fileName = "SharedAudio_\(UUID().uuidString).m4a"
                let destinationUrl = containerUrl.appendingPathComponent(fileName)

                do {
                    try audioData.write(to: destinationUrl)
                    self.processSharedAudio(
                        fileUri: destinationUrl.absoluteString,
                        mimeType: "audio/mp4",
                        fileName: fileName,
                        fileSize: audioData.count
                    )
                } catch {
                    self.completeWithError()
                }
            } else {
                self.completeWithError()
            }
        }
    }

    /// Process a shared text payload.
    /// Checks if it contains a URL; if so, uses the URL flow.
    /// Otherwise, passes it as raw text content.
    private func processSharedText(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            completeWithError()
            return
        }

        // Check if the text contains a URL
        if let url = extractUrl(from: trimmed) {
            processSharedUrl(url)
        } else {
            // No URL found: this is a plain text share (e.g., WhatsApp message)
            processSharedPlainText(trimmed)
        }
    }

    /// Process shared content as a URL (existing flow).
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
        completeSuccessfully()
    }

    /// Process shared content as plain text (no URL detected).
    private func processSharedPlainText(_ text: String) {
        let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier)
        sharedDefaults?.set(text, forKey: "SharedText")
        sharedDefaults?.set("text", forKey: "SharedContentType")
        sharedDefaults?.set(Date().timeIntervalSince1970, forKey: "SharedTextTimestamp")
        sharedDefaults?.synchronize()

        // Open the main app with text content type
        let encodedText = text.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? text
        let appUrl = URL(string: "\(appScheme)://share?contentType=text&text=\(encodedText)")!

        openURL(appUrl)
        completeSuccessfully()
    }

    /// Process shared audio file content.
    private func processSharedAudio(fileUri: String, mimeType: String, fileName: String, fileSize: Int) {
        let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier)
        sharedDefaults?.set(fileUri, forKey: "SharedAudioFileUri")
        sharedDefaults?.set(mimeType, forKey: "SharedAudioMimeType")
        sharedDefaults?.set(fileName, forKey: "SharedAudioFileName")
        sharedDefaults?.set(fileSize, forKey: "SharedAudioFileSize")
        sharedDefaults?.set("audio", forKey: "SharedContentType")
        sharedDefaults?.set(Date().timeIntervalSince1970, forKey: "SharedAudioTimestamp")
        sharedDefaults?.synchronize()

        // Open the main app with audio content type
        let encodedUri = fileUri.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? fileUri
        let encodedName = fileName.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? fileName
        let appUrl = URL(string: "\(appScheme)://share?contentType=audio&fileUri=\(encodedUri)&mimeType=\(mimeType)&fileName=\(encodedName)&fileSize=\(fileSize)")!

        openURL(appUrl)
        completeSuccessfully()
    }

    /// Extract a URL from text if present.
    private func extractUrl(from text: String) -> String? {
        // If the entire text is a URL
        if let url = URL(string: text), let scheme = url.scheme,
           (scheme == "http" || scheme == "https"), url.host != nil {
            return text
        }

        // Search for URLs within the text
        let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue)
        let range = NSRange(text.startIndex..., in: text)
        if let match = detector?.firstMatch(in: text, options: [], range: range),
           let url = match.url,
           let scheme = url.scheme,
           (scheme == "http" || scheme == "https") {
            return url.absoluteString
        }

        return nil
    }

    /// Determine MIME type from file extension.
    private func mimeTypeForExtension(_ ext: String) -> String {
        switch ext.lowercased() {
        case "opus": return "audio/ogg"
        case "ogg": return "audio/ogg"
        case "m4a": return "audio/mp4"
        case "mp3": return "audio/mpeg"
        case "aac": return "audio/aac"
        case "wav": return "audio/wav"
        case "flac": return "audio/flac"
        case "amr": return "audio/amr"
        case "mp4": return "audio/mp4"
        default: return "audio/mp4"
        }
    }

    private func completeSuccessfully() {
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
