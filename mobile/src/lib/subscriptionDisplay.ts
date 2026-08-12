/**
 * Display-only helpers for the subscription state returned by
 * `GET /api/v1/entitlements/status`.
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
 * Display names of the backend subscription tiers, kept in sync with the
 * `display_name` values of OFFERINGS_CONFIG in
 * `media_summarizer/api/endpoints/entitlements.py`.
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
 * Human-readable period end ("Sep 12", plus the year when it is not the
 * current one). Returns `null` for a missing or unparseable date so callers
 * render an explicit unknown instead of "Invalid Date".
 */
export function formatPeriodEnd(isoDate: string | null): string | null {
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
 * What the period end date means. `auto_renew_status` is nullable, and an
 * unknown renewal intent stays neutral rather than promising a renewal.
 */
export function getPeriodEndLabel(entitlement: EntitlementStatus): string {
  if (entitlement.auto_renew_status === true) return "RENEWS";
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
 * Reader carries no audio allowance at all, so its "0 minutes left" describes
 * the plan rather than an exhausted balance. Display nuance only — the balance
 * itself always comes from the backend.
 */
export function includesAudioMinutes(tier: string | null): boolean {
  return tier !== null && tier !== "S";
}
