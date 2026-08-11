import { Config } from "../constants/config";
import { createHttpError, parseErrorResponse } from "../lib/httpError";

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
  token?: string | null;
  headers?: Record<string, string>;
};

/**
 * Base API client with auth header injection and standardized error handling.
 * Adapted from the web frontend's fetch patterns (authService, settingsService).
 */
export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, token, headers: extraHeaders } = options;

  const url = `${Config.API_BASE_URL}${path}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extraHeaders,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const fetchOptions: RequestInit = {
    method,
    headers,
  };

  if (body !== undefined) {
    fetchOptions.body = JSON.stringify(body);
  }

  const response = await fetch(url, fetchOptions);

  if (!response.ok) {
    const { message, code, quotaErrorCode } = await parseErrorResponse(
      response,
      `Request failed: ${method} ${path}`,
    );
    throw createHttpError(message, response.status, code, quotaErrorCode);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}
