/**
 * Local file ingestion (task-264): importing a file from the device and taking
 * a photo, both of which end up on one of the two upload endpoints — through a
 * presigned S3 PUT, since neither endpoint accepts bytes (task-345).
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

/**
 * The image half of the document endpoint: extensions the backend OCRs rather
 * than parses. Named apart because a share or an import that lands on one of them
 * is shown as a picture, not as a file card (`isImageUpload`).
 */
export const IMAGE_UPLOAD_EXTENSIONS = [
  "jpg",
  "jpeg",
  "png",
  "tiff",
  "tif",
  "bmp",
  "heif",
  "heic",
] as const;

/** Extensions (no dot) accepted by POST /api/media/upload. */
export const DOCUMENT_UPLOAD_EXTENSIONS = [
  "pdf",
  "docx",
  "pptx",
  "xlsx",
  ...IMAGE_UPLOAD_EXTENSIONS,
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
 * 50 MB, in `media_summarizer/api/endpoints/media.py`). The same value is what
 * `POST /api/media/upload-url` checks before signing anything, so mirroring it
 * here refuses an oversized file with a clear message on the device instead of
 * spending the user's bandwidth to be told the same thing.
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
 * The extension a file of each accepted format is expected to carry, and the MIME
 * type that goes with it. Read in both directions: down to name the Content-Type
 * of an S3 PUT when the picker reported none, up to recover an extension when the
 * name has none (`extensionForMimeType`).
 */
const EXTENSION_MIME_TYPES: Record<string, string> = {
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

/**
 * MIME type -> extension, the reverse of the map above plus the spellings the
 * platforms actually report for the same bytes (the iOS share extension calls a
 * bitmap `image/x-ms-bmp`, Android content providers hand back `image/jpg` and
 * `audio/x-m4a`).
 *
 * First declaration wins, which is what makes `image/jpeg` resolve to `jpg` and
 * `image/tiff` to `tiff` rather than to their aliases.
 */
const MIME_TYPE_EXTENSIONS: Record<string, string> = Object.entries(
  EXTENSION_MIME_TYPES,
).reduce<Record<string, string>>(
  (acc, [ext, mimeType]) => {
    if (!(mimeType in acc)) acc[mimeType] = ext;
    return acc;
  },
  {
    "image/jpg": "jpg",
    "image/x-ms-bmp": "bmp",
    "audio/x-m4a": "m4a",
    "audio/x-wav": "wav",
  },
);

/** The extension for a MIME type the backend accepts, or "" for anything else. */
function extensionForMimeType(mimeType?: string | null): string {
  const normalized = mimeType?.trim().split(";")[0].toLowerCase();
  if (!normalized) return "";
  return MIME_TYPE_EXTENSIONS[normalized] ?? "";
}

/**
 * Fallback MIME type when the picker reports none. Android content providers
 * routinely omit it, and the PUT to S3 still needs a Content-Type — it is what
 * the object keeps, and what the ingestion endpoint reads back from it.
 */
function defaultMimeTypeFor(fileName: string): string {
  return (
    EXTENSION_MIME_TYPES[getFileExtension(fileName)] ??
    "application/octet-stream"
  );
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

/**
 * A file name that carries an extension the backend can route on, for content
 * arriving from the system share sheet.
 *
 * The extension is the only discriminant `classifyUploadFile` has, and the name
 * reported by a share is not guaranteed to have one: iOS hands over `uuid +
 * extension` and Android the provider's `DISPLAY_NAME`, but a screenshot passed
 * as raw image data reaches the extension with no name at all. So when the
 * reported name has no usable extension, one is recovered from the copied file's
 * `path` and then from the `mimeType` — refusing a PNG the backend knows how to
 * OCR because nobody bothered to name it would be a silent dead end (task-347).
 *
 * Returns the reported name untouched when it already routes, and when nothing
 * can be recovered — an unsupported format still has to reach its refusal.
 */
export function resolveUploadFileName(input: {
  fileName?: string | null;
  path: string;
  mimeType?: string | null;
}): string {
  const reported = input.fileName?.trim() ?? "";
  if (reported && classifyUploadFile(reported)) {
    return reported;
  }

  // The share extension copies the item to `<uuid>.<ext>`, so the path carries
  // the extension even when the name does not. Query and fragment go first: the
  // path is a URL, not a file system path.
  const pathName = input.path.split(/[?#]/)[0].split("/").pop() ?? "";
  const recovered =
    (classifyUploadFile(pathName) ? getFileExtension(pathName) : "") ||
    extensionForMimeType(input.mimeType);
  if (!recovered) {
    return reported || "file";
  }

  const stem =
    stripExtension(reported) ||
    stripExtension(pathName) ||
    `shared-${Date.now()}`;
  return `${stem}.${recovered}`;
}

/** A file name without its extension, or "" when there is nothing left. */
function stripExtension(fileName: string): string {
  const trimmed = fileName.trim();
  const lastDot = trimmed.lastIndexOf(".");
  return (lastDot > 0 ? trimmed.slice(0, lastDot) : trimmed).trim();
}

/**
 * Whether this upload is a picture, and should therefore be presented as one
 * rather than as a file card. Both discriminants are used because either can be
 * the only one available: a share reports a MIME type the extension list has
 * never heard of (`application/octet-stream` for a HEIC), and a picked file
 * reports an extension with no MIME type at all.
 */
export function isImageUpload(file: LocalUploadFile): boolean {
  return (
    file.mimeType.startsWith("image/") ||
    (IMAGE_UPLOAD_EXTENSIONS as readonly string[]).includes(
      getFileExtension(file.name),
    )
  );
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
