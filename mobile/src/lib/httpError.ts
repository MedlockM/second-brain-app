/** Header the backend quota enforcer sets on every refused submission. */
export const QUOTA_ERROR_CODE_HEADER = "X-Quota-Error-Code";

export type HttpError = Error & {
  status?: number;
  code?: string;
  /**
   * Raw X-Quota-Error-Code value when the backend quota enforcer refused the
   * request (tier_quota_exceeded, audio_too_long, daily_rate_limit, …).
   */
  quotaErrorCode?: string;
};

export function createHttpError(
  message: string,
  status?: number,
  code?: string,
  quotaErrorCode?: string,
): HttpError {
  const error = new Error(message) as HttpError;
  if (status !== undefined) {
    error.status = status;
  }
  if (code) {
    error.code = code;
  }
  if (quotaErrorCode) {
    error.quotaErrorCode = quotaErrorCode;
  }
  return error;
}

export async function parseErrorResponse(
  response: Response,
  fallbackMessage: string,
): Promise<{ message: string; code?: string; quotaErrorCode?: string }> {
  // Read the header before the body: a payload we cannot parse must not cost us
  // the quota code, which is what decides whether the paywall is offered.
  const quotaErrorCode =
    response.headers.get(QUOTA_ERROR_CODE_HEADER) ?? undefined;

  try {
    const data = await response.json();
    const errorData = data?.error ?? data ?? {};
    const message =
      errorData.message ||
      errorData.detail ||
      data?.detail ||
      fallbackMessage;
    const code = errorData.code || data?.code;
    return { message, code, quotaErrorCode };
  } catch {
    return { message: fallbackMessage, quotaErrorCode };
  }
}
