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
 *
 * What a plan *does* — the sources it accepts, the artifacts it generates, the
 * organisation and search around them — is the other half of the answer, and it
 * is the same for every tier, so it is stated once rather than three times on
 * the cards. It comes in two lengths, and both are built from the app's own
 * catalogues (`ARTIFACT_TILES`, `V1_READING_LANGUAGES`) wherever one exists, so
 * a capability cannot be advertised here after being removed there:
 *
 * - `buildPlanHighlights` — four check lines, under the plans. What a reader
 *   who has seen the prices wants confirmed before paying.
 * - `buildPlanIncludes` — the same four subjects, exhaustively, behind a
 *   disclosure. Kept because "everything an import can be" is a real question
 *   and the answer is long; put on screen unprompted it is the wall of text
 *   every paywall study says nobody reads.
 *
 * The screen also *argues*, and the second rule is that it may only argue from
 * checkable facts: `buildPlanGuidance` derives the recommended plan from minutes
 * the account really spent and "best value" from arithmetic on the store's own
 * prices, `buildHourlyRate` makes three allowances comparable without mental
 * division, and `buildPaywallReasonLine` restates the refusal the reader is
 * standing in. Nothing here claims popularity or urgency: with no users, both
 * would be inventions.
 */
import { ARTIFACT_TILES } from "../components/ArtifactTile";
import { V1_READING_LANGUAGES } from "../services/userPreferencesService";
import type { EntitlementStatus } from "../contexts/PurchasesContext";
import type {
  PublicPricing,
  PricingTier,
  PricingUnitConversion,
} from "../services/pricingService";
import { formatResetDate } from "./subscriptionDisplay";
import { formatNumber, getActiveLocale, t, tCount } from "../i18n";

/**
 * Human duration for a minute figure ("45 min", "3 h", "4 h 12 min").
 *
 * Same shape as `format_minutes()` in `media_summarizer/core/services/
 * quota_enforcer.py`, so the ceiling printed on a card and the one quoted in the
 * refusal that follows read identically.
 */
export function formatMinutes(minutes: number): string {
  const total = Math.max(0, Math.trunc(minutes));
  if (total < 60) return tCount("duration.minutes", total);
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return rest === 0
    ? tCount("duration.hours", hours)
    : t("duration.hoursMinutes", {
        hours: tCount("duration.hours", hours),
        minutes: tCount("duration.minutes", rest),
      });
}

/**
 * Money, formatted in the store's own currency.
 *
 * Only ever fed amounts *derived from the store package* (`product.price`,
 * `product.currencyCode`), never from the pricing config: the config holds one
 * EUR figure while the store bills whatever the user's storefront charges, so a
 * configured price rendered on a purchase screen is a price the user will not
 * be charged. Returns `null` rather than guessing when the platform has no Intl
 * data — a missing line is fine, a wrong currency is not.
 */
function formatCurrency(amount: number, currencyCode: string | null): string | null {
  if (currencyCode === null || currencyCode.length === 0) return null;
  try {
    // The active UI locale, never `undefined`: that resolves to the *system*
    // locale, which stops being the right answer the moment the in-app override
    // exists — a French interface would print a dollar amount US-style.
    return new Intl.NumberFormat(getActiveLocale(), {
      style: "currency",
      currency: currencyCode,
    }).format(amount);
  } catch {
    return null;
  }
}

/**
 * What an hour of transcription costs on a tier, e.g. "≈ 1,00 € an hour".
 *
 * The one figure that makes three plans comparable at a glance. Without it the
 * reader has to divide a price by an allowance in their head, and the actual
 * shape of the offer — the entry tier costs several times more per hour than the
 * one above it — stays invisible. Derived, never authored: it moves with both the
 * config's allowance and the store's price.
 */
export function buildHourlyRate(
  priceAmount: number | null,
  currencyCode: string | null,
  minutesPerMonth: number | null,
): string | null {
  if (priceAmount === null || !Number.isFinite(priceAmount) || priceAmount <= 0) {
    return null;
  }
  if (minutesPerMonth === null || minutesPerMonth <= 0) return null;
  const formatted = formatCurrency((priceAmount * 60) / minutesPerMonth, currencyCode);
  return formatted === null ? null : t("plan.hourlyRate", { price: formatted });
}

/** What one tier card shows. Every string is derived, none is authored twice. */
export interface PlanCard {
  /** Tier id, also the RevenueCat package identifier and the card's testID. */
  id: string;
  name: string;
  /** The tier's own monthly allowance — the card's dominant line. */
  allowance: string | null;
  /** Minutes behind `allowance`, for the hourly rate and the recommendation. */
  minutesPerMonth: number | null;
  /** The tier's own longest single import, which differs from tier to tier. */
  perImportLimit: string | null;
  /** The tier the server-side trial grants; highlighted, never labelled "popular". */
  isTrialTier: boolean;
}

function buildPlanCard(tier: PricingTier, trialTierId: string | null): PlanCard {
  return {
    id: tier.id,
    name: tier.name,
    // "a month" is carried by the price column ("per month"), not repeated here:
    // this line has to survive at 20px next to a price on a 375pt screen.
    allowance:
      tier.minutes_per_month === null
        ? null
        : t("plan.card.allowance", {
            duration: formatMinutes(tier.minutes_per_month),
          }),
    minutesPerMonth: tier.minutes_per_month,
    // Lower case and clause-shaped: it is read inside a "·"-separated meta line
    // under the allowance, never as a sentence of its own.
    perImportLimit:
      tier.max_minutes_per_item === null
        ? null
        : t("plan.card.perImport", {
            duration: formatMinutes(tier.max_minutes_per_item),
          }),
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
 * How much of the current allowance has to be spent before consumption is worth
 * reasoning from. A quarter: enough that the figure reflects a habit rather than
 * a first evening with the app, low enough that someone halfway through their
 * period still gets advice.
 */
const USAGE_SIGNAL_RATIO = 0.25;

/** Which plan the screen argues for, why, and what each card is labelled. */
export interface PlanGuidance {
  /** Tier the screen preselects, or `null` when nothing justifies a choice. */
  recommendedTierId: string | null;
  /** The reasoning, shown above the cards. `null` when there is none to give. */
  recommendationLine: string | null;
  /** Tier id → the single badge its card carries. */
  badges: Record<string, string>;
}

/**
 * Turn what the account has actually consumed into a recommendation.
 *
 * The screen used to preselect the trial's tier for everyone, including people
 * who never had a trial, and showed no reason at all — a card highlighted for
 * reasons the reader cannot see is just a nudge. Every label produced here is a
 * checkable fact instead: minutes the account really spent, an hourly rate
 * computed from the store's own price. Nothing claims popularity, which is not
 * something this app can honestly claim.
 *
 * Two rules shape the pick:
 *
 * - the smallest plan that covers the period's consumption, so the screen is
 *   allowed to argue *down* — recommending the cheapest plan that works is the
 *   part that makes the rest believable;
 * - never below the plan the user is currently living in. Someone three days
 *   into a trial has barely spent anything, and answering "take the cheaper one"
 *   would offer them less than what they are trying.
 *
 * With no consumption recorded there is nothing to reason from, so it returns no
 * line and lets the caller fall back to the trial's tier.
 */
export function buildPlanGuidance(
  cards: PlanCard[],
  /** Store price amount per tier id. Only tiers actually purchasable appear. */
  priceByTier: Record<string, number>,
  entitlement: EntitlementStatus | null,
): PlanGuidance {
  const badges: Record<string, string> = {};
  const ranked = cards
    .filter((card) => card.minutesPerMonth !== null && card.minutesPerMonth > 0)
    .sort((a, b) => (a.minutesPerMonth ?? 0) - (b.minutesPerMonth ?? 0));

  const isTrial = entitlement?.is_free_trial === true;
  const trialCard = cards.find((card) => card.isTrialTier) ?? null;
  const used = entitlement?.minutes_used ?? 0;
  const allowance = entitlement?.minutes_included ?? 0;
  // Consumption only becomes evidence once there is enough of it. Six minutes
  // spent trying the app out is noise, and the screen used to turn it into a
  // firm "Reader is the smallest plan that covers that", badge included —
  // advice built on a sample that says nothing, offered to someone who has not
  // yet found out what they would use the app for. Below the threshold there is
  // no line and no badge, and the selection falls back to the neutral default.
  const hasUsageSignal = allowance > 0 && used >= allowance * USAGE_SIGNAL_RATIO;

  let recommended: PlanCard | null = null;
  let recommendationLine: string | null = null;

  if (hasUsageSignal && ranked.length > 0) {
    const largest = ranked[ranked.length - 1];
    // Spending the whole allowance is not the same as spending part of it. The
    // figure stops being a measure of what the user needs and becomes the point
    // where they were stopped — their real need is *at least* that, and unknown
    // above it. Recommending the plan that covers it would hand them back the
    // one that just refused their import, so a capped period looks strictly one
    // size up instead.
    const isCapped = used >= allowance;

    if (isCapped) {
      const nextUp = ranked.find(
        (card) => (card.minutesPerMonth ?? 0) > allowance,
      ) ?? null;
      recommended = nextUp ?? largest;
      recommendationLine =
        nextUp === null
          ? t("plan.rec.cappedLargest", {
              duration: formatMinutes(allowance),
              plan: largest.name,
            })
          : t("plan.rec.cappedNextUp", {
              duration: formatMinutes(allowance),
              plan: nextUp.name,
            });
    } else {
      const covering =
        ranked.find((card) => (card.minutesPerMonth ?? 0) >= used) ?? null;
      // The plan being lived in is a floor, never a ceiling.
      const floor = isTrial && trialCard !== null ? trialCard : null;
      const floorMinutes = floor?.minutesPerMonth ?? 0;

      if (covering === null) {
        recommended = largest;
        recommendationLine = t("plan.rec.overLargest", {
          duration: formatMinutes(used),
          plan: largest.name,
        });
      } else if ((covering.minutesPerMonth ?? 0) < floorMinutes && floor !== null) {
        recommended = floor;
        recommendationLine = t("plan.rec.trialFloor", {
          duration: formatMinutes(used),
          plan: floor.name,
        });
      } else {
        recommended = covering;
        recommendationLine = t("plan.rec.covering", {
          duration: formatMinutes(used),
          plan: covering.name,
        });
      }
    }
  }

  if (recommended !== null) {
    badges[recommended.id] = t("plan.badge.recommended");
  }
  // A trial tier is worth naming, but only to someone the backend reports as
  // actually being in the trial — a badge for a trial they never had is a lie.
  if (isTrial && trialCard !== null && badges[trialCard.id] === undefined) {
    badges[trialCard.id] = t("plan.badge.yourTrial");
  }

  const cheapestPerMinute = pickBestValue(ranked, priceByTier);
  if (cheapestPerMinute !== null && badges[cheapestPerMinute] === undefined) {
    badges[cheapestPerMinute] = t("plan.badge.bestValue");
  }

  return {
    recommendedTierId: recommended?.id ?? trialCard?.id ?? null,
    recommendationLine,
    badges,
  };
}

/**
 * The tier with the lowest price per minute, or `null` when no single tier wins
 * outright. Arithmetic on the store's own prices, so it is a statement about the
 * offer rather than a marketing claim.
 */
function pickBestValue(
  ranked: PlanCard[],
  priceByTier: Record<string, number>,
): string | null {
  const rates = ranked
    .filter((card) => typeof priceByTier[card.id] === "number")
    .map((card) => ({
      id: card.id,
      rate: priceByTier[card.id] / (card.minutesPerMonth ?? 1),
    }));
  if (rates.length < 2) return null;

  const sorted = [...rates].sort((a, b) => a.rate - b.rate);
  return sorted[0].rate < sorted[1].rate ? sorted[0].id : null;
}

/** Why the paywall was opened, when the caller knows. */
export type PaywallReason = "out_of_minutes" | "running_low";

/**
 * The refusal the user is standing in, restated at the top of the paywall.
 *
 * The screen is reached from three places — the Account tab, the usage banner
 * and a submission the backend just refused — and used to look identical from
 * all three. Someone who arrives mid-import, having just been told they cannot
 * save the thing they were saving, should not have to re-derive why they are
 * looking at prices. Built from the live entitlement rather than from text
 * carried in the route, so the figures cannot go stale between the two screens.
 */
export function buildPaywallReasonLine(
  reason: PaywallReason | null,
  entitlement: EntitlementStatus | null,
): string | null {
  if (reason === null || entitlement === null) return null;

  const isTrial = entitlement.is_free_trial;
  const resetsOn = formatResetDate(entitlement.resets_at);

  if (reason === "out_of_minutes") {
    // A trial allowance is a single window that never refills (task-300), so
    // "they come back on the 12th" would be false for exactly the people most
    // likely to read this line.
    if (isTrial) {
      return t("paywall.reason.trialOut");
    }
    return resetsOn === null
      ? t("paywall.reason.outNoDate")
      : t("paywall.reason.outWithDate", { date: resetsOn });
  }

  const left = formatMinutes(entitlement.minutes_remaining);
  if (isTrial) {
    return t("paywall.reason.trialLow", { left });
  }
  return resetsOn === null
    ? t("paywall.reason.lowNoDate", { left })
    : t("paywall.reason.lowWithDate", { left, date: resetsOn });
}

/**
 * The one thing a minute is, said once. Also the Account tab's hint, so the
 * gauge there and the plans here explain themselves in the same words.
 *
 * "Reading your library", not "reading": consulting anything already saved is
 * free forever, but *importing* a PDF debits minutes, so the unqualified form
 * would have contradicted the very next sentence.
 */
export function minutesRule(): string {
  return t("plan.minutesRule");
}

/**
 * What debits a minute and what does not, built from the conversions the
 * enforcer actually applies. The free list is the exact set of paths
 * `quota_enforcer` charges zero for — a document is not on it, because five of
 * its pages cost a minute, and neither is any transcribed clip.
 *
 * Returned as separate sentences rather than one paragraph: this is the part a
 * reader has to hold four rules in their head for, and a wall of prose is where
 * they stop reading.
 */
export function buildMinutesLegend(pricing: PublicPricing): string[] {
  const conversion: Partial<PricingUnitConversion> = pricing.unit_conversion ?? {};
  const captions = conversion.captions_minutes ?? null;
  const pagesPerMinute = conversion.document_pages_per_minute ?? null;
  const sourcesPerMinute = conversion.collection_sources_per_minute ?? null;

  const sentences = [minutesRule(), t("plan.legend.realLength")];

  // One rule per sentence. Strung together as a comma list they were unreadable
  // to anyone who did not already know the model they describe.
  if (captions !== null) {
    sentences.push(
      t("plan.legend.captions", { duration: formatMinutes(captions) }),
    );
  }
  if (pagesPerMinute !== null) {
    sentences.push(
      t("plan.legend.documents", { pages: formatNumber(pagesPerMinute) }),
    );
  }
  if (sourcesPerMinute !== null) {
    sentences.push(
      t("plan.legend.collections", { sources: formatNumber(sourcesPerMinute) }),
    );
  }

  sentences.push(t("plan.legend.free"));
  sentences.push(t("plan.legend.overLimit"));

  return sentences;
}

/** One scannable promise, rendered as a check line above the plans. */
export interface PlanHighlight {
  /** React key and testID suffix — matches the id of the detailed section. */
  id: string;
  text: string;
}

/**
 * The four things a subscription does, one short line each, shown *above* the
 * plans.
 *
 * This is the version almost everyone reads. The detailed sections below say the
 * same four things exhaustively for the minority who open them, and the two are
 * built from the same catalogues so they cannot drift: same ids, same order.
 * A reader deciding between three allowances needs to know what an allowance
 * buys before they see the prices, not after the CTA.
 */
export function buildPlanHighlights(): PlanHighlight[] {
  return [
    { id: "capture", text: t("plan.highlight.capture") },
    { id: "read", text: t("plan.highlight.read") },
    {
      id: "generate",
      text: t("plan.highlight.generate", { list: listArtifactLabels() }),
    },
    { id: "organise", text: t("plan.highlight.organise") },
  ];
}

/** "summaries, notes, flashcards and quizzes", from the tiles themselves. */
function listArtifactLabels(): string {
  const labels = ARTIFACT_TILES.map((tile) => t(tile.labelKey).toLowerCase());
  if (labels.length < 2) return labels.join("");
  return t("plan.list.lastConjunction", {
    list: labels.slice(0, -1).join(t("plan.list.separator")),
    last: labels[labels.length - 1],
  });
}

/** A titled group of plain sentences, rendered as one block under the cards. */
export interface PlanIncludesSection {
  /** React key and testID suffix. */
  id: string;
  title: string;
  items: string[];
}

/**
 * Everything a subscription lets you do, in the order a newcomer meets it: put
 * something in, read it, turn it into something, find it again — then what the
 * meter counts.
 *
 * Why it exists: the cards carry the two figures that separate the tiers and
 * nothing else, which reads perfectly to someone who already uses the app and
 * says nothing at all to someone deciding whether to. None of this varies by
 * tier, so it belongs under the cards, once.
 *
 * Every list here is checkable against something in the repo, and the checks are
 * named so the next person can redo them: the sources are the classifier's own
 * hosts and `docs/INGESTION_WORKERS_PROVIDERS.md`, the file formats are
 * `UPLOAD_PICKER_MIME_TYPES` and `DocumentFormat.supported_extensions()`, the
 * generations are `ARTIFACT_TILES`, the languages `V1_READING_LANGUAGES`.
 * Nothing is promised that no worker delivers.
 */
export function buildPlanIncludes(pricing: PublicPricing): PlanIncludesSection[] {
  // Derived, not retyped: the tiles are what the media screen actually offers.
  const generations = ARTIFACT_TILES.map((tile) =>
    t(tile.labelKey).toLowerCase(),
  ).join(t("plan.list.separator"));
  const languageCount = V1_READING_LANGUAGES.length;

  return [
    {
      id: "capture",
      title: t("plan.includes.capture.title"),
      items: [
        t("plan.includes.capture.links"),
        t("plan.includes.capture.files"),
      ],
    },
    {
      id: "read",
      title: t("plan.includes.read.title"),
      items: [
        t("plan.includes.read.transcripts"),
        t("plan.includes.read.translation", {
          count: formatNumber(languageCount),
        }),
      ],
    },
    {
      id: "generate",
      title: t("plan.includes.generate.title"),
      items: [
        t("plan.includes.generate.onDemand", { list: generations }),
        t("plan.includes.generate.collection"),
        t("plan.includes.generate.kept"),
      ],
    },
    {
      id: "organise",
      title: t("plan.includes.organise.title"),
      items: [
        t("plan.includes.organise.file"),
        t("plan.includes.organise.search"),
        t("plan.includes.organise.digest"),
      ],
    },
    {
      id: "minutes",
      title: t("plan.includes.minutes.title"),
      items: buildMinutesLegend(pricing),
    },
  ];
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

  // The access clause is a noun phrase the sentence embeds, and the sentence
  // itself is one of four whole strings rather than a stem with clauses bolted
  // on: neither the order of "until <date>" nor the punctuation around the
  // colon survives translation intact.
  const access =
    tierName === null
      ? t("plan.trial.accessFull")
      : t("plan.trial.accessTier", { tier: tierName });

  if (trial === null) {
    return endsOn === null
      ? t("plan.trial.generic", { access })
      : t("plan.trial.genericWithDate", { access, date: endsOn });
  }
  return endsOn === null
    ? t("plan.trial.days", { access, days: formatNumber(trial.duration_days) })
    : t("plan.trial.daysWithDate", {
        access,
        days: formatNumber(trial.duration_days),
        date: endsOn,
      });
}
