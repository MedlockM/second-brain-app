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

/**
 * Every code the backend can name a failure with, mapped to the sentence the
 * reader gets in their own language.
 *
 * Two vocabularies land here on purpose. The first names the *transport* refusal
 * of a request (`CanonicalErrorCode`: a 400, a 404, an expired session). The
 * second names why an ingestion job failed (`MediaFailureCode`, mirrored in
 * `types/media.ts`) — those are the entries this table gained with task-359, when
 * the workers stopped writing English sentences on the job. A code missing from
 * here is not a crash: `getFriendlyErrorMessage` falls through to its `fallback`,
 * which the media screens set to `media.failedFallback`.
 *
 * Several codes deliberately share a key. Three provider-side causes (our
 * credentials, our credits, our configuration) are one thing from where the
 * reader stands: imports are down and it is on us. Same for the three codes that
 * only ever mean "our bug".
 */
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

  // --- Ingestion failures (`MediaFailureCode`) ---
  MEDIA_UNAVAILABLE: "mediaError.mediaUnavailable",
  GEO_RESTRICTED: "mediaError.geoRestricted",
  AGE_RESTRICTED: "mediaError.ageRestricted",
  LIVE_CONTENT_UNSUPPORTED: "mediaError.liveContentUnsupported",
  IMAGE_POST_UNSUPPORTED: "mediaError.imagePostUnsupported",
  NO_TRANSCRIBABLE_MEDIA: "mediaError.noTranscribableMedia",
  NO_TRANSCRIPT_AVAILABLE: "mediaError.noTranscriptAvailable",
  POST_TEXT_EMPTY: "mediaError.postTextEmpty",
  NOT_AN_ARTICLE_PAGE: "mediaError.notAnArticlePage",
  ARTICLE_TEXT_NOT_FOUND: "mediaError.articleTextNotFound",
  DOCUMENT_PARSE_FAILED: "mediaError.documentParseFailed",
  PROVIDER_UNAVAILABLE: "mediaError.providerUnavailable",
  PROVIDER_RESULT_INVALID: "mediaError.providerResultInvalid",
  PROVIDER_RATE_LIMITED: "mediaError.providerRateLimited",
  PROVIDER_TIMED_OUT: "mediaError.providerTimedOut",
  PROVIDER_AUTH_FAILED: "mediaError.serviceUnavailable",
  PROVIDER_CREDITS_DEPLETED: "mediaError.serviceUnavailable",
  PROVIDER_CONFIG_ERROR: "mediaError.serviceUnavailable",
  OUT_OF_MINUTES: OUT_OF_MINUTES,
  ITEM_TOO_LONG: "mediaError.itemTooLong",
  INVALID_JOB_MESSAGE: "mediaError.internal",
  SUBMISSION_FAILED: "mediaError.internal",
  UNEXPECTED_ERROR: "mediaError.internal",
};

/**
 * The failure codes for which "this media source isn't supported yet" is a true
 * sentence — and therefore the only ones the detail screen offers to request
 * support for (task-381).
 *
 * Eight of the twenty-four `MediaFailureCode` members. The sixteen left out are
 * left out for a reason, and each reason is a different one:
 *
 * - `MEDIA_UNAVAILABLE`, `GEO_RESTRICTED`, `AGE_RESTRICTED` — the source *is*
 *   supported; this particular item is out of reach.
 * - `OUT_OF_MINUTES`, `ITEM_TOO_LONG` — the reader's own allowance. There is
 *   nothing to add support for.
 * - the seven `PROVIDER_*` codes, `INVALID_JOB_MESSAGE`, `SUBMISSION_FAILED`,
 *   `UNEXPECTED_ERROR` — a passing outage, our budget or our bug. A retry may be
 *   all it takes.
 *
 * Offering the block on all of them would turn three requests out of four into a
 * request for a source that already works, prompted by a sentence that was false.
 */
const SOURCE_SUPPORT_REQUESTABLE_CODES: ReadonlySet<string> = new Set([
  "LIVE_CONTENT_UNSUPPORTED",
  "IMAGE_POST_UNSUPPORTED",
  "NOT_AN_ARTICLE_PAGE",
  "ARTICLE_TEXT_NOT_FOUND",
  "DOCUMENT_PARSE_FAILED",
  "NO_TRANSCRIBABLE_MEDIA",
  "NO_TRANSCRIPT_AVAILABLE",
  "POST_TEXT_EMPTY",
]);

/**
 * Whether a failed import is one whose *source* the reader can usefully ask us to
 * support. False for a job that failed without a code: with nothing naming the
 * cause, there is no claim to make about the source.
 */
export function isSourceSupportRequestable(
  code: string | null | undefined,
): boolean {
  return code != null && SOURCE_SUPPORT_REQUESTABLE_CODES.has(code);
}

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
