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
 * lives in `buildPlanIncludes` below. It is the same for every tier, so it is
 * stated once under the cards instead of three times on them, and it is derived
 * from the app's own catalogues (`ARTIFACT_TILES`, `V1_READING_LANGUAGES`)
 * wherever one exists, so a capability cannot be advertised here after being
 * removed there.
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
        : `${formatMinutes(tier.minutes_per_month)} of audio and video transcribed every month`,
    perImportLimit:
      tier.max_minutes_per_item === null
        ? null
        : `Up to ${formatMinutes(tier.max_minutes_per_item)} in one single import`,
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

  const sentences = [
    MINUTES_RULE,
    "Audio and video count their real length, minute for minute.",
  ];

  // One rule per sentence. Strung together as a comma list they were unreadable
  // to anyone who did not already know the model they describe.
  if (captions !== null) {
    sentences.push(
      `A video that already has subtitles we can buy costs ${formatMinutes(captions)}, ` +
        "however long it is.",
    );
  }
  if (pagesPerMinute !== null) {
    sentences.push(
      "A PDF, an Office document or a photo we read the text off costs 1 min " +
        `per ${pagesPerMinute} pages.`,
    );
  }
  if (sourcesPerMinute !== null) {
    sentences.push(
      `A generation over a whole collection costs 1 min per ${sourcesPerMinute} ` +
        "items in it. On a single item it is free.",
    );
  }

  sentences.push(
    "Articles, web pages, TikToks and Instagram photo posts cost nothing at " +
      "all: they are not transcribed.",
  );
  sentences.push(
    "Past a plan's single-import maximum, an import is refused rather than " +
      "billed — split it into shorter parts.",
  );

  return sentences;
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
  const generations = ARTIFACT_TILES.map((tile) => tile.label.toLowerCase()).join(
    ", ",
  );
  const languageCount = V1_READING_LANGUAGES.length;

  return [
    {
      id: "capture",
      title: "Save anything, from any app",
      items: [
        "Share a link from any app, or paste one: YouTube videos, podcast " +
          "episodes from Apple Podcasts, Spotify, Deezer or any RSS feed, " +
          "TikToks, Instagram reels and photo posts, X posts, news articles " +
          "and any web page.",
        "Send a file from your phone: PDF, Word, PowerPoint and Excel " +
          "documents, photos and screenshots we read the text off, and audio " +
          "recordings (MP3, M4A, WAV, FLAC, AAC, OGG, Opus).",
      ],
    },
    {
      id: "read",
      title: "Read it, whatever it was",
      items: [
        "Audio and video come back as full text, transcribed word for word, so " +
          "an episode you have no time to listen to is one you can read, skim " +
          "or search instead.",
        `Transcripts are translated into your reading language, ${languageCount} to choose ` +
          "from, and you can change it whenever you like.",
      ],
    },
    {
      id: "generate",
      title: "Turn it into something you keep",
      items: [
        `On any item, on demand: ${generations}.`,
        "Run the same generations across a whole collection to get one " +
          "synthesis of everything you filed in it.",
        "Every generation is kept, so you can come back to it or ask for a " +
          "fresh one later.",
      ],
    },
    {
      id: "organise",
      title: "Find it again months later",
      items: [
        "File anything into collections and tags, at the moment you save it " +
          "or any time after.",
        "Full-text search across everything you have ever saved, transcripts " +
          "included.",
        "A daily and a weekly digest of what came in and what is worth going " +
          "back to.",
      ],
    },
    {
      id: "minutes",
      title: "What the monthly minutes count",
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

  const opening =
    trial === null
      ? "Your free trial is running"
      : `Your ${trial.duration_days}-day free trial is running`;
  const access = tierName === null ? "full access" : `${tierName} access`;
  const until = endsOn === null ? access : `${access} until ${endsOn}`;

  return `${opening}: ${until}, at no charge and nothing to cancel.`;
}
