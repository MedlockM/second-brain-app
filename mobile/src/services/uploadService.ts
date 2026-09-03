/**
 * Uploads a file picked or captured on the device to one of the two ingestion
 * endpoints (task-264):
 *
 * - `POST /api/media/upload` for documents and images (LlamaParse, OCR)
 * - `POST /api/media/upload-audio` for audio (Deepgram)
 *
 * Both accept the same `folder_id` / `tag_ids` organization fields as
 * `ingest-url` and `ingest-shared-content`, so an import lands in the collection
 * and tags the user picked on the confirmation screen.
 *
 * The file itself never goes through the API (task-345): `stageUpload` sends it
 * straight to S3 through a presigned PUT, and these calls only carry the
 * resulting key, as JSON. That is what makes a 12 MB document importable at all —
 * API Gateway refuses any body past ~4.5 MB before the API sees it.
 */

import { apiRequest } from "./apiClient";
import { stageUpload } from "./presignedUpload";
import type {
  LocalUploadFile,
  UploadAudioResponse,
  UploadDocumentResponse,
} from "../types/upload";

export interface UploadOrganizationOptions {
  folderId?: string | null;
  tagIds?: string[];
}

function organizationBody(options: UploadOrganizationOptions): {
  folder_id: string | null;
  tag_ids: string[] | null;
} {
  return {
    folder_id: options.folderId ?? null,
    tag_ids: options.tagIds && options.tagIds.length > 0 ? options.tagIds : null,
  };
}

export class UploadService {
  /** Documents and images (pdf, docx, pptx, xlsx, jpg, png, heic, …). */
  static async uploadDocument(
    file: LocalUploadFile,
    options: UploadOrganizationOptions = {},
  ): Promise<UploadDocumentResponse> {
    const uploadKey = await stageUpload({
      target: "document",
      uri: file.uri,
      fileName: file.name,
      mimeType: file.mimeType,
      size: file.size,
    });

    return apiRequest<UploadDocumentResponse>("/api/media/upload", {
      method: "POST",
      body: { upload_key: uploadKey, ...organizationBody(options) },
    });
  }

  /** Audio files (mp3, m4a, aac, ogg, wav, flac, opus). */
  static async uploadAudio(
    file: LocalUploadFile,
    options: UploadOrganizationOptions = {},
  ): Promise<UploadAudioResponse> {
    const uploadKey = await stageUpload({
      target: "audio",
      uri: file.uri,
      fileName: file.name,
      mimeType: file.mimeType,
      size: file.size,
    });

    return apiRequest<UploadAudioResponse>("/api/media/upload-audio", {
      method: "POST",
      body: { upload_key: uploadKey, ...organizationBody(options) },
    });
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
