/**
 * Client-side reading of the backend quota enforcer contract.
 *
 * Every submission the enforcer refuses answers with the `X-Quota-Error-Code`
 * header (see `media_summarizer/core/services/quota_enforcer.py`) plus a detail
 * message that already names the limit that was reached. The header is what
 * tells us whether an upgrade is the fix: only a tier limit is solved by
 * subscribing, an oversized single audio file is not.
 */
import type { HttpError } from "./httpError";

export type QuotaErrorCode =
  /** Tier has no or too small an allowance: subscribing/upgrading fixes it. */
  | "tier_quota_exceeded"
  /** Single import longer than the per-import or tier ceiling. */
  | "audio_too_long"
  /** Per-day import counter exhausted; resets tomorrow. */
  | "daily_rate_limit"
  /** Global cost guard tripped; paused until the next billing period. */
  | "cost_hard_block";

const QUOTA_ERROR_CODES: readonly QuotaErrorCode[] = [
  "tier_quota_exceeded",
  "audio_too_long",
  "daily_rate_limit",
  "cost_hard_block",
];

const QUOTA_ERROR_TITLES: Record<QuotaErrorCode, string> = {
  tier_quota_exceeded: "Plan limit reached",
  audio_too_long: "Audio too long",
  daily_rate_limit: "Daily limit reached",
  cost_hard_block: "Imports paused",
};

const QUOTA_ERROR_FALLBACK_MESSAGES: Record<QuotaErrorCode, string> = {
  tier_quota_exceeded:
    "Your current plan does not cover this import. Upgrade to keep saving.",
  audio_too_long:
    "This audio is longer than the maximum allowed for a single import.",
  daily_rate_limit:
    "You reached today's import limit. Try again tomorrow.",
  cost_hard_block:
    "Imports are paused for the rest of this billing period.",
};

function isQuotaErrorCode(value: unknown): value is QuotaErrorCode {
  return (
    typeof value === "string" &&
    QUOTA_ERROR_CODES.includes(value as QuotaErrorCode)
  );
}

/**
 * Extract the quota code carried by a failed request, or null when the failure
 * did not come from the quota enforcer.
 */
export function getQuotaErrorCode(error: unknown): QuotaErrorCode | null {
  if (!error || typeof error !== "object") {
    return null;
  }
  const candidate = (error as HttpError).quotaErrorCode;
  return isQuotaErrorCode(candidate) ? candidate : null;
}

/**
 * Whether a paywall entry point is the right answer for this refusal.
 * Only a tier allowance is bought back with a subscription: a per-import
 * duration ceiling, a daily counter or the cost guard are not.
 */
export function quotaErrorOffersUpgrade(code: QuotaErrorCode): boolean {
  return code === "tier_quota_exceeded";
}

export function getQuotaErrorTitle(code: QuotaErrorCode): string {
  return QUOTA_ERROR_TITLES[code];
}

/**
 * The backend detail is the only place the actual figures live ("Monthly audio
 * quota reached (300/300 minutes used)"), so it is surfaced verbatim. It is
 * deliberately not routed through getFriendlyErrorMessage, whose /quota/ rule
 * would replace it with a generic sentence and drop the numbers.
 */
export function getQuotaErrorMessage(
  error: unknown,
  code: QuotaErrorCode,
): string {
  const detail =
    error instanceof Error ? error.message.trim() : String(error ?? "").trim();
  return detail.length > 0 ? detail : QUOTA_ERROR_FALLBACK_MESSAGES[code];
}
