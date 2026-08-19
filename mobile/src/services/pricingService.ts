/**
 * What a plan costs and what it includes, read from the backend at runtime.
 *
 * `GET /api/pricing` serves the pricing config itself (DynamoDB, seeded from
 * `DEFAULT_PRICING_CONFIG` and editable through `PUT /api/pricing/admin`), so it
 * is the *only* place the app learns a tier's allowance, its per-import ceiling
 * or the trial terms. Nothing in `mobile/` restates those figures: before
 * task-299 they lived in three places at once and the screen had drifted from
 * the config it was supposed to describe.
 *
 * Public endpoint, so it is fetched without a session: the paywall must be able
 * to describe the plans even when the token is being rotated, and a price list
 * is not user data.
 */
import { Config } from "../constants/config";

/** One purchasable tier. `id` matches the RevenueCat package identifier. */
export interface PricingTier {
  id: string;
  name: string;
  name_fr: string;
  /** Configured price. The store package's own `priceString` wins when loaded. */
  price_ttc_eur: number | null;
  /** Minutes the tier includes per period. */
  minutes_per_month: number | null;
  /** Longest single import the tier accepts, in minutes. Over it: refusal. */
  max_minutes_per_item: number | null;
}

/** Server-side trial. Granted by account age — never a store introductory offer. */
export interface PricingFreeTrial {
  enabled: boolean;
  duration_days: number;
  /** Tier id the trial grants. */
  tier: string;
  minutes_per_month: number | null;
  max_minutes_per_item: number | null;
}

/** How a metered event converts into minutes, from `quota_enforcer`'s own table. */
export interface PricingUnitConversion {
  captions_minutes: number | null;
  document_pages_per_minute: number | null;
  collection_sources_per_minute: number | null;
}

export interface PublicPricing {
  tiers: PricingTier[];
  free_trial: PricingFreeTrial | null;
  unit_conversion: PricingUnitConversion;
  currency: string;
  billing_period: string;
}

/**
 * Fetch the public pricing. Throws on any failure: a paywall with no figures
 * must say so, never fall back to numbers baked into the build — that is exactly
 * the copy this endpoint replaces.
 */
export async function fetchPublicPricing(): Promise<PublicPricing> {
  const response = await fetch(`${Config.API_BASE_URL}/api/pricing`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Failed to load pricing: HTTP ${response.status}`);
  }

  return (await response.json()) as PublicPricing;
}
