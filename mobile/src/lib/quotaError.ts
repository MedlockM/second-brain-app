/**
 * Client-side reading of the backend consumption contract.
 *
 * A refused submission answers with the `X-Quota-Error-Code` header (see
 * `media_summarizer/core/services/quota_enforcer.py`) plus a detail message that
 * already names the figures behind the refusal. Two codes exist, because there
 * are only two reasons an import can be refused, and the difference between them
 * is whether upgrading fixes it:
 *
 * - `out_of_minutes` — the period's minutes are spent. Upgrading buys more.
 * - `item_too_long` — this single item is longer than one import may use on this
 *   plan. Splitting it fixes it; upgrading is not the answer, so no paywall.
 */
import type { HttpError } from "./httpError";

export type QuotaErrorCode =
  /** No minutes left in the period (or no plan at all): upgrading fixes it. */
  | "out_of_minutes"
  /** One item longer than a single import may use on this plan. */
  | "item_too_long";

const QUOTA_ERROR_CODES: readonly QuotaErrorCode[] = [
  "out_of_minutes",
  "item_too_long",
];

const QUOTA_ERROR_TITLES: Record<QuotaErrorCode, string> = {
  out_of_minutes: "Out of minutes",
  item_too_long: "Too long for one import",
};

const QUOTA_ERROR_FALLBACK_MESSAGES: Record<QuotaErrorCode, string> = {
  out_of_minutes:
    "You're out of minutes for this period. Upgrade to keep importing audio and video.",
  item_too_long:
    "This is too long for a single import on your plan. Split it into shorter parts.",
};

function isQuotaErrorCode(value: unknown): value is QuotaErrorCode {
  return (
    typeof value === "string" &&
    QUOTA_ERROR_CODES.includes(value as QuotaErrorCode)
  );
}

/**
 * Extract the consumption code carried by a failed request, or null when the
 * failure did not come from the consumption gate.
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
 * Only an exhausted allowance is bought back with a subscription: a single item
 * that is too long stays too long on every tier the user could move to.
 */
export function quotaErrorOffersUpgrade(code: QuotaErrorCode): boolean {
  return code === "out_of_minutes";
}

export function getQuotaErrorTitle(code: QuotaErrorCode): string {
  return QUOTA_ERROR_TITLES[code];
}

/**
 * The backend detail is the only place the actual figures live ("That podcast is
 * 45 minutes and you have 12 left this month"), so it is surfaced verbatim. It is
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
