import { useEffect, useRef } from "react";
import { Linking, Platform, AppState, AppStateStatus } from "react-native";
import { useRouter } from "expo-router";
import {
  ShareIntentService,
  type ShareIntentPayload,
} from "../services/shareIntentService";
import { extractUrlFromText } from "../lib/urlValidation";
import { isWhatsAppAudioFile } from "../types/sharedContent";
import type { SharedFileAttachment } from "../types/sharedContent";

/**
 * Hook that listens for incoming share intents and navigates to the
 * share confirmation screen when valid content is received.
 *
 * Supports three content types:
 * - URL shares: text containing a valid URL (existing flow)
 * - Text shares: plain text without URL (WhatsApp text messages)
 * - Audio shares: audio file attachments (WhatsApp voice messages)
 *
 * iOS: Receives shared content via the app's custom URL scheme or App Groups.
 * Android: Receives shared text via intent filters (text/plain and audio/* SEND action).
 *
 * Must be used within a navigation context (expo-router).
 */
export function useShareIntent(): void {
  const router = useRouter();
  const processedKeys = useRef<Set<string>>(new Set());

  useEffect(() => {
    // Handle initial URL (app was opened via share)
    const handleInitialUrl = async () => {
      try {
        const initialUrl = await Linking.getInitialURL();
        if (initialUrl) {
          processShareInput(initialUrl);
        }
      } catch (error) {
        console.warn("[ShareIntent] Failed to get initial URL:", error);
      }
    };

    // Handle URL events while app is running
    const handleUrlEvent = (event: { url: string }) => {
      if (event.url) {
        processShareInput(event.url);
      }
    };

    // Handle app state changes (app comes to foreground from share extension)
    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === "active") {
        // Check for pending share intent when app becomes active
        const pending = ShareIntentService.consumePending();
        if (pending) {
          processSharePayload(pending);
        }
      }
    };

    handleInitialUrl();

    const linkingSubscription = Linking.addEventListener("url", handleUrlEvent);
    const appStateSubscription = AppState.addEventListener(
      "change",
      handleAppStateChange,
    );

    // Subscribe to ShareIntentService for programmatic receives
    const unsubscribeShareIntent = ShareIntentService.subscribe(
      (payload: ShareIntentPayload) => {
        processSharePayload(payload);
      },
    );

    return () => {
      linkingSubscription.remove();
      appStateSubscription.remove();
      unsubscribeShareIntent();
    };
  }, []);

  /**
   * Process a ShareIntentPayload (already parsed by the service).
   */
  function processSharePayload(payload: ShareIntentPayload): void {
    if (payload.contentType === "audio" && payload.files.length > 0) {
      const file = payload.files[0];
      processAudioFile(file);
      return;
    }

    if (payload.contentType === "text" && payload.text) {
      processTextShare(payload.text);
      return;
    }

    // Default: try URL extraction from text
    if (payload.text) {
      processShareInput(payload.text);
    }
  }

  /**
   * Process an incoming URL/text from a share intent.
   * Routes to the appropriate handler based on content type detection.
   */
  function processShareInput(rawInput: string): void {
    // Parse the incoming URL to check if it's our custom scheme
    let sharedText = rawInput;

    // Handle our custom URL scheme: media-summarizer://share?...
    if (rawInput.startsWith("media-summarizer://")) {
      try {
        const parsed = new URL(rawInput);
        const contentType = parsed.searchParams.get("contentType");

        // Handle audio content type from iOS share extension
        if (contentType === "audio") {
          const fileUri = parsed.searchParams.get("fileUri");
          const mimeType = parsed.searchParams.get("mimeType") ?? "audio/mp4";
          const fileName = parsed.searchParams.get("fileName");
          const fileSize = parsed.searchParams.get("fileSize");

          if (fileUri) {
            const file: SharedFileAttachment = {
              uri: decodeURIComponent(fileUri),
              mimeType,
              fileName: fileName ? decodeURIComponent(fileName) : null,
              fileSize: fileSize ? Number(fileSize) : null,
            };
            processAudioFile(file);
            return;
          }
        }

        // Handle text-only content type from iOS share extension
        if (contentType === "text") {
          const textParam = parsed.searchParams.get("text");
          if (textParam) {
            processTextShare(decodeURIComponent(textParam));
            return;
          }
        }

        // Existing URL handling
        const urlParam = parsed.searchParams.get("url");
        const textParam = parsed.searchParams.get("text");
        sharedText = urlParam || textParam || rawInput;
      } catch {
        // Not a valid scheme URL, treat as raw text
      }
    }

    // Extract URL from the shared text
    const extracted = extractUrlFromText(sharedText);

    if (extracted) {
      // URL found: use existing URL flow
      processUrlShare(extracted);
    } else if (sharedText && sharedText.trim().length > 0) {
      // No URL found: treat as plain text share (WhatsApp text message)
      processTextShare(sharedText.trim());
    }
  }

  /**
   * Process a URL share (existing flow).
   */
  function processUrlShare(url: string): void {
    const key = `url:${url}`;
    if (isDuplicate(key)) return;

    router.push({
      pathname: "/share-confirm",
      params: {
        url,
        sourceApp:
          Platform.OS === "ios"
            ? "ios-share-extension"
            : "android-share-intent",
      },
    });
  }

  /**
   * Process a plain text share (WhatsApp text message without URL).
   * Routes to the SharedContentService via the ShareIntentService.
   */
  function processTextShare(text: string): void {
    const key = `text:${text.slice(0, 100)}`;
    if (isDuplicate(key)) return;

    ShareIntentService.receiveText(
      text,
      Platform.OS === "ios" ? "ios-share-extension" : "android-share-intent",
    );
  }

  /**
   * Process an audio file share (WhatsApp voice message).
   * Routes to the SharedContentService via the ShareIntentService.
   */
  function processAudioFile(file: SharedFileAttachment): void {
    const key = `audio:${file.uri}`;
    if (isDuplicate(key)) return;

    if (!isWhatsAppAudioFile(file)) {
      console.warn(
        "[ShareIntent] Unsupported audio MIME type:",
        file.mimeType,
      );
      // Still attempt to process it -- the SharedContentService will validate
    }

    ShareIntentService.receiveAudioFile(
      file,
      Platform.OS === "ios" ? "ios-share-extension" : "android-share-intent",
    );
  }

  /**
   * Deduplication guard. Returns true if this key was already processed recently.
   */
  function isDuplicate(key: string): boolean {
    if (processedKeys.current.has(key)) {
      return true;
    }
    processedKeys.current.add(key);

    // Clear dedup after a short delay to allow re-sharing
    setTimeout(() => {
      processedKeys.current.delete(key);
    }, 5000);

    return false;
  }
}
