/**
 * Native intent handler for Expo Router.
 *
 * This file intercepts deep links BEFORE the router tries to match them
 * as pathnames. Without this, the share extension URL pattern:
 *   media-summarizer://dataUrl=<key>?nonce=<uuid>#weburl
 * would be parsed as path "/dataUrl=..." and trigger "Unmatched Route".
 *
 * By detecting the share extension pattern here, we redirect to
 * /share-confirmation where our ShareIntentContext (backed by the
 * expo-share-intent package) handles the actual data resolution.
 *
 * Reference: https://docs.expo.dev/router/advanced/native-intent/
 */

type RedirectSystemPathOptions = {
  path: string;
  initial: boolean;
};

/**
 * Intercept system paths and redirect share extension URLs to the
 * share-confirmation screen.
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
  // Pattern: contains "dataUrl=" which is the App Groups data key
  if (path.includes("dataUrl=")) {
    return "/share-confirmation";
  }

  // Detect plain share text URLs that arrive via the scheme
  // Pattern: media-summarizer://share?text=... or media-summarizer://share?url=...
  if (path.includes("://share?") || path.includes("://share/")) {
    return "/share-confirmation";
  }

  // Let all other paths pass through normally
  return path;
}
