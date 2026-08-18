import { Config } from "../constants/config";
import { createHttpError, parseErrorResponse } from "../lib/httpError";
import { SessionManager } from "./sessionManager";

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
  headers?: Record<string, string>;
};

/**
 * Base API client for every authenticated call.
 *
 * The bearer token is resolved here, from the keychain, at the moment the request
 * leaves — never handed in by a screen, which could only ever pass a copy taken
 * when it rendered. That is what makes the 401 interceptor below possible: on a
 * refusal it rotates the session once and replays the request with the token it
 * just obtained, and only propagates the error if that replay fails too.
 */
async function sendAuthenticated(
  send: (accessToken: string) => Promise<Response>,
): Promise<Response> {
  const accessToken = await SessionManager.getAccessToken();
  if (!accessToken) {
    throw createHttpError(
      SessionManager.SESSION_EXPIRED_MESSAGE,
      401,
      SessionManager.SESSION_EXPIRED_CODE,
    );
  }

  const response = await send(accessToken);
  if (response.status !== 401) {
    return response;
  }

  // The token was refused mid-flight (clock skew, an expiry we read as still
  // valid, a rotation from another path). One refresh, one replay, then whatever
  // comes back is the answer — a second 401 is not a transport problem.
  const refreshedToken = await SessionManager.refreshAccessToken();
  return send(refreshedToken);
}

async function parseResponse<T>(
  response: Response,
  fallbackMessage: string,
): Promise<T> {
  if (!response.ok) {
    const { message, code, quotaErrorCode, details } = await parseErrorResponse(
      response,
      fallbackMessage,
    );
    throw createHttpError(
      message,
      response.status,
      code,
      quotaErrorCode,
      details,
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, headers: extraHeaders } = options;
  const url = `${Config.API_BASE_URL}${path}`;

  const response = await sendAuthenticated((accessToken) => {
    const fetchOptions: RequestInit = {
      method,
      headers: {
        "Content-Type": "application/json",
        ...extraHeaders,
        Authorization: `Bearer ${accessToken}`,
      },
    };
    if (body !== undefined) {
      fetchOptions.body = JSON.stringify(body);
    }
    return fetch(url, fetchOptions);
  });

  return parseResponse<T>(response, `Request failed: ${method} ${path}`);
}

/**
 * Same client, multipart body. Kept separate because the Content-Type has to be
 * set by the runtime, with the boundary it generates — we must not send one.
 * Uploads go through here rather than a bare fetch so they get the same session
 * resolution and the same one-shot 401 replay as every other call.
 */
export async function apiUpload<T = unknown>(
  path: string,
  formData: FormData,
  fallbackMessage: string,
): Promise<T> {
  const url = `${Config.API_BASE_URL}${path}`;

  const response = await sendAuthenticated((accessToken) =>
    fetch(url, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: formData,
    }),
  );

  return parseResponse<T>(response, fallbackMessage);
}
