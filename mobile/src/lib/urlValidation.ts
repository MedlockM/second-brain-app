/**
 * URL validation and extraction utilities for share intent payloads.
 *
 * Used by both Android share intent (SEND action with text/plain) and
 * iOS share extension. Shared payloads can contain:
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
    // If the entire text looks like a bare domain (e.g. "example.com/path"),
    // prepend https://
    const bareDomainRegex = /^[a-z0-9][-a-z0-9]*(\.[a-z]{2,})+([/?#].*)?$/i;
    if (bareDomainRegex.test(trimmed)) {
      return `https://${trimmed}`;
    }
    return null;
  }

  // Return the first valid URL found
  for (const match of matches) {
    const cleaned = cleanUrl(match);
    const parsed = tryParseUrl(cleaned);
    if (parsed) {
      return parsed;
    }
  }

  return null;
}

/**
 * Alias for extractUrlFromSharedText (used by iOS share extension code).
 */
export function extractUrlFromText(text: string): string | null {
  return extractUrlFromSharedText(text);
}

/**
 * Cleans a URL by removing trailing punctuation that may have been captured
 * from surrounding text context.
 */
function cleanUrl(url: string): string {
  return url.replace(/[.,;:!?)]+$/, "");
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
 * Validates that a URL is well-formed and uses an allowed scheme.
 */
export function isValidShareUrl(url: string): boolean {
  return tryParseUrl(url) !== null;
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
 * Alias result type for iOS share extension code.
 */
export type UrlValidationResult =
  | { valid: true; url: string }
  | { valid: false; error: string };

/**
 * Validates shared content and extracts a valid URL.
 * Returns either the cleaned URL or a user-friendly error message.
 * Used primarily by the iOS share extension flow.
 */
export function validateShareInput(text: string | null | undefined): UrlValidationResult {
  const result = validateShareIntentPayload(text);
  if (result.valid) {
    return result;
  }
  return { valid: false, error: getShareIntentErrorMessage(result.reason) };
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
