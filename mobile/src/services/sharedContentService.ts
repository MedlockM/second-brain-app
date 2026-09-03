/**
 * Service for ingesting shared content (text and audio) from WhatsApp
 * via the POST /api/media/ingest-shared-content endpoint.
 *
 * This service handles the non-URL share path where the content is either
 * raw text (no URL found) or an audio file attachment.
 *
 * The endpoint takes JSON, never bytes (task-345): a shared voice message is sent
 * straight to S3 through a presigned PUT, and the submission below only carries
 * the resulting key.
 */

import { Platform } from "react-native";
import { apiRequest } from "./apiClient";
import { stageUpload } from "./presignedUpload";
import type {
  IngestSharedContentResponse,
  SharedFileAttachment,
} from "../types/sharedContent";
import {
  MAX_SHARED_AUDIO_SIZE_BYTES,
  MAX_SHARED_TEXT_LENGTH,
  isSupportedAudioMimeType,
} from "../types/sharedContent";

/**
 * Error thrown when shared content validation fails before API call.
 */
export class SharedContentValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SharedContentValidationError";
  }
}

/**
 * Generates a deterministic-ish idempotency key for deduplication.
 * Uses a prefix + timestamp + partial content hash to avoid double-submissions.
 */
function generateIdempotencyKey(prefix: string, content: string): string {
  // Simple hash: first 8 chars of content + timestamp rounded to 10s window
  const contentSlice = content.slice(0, 64);
  const timeWindow = Math.floor(Date.now() / 10000).toString(36);
  const hash = contentSlice
    .split("")
    .reduce((acc, char) => ((acc << 5) - acc + char.charCodeAt(0)) | 0, 0)
    .toString(36);
  return `${prefix}-${hash}-${timeWindow}`;
}

export class SharedContentService {
  /**
   * Submit a shared text message for ingestion.
   * Used when WhatsApp text is shared and no URL is found in it.
   */
  static async ingestSharedText(
    text: string,
    options: {
      sourceApp?: string;
      locale?: string;
      folderId?: string | null;
      tagIds?: string[];
    } = {},
  ): Promise<IngestSharedContentResponse> {
    // Validate text
    const trimmed = text.trim();
    if (!trimmed) {
      throw new SharedContentValidationError(
        "Shared text is empty. Nothing to save.",
      );
    }
    if (trimmed.length > MAX_SHARED_TEXT_LENGTH) {
      throw new SharedContentValidationError(
        `Text is too long (${trimmed.length} characters). Maximum is ${MAX_SHARED_TEXT_LENGTH}.`,
      );
    }

    const sourceApp =
      options.sourceApp ??
      (Platform.OS === "ios" ? "ios-share-extension" : "android-share-intent");
    const idempotencyKey = generateIdempotencyKey("wa-text", trimmed);

    return SharedContentService.submitIngest({
      share_type: "text",
      source_platform: "whatsapp",
      source_app: sourceApp,
      idempotency_key: idempotencyKey,
      text: trimmed,
      locale: options.locale ?? null,
      folder_id: options.folderId ?? null,
      tag_ids:
        options.tagIds && options.tagIds.length > 0 ? options.tagIds : null,
    });
  }

  /**
   * Submit a shared audio file for ingestion.
   * Used when WhatsApp audio (voice message or file) is shared.
   */
  static async ingestSharedAudio(
    file: SharedFileAttachment,
    options: {
      sourceApp?: string;
      locale?: string;
      folderId?: string | null;
      tagIds?: string[];
    } = {},
  ): Promise<IngestSharedContentResponse> {
    // Validate MIME type
    if (!isSupportedAudioMimeType(file.mimeType)) {
      throw new SharedContentValidationError(
        `Unsupported audio format: ${file.mimeType}. Please share an audio file in a supported format (MP3, M4A, OGG, OPUS, WAV, AAC, FLAC).`,
      );
    }

    // Validate file size
    if (file.fileSize !== null && file.fileSize > MAX_SHARED_AUDIO_SIZE_BYTES) {
      const maxMB = Math.round(MAX_SHARED_AUDIO_SIZE_BYTES / (1024 * 1024));
      throw new SharedContentValidationError(
        `Audio file is too large (${Math.round(file.fileSize / (1024 * 1024))} MB). Maximum is ${maxMB} MB.`,
      );
    }

    if (file.fileSize !== null && file.fileSize === 0) {
      throw new SharedContentValidationError(
        "Audio file is empty. Please share a valid audio file.",
      );
    }

    const sourceApp =
      options.sourceApp ??
      (Platform.OS === "ios" ? "ios-share-extension" : "android-share-intent");
    const fileName = file.fileName ?? `whatsapp-audio.${getExtension(file.mimeType)}`;
    const idempotencyKey = generateIdempotencyKey(
      "wa-audio",
      `${fileName}:${file.fileSize ?? 0}`,
    );

    // The audio itself goes straight to S3; the submission carries its key.
    const uploadKey = await stageUpload({
      target: "shared_audio",
      uri: file.uri,
      fileName,
      mimeType: file.mimeType,
      size: file.fileSize,
    });

    return SharedContentService.submitIngest({
      share_type: "audio",
      source_platform: "whatsapp",
      source_app: sourceApp,
      idempotency_key: idempotencyKey,
      content_mime_type: file.mimeType,
      original_name: fileName,
      upload_key: uploadKey,
      locale: options.locale ?? null,
      folder_id: options.folderId ?? null,
      tag_ids:
        options.tagIds && options.tagIds.length > 0 ? options.tagIds : null,
    });
  }

  /**
   * Submit the prepared body to the ingest-shared-content endpoint. Same bearer
   * resolution and same one-shot replay on a 401 as every other authenticated
   * call.
   */
  private static async submitIngest(
    body: Record<string, unknown>,
  ): Promise<IngestSharedContentResponse> {
    const response = await apiRequest<IngestSharedContentResponse | undefined>(
      "/api/media/ingest-shared-content",
      { method: "POST", body },
    );

    // A 204 carries no body: the submission was accepted and nothing is known
    // about the item yet.
    return (
      response ?? {
        media_item_id: "",
        status: "pending",
        source_platform: "whatsapp",
      }
    );
  }
}

/**
 * Get a file extension from a MIME type.
 */
function getExtension(mimeType: string): string {
  const map: Record<string, string> = {
    "audio/ogg": "ogg",
    "audio/opus": "opus",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/aac": "aac",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "audio/amr": "amr",
  };
  return map[mimeType.toLowerCase()] ?? "audio";
}
