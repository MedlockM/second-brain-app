import { apiRequest } from "./apiClient";
import {
  putLocalFileToUrl,
  redactSensitive,
  stageLocalFile,
  type LocalFilePutResult,
  type StagedLocalFile,
} from "./localFileTransfer";

/**
 * Allowed file extensions for bug report attachments.
 */
export const ALLOWED_EXTENSIONS = [
  ".jpg",
  ".jpeg",
  ".png",
  ".heic",
  ".mp4",
  ".mov",
  ".pdf",
  ".zip",
] as const;

/**
 * Allowed MIME types for bug report attachments.
 */
export const ALLOWED_MIME_TYPES = [
  "image/jpeg",
  "image/png",
  "image/heic",
  "image/heif",
  "video/mp4",
  "video/quicktime",
  "application/pdf",
  "application/zip",
  "application/x-zip-compressed",
] as const;

/** Maximum file size: 50 MB */
export const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024;

/**
 * An attachment that could not be read or could not be sent.
 *
 * Carries a code rather than a sentence: `getFriendlyErrorMessage` turns it into
 * "remove the attachment and send the report on its own, or try again", which is
 * true whichever of the two happened and is the only thing left to do either way.
 * What actually happened goes to the log — S3's status and Cocoa's complaint about
 * a missing file describe our signature and someone's file name, neither of which
 * belongs in an `Alert`.
 */
export class BugReportAttachmentError extends Error {
  readonly code = "ATTACHMENT_UPLOAD_FAILED";

  constructor(detail: string) {
    super("Bug report attachment upload failed");
    this.name = "BugReportAttachmentError";
    console.error(`[bug-report] attachment: ${detail}`);
  }
}

// --- Types ---

export interface RequestUploadUrlPayload {
  filename: string;
  content_type: string;
  file_size: number;
}

export interface RequestUploadUrlResponse {
  upload_url: string;
  attachment_key: string;
  expires_in: number;
}

export interface CreateBugReportPayload {
  subject: string;
  description: string;
  attachment_key?: string | null;
  source_app_version?: string | null;
  source_platform?: string | null;
  /**
   * The library item this report is about, when it is about one — a request to
   * support the source of a media that failed to import (task-381). Absent on a
   * report filed from the Account tab, which is about the app.
   *
   * The URL is deliberately *not* sent: the server holds the caller's id, so this
   * id is the second half of the item's primary key and it reads the address off
   * the row itself.
   */
  media_item_id?: string | null;
  /**
   * The `MediaFailureCode` the client saw on that item. Sent rather than looked up
   * server-side because the job row it lives on carries a TTL and may be gone by
   * the time anyone reads the report.
   */
  error_code?: string | null;
}

export interface CreateBugReportResponse {
  id: string;
  status: string;
  message: string;
}

// --- Validation helpers ---

/**
 * Check if a file extension is allowed for bug report attachments.
 */
export function isAllowedExtension(filename: string): boolean {
  const ext = "." + filename.toLowerCase().split(".").pop();
  return ALLOWED_EXTENSIONS.includes(ext as (typeof ALLOWED_EXTENSIONS)[number]);
}

/**
 * Check if a MIME type is allowed for bug report attachments.
 */
export function isAllowedMimeType(mimeType: string): boolean {
  return ALLOWED_MIME_TYPES.includes(
    mimeType.toLowerCase() as (typeof ALLOWED_MIME_TYPES)[number],
  );
}

/**
 * Check if a file size is within the allowed limit.
 */
export function isWithinSizeLimit(sizeBytes: number): boolean {
  return sizeBytes > 0 && sizeBytes <= MAX_FILE_SIZE_BYTES;
}

/**
 * Format a byte size into a human-readable string.
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// --- Service ---

/**
 * Bug Report service for mobile.
 * Handles presigned upload URL requests and bug report submission.
 */
export class BugReportService {
  /**
   * Request a presigned S3 upload URL for an attachment.
   * POST /api/bug-reports/upload-url
   */
  static async requestUploadUrl(
    payload: RequestUploadUrlPayload,
  ): Promise<RequestUploadUrlResponse> {
    return apiRequest<RequestUploadUrlResponse>("/api/bug-reports/upload-url", {
      method: "POST",
      body: payload,
    });
  }

  /**
   * Upload a file directly to S3 using the presigned PUT URL.
   * This does NOT go through the backend API.
   *
   * The attachment is read and streamed by `localFileTransfer`. It used to be
   * `fetch(fileUri)` then `.blob()`, the same anti-pattern that made a shared
   * Markdown note fail to import on build 9 — a local file is not a URL you can
   * fetch, and on iOS the attempt fails as a network error about a network that
   * was never involved. An attachment here is a screenshot or a screen recording,
   * so it comes from the photo picker rather than a share intent, but it is the
   * same read on the same URIs and it deserved the same correction.
   */
  static async uploadFileToS3(
    uploadUrl: string,
    fileUri: string,
    contentType: string,
  ): Promise<void> {
    let staged: StagedLocalFile;
    try {
      staged = await stageLocalFile(fileUri);
    } catch (error) {
      // Redacted even though this only reaches a log now: Cocoa's way of saying a
      // file is missing is to quote its name, and a device log is attached to bug
      // reports whole.
      throw new BugReportAttachmentError(
        `read_file · ${redactSensitive(
          error instanceof Error ? error.message : String(error),
        )}`,
      );
    }
    try {
      let result: LocalFilePutResult;
      try {
        result = await putLocalFileToUrl({
          url: uploadUrl,
          fileUri: staged.fileUri,
          contentType,
        });
      } catch (error) {
        // `URLSession` reports the URL it failed on, and that URL is a bearer
        // credential for the object. Redacted before it reaches the log.
        throw new BugReportAttachmentError(
          `put_network · ${redactSensitive(
            error instanceof Error ? error.message : String(error),
          )}`,
        );
      }
      if (result.status < 200 || result.status >= 300) {
        // No `statusText` to report: a native upload gives back a status code and
        // a body, not a reason phrase. The code is the half that identifies the
        // refusal anyway.
        throw new BugReportAttachmentError(`put_rejected · ${result.status}`);
      }
    } finally {
      staged.release();
    }
  }

  /**
   * Submit a bug report.
   * POST /api/bug-reports
   */
  static async createBugReport(
    payload: CreateBugReportPayload,
  ): Promise<CreateBugReportResponse> {
    return apiRequest<CreateBugReportResponse>("/api/bug-reports", {
      method: "POST",
      body: payload,
    });
  }
}
