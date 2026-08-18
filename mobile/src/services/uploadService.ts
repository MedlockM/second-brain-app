/**
 * Uploads a file picked or captured on the device to one of the two multipart
 * ingestion endpoints (task-264):
 *
 * - `POST /api/media/upload` for documents and images (LlamaParse, OCR)
 * - `POST /api/media/upload-audio` for audio (Deepgram)
 *
 * Both accept the same `folder_id` / `tag_ids` organization fields as
 * `ingest-url` and `ingest-shared-content`, so an import lands in the collection
 * and tags the user picked on the confirmation screen.
 *
 * They go through `apiUpload` rather than `apiRequest` because the body is
 * multipart/form-data: the boundary must be set by the runtime, which means the
 * Content-Type header cannot be provided by us. The session handling — bearer
 * resolution and the one-shot replay on a 401 — is the same as everywhere else.
 */

import { apiUpload } from "./apiClient";
import type {
  LocalUploadFile,
  UploadAudioResponse,
  UploadDocumentResponse,
} from "../types/upload";

export interface UploadOrganizationOptions {
  folderId?: string | null;
  tagIds?: string[];
}

function buildUploadFormData(
  file: LocalUploadFile,
  options: UploadOrganizationOptions,
): FormData {
  const formData = new FormData();

  // React Native's FormData takes an object with uri/type/name for file parts.
  formData.append("file", {
    uri: file.uri,
    type: file.mimeType,
    name: file.name,
  } as unknown as Blob);

  if (options.folderId) {
    formData.append("folder_id", options.folderId);
  }
  if (options.tagIds && options.tagIds.length > 0) {
    formData.append("tag_ids", JSON.stringify(options.tagIds));
  }

  return formData;
}

export class UploadService {
  /** Documents and images (pdf, docx, pptx, xlsx, jpg, png, heic, …). */
  static async uploadDocument(
    file: LocalUploadFile,
    options: UploadOrganizationOptions = {},
  ): Promise<UploadDocumentResponse> {
    return apiUpload<UploadDocumentResponse>(
      "/api/media/upload",
      buildUploadFormData(file, options),
      "Failed to import this file. Please try again.",
    );
  }

  /** Audio files (mp3, m4a, aac, ogg, wav, flac, opus). */
  static async uploadAudio(
    file: LocalUploadFile,
    options: UploadOrganizationOptions = {},
  ): Promise<UploadAudioResponse> {
    return apiUpload<UploadAudioResponse>(
      "/api/media/upload-audio",
      buildUploadFormData(file, options),
      "Failed to import this audio file. Please try again.",
    );
  }

  /** Route a prepared file to the endpoint its extension belongs to. */
  static async upload(
    file: LocalUploadFile,
    options: UploadOrganizationOptions = {},
  ): Promise<UploadDocumentResponse | UploadAudioResponse> {
    return file.kind === "audio"
      ? UploadService.uploadAudio(file, options)
      : UploadService.uploadDocument(file, options);
  }
}
