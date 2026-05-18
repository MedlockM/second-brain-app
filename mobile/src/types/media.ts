/**
 * Media types for the mobile app.
 * Ported from front/src/types/media.ts - types needed for share intake and inbox.
 * Used by both Android share intent and iOS share extension flows.
 */

export type MediaType =
  | "podcast_episode"
  | "article"
  | "youtube_video"
  | "short_video"
  | "audio_file"
  | "shared_text"
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

export type ArtifactType = "summary" | "quiz" | "notes";

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

export interface ArtifactStatusSnapshot {
  status: ArtifactStatus;
  updated_at: string;
  artifact_id?: string;
}

export interface MediaItemContract {
  media_item_id: string;
  media_key: string;
  original_url: string;
  normalized_url: string;
  media_type: MediaType;
  source_platform: SourcePlatform;
  status: MediaItemStatus;
  transcript: TranscriptInfo;
  artifact_statuses: Partial<Record<ArtifactType, ArtifactStatusSnapshot>>;
  created_at: string;
  updated_at: string;
}

export interface IngestUrlRequest {
  url: string;
  source_app?: string;
  locale?: string;
  idempotency_key?: string;
}

export interface IngestUrlResponse {
  media_item: MediaItemContract;
  processing_job: ProcessingJobContract;
  deduplicated: boolean;
  duplicate_of_media_item_id?: string;
}

export interface MediaStatusResponse {
  media_item: MediaItemContract;
  processing_job: ProcessingJobContract;
  artifacts: Array<{
    artifact_id: string;
    media_item_id: string;
    artifact_type: ArtifactType;
    status: ArtifactStatus;
    created_at: string;
    updated_at: string;
  }>;
}
