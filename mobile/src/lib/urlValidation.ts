/**
 * URL validation utilities for the share extension intake.
 * Validates and sanitizes URLs before ingestion submission.
 */

/**
 * Extracts the first URL found in a text string.
 * Handles cases where the shared text contains a URL mixed with other content.
 */
export function extractUrlFromText(text: string): string | null {
  if (!text || typeof text !== "string") {
    return null;
  }

  const trimmed = text.trim();
  if (trimmed.length === 0) {
    return null;
  }

  // Try to match a URL pattern in the text
  const urlRegex = /https?:\/\/[^\s<>"{}|\\^`[\]]+/i;
  const match = trimmed.match(urlRegex);

  if (match) {
    return cleanUrl(match[0]);
  }

  // If the entire text looks like a bare domain (e.g. "example.com/path"),
  // prepend https://
  const bareDomainRegex = /^[a-z0-9][-a-z0-9]*(\.[a-z]{2,})+([/?#].*)?$/i;
  if (bareDomainRegex.test(trimmed)) {
    return `https://${trimmed}`;
  }

  return null;
}

/**
 * Cleans a URL by removing trailing punctuation that may have been captured
 * from surrounding text context.
 */
function cleanUrl(url: string): string {
  // Remove trailing punctuation that is likely not part of the URL
  return url.replace(/[.,;:!?)]+$/, "");
}

/**
 * Validates that a URL is well-formed and uses an allowed scheme.
 */
export function isValidShareUrl(url: string): boolean {
  if (!url || typeof url !== "string") {
    return false;
  }

  try {
    const parsed = new URL(url);
    // Only allow http and https
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return false;
    }
    // Must have a hostname with at least one dot
    if (!parsed.hostname.includes(".")) {
      return false;
    }
    // Reject obviously invalid hostnames
    if (parsed.hostname.length < 3) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

export type UrlValidationResult =
  | { valid: true; url: string }
  | { valid: false; error: string };

/**
 * Validates shared content and extracts a valid URL.
 * Returns either the cleaned URL or a user-friendly error message.
 */
export function validateShareInput(text: string | null | undefined): UrlValidationResult {
  if (!text || text.trim().length === 0) {
    return { valid: false, error: "No content was shared. Please try again." };
  }

  const extracted = extractUrlFromText(text);

  if (!extracted) {
    return {
      valid: false,
      error: "No valid link found in the shared content. Please share a URL.",
    };
  }

  if (!isValidShareUrl(extracted)) {
    return {
      valid: false,
      error: "This link is invalid. Please try sharing a different URL.",
    };
  }

  return { valid: true, url: extracted };
}
