/**
 * Media types for the mobile app.
 * Ported from front/src/types/media.ts - types needed for share intake and inbox.
 * Used by both Android share intent and iOS share extension flows.
 */

/**
 * `document` and `audio` are what the two upload endpoints store on the library
 * row (task-264), and the list endpoint returns that value as-is. They are not
 * part of the canonical MediaType enum, so they only ever show up in a list
 * payload — the detail endpoint normalizes them to `article` / `audio_file`.
 */
export type MediaType =
  | "podcast_episode"
  | "article"
  | "youtube_video"
  | "short_video"
  | "audio_file"
  | "shared_text"
  | "document"
  | "audio"
  | "unknown";

export type SourcePlatform =
  | "spotify"
  | "apple_podcasts"
  | "deezer"
  | "rss"
  | "podcast_index"
  | "youtube"
  | "instagram"
  | "tiktok"
  | "x"
  | "whatsapp"
  | "web"
  | "direct_url"
  | "unknown";

export type MediaItemStatus =
  | "ingested"
  | "resolving"
  | "processing"
  | "ready_for_artifacts"
  | "failed"
  | "cancelled";

export type ProcessingJobLifecycleStatus =
  | "pending"
  | "classifying"
  | "resolving"
  | "downloading"
  | "extracting"
  | "transcribing"
  | "ready_for_artifacts"
  | "completed"
  | "failed"
  | "cancelled";

export type ArtifactStatus = "queued" | "generating" | "ready" | "failed";

/**
 * Internal artifact types as produced/accepted by the backend workers.
 * `summary` is the legacy alias still emitted by older items; new ones use
 * `summary_short` / `summary_detailed` explicitly.
 */
export type ArtifactType =
  | "summary"
  | "summary_short"
  | "summary_detailed"
  | "notes"
  | "quiz"
  | "flashcards";

/**
 * Chronological direction of a `GET /api/media` page (task-323).
 *
 * Mirrors the backend `SortDirection` literal: anything else is a 422 there, so
 * the two values are spelled out here rather than typed as a bare string.
 */
export type MediaSortDirection = "asc" | "desc";

export type TranscriptStatus =
  | "pending"
  | "extracting"
  | "transcribing"
  | "ready"
  | "failed";

export type CanonicalErrorCode =
  | "BAD_REQUEST"
  | "INVALID_URL"
  | "UNSUPPORTED_URL"
  | "SESSION_EXPIRED"
  | "NOT_AUTHORIZED"
  | "NOT_FOUND"
  | "MEDIA_NOT_FOUND"
  | "ARTIFACT_NOT_FOUND"
  | "CONFLICT"
  | "VALIDATION_ERROR"
  | "RATE_LIMITED"
  | "PAYMENT_REQUIRED"
  | "QUOTA_EXCEEDED"
  | "INSUFFICIENT_MINUTES"
  | "INTERNAL_ERROR";

export interface ProcessingProgress {
  percentage: number;
  stage: ProcessingJobLifecycleStatus;
}

export interface TranscriptInfo {
  status: TranscriptStatus;
  transcription_s3_key?: string;
  source?: string;
  language?: string;
  /**
   * Number of transcript paragraphs. Every producer reports the same unit since
   * task-232, so the value is comparable across sources.
   */
  segments_count?: number;
  duration_seconds?: number;
}

export interface ProcessingJobContract {
  job_id: string;
  status: ProcessingJobLifecycleStatus;
  progress: ProcessingProgress;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
  error_code?: CanonicalErrorCode;
  error_message?: string;
}

export interface MediaItemContract {
  media_item_id: string;
  media_key: string;
  /**
   * Display title of the durable library row — the same field `MediaListItem`
   * carries, so the detail header and the inbox vignette render one value. Null
   * while the item's metadata has not resolved yet.
   */
  title?: string | null;
  /**
   * Cover image, already resolved into a fetchable URL by the API — a re-hosted
   * cover is stored as an `s3://` locator server-side and signed on read, so a
   * client never sees one (task-304).
   */
  media_image?: string | null;
  /** Publisher of the media: a channel, a show, a site, an account. */
  creator_name?: string | null;
  original_url: string;
  normalized_url: string;
  media_type: MediaType;
  source_platform: SourcePlatform;
  status: MediaItemStatus;
  transcript: TranscriptInfo;
  folder_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IngestUrlRequest {
  url: string;
  source_app?: string;
  locale?: string;
  idempotency_key?: string;
  folder_id?: string | null;
  tag_ids?: string[];
}

export interface IngestUrlResponse {
  media_item: MediaItemContract;
  processing_job: ProcessingJobContract;
  deduplicated: boolean;
  duplicate_of_media_item_id?: string;
}

/**
 * Per-item detail shape. It carries no artifact projection: artifacts are an
 * append-only history per scope, so "the artifact of this type" no longer
 * exists. Read `GET /api/artifacts?scope=media&scope_id=...` through
 * `ArtifactService.listArtifacts`, which returns the history and the in-flight
 * entries in one call.
 */
export interface MediaStatusResponse {
  media_item: MediaItemContract;
  processing_job: ProcessingJobContract;
}

/**
 * The triage card mirrored from the `review_blurb` artifact (task-323).
 * Mirrors `ReviewBlurb` in `media_summarizer/core/models/user_media.py`.
 *
 * Three fields rather than one paragraph because the triage screen is scanned in
 * about three seconds, not read: `hook` is the headline, `points` the bullets,
 * `audience` the footer line. `audience` is empty when the sources are for no one
 * in particular, and the card then hides its last line rather than inventing a
 * reader.
 */
export interface ReviewBlurb {
  hook: string;
  points: string[];
  audience?: string | null;
}

/**
 * Flat list-row shape returned by `GET /api/media`.
 * Mirrors `MediaSearchItem` in `media_summarizer/api/endpoints/media.py`.
 * Distinct from `MediaStatusResponse` (which is the per-item detail shape).
 */
export interface MediaListItem {
  media_item_id: string;
  title?: string | null;
  /**
   * Triage card mirrored from the `review_blurb` artifact (task-323), for a
   * surface that has to say what a source is about without opening it.
   *
   * Nullable by contract and forever null on an item ingested before that task
   * or whose generation failed — a row without a blurb is a normal row, and the
   * only surface that reads it (the unsorted review) prints a fallback line.
   */
  review_blurb?: ReviewBlurb | null;
  /**
   * Publisher of the media — the tile's second line. Null for shared text,
   * documents and audio files, which have no creator by construction: the line
   * is then omitted rather than filled with a placeholder (task-304).
   */
  creator_name?: string | null;
  source_platform?: SourcePlatform | string | null;
  media_type?: MediaType | string | null;
  status: string;
  folder_id?: string | null;
  tag_ids: string[];
  source_url?: string | null;
  media_image?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  error_message?: string | null;
}
