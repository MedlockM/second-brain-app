/**
 * URL validation and extraction utilities for Android share intent payloads.
 *
 * Android SEND intents with text/plain can contain:
 * - A raw URL: "https://example.com/article"
 * - A URL with surrounding text: "Check this out https://example.com/article cool stuff"
 * - Plain text with no URL at all
 * - Malformed or unsupported schemes
 */

const URL_REGEX =
  /https?:\/\/[^\s<>"{}|\\^`\[\]]+/gi;

const SUPPORTED_SCHEMES = ["http:", "https:"];

/**
 * Extracts the first valid HTTP(S) URL from a shared text payload.
 * Returns null if no valid URL is found.
 */
export function extractUrlFromSharedText(text: string | null | undefined): string | null {
  if (!text || typeof text !== "string") {
    return null;
  }

  const trimmed = text.trim();
  if (trimmed.length === 0) {
    return null;
  }

  // Try to parse the entire text as a URL first (most common case)
  const directUrl = tryParseUrl(trimmed);
  if (directUrl) {
    return directUrl;
  }

  // Search for URLs within the text
  const matches = trimmed.match(URL_REGEX);
  if (!matches || matches.length === 0) {
    return null;
  }

  // Return the first valid URL found
  for (const match of matches) {
    const parsed = tryParseUrl(match);
    if (parsed) {
      return parsed;
    }
  }

  return null;
}

/**
 * Attempts to parse and validate a string as a URL.
 * Returns the cleaned URL string or null if invalid.
 */
function tryParseUrl(candidate: string): string | null {
  try {
    const url = new URL(candidate);

    if (!SUPPORTED_SCHEMES.includes(url.protocol)) {
      return null;
    }

    // Must have a hostname with at least one dot (no localhost-style URLs)
    if (!url.hostname.includes(".")) {
      return null;
    }

    // Hostname must not be empty after the protocol
    if (url.hostname.length < 3) {
      return null;
    }

    return url.toString();
  } catch {
    return null;
  }
}

/**
 * Result of validating a share intent payload.
 */
export type ShareIntentValidationResult =
  | { valid: true; url: string }
  | { valid: false; reason: ShareIntentErrorReason };

export type ShareIntentErrorReason =
  | "empty_payload"
  | "no_url_found"
  | "invalid_url";

/**
 * Validates an incoming share intent payload and extracts the URL.
 */
export function validateShareIntentPayload(
  text: string | null | undefined,
): ShareIntentValidationResult {
  if (!text || text.trim().length === 0) {
    return { valid: false, reason: "empty_payload" };
  }

  const url = extractUrlFromSharedText(text);

  if (!url) {
    return { valid: false, reason: "no_url_found" };
  }

  return { valid: true, url };
}

/**
 * Returns a user-friendly error message for a share intent validation failure.
 */
export function getShareIntentErrorMessage(reason: ShareIntentErrorReason): string {
  switch (reason) {
    case "empty_payload":
      return "Nothing was shared. Please try sharing a link from another app.";
    case "no_url_found":
      return "No link found in the shared content. Please share a URL.";
    case "invalid_url":
      return "The shared link is invalid. Please try a different URL.";
  }
}
