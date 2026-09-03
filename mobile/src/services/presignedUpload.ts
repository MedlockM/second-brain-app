/**
 * Direct-to-S3 transfer for every ingestion flow that carries a file (task-345).
 *
 * The API cannot receive the bytes: requests reach it through API Gateway, which
 * base64-encodes the body into the Lambda event, so any body past 4 718 592 raw
 * bytes is refused by the gateway itself with `Request Entity Too Large` — before
 * the API can translate anything. A 12 MB PDF or a five-minute voice memo would
 * never make it, whatever the documented 50 MB limit said.
 *
 * So the file goes straight to S3, in three steps:
 *
 * 1. `POST /api/media/upload-url` — the API checks format and size, then signs a
 *    PUT on a key namespaced under the caller's id.
 * 2. `PUT` to that URL, without the session: the signature is the credential, and
 *    the bearer must not be sent to a host that is not our API.
 * 3. the ingestion endpoint is called with the returned key, as plain JSON.
 *
 * Everything that fails between the device and S3 surfaces as `DirectUploadError`
 * with an already-translated message: S3 answers XML no user should read, and its
 * status codes describe the signature, not what the user did.
 */

import { t } from "../i18n";
import { apiRequest } from "./apiClient";

/** Which ingestion flow a staged object is destined for. */
export type UploadTarget = "document" | "audio" | "shared_audio";

interface UploadUrlResponse {
  upload_url: string;
  upload_key: string;
  expires_in: number;
}

/**
 * A transfer that never reached S3, or that S3 refused.
 *
 * Carries a message that is already translated, so callers must render it as-is
 * rather than pass it through `getFriendlyErrorMessage` — whose critical-pattern
 * rules would flatten anything mentioning S3 into the generic error sentence.
 */
export class DirectUploadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DirectUploadError";
  }
}

/** Read a local file (file:// or content://) as a blob backed by the native side. */
async function readLocalFile(uri: string): Promise<Blob> {
  try {
    const response = await fetch(uri);
    return await response.blob();
  } catch {
    throw new DirectUploadError(t("upload.transferFailed"));
  }
}

async function putToS3(
  uploadUrl: string,
  blob: Blob,
  contentType: string,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(uploadUrl, {
      method: "PUT",
      headers: { "Content-Type": contentType },
      body: blob,
    });
  } catch {
    throw new DirectUploadError(t("upload.transferFailed"));
  }
  if (!response.ok) {
    // An expired signature reads 403, a truncated body 400, and the body is XML.
    // None of that is actionable: the answer is always "send it again".
    throw new DirectUploadError(t("upload.transferFailed"));
  }
}

/**
 * Send a local file to S3 and return the key the ingestion endpoint expects.
 *
 * `size` is what the picker reported; when it reported nothing, the blob's own
 * size is used, since the API needs a figure to check the ceiling against before
 * signing.
 */
export async function stageUpload(params: {
  target: UploadTarget;
  uri: string;
  fileName: string;
  mimeType: string;
  size?: number | null;
}): Promise<string> {
  const blob = await readLocalFile(params.uri);
  const fileSize =
    params.size && params.size > 0 ? params.size : blob.size || 1;

  const issued = await apiRequest<UploadUrlResponse>("/api/media/upload-url", {
    method: "POST",
    body: {
      target: params.target,
      filename: params.fileName,
      content_type: params.mimeType,
      file_size: fileSize,
    },
  });

  await putToS3(issued.upload_url, blob, params.mimeType);
  return issued.upload_key;
}
