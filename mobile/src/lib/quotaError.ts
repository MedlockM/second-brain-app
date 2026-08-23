/**
 * Client-side reading of the backend consumption contract.
 *
 * A refused submission answers with the `X-Quota-Error-Code` header (see
 * `media_summarizer/core/services/quota_enforcer.py`) plus a typed body holding
 * the *figures* behind the refusal — never the sentence. The sentence is built
 * here, from this app's catalogue, because the server has no idea which of the
 * eleven interface languages the reader chose. Two codes exist, because there
 * are only two reasons an import can be refused, and the difference between them
 * is whether upgrading fixes it:
 *
 * - `out_of_minutes` — the period's minutes are spent, or there is no plan at
 *   all (`has_plan: false`). Upgrading buys more.
 * - `item_too_long` — this single item is longer than one import may use on this
 *   plan. Splitting it fixes it; upgrading is not the answer, so no paywall.
 */
import type { HttpError } from "./httpError";
import { formatDate, t, tCount } from "../i18n";
import { formatMinutes } from "./planCopy";

export type QuotaErrorCode =
  /** No minutes left in the period (or no plan at all): upgrading fixes it. */
  | "out_of_minutes"
  /** One item longer than a single import may use on this plan. */
  | "item_too_long";

const QUOTA_ERROR_CODES: readonly QuotaErrorCode[] = [
  "out_of_minutes",
  "item_too_long",
];

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
  return code === "out_of_minutes"
    ? t("quota.title.outOfMinutes")
    : t("quota.title.itemTooLong");
}

/** A figure from the refusal body, or `null` when the body did not carry it. */
function readNumber(
  details: Record<string, unknown>,
  key: string,
): number | null {
  const value = details[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** The period boundary, written for the active locale, or `null`. */
function readPeriodEnd(details: Record<string, unknown>): string | null {
  const raw = details.period_end;
  if (typeof raw !== "string") return null;
  const timestamp = new Date(raw).getTime();
  if (Number.isNaN(timestamp)) return null;
  const date = new Date(timestamp);
  const isCurrentYear = date.getFullYear() === new Date().getFullYear();
  return formatDate(date, {
    month: "short",
    day: "numeric",
    ...(isCurrentYear ? {} : { year: "numeric" }),
  });
}

/**
 * The refusal, worded from the figures the backend sent.
 *
 * Every branch has a shorter form for the figures that did not arrive, so a
 * refusal reaching the app without its body still says something true rather
 * than a sentence with a hole in it. Deliberately not routed through
 * `getFriendlyErrorMessage`, whose /quota/ rule would flatten all of this into
 * one generic line and drop the numbers.
 */
export function getQuotaErrorMessage(
  error: unknown,
  code: QuotaErrorCode,
): string {
  const details =
    (error as HttpError | undefined)?.details ??
    ({} as Record<string, unknown>);

  if (code === "item_too_long") {
    const needed = readNumber(details, "minutes_needed");
    const max = readNumber(details, "max_minutes_per_item");
    if (needed === null || max === null) {
      return t("quota.refusal.itemTooLongGeneric");
    }
    return t("quota.refusal.itemTooLong", {
      duration: formatMinutes(needed),
      max: formatMinutes(max),
    });
  }

  // No plan at all is a different sentence from an allowance run down: there is
  // no figure to quote and nothing has been spent.
  if (details.has_plan === false) {
    return t("quota.refusal.noPlan");
  }

  const remaining = readNumber(details, "minutes_remaining");
  const needed = readNumber(details, "minutes_needed");
  const periodEnd = readPeriodEnd(details);

  if (remaining !== null && remaining > 0 && needed !== null) {
    return periodEnd === null
      ? t("quota.refusal.needsMoreNoDate", {
          needed: tCount("duration.minutes", needed),
          remaining: tCount("duration.minutes", remaining),
        })
      : t("quota.refusal.needsMore", {
          needed: tCount("duration.minutes", needed),
          remaining: tCount("duration.minutes", remaining),
          date: periodEnd,
        });
  }

  return periodEnd === null
    ? t("quota.refusal.outOfMinutes")
    : t("quota.refusal.outOfMinutesUntil", { date: periodEnd });
}
