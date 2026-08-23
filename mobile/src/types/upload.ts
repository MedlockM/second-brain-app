/**
 * Local file ingestion (task-264): importing a file from the device and taking
 * a photo, both of which end up on one of the two multipart upload endpoints.
 *
 * The two extension lists below mirror the backend exactly and are the reason a
 * refusal can be pronounced before any byte leaves the device:
 * - documents/images: `DocumentFormat.supported_extensions()`
 *   (`media_summarizer/core/ports/document_parser.py`) — parsed by LlamaParse,
 *   with OCR for the image formats
 * - audio: `_AUDIO_EXTENSIONS` (`media_summarizer/api/endpoints/media.py`) —
 *   transcribed by Deepgram
 *
 * A file whose extension is in neither list has no backend route, so offering it
 * would only produce a 400 after a pointless upload.
 */

import { t } from "../i18n";

/** Which upload endpoint a file belongs to. */
export type LocalUploadKind = "document" | "audio";

/** Extensions (no dot) accepted by POST /api/media/upload. */
export const DOCUMENT_UPLOAD_EXTENSIONS = [
  "pdf",
  "docx",
  "pptx",
  "xlsx",
  "jpg",
  "jpeg",
  "png",
  "tiff",
  "tif",
  "bmp",
  "heif",
  "heic",
] as const;

/** Extensions (no dot) accepted by POST /api/media/upload-audio. */
export const AUDIO_UPLOAD_EXTENSIONS = [
  "mp3",
  "m4a",
  "aac",
  "ogg",
  "wav",
  "flac",
  "opus",
] as const;

/**
 * MIME types handed to the document picker so the system browser only shows
 * files that have a backend route. Advisory only — some providers hand back
 * anything regardless of the filter, which is why `classifyUploadFile` runs on
 * the picked result and is the authoritative gate.
 */
export const UPLOAD_PICKER_MIME_TYPES = [
  // Documents
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  // Images (OCR)
  "image/jpeg",
  "image/png",
  "image/tiff",
  "image/bmp",
  "image/heic",
  "image/heif",
  // Audio (transcription)
  "audio/mpeg",
  "audio/mp4",
  "audio/x-m4a",
  "audio/aac",
  "audio/ogg",
  "audio/opus",
  "audio/wav",
  "audio/x-wav",
  "audio/flac",
] as const;

/**
 * Server-side ceiling for both upload endpoints (`MAX_UPLOAD_SIZE_BYTES`,
 * 50 MB by default). Mirrored here so an oversized file is refused with a clear
 * message instead of consuming the user's bandwidth for a 413.
 */
export const MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024;

/** A file picked or captured on the device, ready for the confirmation screen. */
export interface LocalUploadFile {
  /** Local URI (file:// or content://) */
  uri: string;
  /** File name including its extension — the backend routes on it. */
  name: string;
  mimeType: string;
  /** Bytes, or null when the picker did not report a size. */
  size: number | null;
  kind: LocalUploadKind;
}

/** Extract a lowercase extension without its dot, or "" when there is none. */
export function getFileExtension(fileName: string): string {
  const trimmed = fileName.trim();
  const lastDot = trimmed.lastIndexOf(".");
  if (lastDot <= 0 || lastDot === trimmed.length - 1) return "";
  return trimmed.slice(lastDot + 1).toLowerCase();
}

/**
 * Which endpoint this file goes to, or null when the backend accepts no such
 * extension.
 */
export function classifyUploadFile(fileName: string): LocalUploadKind | null {
  const ext = getFileExtension(fileName);
  if (!ext) return null;
  if ((DOCUMENT_UPLOAD_EXTENSIONS as readonly string[]).includes(ext)) {
    return "document";
  }
  if ((AUDIO_UPLOAD_EXTENSIONS as readonly string[]).includes(ext)) {
    return "audio";
  }
  return null;
}

/** Human-readable size, used in both refusal messages and previews. */
export function formatUploadSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** All accepted extensions, for the "not supported" message. */
export function getSupportedUploadExtensionsLabel(): string {
  return [...DOCUMENT_UPLOAD_EXTENSIONS, ...AUDIO_UPLOAD_EXTENSIONS]
    .map((ext) => `.${ext}`)
    .join(", ");
}

export type LocalUploadRejectionReason =
  | "unsupported_extension"
  | "too_large"
  | "empty";

export interface LocalUploadRejection {
  reason: LocalUploadRejectionReason;
  /** Message naming the reason, shown to the user as-is. */
  message: string;
}

/**
 * Turn a picked/captured file into either an accepted `LocalUploadFile` or a
 * rejection naming the reason. Nothing here touches the network: an unsupported
 * or oversized file never reaches the API.
 */
export function prepareLocalUploadFile(input: {
  uri: string;
  name: string;
  mimeType?: string | null;
  size?: number | null;
}): { file: LocalUploadFile } | { rejection: LocalUploadRejection } {
  const kind = classifyUploadFile(input.name);
  if (!kind) {
    const ext = getFileExtension(input.name);
    return {
      rejection: {
        reason: "unsupported_extension",
        message: ext
          ? t("upload.reject.extension", {
              extension: ext,
              formats: getSupportedUploadExtensionsLabel(),
            })
          : t("upload.reject.noExtension", {
              formats: getSupportedUploadExtensionsLabel(),
            }),
      },
    };
  }

  const size = input.size ?? null;
  if (size !== null && size === 0) {
    return {
      rejection: {
        reason: "empty",
        message: t("upload.reject.empty"),
      },
    };
  }
  if (size !== null && size > MAX_UPLOAD_SIZE_BYTES) {
    return {
      rejection: {
        reason: "too_large",
        message: t("upload.reject.tooLarge", {
          size: formatUploadSize(size),
          max: formatUploadSize(MAX_UPLOAD_SIZE_BYTES),
        }),
      },
    };
  }

  return {
    file: {
      uri: input.uri,
      name: input.name,
      mimeType: input.mimeType?.trim() || defaultMimeTypeFor(input.name),
      size,
      kind,
    },
  };
}

/**
 * Fallback MIME type when the picker reports none. Android content providers
 * routinely omit it, and the multipart part still needs a type.
 */
function defaultMimeTypeFor(fileName: string): string {
  const ext = getFileExtension(fileName);
  const map: Record<string, string> = {
    pdf: "application/pdf",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    png: "image/png",
    tiff: "image/tiff",
    tif: "image/tiff",
    bmp: "image/bmp",
    heif: "image/heif",
    heic: "image/heic",
    mp3: "audio/mpeg",
    m4a: "audio/mp4",
    aac: "audio/aac",
    ogg: "audio/ogg",
    wav: "audio/wav",
    flac: "audio/flac",
    opus: "audio/opus",
  };
  return map[ext] ?? "application/octet-stream";
}

/** Response shape of POST /api/media/upload. */
export interface UploadDocumentResponse {
  media_item_id: string;
  status: string;
  source_platform: string;
  file_name: string;
}

/** Response shape of POST /api/media/upload-audio. */
export interface UploadAudioResponse {
  media_item_id: string;
  status: string;
  source_platform: string;
}
