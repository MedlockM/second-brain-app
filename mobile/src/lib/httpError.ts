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
  /**
   * The whole structured refusal body, when the backend sent one. Typed refusals
   * carry the numbers the screen needs to be specific — `source_count` /
   * `max_sources` on a collection that is too large, `pending_count` on sources
   * still being prepared — and losing them would leave the UI with a generic
   * sentence where the API gave it an exact one.
   */
  details?: Record<string, unknown>;
};

export function createHttpError(
  message: string,
  status?: number,
  code?: string,
  quotaErrorCode?: string,
  details?: Record<string, unknown>,
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
  if (details) {
    error.details = details;
  }
  return error;
}

export async function parseErrorResponse(
  response: Response,
  fallbackMessage: string,
): Promise<{
  message: string;
  code?: string;
  quotaErrorCode?: string;
  details?: Record<string, unknown>;
}> {
  // Read the header before the body: a payload we cannot parse must not cost us
  // the quota code, which is what decides whether the paywall is offered.
  const quotaErrorCode =
    response.headers.get(QUOTA_ERROR_CODE_HEADER) ?? undefined;

  try {
    const data = await response.json();

    // A typed refusal sends `detail` as an object ({error_code, message, …}).
    // Read through it: the previous chain handed that object to `new Error()`,
    // which rendered "[object Object]" to the user and dropped the error code.
    const detail = data?.detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const structured = detail as Record<string, unknown>;
      const code =
        typeof structured.error_code === "string"
          ? structured.error_code
          : undefined;
      return {
        message:
          typeof structured.message === "string"
            ? structured.message
            : fallbackMessage,
        code,
        quotaErrorCode: quotaErrorCode ?? code,
        details: structured,
      };
    }

    const errorData = data?.error ?? data ?? {};
    const message =
      errorData.message ||
      (typeof errorData.detail === "string" ? errorData.detail : undefined) ||
      (typeof data?.detail === "string" ? data.detail : undefined) ||
      fallbackMessage;
    const code = errorData.code || data?.code;
    return { message, code, quotaErrorCode };
  } catch {
    return { message: fallbackMessage, quotaErrorCode };
  }
}
