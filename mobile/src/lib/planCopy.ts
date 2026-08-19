/**
 * Every sentence the app says about what a plan includes.
 *
 * One rule holds this file together: **no figure is written here**. Allowances,
 * per-import ceilings, trial length and the minute conversions all arrive from
 * `GET /api/pricing`, which serves the backend pricing config, and this module
 * only decides the words around them. That is what makes an owner's change
 * through `PUT /api/pricing/admin` move the screen with no build, and what stops
 * the paywall drifting from the enforcer the way it had (task-299).
 *
 * The paywall and the Account tab both read from here, so a rule stated on one
 * cannot contradict the other: `MINUTES_RULE` is literally the sentence both
 * screens show, and the refusal wording matches `quota_enforcer.py`.
 */
import type { EntitlementStatus } from "../contexts/PurchasesContext";
import type {
  PublicPricing,
  PricingTier,
  PricingUnitConversion,
} from "../services/pricingService";
import { formatResetDate } from "./subscriptionDisplay";

/**
 * Human duration for a minute figure ("45 min", "3 h", "4 h 12 min").
 *
 * Same shape as `format_minutes()` in `media_summarizer/core/services/
 * quota_enforcer.py`, so the ceiling printed on a card and the one quoted in the
 * refusal that follows read identically.
 */
export function formatMinutes(minutes: number): string {
  const total = Math.max(0, Math.trunc(minutes));
  if (total < 60) return `${total} min`;
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

/** Configured price as a fallback label, e.g. "5 EUR/mo". */
function formatConfiguredPrice(price: number | null): string | null {
  if (price === null || !Number.isFinite(price)) return null;
  const rounded = Math.round(price * 100) / 100;
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(2)} EUR/mo`;
}

/** What one tier card shows. Every string is derived, none is authored twice. */
export interface PlanCard {
  /** Tier id, also the RevenueCat package identifier and the card's testID. */
  id: string;
  name: string;
  /** Shown only until the store package is loaded, then its price wins. */
  configuredPrice: string | null;
  /** The tier's own monthly allowance, stated once on the card. */
  allowance: string | null;
  /** The tier's own longest single import, which differs from tier to tier. */
  perImportLimit: string | null;
  /** The tier the server-side trial grants; highlighted, never labelled "popular". */
  isTrialTier: boolean;
}

function buildPlanCard(tier: PricingTier, trialTierId: string | null): PlanCard {
  return {
    id: tier.id,
    name: tier.name,
    configuredPrice: formatConfiguredPrice(tier.price_ttc_eur),
    allowance:
      tier.minutes_per_month === null
        ? null
        : `${formatMinutes(tier.minutes_per_month)} of audio and video a month`,
    perImportLimit:
      tier.max_minutes_per_item === null
        ? null
        : `${formatMinutes(tier.max_minutes_per_item)} max per import`,
    isTrialTier: trialTierId !== null && tier.id === trialTierId,
  };
}

export function buildPlanCards(pricing: PublicPricing): PlanCard[] {
  const trial = pricing.free_trial;
  const trialTierId = trial && trial.enabled ? trial.tier : null;
  // Defensive on the payload's own shape, not on an older contract: this is a
  // parsed network response, and a missing key must leave a sentence out, never
  // throw inside a render.
  return (pricing.tiers ?? []).map((tier) => buildPlanCard(tier, trialTierId));
}

/**
 * The one thing a minute is, said once. Also the Account tab's hint, so the
 * gauge there and the plans here explain themselves in the same words.
 *
 * "Reading your library", not "reading": consulting anything already saved is
 * free forever, but *importing* a PDF debits minutes, so the unqualified form
 * would have contradicted the very next sentence.
 */
export const MINUTES_RULE =
  "Minutes cover audio and video we transcribe. Reading your library is unlimited.";

/**
 * What debits a minute and what does not, built from the conversions the
 * enforcer actually applies. The free list is the exact set of paths
 * `quota_enforcer` charges zero for — a document is not on it, because five of
 * its pages cost a minute, and neither is any transcribed clip.
 */
export function buildMinutesLegend(pricing: PublicPricing): string {
  const conversion: Partial<PricingUnitConversion> = pricing.unit_conversion ?? {};
  const captions = conversion.captions_minutes ?? null;
  const pagesPerMinute = conversion.document_pages_per_minute ?? null;
  const sourcesPerMinute = conversion.collection_sources_per_minute ?? null;

  const sentences = [MINUTES_RULE];

  const conversions: string[] = ["Audio and video count their real length"];
  if (captions !== null) {
    conversions.push(`a video with bought subtitles ${formatMinutes(captions)}`);
  }
  if (pagesPerMinute !== null) {
    conversions.push(`a PDF 1 min per ${pagesPerMinute} pages`);
  }
  if (sourcesPerMinute !== null) {
    conversions.push(
      `a whole-collection generation 1 min per ${sourcesPerMinute} sources`,
    );
  }
  sentences.push(`${conversions.join(", ")}.`);

  sentences.push(
    "Articles, web pages, TikToks, Instagram photo posts and single-item " +
      "generations count nothing.",
  );
  sentences.push(
    "Past a plan's per-import maximum an import is refused, not billed: split " +
      "it into shorter parts.",
  );

  return sentences.join(" ");
}

/**
 * The trial line, or `null` when the caller is not in one.
 *
 * Built from the live entitlement (`is_free_trial`, `resets_at`) rather than
 * printed as a standing offer, so the screen stays true on day 31 — the trial is
 * granted by account age and never comes back. It is a server-side trial, not a
 * store introductory offer (`task-261`), which is why it says no charge and
 * nothing to cancel: there is no purchase behind it to cancel.
 */
export function buildFreeTrialLine(
  pricing: PublicPricing | null,
  entitlement: EntitlementStatus | null,
): string | null {
  if (!entitlement?.is_free_trial) return null;

  const trial = pricing?.free_trial ?? null;
  const tierName =
    trial === null
      ? null
      : (pricing?.tiers.find((tier) => tier.id === trial.tier)?.name ?? null);
  const endsOn = formatResetDate(entitlement.resets_at);

  const opening =
    trial === null
      ? "Your free trial is running"
      : `Your ${trial.duration_days}-day free trial is running`;
  const access = tierName === null ? "full access" : `${tierName} access`;
  const until = endsOn === null ? access : `${access} until ${endsOn}`;

  return `${opening}: ${until}, at no charge and nothing to cancel.`;
}
