/**
 * Types for the shared content ingestion flow (non-URL shares): raw text or an
 * audio file handed over by the system share sheet, ingested through
 * POST /api/media/ingest-shared-content.
 *
 * The two halves carry a different `source_platform`, and for a reason that is
 * platform-imposed rather than chosen (task-380):
 *
 * - **text -> `notes`**. Neither iOS nor Android names the app a share came from —
 *   `expo-share-intent` exposes no host-app field on either platform — so there is
 *   nothing to branch on. Shared text is therefore attributed to Notes, which is
 *   what it is in the overwhelming majority of cases (Apple Notes, Google Keep,
 *   Samsung Notes) and is an honest label for the rest.
 * - **audio -> `whatsapp`**. Voice notes are what WhatsApp actually sends, and it
 *   stays the source of those.
 */

import { formatNumber, t } from "../i18n";

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
 * Mirrors `MAX_SHARED_TEXT_LENGTH` in `media_summarizer/api/endpoints/media.py`,
 * so a note over the ceiling is refused with a readable reason on the device
 * instead of coming back as a 400.
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
  source_platform: "notes";
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

/** Why a shared note could not be turned into something to save. */
export type SharedNoteRejectionReason = "no_text" | "too_long";

export interface SharedNoteRejection {
  reason: SharedNoteRejectionReason;
  /** Message naming the reason, shown to the user as-is. */
  message: string;
}

/**
 * A shared note's text, or a rejection naming what is wrong with it (task-380).
 *
 * Two cases, both of which used to end in a screen that simply closed itself:
 * a note with nothing readable in it — a locked note hands over an empty string,
 * and so does a note holding only a drawing or a photo — and a note past the
 * server's ceiling. Neither is a bug to hide; both are a sentence the
 * confirmation screen can show.
 *
 * Shared by the confirmation flow and by `SharedContentService`, so the reason
 * the user reads and the reason the submission refuses can never diverge.
 */
export function validateSharedNoteText(
  rawText: string | null | undefined,
): { text: string } | { rejection: SharedNoteRejection } {
  const trimmed = (rawText ?? "").trim();
  if (!trimmed) {
    return {
      rejection: { reason: "no_text", message: t("share.reject.noText") },
    };
  }
  if (trimmed.length > MAX_SHARED_TEXT_LENGTH) {
    return {
      rejection: {
        reason: "too_long",
        message: t("share.reject.tooLong", {
          count: formatNumber(trimmed.length),
          max: formatNumber(MAX_SHARED_TEXT_LENGTH),
        }),
      },
    };
  }
  return { text: trimmed };
}
