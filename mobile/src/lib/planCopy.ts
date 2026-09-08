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
 * cannot contradict the other: `minutesRule` is literally the sentence both
 * screens show — under the plan cards on one, under the usage gauge on the other
 * — and the refusal wording matches `quota_enforcer.py`.
 *
 * What a plan *does* is the same for every tier, so it is stated once rather
 * than three times on the cards — and after task-377 it is stated in three flat
 * blocks instead of a disclosure nobody opened:
 *
 * - `buildPromise` — one sentence, above the plans. What the app gives back.
 * - `buildSourceShowcase` — one chip per thing you can send, **derived from the
 *   list the backend serves** rather than written here. The prose version was
 *   retyped in eleven catalogues and had drifted: it sold Instagram photo posts
 *   the worker refuses and never mentioned WhatsApp. Names only, never a logo
 *   and never a look-alike pictogram — four of these brands forbid appearing in
 *   a row of logos on a screen that sells something.
 * - `buildCostTable` — what each kind of import debits, one row each, every
 *   figure interpolated from `unit_conversion`.
 *
 * The screen also *argues*, and the second rule is that it may only argue from
 * checkable facts: `buildPlanGuidance` derives the recommended plan from minutes
 * the account really spent and "best value" from arithmetic on the store's own
 * prices, `buildHourlyRate` makes three allowances comparable without mental
 * division, and `buildPaywallReasonLine` restates the refusal the reader is
 * standing in. Nothing here claims popularity or urgency: with no users, both
 * would be inventions.
 */
import type { EntitlementStatus } from "../contexts/PurchasesContext";
import type {
  PublicPricing,
  PricingShareTarget,
  PricingTier,
  PricingUnitConversion,
} from "../services/pricingService";
import { formatResetDate } from "./subscriptionDisplay";
import { formatNumber, getActiveLocale, t, tCount } from "../i18n";
import type { TranslationKey } from "../i18n";


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
    // The quantity, and nothing but the quantity.
    //
    // It used to name the process — "{duration} of transcription" — which made
    // the dominant line of the screen call the app an audio product, in a word
    // ("transcription") that is jargon in all eleven languages and false for
    // half of what the minutes actually buy: a PDF read for its text is not
    // transcribed, and it debits minutes all the same. Naming a process to
    // qualify a quantity is what Google One avoids by writing "Standard
    // (200 GB)" rather than "200 GB of file storage": the card carries the
    // amount, and what the amount buys is said **once, elsewhere** — here, in
    // the cost table right below the cards (`buildCostTable`), with figures.
    allowance:
      tier.minutes_per_month === null
        ? null
        : t("plan.card.allowance", {
            duration: formatMinutes(tier.minutes_per_month),
          }),
    minutesPerMonth: tier.minutes_per_month,
    // Lower case and clause-shaped: it is read inside a "·"-separated meta line
    // under the allowance, never as a sentence of its own.
    //
    // "at a time", not "in one import": the user shares or sends something, and
    // "import" is a word only the people who wrote the pipeline use.
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
 * The one thing a minute is, said once — and the one thing it is not.
 *
 * Read under the usage gauge in the Account tab, which is the surface that
 * *consults* a subscription. The paywall no longer shows it: there, the same
 * question is answered with figures by `buildCostTable`, and saying it twice on
 * one screen in two registers is how the two ended up disagreeing.
 *
 * It carries both halves of the answer. What the minutes cover (the audio and
 * video you send) qualifies the allowance the gauge counts down, and what they
 * do not cover (articles and web pages) is the half that surprises people —
 * someone watching a gauge fall wants to know what is moving it.
 *
 * "Cover", never "only cover": documents and folder-wide generations debit
 * minutes too (`buildCostTable`), so an exclusive form would be false.
 *
 * "Reading your library", not "reading": consulting anything already saved is
 * free forever, but *sending* a PDF debits minutes, so the unqualified form
 * would have contradicted the very next sentence.
 *
 * It no longer names transcription. The word is jargon in eleven languages and
 * only true of half the debits, and the sentence needs it for nothing: what the
 * user did is *send audio and video*, which is the fragment every catalogue
 * already carried.
 */
export function minutesRule(): string {
  return t("plan.minutesRule");
}

/**
 * One sentence about what the app gives back, above the plans.
 *
 * It replaces four check lines and five disclosure sections that between them
 * said everything and were read by nobody: the disclosure was two taps from the
 * only figures on the screen, and the four lines stood between the reader and
 * the prices. A purchase screen gets one sentence to say what it is for, and
 * everything else it has to say has to be readable at a glance — which is what
 * the showcase and the cost table below are.
 *
 * Deliberately not a list of features. Naming the five generations here would
 * put a five-item interpolated list in the header, three lines in German, and
 * push the first price further down the screen than the version this replaces —
 * undoing the one property the rearrangement exists for.
 */
export function buildPromise(): string {
  return t("paywall.promise");
}

/** Chips for what the user can send, in two rows that answer two questions. */
export interface SourceShowcase {
  /** Platforms and generic link kinds — proper nouns wherever there is one. */
  platforms: string[];
  /** File families, each chip listing its own formats: "PDF DOCX PPTX XLSX". */
  files: string[];
  /** The platform row as one spoken list, so VoiceOver stops once, not eleven times. */
  platformsSpoken: string;
  /** The file row as one spoken list, same reason. */
  filesSpoken: string;
}

/**
 * The showcase, resolved from the list `GET /api/pricing` serves.
 *
 * Nothing here decides *what* is on the list — that is
 * `core/media_ingestion/adapters/share_targets.py`, derived from the classifier's
 * own host tables, so the screen cannot advertise a platform no worker handles
 * or omit one it does. This only decides how each entry reads:
 *
 * - a proper noun (`YouTube`, `WhatsApp`) is shown as served, because it is the
 *   same word in every locale — `ar.ts` already writes these in Latin script;
 * - a file family is shown as its own formats, because "PDF DOCX PPTX XLSX"
 *   answers the question and "Documents" does not;
 * - an entry with neither gets its label from this app's catalogue, keyed by the
 *   backend's own id. Three exist, and all three are common nouns no brand owns.
 *
 * Text only, never a logo: Apple, TikTok, WhatsApp, Instagram and Spotify each
 * forbid, in writing, exactly the arrangement a logo row on a paid-subscription
 * screen would be. A pictogram that merely resembles a logo is worse, being an
 * imitation, so the chips carry words and nothing else.
 */
const GENERIC_SOURCE_LABEL_KEYS: Record<string, TranslationKey> = {
  // `SourcePlatform.WEB` — the classifier's terminal case, any host at all.
  web: "plan.source.web",
  // `SourcePlatform.DIRECT_URL` — any link whose path ends in an audio extension.
  direct_url: "plan.source.audioUrl",
  // `SourcePlatform.NOTES` — text shared from a notes app (task-380). Unbranded
  // on purpose: no platform names the app a share came from, so the chip cannot
  // honestly say "Apple Notes" and does not try.
  notes: "plan.source.notes",
};

function resolveChipLabel(target: PricingShareTarget): string | null {
  if (target.label !== null && target.label.length > 0) return target.label;
  if (target.formats.length > 0) return target.formats.join(" ");
  const key = GENERIC_SOURCE_LABEL_KEYS[target.id];
  // An id this build has no word for is left out rather than shown raw: a chip
  // reading "direct_url" would be worse than one chip fewer.
  return key === undefined ? null : t(key);
}

export function buildSourceShowcase(pricing: PublicPricing): SourceShowcase {
  const targets = pricing.sources ?? [];
  const labelsFor = (group: string): string[] =>
    targets
      .filter((target) => target.group === group)
      .map(resolveChipLabel)
      .filter((label): label is string => label !== null);

  const platforms = labelsFor("platform");
  const files = labelsFor("file");
  return {
    platforms,
    files,
    platformsSpoken: joinList(platforms),
    filesSpoken: joinList(files),
  };
}

/** "a, b and c", with the locale's own separator and conjunction. */
function joinList(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  return t("plan.list.lastConjunction", {
    list: items.slice(0, -1).join(t("plan.list.separator")),
    last: items[items.length - 1],
  });
}

/** One row of the cost table: what you send, and what it debits. */
export interface CostRow {
  /** React key and testID suffix. */
  id: string;
  label: string;
  /** Free, a real duration, or a conversion — always from the config. */
  value: string;
}

/**
 * What each kind of import debits, one row per regime the enforcer applies.
 *
 * Built here rather than in the screen so the two surfaces cannot disagree: the
 * Account tab states the same rule in prose (`minutesRule`) under its gauge, and
 * both now come out of this file.
 *
 * Every value is either a word ("Free", "Its real length") or a figure
 * interpolated from `unit_conversion` — `captions_minutes` for a YouTube video,
 * `document_pages_per_minute` for a document, `text_file_minutes` for a note
 * shared as a text file, `folder_sources_per_minute` for a folder-wide
 * generation. The "one minute" in the per-page and per-item rows is spelled out
 * because it is the *denominator's name* ("pages per minute"), not a number that
 * can change: nothing in `mobile/` writes a digit.
 *
 * Seven rows, not four. Three of them cost nothing and are kept apart on purpose —
 * "a podcast that publishes its own text is free" is a real tariff advantage
 * that has never been visible anywhere in the app, and "a note costs nothing"
 * is the answer to the question a text file raises — and the folder row is here
 * because a folder-wide generation genuinely debits minutes: leaving it out
 * would make the table understate what the meter counts.
 *
 * A regime whose conversion the config does not carry is dropped rather than
 * guessed. The two free rows and the real-length row need no figure, so they
 * always render, which keeps the table from ever being empty.
 */
export function buildCostTable(pricing: PublicPricing): CostRow[] {
  const conversion: Partial<PricingUnitConversion> = pricing.unit_conversion ?? {};
  const captions = conversion.captions_minutes ?? null;
  const pagesPerMinute = conversion.document_pages_per_minute ?? null;
  const sourcesPerMinute = conversion.folder_sources_per_minute ?? null;
  const textFileMinutes = conversion.text_file_minutes ?? null;

  const rows: CostRow[] = [
    {
      id: "free",
      label: t("plan.cost.free.label"),
      value: t("plan.cost.value.free"),
    },
  ];

  if (captions !== null) {
    rows.push({
      id: "captions",
      label: t("plan.cost.captions.label"),
      value: formatMinutes(captions),
    });
  }

  rows.push(
    {
      id: "transcript",
      label: t("plan.cost.transcript.label"),
      value: t("plan.cost.value.free"),
    },
    {
      id: "duration",
      label: t("plan.cost.duration.label"),
      value: t("plan.cost.value.realLength"),
    },
  );

  if (pagesPerMinute !== null) {
    rows.push({
      id: "document",
      label: t("plan.cost.document.label"),
      value: t("plan.cost.value.perPages", {
        pages: formatNumber(pagesPerMinute),
      }),
    });
  }
  if (textFileMinutes !== null) {
    // Its own row rather than folded into the document one: a note shared as a
    // text file has no pages, so the per-page rule does not describe it, and the
    // figure is read from the config even though it is currently zero — a tariff
    // the screen invents is a tariff that can go stale (task-380).
    rows.push({
      id: "textFile",
      label: t("plan.cost.textFile.label"),
      value:
        textFileMinutes === 0
          ? t("plan.cost.value.free")
          : formatMinutes(textFileMinutes),
    });
  }
  if (sourcesPerMinute !== null) {
    rows.push({
      id: "folder",
      label: t("plan.cost.folder.label"),
      value: t("plan.cost.value.perSources", {
        sources: formatNumber(sourcesPerMinute),
      }),
    });
  }

  return rows;
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
