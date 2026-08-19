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

export type SubscriptionTier = "S" | "M" | "L";

/**
 * Display names of the backend subscription tiers.
 *
 * The store-facing enum (S/M/L) only ever travels on the entitlement payload,
 * which does not carry a label, so the account card needs one here. The paywall
 * does not: it reads the tier names from `GET /api/pricing` along with their
 * figures. If a tier is ever renamed, this map is the one place that follows.
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
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    ...(isCurrentYear ? {} : { year: "numeric" }),
  });
}

/**
 * What the `resets_at` date means. On a renewing plan it is when the minutes
 * refill — nothing rolls over, so that date is the only thing that gives the
 * remaining balance a deadline. On a plan that will not renew it is when access
 * stops instead, and `auto_renew_status` is nullable, so an unknown renewal
 * intent stays neutral rather than promising a refill.
 */
export function getResetDateLabel(entitlement: EntitlementStatus): string {
  if (entitlement.auto_renew_status === true) return "RESETS";
  if (entitlement.auto_renew_status === false) return "ENDS";
  return "PERIOD ENDS";
}

/**
 * Short note for the subscription statuses that keep access alive but still
 * need the user's attention. The entitlements endpoint only reports `active`,
 * `grace_period` and `canceled` as active, so anything else gets no note.
 */
export function getStatusNote(subscriptionStatus: string | null): string | null {
  switch (subscriptionStatus) {
    case "grace_period":
      return "Payment issue";
    case "canceled":
      return "Cancelled";
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
