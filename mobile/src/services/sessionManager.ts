import { Config } from "../constants/config";
import { createHttpError, parseErrorResponse, type HttpError } from "../lib/httpError";
import { TokenStorage } from "./tokenStorage";
import type { AuthUser, TokenVerificationResponse } from "../types/auth";

/**
 * The single owner of the mobile session.
 *
 * Everything that can rotate the tokens goes through here: the proactive timer in
 * AuthContext, the 401 interceptor in apiClient, and the revalidation triggered
 * when the app comes back to the foreground. They all await the *same* promise,
 * so a single-use refresh token can never be spent twice concurrently.
 *
 * The purge policy is the other half of the job. Losing the keychain is only ever
 * correct when the backend refuses the refresh token itself — a 401, which this
 * module normalizes to the `SESSION_EXPIRED` code. Anything else (no network, a
 * timeout, a 5xx, a 429) keeps the tokens: the session is still valid, only the
 * transport is missing, so the app retries with a backoff and stays signed in.
 */

/** The one code that means "this refresh token is dead, sign in again". */
const SESSION_EXPIRED_CODE = "SESSION_EXPIRED";

const SESSION_EXPIRED_MESSAGE = "Your session has expired. Please sign in again.";

/**
 * A refresh is spent this long before the access token actually expires, so a
 * request that leaves just before the deadline still carries a live token.
 */
const REFRESH_BUFFER_MS = 30_000;

/**
 * Ceiling on a single refresh round trip. Without it a socket that never answers
 * would leave the shared promise pending forever, and every caller with it.
 */
const REFRESH_TIMEOUT_MS = 15_000;

/** Backoff between attempts, used only for failures that may pass on their own. */
const REFRESH_RETRY_DELAYS_MS = [1_000, 3_000, 8_000] as const;

/**
 * What a revalidation concluded.
 * - `active`: a usable access token is in hand.
 * - `unreachable`: the session is still ours but the API could not be reached.
 *   The caller must keep the user in the app, offline, and not sign them out.
 * - `expired`: there is no session left. The keychain has already been cleared.
 */
export type SessionStatus = "active" | "unreachable" | "expired";

/**
 * Emitted whenever the session changes underneath React.
 * `refreshed` carries the profile the backend returned with the rotated tokens.
 */
export type SessionEvent =
  | { type: "refreshed"; user: AuthUser }
  | { type: "unreachable"; error: unknown }
  | { type: "expired" };

type SessionListener = (event: SessionEvent) => void;

const listeners = new Set<SessionListener>();

/** The one refresh in flight, shared by every caller until it settles. */
let refreshInFlight: Promise<string> | null = null;

function emit(event: SessionEvent): void {
  for (const listener of [...listeners]) {
    try {
      listener(event);
    } catch (error) {
      console.warn("[session] listener threw on", event.type, error);
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * True when the backend rejected the refresh token itself. This is the only
 * failure that costs the user their session.
 */
function isSessionRejection(error: unknown): boolean {
  const { status, code } = (error ?? {}) as HttpError;
  return status === 401 && code === SESSION_EXPIRED_CODE;
}

/**
 * True when retrying the very same refresh may succeed: no response at all
 * (offline, DNS, abort), a timeout, a throttle, or a server-side fault.
 */
function isRetryable(error: unknown): boolean {
  const { status } = (error ?? {}) as HttpError;
  if (status === undefined) return true;
  return status === 408 || status === 429 || status >= 500;
}

async function postRefresh(
  refreshToken: string,
): Promise<TokenVerificationResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REFRESH_TIMEOUT_MS);

  try {
    const response = await fetch(`${Config.API_BASE_URL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to refresh the session",
      );
      // Nothing but the refresh token is authenticated on this endpoint, so a
      // 401 can only mean that token was refused — whatever wording the backend
      // used. Stamping the canonical code here leaves one condition to test
      // everywhere else, and one place to change if that wording moves.
      throw createHttpError(
        message,
        response.status,
        response.status === 401 ? SESSION_EXPIRED_CODE : code,
      );
    }

    return (await response.json()) as TokenVerificationResponse;
  } finally {
    clearTimeout(timeout);
  }
}

async function runRefresh(): Promise<string> {
  let attempt = 0;

  for (;;) {
    // Re-read on every attempt: the token may have been rotated or dropped
    // while this loop was sleeping.
    const refreshToken = await TokenStorage.getRefreshToken();
    if (!refreshToken) {
      await clearSession();
      emit({ type: "expired" });
      throw createHttpError(SESSION_EXPIRED_MESSAGE, 401, SESSION_EXPIRED_CODE);
    }

    try {
      const result = await postRefresh(refreshToken);
      await persistSession(result);
      emit({ type: "refreshed", user: result.user });
      return result.access_token;
    } catch (error) {
      if (isSessionRejection(error)) {
        await clearSession();
        emit({ type: "expired" });
        throw error;
      }

      const delay = isRetryable(error)
        ? REFRESH_RETRY_DELAYS_MS[attempt]
        : undefined;
      if (delay === undefined) {
        // Out of attempts, or a failure retrying cannot fix. The tokens stay:
        // the session is intact, the network or the backend is not.
        emit({ type: "unreachable", error });
        throw error;
      }

      attempt += 1;
      await sleep(delay);
    }
  }
}

/**
 * Rotate the tokens, or join the rotation already running.
 *
 * Resolves with a fresh access token. Rejects with a `SESSION_EXPIRED` error when
 * the refresh token was refused (the keychain is cleared and an `expired` event
 * is emitted before rejecting), or with the transport error once the backoff is
 * exhausted (the keychain is left alone, `unreachable` is emitted).
 */
function refreshAccessToken(): Promise<string> {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  const operation = runRefresh();
  refreshInFlight = operation;
  // Attached with a rejection handler so a caller-less refresh (the proactive
  // timer) cannot surface as an unhandled rejection.
  const settle = () => {
    if (refreshInFlight === operation) {
      refreshInFlight = null;
    }
  };
  operation.then(settle, settle);
  return operation;
}

/**
 * The access token to send with the next request, refreshing first when the
 * current one is spent.
 *
 * Returns null only when there is nothing left to authenticate with, in which
 * case the keychain has already been cleared and `expired` emitted. Throws when a
 * refresh was needed and failed — the caller must not fall back to a dead token.
 */
async function getAccessToken(): Promise<string | null> {
  const accessToken = await TokenStorage.getAccessToken();
  const expiry = await TokenStorage.getTokenExpiry();

  if (accessToken && expiry !== null && Date.now() < expiry - REFRESH_BUFFER_MS) {
    return accessToken;
  }

  const refreshToken = await TokenStorage.getRefreshToken();
  if (!refreshToken) {
    await clearSession();
    emit({ type: "expired" });
    return null;
  }

  return refreshAccessToken();
}

/**
 * Check the session without sending anything of the caller's own.
 * Used on app start, on every return to the foreground, and by the share
 * confirmation guard.
 */
async function revalidate(): Promise<SessionStatus> {
  try {
    const accessToken = await getAccessToken();
    return accessToken ? "active" : "expired";
  } catch (error) {
    return isSessionRejection(error) ? "expired" : "unreachable";
  }
}

/**
 * How long until the access token should be rotated proactively, or null when
 * there is no session to rotate. Drives the foreground timer.
 */
async function millisUntilProactiveRefresh(): Promise<number | null> {
  const expiry = await TokenStorage.getTokenExpiry();
  if (expiry === null) return null;
  return Math.max(0, expiry - Date.now() - REFRESH_BUFFER_MS);
}

/**
 * Write a freshly issued session to the keychain. The profile is stored with the
 * tokens so a cold start with no network still knows who is signed in.
 */
async function persistSession(response: {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: AuthUser;
}): Promise<void> {
  await TokenStorage.saveAccessToken(response.access_token, response.expires_in);
  await TokenStorage.saveRefreshToken(response.refresh_token);
  await TokenStorage.saveUser(response.user);
}

/** Drop everything the session was made of. */
async function clearSession(): Promise<void> {
  refreshInFlight = null;
  await TokenStorage.clearAll();
}

function subscribe(listener: SessionListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export const SessionManager = {
  SESSION_EXPIRED_CODE,
  SESSION_EXPIRED_MESSAGE,
  subscribe,
  getAccessToken,
  refreshAccessToken,
  revalidate,
  millisUntilProactiveRefresh,
  persistSession,
  clearSession,
  isSessionRejection,
} as const;
