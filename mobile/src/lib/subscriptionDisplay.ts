/**
 * Display-only helpers for the subscription state returned by
 * `GET /api/entitlements/status`.
 *
 * Nothing here decides what the user is allowed to do: tier and quota
 * enforcement lives in the backend (`quota_enforcer.py`), the only place it
 * cannot be bypassed. These helpers turn the payload into copy, and every
 * function degrades to `null` rather than guessing when a field is missing —
 * an unknown plan must never be rendered as a known one.
 */
import type { EntitlementStatus } from "../contexts/PurchasesContext";
import { formatDate, t } from "../i18n";

export type SubscriptionTier = "S" | "M" | "L";

/**
 * Display names of the backend subscription tiers.
 *
 * The store-facing enum (S/M/L) only ever travels on the entitlement payload,
 * which does not carry a label, so the account card needs one here. The paywall
 * does not: it reads the tier names from `GET /api/pricing` along with their
 * figures. If a tier is ever renamed, this map is the one place that follows.
 *
 * Deliberately **not** translated: these are the product names the pricing
 * config, the two store listings and `GET /api/pricing` all carry, and a plan
 * the user bought as "Reader" has to be called Reader on every screen of every
 * locale — the way an app's own name is not translated either.
 */
const TIER_LABELS: Record<SubscriptionTier, string> = {
  S: "Reader",
  M: "Mix",
  L: "Audio-Heavy",
};

/** Tier display name, or `null` for no tier / a tier this build does not know. */
export function getTierLabel(tier: string | null): string | null {
  if (!tier) return null;
  return TIER_LABELS[tier as SubscriptionTier] ?? null;
}

/**
 * Human-readable reset date ("Sep 12", plus the year when it is not the current
 * one). Returns `null` for a missing or unparseable date so callers render an
 * explicit unknown instead of "Invalid Date".
 */
export function formatResetDate(isoDate: string | null): string | null {
  if (!isoDate) return null;
  const timestamp = new Date(isoDate).getTime();
  if (Number.isNaN(timestamp)) return null;

  const date = new Date(timestamp);
  const isCurrentYear = date.getFullYear() === new Date().getFullYear();
  // The active UI locale rather than `undefined`, which resolves to the system
  // one and would ignore an in-app override.
  return formatDate(date, {
    month: "short",
    day: "numeric",
    ...(isCurrentYear ? {} : { year: "numeric" }),
  });
}

/**
 * What the `resets_at` date means. During the free trial it is the instant the
 * trial closes, after which nothing refills at all (task-300), so it is named
 * for what it is — `auto_renew_status` is always null on a trial, which used to
 * make it fall through to the vague "PERIOD ENDS". On a renewing plan the date
 * is when the minutes refill — nothing rolls over, so it is the only thing that
 * gives the remaining balance a deadline. On a plan that will not renew it is
 * when access stops instead, and `auto_renew_status` is nullable, so an unknown
 * renewal intent stays neutral rather than promising a refill.
 */
export function getResetDateLabel(entitlement: EntitlementStatus): string {
  if (entitlement.is_free_trial) return t("subscription.resetLabel.trialEnds");
  if (entitlement.auto_renew_status === true)
    return t("subscription.resetLabel.resets");
  if (entitlement.auto_renew_status === false)
    return t("subscription.resetLabel.ends");
  return t("subscription.resetLabel.periodEnds");
}

/**
 * Whole days left before `isoDate`, counted as **local midnight boundaries**:
 * 0 while the closing instant falls on today, 1 when it falls tomorrow, and so
 * on. Returns `null` for a missing or unparseable date, and never a negative
 * number.
 *
 * Counting boundaries rather than 24-hour slices is what keeps a countdown and
 * `formatResetDate` from disagreeing: both project the same instant into the
 * device's local calendar, so "2 days left" and "ends Sep 18" cannot be off by
 * a day the way a `Math.ceil` over elapsed milliseconds would be near midnight.
 *
 * This says nothing about entitlement — a 0 means "closes today", not "over".
 * Whether access is still granted is `is_free_trial` from the backend, and the
 * caller keeps that separation.
 */
export function getDaysUntil(isoDate: string | null, now: Date = new Date()): number | null {
  if (!isoDate) return null;
  const timestamp = new Date(isoDate).getTime();
  if (Number.isNaN(timestamp)) return null;

  const end = startOfLocalDay(new Date(timestamp));
  const today = startOfLocalDay(now);
  const days = Math.round((end - today) / MS_PER_DAY);
  return Math.max(0, days);
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/** Local midnight of the day `date` falls on, as a timestamp. */
function startOfLocalDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/**
 * Short note for the subscription statuses that keep access alive but still
 * need the user's attention. The entitlements endpoint only reports `active`,
 * `grace_period` and `canceled` as active, so anything else gets no note.
 */
export function getStatusNote(subscriptionStatus: string | null): string | null {
  switch (subscriptionStatus) {
    case "grace_period":
      return t("subscription.status.paymentIssue");
    case "canceled":
      return t("subscription.status.cancelled");
    default:
      return null;
  }
}

/**
 * How full the period's allowance is, as a 0..1 ratio for the usage bar.
 *
 * Clamped both ways: the backend counter is allowed to overshoot the allowance
 * (a settlement stores what the provider actually billed, which is the truth),
 * but a bar wider than its track is a rendering bug, not a message.
 */
export function getUsageRatio(entitlement: EntitlementStatus): number {
  if (entitlement.minutes_included <= 0) return 0;
  const ratio = entitlement.minutes_used / entitlement.minutes_included;
  return Math.min(1, Math.max(0, ratio));
}
