import { t, type TranslationKey } from "../i18n";

interface FriendlyErrorRule {
  regex: RegExp;
  /**
   * Catalogue key, resolved at call time. These tables are module constants
   * evaluated once at import, so holding a resolved sentence would pin every
   * error message to whatever language the app started in.
   */
  messageKey: TranslationKey;
}

const CRITICAL_ERROR: TranslationKey = "common.error";

/**
 * Last-resort wording for an exhausted allowance, used when a refusal reaches the
 * app without its typed code and figures. Minutes are the only thing a plan
 * limits, so there is one sentence and no "credits" vocabulary; the specific
 * version with the figures is built by `quotaError.ts` from what the backend
 * sends.
 */
const OUT_OF_MINUTES: TranslationKey = "error.outOfMinutes";

const ERROR_CODE_MESSAGES: Record<string, TranslationKey> = {
  SESSION_EXPIRED: "error.sessionExpired",
  INVALID_CREDENTIALS: "error.invalidCredentials",
  EMAIL_NOT_VERIFIED: "error.emailNotVerified",
  EMAIL_ALREADY_EXISTS: "error.emailAlreadyExists",
  INVALID_VERIFICATION_TOKEN: "error.invalidVerificationToken",
  USER_NOT_FOUND: "error.userNotFound",
  NOT_AUTHORIZED: "error.notAuthorized",
  NOT_FOUND: "error.notFound",
  MEDIA_NOT_FOUND: "error.mediaNotFound",
  ARTIFACT_NOT_FOUND: "error.artifactNotFound",
  INVALID_URL: "error.invalidUrl",
  UNSUPPORTED_URL: "error.unsupportedUrl",
  VALIDATION_ERROR: "error.validation",
  PAYMENT_REQUIRED: OUT_OF_MINUTES,
  INSUFFICIENT_MINUTES: OUT_OF_MINUTES,
  QUOTA_EXCEEDED: OUT_OF_MINUTES,
  RATE_LIMITED: "error.rateLimited",
  CONFLICT: "error.conflict",
  BAD_REQUEST: "error.badRequest",
  INTERNAL_ERROR: CRITICAL_ERROR,
  UNKNOWN_ERROR: CRITICAL_ERROR,
};

const DEFAULT_RULES: FriendlyErrorRule[] = [
  {
    regex: /session expired|session has expired|please sign in again/i,
    messageKey: "error.sessionExpired",
  },
  {
    regex:
      /401|unauthorized|invalid token|expired token|missing token|token expired|authentication token required|not authenticated/i,
    messageKey: "error.sessionExpired",
  },
  {
    regex:
      /invalid credentials|incorrect email or password|authentication failed/i,
    messageKey: "error.invalidCredentials",
  },
  {
    regex: /email not verified/i,
    messageKey: "error.emailNotVerified",
  },
  {
    regex: /account not found|user not found/i,
    messageKey: "error.userNotFound",
  },
  {
    regex: /email already exists/i,
    messageKey: "error.emailAlreadyExists",
  },
  {
    regex: /(payment required|402)|out of minutes|insufficient minutes|quota/i,
    messageKey: OUT_OF_MINUTES,
  },
  {
    regex: /invalid email|email is not valid/i,
    messageKey: "error.invalidEmail",
  },
  {
    regex: /password too short|password must be at least/i,
    messageKey: "error.passwordTooShort",
  },
  {
    regex: /passwords do not match/i,
    messageKey: "error.passwordsDoNotMatch",
  },
  {
    regex: /403|forbidden|not authorized|permission denied/i,
    messageKey: "error.notAuthorized",
  },
  {
    regex: /network error|failed to fetch|connection failed/i,
    messageKey: "error.network",
  },
  {
    regex: /timeout|timed out/i,
    messageKey: "error.timeout",
  },
  {
    regex: /too many requests|rate limit/i,
    messageKey: "error.rateLimited",
  },
  {
    regex: /not found(?!.*account)/i,
    messageKey: "error.notFound",
  },
];

const CRITICAL_ERROR_PATTERNS = [
  /database|sql|query failed|postgres|mysql|mongodb|redis/i,
  /internal server error|500|server error/i,
  /undefined|null|cannot read property|is not a function/i,
  /reference error|type error|syntax error|unexpected token/i,
  /traceback|exception|stack trace/i,
  /aws|s3|lambda|cloudfront|dynamodb/i,
  /econnrefused|connection refused|enotfound/i,
  /cors|cross-origin/i,
];

/**
 * Maps error messages to user-friendly text.
 * Returns a user-friendly error message for actionable errors,
 * or "Error" for critical/technical errors that users cannot fix.
 */
export function getFriendlyErrorMessage(
  error: unknown,
  options: { fallback?: string; additionalRules?: FriendlyErrorRule[] } = {},
): string {
  const fallback = options.fallback ?? t(CRITICAL_ERROR);

  if (!error) {
    return fallback;
  }

  const code =
    (error as { code?: string }).code ||
    (error as { error?: { code?: string } }).error?.code;
  if (code && ERROR_CODE_MESSAGES[code]) {
    return t(ERROR_CODE_MESSAGES[code]);
  }

  let errorMessage = "";
  if (typeof error === "string") {
    errorMessage = error;
  } else if (error instanceof Error) {
    errorMessage = error.message || "";
  } else if (typeof error === "object" && error && "message" in error) {
    errorMessage = String((error as { message: unknown }).message);
  } else {
    return fallback;
  }

  const normalized = errorMessage.trim().toLowerCase();

  // Check for critical errors first
  for (const pattern of CRITICAL_ERROR_PATTERNS) {
    if (pattern.test(normalized)) {
      return fallback;
    }
  }

  // Check status code
  const status = (error as { status?: number }).status;
  if (typeof status === "number" && status >= 500) {
    return fallback;
  }

  // Check against rules
  const rules = [...DEFAULT_RULES, ...(options.additionalRules ?? [])];
  for (const rule of rules) {
    if (rule.regex.test(normalized)) {
      return t(rule.messageKey);
    }
  }

  // Status-based fallbacks
  if (status === 401) {
    return t("error.sessionExpired");
  }
  if (status === 403) {
    return t("error.notAuthorized");
  }
  if (status === 404) {
    return t("error.notFound");
  }
  if (status === 429) {
    return t("error.rateLimited");
  }

  return fallback;
}

/**
 * Checks if an error is actionable (user can fix it) vs critical (site bug).
 */
export function isActionableError(error: unknown): boolean {
  const friendlyMessage = getFriendlyErrorMessage(error);
  return friendlyMessage !== t(CRITICAL_ERROR);
}
