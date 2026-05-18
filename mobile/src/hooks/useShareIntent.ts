import { useEffect, useRef } from "react";
import { Linking, Platform, AppState, AppStateStatus } from "react-native";
import { useRouter } from "expo-router";
import { ShareIntentService } from "../services/shareIntentService";
import { extractUrlFromText } from "../lib/urlValidation";

/**
 * Hook that listens for incoming share intents and navigates to the
 * share confirmation screen when a valid URL is received.
 *
 * iOS: Receives shared URLs via the app's custom URL scheme or App Groups.
 * Android: Receives shared text via intent filters (text/plain SEND action).
 *
 * Must be used within a navigation context (expo-router).
 */
export function useShareIntent(): void {
  const router = useRouter();
  const processedUrls = useRef<Set<string>>(new Set());

  useEffect(() => {
    // Handle initial URL (app was opened via share)
    const handleInitialUrl = async () => {
      try {
        const initialUrl = await Linking.getInitialURL();
        if (initialUrl) {
          processShareUrl(initialUrl);
        }
      } catch (error) {
        console.warn("[ShareIntent] Failed to get initial URL:", error);
      }
    };

    // Handle URL events while app is running
    const handleUrlEvent = (event: { url: string }) => {
      if (event.url) {
        processShareUrl(event.url);
      }
    };

    // Handle app state changes (app comes to foreground from share extension)
    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === "active") {
        // Check for pending share intent when app becomes active
        const pending = ShareIntentService.consumePending();
        if (pending?.text) {
          processShareUrl(pending.text);
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
    const unsubscribeShareIntent = ShareIntentService.subscribe((payload) => {
      if (payload.text) {
        processShareUrl(payload.text);
      }
    });

    return () => {
      linkingSubscription.remove();
      appStateSubscription.remove();
      unsubscribeShareIntent();
    };
  }, []);

  /**
   * Process an incoming URL/text from a share intent.
   * Navigates to the share confirmation screen if a valid URL is found.
   */
  function processShareUrl(rawInput: string): void {
    // Parse the incoming URL to check if it's our custom scheme
    let sharedText = rawInput;

    // Handle our custom URL scheme: media-summarizer://share?url=...&text=...
    if (rawInput.startsWith("media-summarizer://")) {
      try {
        const parsed = new URL(rawInput);
        const urlParam = parsed.searchParams.get("url");
        const textParam = parsed.searchParams.get("text");
        sharedText = urlParam || textParam || rawInput;
      } catch {
        // Not a valid scheme URL, treat as raw text
      }
    }

    // Extract URL from the shared text
    const extracted = extractUrlFromText(sharedText);
    const urlToShare = extracted || sharedText;

    // Dedup: don't process the same URL twice within a session
    if (processedUrls.current.has(urlToShare)) {
      return;
    }
    processedUrls.current.add(urlToShare);

    // Clear dedup after a short delay to allow re-sharing
    setTimeout(() => {
      processedUrls.current.delete(urlToShare);
    }, 5000);

    // Navigate to the share confirmation screen
    router.push({
      pathname: "/share-confirm",
      params: {
        url: urlToShare,
        sourceApp: Platform.OS === "ios" ? "ios-share-extension" : "android-share-intent",
      },
    });
  }
}
