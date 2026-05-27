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

export type SharedContentType = "text" | "audio";

export type MediaItemStatus =
  | "ingested"
  | "resolving"
  | "processing"
  | "ready_for_artifacts"
  | "failed"
  | "cancelled";

export type TranscriptStatus =
  | "pending"
  | "extracting"
  | "transcribing"
  | "ready"
  | "failed";

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

export type ArtifactType = "summary" | "quiz" | "notes";

export type ArtifactStatus = "queued" | "generating" | "ready" | "failed";

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

export interface CanonicalErrorPayload {
  code: CanonicalErrorCode;
  message: string;
  request_id?: string;
}

export interface CanonicalErrorResponse {
  error: CanonicalErrorPayload;
  detail?: string;
}

export interface ProcessingProgress {
  percentage: number;
  stage: ProcessingJobLifecycleStatus;
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

export interface TranscriptInfo {
  status: TranscriptStatus;
  transcription_s3_key?: string;
  source?:
    | "native_transcript"
    | "deepgram"
    | "article_extractor"
    | "shared_text"
    | string;
  language?: string;
  segments_count?: number;
  duration_seconds?: number;
}

export interface ArtifactSourceInfo {
  transcript_s3_key: string;
  generator_version?: string;
}

export interface SummaryContent {
  main_topics: string[];
  key_points: string[];
  notable_quotes: string[];
  conclusion: string | string[];
}

export interface SummaryArtifactPayload {
  artifact_id: string;
  media_item_id: string;
  artifact_type: "summary";
  podcast_title: string;
  episode_title: string;
  episode_image?: string;
  content: SummaryContent;
  transcription_length?: number;
  generated_at: string;
  source: ArtifactSourceInfo;
}

export interface QuizChoice {
  id: string;
  text: string;
  correct: boolean;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  multiple: boolean;
  choices: QuizChoice[];
  explanation?: string | null;
}

export interface QuizContent {
  id: string;
  episode_id: string | null;
  language: string;
  questions: QuizQuestion[];
}

export interface QuizArtifactPayload {
  artifact_id: string;
  media_item_id: string;
  artifact_type: "quiz";
  podcast_title: string;
  episode_title: string;
  episode_image?: string;
  generated_at: string;
  source: ArtifactSourceInfo;
  content: QuizContent;
}

export interface NotesConcept {
  term: string;
  explanation: string;
  importance: "core" | "supporting";
}

export interface NotesGlossaryItem {
  term: string;
  definition: string;
}

export interface NotesContent {
  objectives: string[];
  concepts: NotesConcept[];
  key_points: string[];
  action_items: string[];
  glossary: NotesGlossaryItem[];
}

export interface NotesArtifactPayload {
  artifact_id: string;
  media_item_id: string;
  artifact_type: "notes";
  generated_at: string;
  source: ArtifactSourceInfo;
  content: NotesContent;
}

export type ArtifactContentPayload =
  | SummaryArtifactPayload
  | QuizArtifactPayload
  | NotesArtifactPayload;

export interface ArtifactContentByType {
  summary: SummaryArtifactPayload;
  quiz: QuizArtifactPayload;
  notes: NotesArtifactPayload;
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

export interface MediaArtifactContract<
  TContent = Record<string, unknown> | ArtifactContentPayload,
> {
  artifact_id: string;
  media_item_id: string;
  artifact_type: ArtifactType;
  status: ArtifactStatus;
  parameters: Record<string, unknown>;
  content?: TContent;
  error_code?: CanonicalErrorCode;
  error_message?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface IngestUrlRequest {
  url: string;
  source_app?: string;
  locale?: string;
  idempotency_key?: string;
}

export interface IngestSharedContentRequest {
  share_type: SharedContentType;
  source_platform: SourcePlatform;
  source_app?: string;
  locale?: string;
  idempotency_key?: string;
  text?: string;
  content_mime_type?: string;
  original_name?: string;
  content_size_bytes?: number;
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
  artifacts: MediaArtifactContract[];
}

export interface ArtifactCreateRequest {
  artifact_type: ArtifactType;
  parameters?: Record<string, unknown>;
  idempotency_key?: string;
}

export interface ArtifactCreateResponse {
  artifact: MediaArtifactContract;
  reused_existing: boolean;
}

export interface ArtifactListResponse {
  media_item_id: string;
  items: MediaArtifactContract[];
  count: number;
}

export interface ArtifactDetailResponse<
  TContent = Record<string, unknown> | ArtifactContentPayload,
> {
  artifact: MediaArtifactContract<TContent>;
}
