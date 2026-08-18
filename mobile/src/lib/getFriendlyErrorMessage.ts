interface FriendlyErrorRule {
  regex: RegExp;
  message: string;
}

const CRITICAL_ERROR = "Error";

/**
 * Last-resort wording for an exhausted allowance, used when a refusal reaches the
 * app without its typed code and message. Minutes are the only thing a plan
 * limits, so there is one sentence and no "credits" vocabulary; the specific
 * version with the figures comes from the backend through `quotaError.ts`.
 */
const OUT_OF_MINUTES =
  "You're out of minutes for this period. Upgrade to keep importing audio and video.";

const ERROR_CODE_MESSAGES: Record<string, string> = {
  SESSION_EXPIRED: "Your session has expired. Please sign in again.",
  INVALID_CREDENTIALS: "Invalid email or password. Please try again.",
  EMAIL_NOT_VERIFIED: "Please verify your email address before signing in.",
  EMAIL_ALREADY_EXISTS: "An account with this email already exists.",
  INVALID_VERIFICATION_TOKEN:
    "Invalid verification link. Please request a new one.",
  USER_NOT_FOUND:
    "No account found with this email address. Please check the email or create a new account.",
  NOT_AUTHORIZED: "You don't have permission to perform this action.",
  NOT_FOUND: "Content not found. Please try searching for something else.",
  MEDIA_NOT_FOUND: "This media item was not found or is no longer available.",
  ARTIFACT_NOT_FOUND: "This artifact was not found or is no longer available.",
  INVALID_URL: "This link is invalid. Please try another URL.",
  UNSUPPORTED_URL: "This link is not supported yet. Please try another source.",
  VALIDATION_ERROR: "Please fill in all required fields.",
  PAYMENT_REQUIRED: OUT_OF_MINUTES,
  INSUFFICIENT_MINUTES: OUT_OF_MINUTES,
  QUOTA_EXCEEDED: OUT_OF_MINUTES,
  RATE_LIMITED: "Too many requests. Please wait a moment and try again.",
  CONFLICT:
    "This action conflicts with existing data. Please refresh and try again.",
  BAD_REQUEST: "Please check your input and try again.",
  INTERNAL_ERROR: CRITICAL_ERROR,
  UNKNOWN_ERROR: CRITICAL_ERROR,
};

const DEFAULT_RULES: FriendlyErrorRule[] = [
  {
    regex: /session expired|session has expired|please sign in again/i,
    message: "Your session has expired. Please sign in again.",
  },
  {
    regex:
      /401|unauthorized|invalid token|expired token|missing token|token expired|authentication token required|not authenticated/i,
    message: "Your session has expired. Please sign in again.",
  },
  {
    regex:
      /invalid credentials|incorrect email or password|authentication failed/i,
    message: "Invalid email or password. Please try again.",
  },
  {
    regex: /email not verified/i,
    message: "Please verify your email address before signing in.",
  },
  {
    regex: /account not found|user not found/i,
    message:
      "No account found with this email address. Please check the email or create a new account.",
  },
  {
    regex: /email already exists/i,
    message: "An account with this email already exists.",
  },
  {
    regex: /(payment required|402)|out of minutes|insufficient minutes|quota/i,
    message: OUT_OF_MINUTES,
  },
  {
    regex: /invalid email|email is not valid/i,
    message: "Please enter a valid email address.",
  },
  {
    regex: /password too short|password must be at least/i,
    message: "Password must be at least 8 characters long.",
  },
  {
    regex: /passwords do not match/i,
    message: "Passwords do not match. Please try again.",
  },
  {
    regex: /403|forbidden|not authorized|permission denied/i,
    message: "You don't have permission to perform this action.",
  },
  {
    regex: /network error|failed to fetch|connection failed/i,
    message: "Network error. Please check your connection and try again.",
  },
  {
    regex: /timeout|timed out/i,
    message: "Request timed out. Please try again.",
  },
  {
    regex: /too many requests|rate limit/i,
    message: "Too many requests. Please wait a moment and try again.",
  },
  {
    regex: /not found(?!.*account)/i,
    message: "Content not found. Please try searching for something else.",
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
  const fallback = options.fallback ?? CRITICAL_ERROR;

  if (!error) {
    return fallback;
  }

  const code =
    (error as { code?: string }).code ||
    (error as { error?: { code?: string } }).error?.code;
  if (code && ERROR_CODE_MESSAGES[code]) {
    return ERROR_CODE_MESSAGES[code];
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
      return rule.message;
    }
  }

  // Status-based fallbacks
  if (status === 401) {
    return "Your session has expired. Please sign in again.";
  }
  if (status === 403) {
    return "You don't have permission to perform this action.";
  }
  if (status === 404) {
    return "Content not found. Please try searching for something else.";
  }
  if (status === 429) {
    return "Too many requests. Please wait a moment and try again.";
  }

  return fallback;
}

/**
 * Checks if an error is actionable (user can fix it) vs critical (site bug).
 */
export function isActionableError(error: unknown): boolean {
  const friendlyMessage = getFriendlyErrorMessage(error);
  return friendlyMessage !== CRITICAL_ERROR;
}
