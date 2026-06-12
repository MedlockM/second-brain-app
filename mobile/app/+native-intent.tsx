/**
 * Native intent handler for Expo Router.
 *
 * This file intercepts deep links BEFORE the router tries to match them
 * as pathnames. Without this, the share extension URL pattern:
 *   media-summarizer://dataUrl=<key>?nonce=<uuid>#weburl
 * would be parsed as path "/dataUrl=..." and trigger "Unmatched Route".
 *
 * We redirect those patterns to the inbox (a safe, always-mounted route).
 * The actual share-confirmation screen is opened by ShareIntentContext
 * AFTER it has resolved a valid intent from the native module — which
 * means a stale launch URL (e.g. on a Metro reload after a previous share)
 * no longer flashes the share-confirmation screen open and shut.
 *
 * Reference: https://docs.expo.dev/router/advanced/native-intent/
 */

type RedirectSystemPathOptions = {
  path: string;
  initial: boolean;
};

/**
 * Intercept system paths and rewrite share extension URLs to a safe route.
 *
 * The expo-share-intent package uses an extension key format:
 *   media-summarizer://dataUrl=<extensionKey>?nonce=<uuid>#<type>
 *
 * The extensionKey follows the pattern: <appScheme>ShareKey
 * (e.g. "media-summarizerShareKey")
 */
export function redirectSystemPath({
  path,
  initial: _initial,
}: RedirectSystemPathOptions): string {
  // Detect the share extension URL pattern from expo-share-intent
  // (contains "dataUrl=") and the plain share scheme variants. In both
  // cases the actual payload lives in the native side; ShareIntentContext
  // will navigate to /share-confirmation only if it resolves a valid intent.
  if (
    path.includes("dataUrl=") ||
    path.includes("://share?") ||
    path.includes("://share/")
  ) {
    return "/(tabs)/inbox";
  }

  // Let all other paths pass through normally
  return path;
}
