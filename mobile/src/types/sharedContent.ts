/**
 * Types for the shared content ingestion flow (non-URL shares).
 * Used when WhatsApp (or other apps) share raw text or audio files
 * that should be ingested via POST /api/media/ingest-shared-content.
 */

export type SharedContentType = "text" | "audio";

/**
 * Supported audio MIME types for shared audio ingestion.
 * WhatsApp voice messages use .opus (audio/ogg) on Android
 * and .m4a (audio/mp4) on iOS.
 */
export const SUPPORTED_AUDIO_MIME_TYPES = [
  "audio/ogg",
  "audio/opus",
  "audio/mp4",
  "audio/mpeg",
  "audio/x-m4a",
  "audio/aac",
  "audio/wav",
  "audio/x-wav",
  "audio/flac",
  "audio/amr",
] as const;

export type SupportedAudioMimeType = (typeof SUPPORTED_AUDIO_MIME_TYPES)[number];

/**
 * Maximum audio file size for shared content ingestion (25 MB).
 * WhatsApp voice messages are typically under 16 MB; this provides headroom.
 */
export const MAX_SHARED_AUDIO_SIZE_BYTES = 25 * 1024 * 1024;

/**
 * Maximum text length for shared text ingestion (50,000 characters).
 */
export const MAX_SHARED_TEXT_LENGTH = 50_000;

/**
 * Represents a file attachment received from a share intent.
 */
export interface SharedFileAttachment {
  /** Local file URI (content:// on Android, file:// on iOS) */
  uri: string;
  /** MIME type of the file */
  mimeType: string;
  /** Original filename if available */
  fileName: string | null;
  /** File size in bytes if known */
  fileSize: number | null;
}

/**
 * Request payload for text-type shared content ingestion.
 */
export interface IngestSharedTextRequest {
  share_type: "text";
  source_platform: "whatsapp";
  source_app: string;
  locale?: string;
  idempotency_key: string;
  text: string;
}

/**
 * Request payload for audio-type shared content ingestion.
 */
export interface IngestSharedAudioRequest {
  share_type: "audio";
  source_platform: "whatsapp";
  source_app: string;
  locale?: string;
  idempotency_key: string;
  content_mime_type: string;
  original_name: string;
}

/**
 * Response from POST /api/media/ingest-shared-content.
 * Matches the existing IngestUrlResponse shape for compatibility.
 */
export interface IngestSharedContentResponse {
  media_item_id: string;
  status: string;
  source_platform: string;
  deduplicated?: boolean;
  duplicate_of_media_item_id?: string;
}

/**
 * Determines if a MIME type is a supported audio type.
 */
export function isSupportedAudioMimeType(mimeType: string): boolean {
  const normalized = mimeType.toLowerCase().trim();
  return SUPPORTED_AUDIO_MIME_TYPES.includes(
    normalized as SupportedAudioMimeType,
  );
}

/**
 * Determines if a file attachment looks like a WhatsApp audio share
 * based on MIME type and optional filename heuristics.
 */
export function isWhatsAppAudioFile(file: SharedFileAttachment): boolean {
  // Check MIME type first
  if (isSupportedAudioMimeType(file.mimeType)) {
    return true;
  }

  // Fallback: check filename extension for common WhatsApp patterns
  if (file.fileName) {
    const lower = file.fileName.toLowerCase();
    const audioExtensions = [
      ".opus",
      ".ogg",
      ".m4a",
      ".mp3",
      ".aac",
      ".wav",
      ".flac",
      ".amr",
    ];
    return audioExtensions.some((ext) => lower.endsWith(ext));
  }

  return false;
}
