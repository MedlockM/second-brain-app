import { createHttpError, parseErrorResponse } from "../lib/httpError";
import type {
  ArtifactCreateRequest,
  ArtifactCreateResponse,
  IngestUrlRequest,
  IngestUrlResponse,
  MediaStatusResponse,
} from "../types/media";

const API_BASE_URL =
  import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || "";

async function fetchJson<T>(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    const { message, code } = await parseErrorResponse(
      response,
      `Request failed: ${response.statusText}`,
    );
    throw createHttpError(message, response.status, code);
  }

  return response.json() as Promise<T>;
}

export class MediaService {
  static async ingestMediaUrl(
    token: string,
    payload: IngestUrlRequest,
  ): Promise<IngestUrlResponse> {
    return fetchJson<IngestUrlResponse>("/api/media/ingest-url", token, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  static async getMediaStatus(
    token: string,
    mediaItemId: string,
  ): Promise<MediaStatusResponse> {
    return fetchJson<MediaStatusResponse>(
      `/api/media/${encodeURIComponent(mediaItemId)}`,
      token,
      {
        method: "GET",
      },
    );
  }

  static async requestArtifact(
    token: string,
    mediaItemId: string,
    payload: ArtifactCreateRequest,
  ): Promise<ArtifactCreateResponse> {
    return fetchJson<ArtifactCreateResponse>(
      `/api/media/${encodeURIComponent(mediaItemId)}/artifacts`,
      token,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }
}
