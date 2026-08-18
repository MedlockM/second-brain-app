import { apiRequest } from "./apiClient";

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
   */
  static async uploadFileToS3(
    uploadUrl: string,
    fileUri: string,
    contentType: string,
  ): Promise<void> {
    const response = await fetch(fileUri);
    const blob = await response.blob();

    const uploadResponse = await fetch(uploadUrl, {
      method: "PUT",
      headers: {
        "Content-Type": contentType,
      },
      body: blob,
    });

    if (!uploadResponse.ok) {
      throw new Error(
        `Upload failed with status ${uploadResponse.status}: ${uploadResponse.statusText}`,
      );
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
