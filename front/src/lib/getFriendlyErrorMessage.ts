import { FriendlyErrorRule } from "./getFriendlyErrorMessage.types";

const CRITICAL_ERROR = "Error";
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
  PAYMENT_REQUIRED: "You need more minutes or credits to continue.",
  INSUFFICIENT_MINUTES: "You need more minutes or credits to continue.",
  QUOTA_EXCEEDED:
    "Your quota has been exceeded. Please upgrade your plan or wait for the next period.",
  RATE_LIMITED: "Too many requests. Please wait a moment and try again.",
  CONFLICT:
    "This action conflicts with existing data. Please refresh and try again.",
  BAD_REQUEST: "Please check your input and try again.",
  INTERNAL_ERROR: CRITICAL_ERROR,
  UNKNOWN_ERROR: CRITICAL_ERROR,
};

/**
 * Comprehensive error message rules
 * These map backend errors to user-friendly messages
 */
const DEFAULT_RULES: FriendlyErrorRule[] = [
  // ===========================
  // Authentication & Session Errors
  // ===========================
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
    regex: /session.*expir|session.*expire/i,
    message: "Your session has expired. Please sign in again.",
  },
  {
    regex:
      /identifiants? (invalides|incorrects)|email.*mot de passe.*incorrect|mot de passe.*incorrect|echec.*connexion|connexion.*echou/i,
    message: "Invalid email or password. Please try again.",
  },
  {
    regex:
      /email.*non v\u00e9rifi|adresse e-?mail.*non v\u00e9rifi|email.*non verifi/i,
    message: "Please verify your email address before signing in.",
  },
  {
    regex: /compte.*introuvable|utilisateur.*introuvable|aucun compte/i,
    message:
      "No account found with this email address. Please check the email or create a new account.",
  },
  {
    regex:
      /email.*d\u00e9j\u00e0|email.*deja|adresse e-?mail.*d\u00e9j\u00e0|adresse e-?mail.*deja/i,
    message: "An account with this email already exists.",
  },

  // ===========================
  // Credit & Billing Errors
  // ===========================
  {
    regex: /insufficient credits|not enough credits|you need to purchase/i,
    message: "Insufficient credits.",
  },
  {
    regex: /(payment required|402)|insufficient minutes|quota/i,
    message: "You need more minutes or credits to continue.",
  },
  {
    regex: /payment failed/i,
    message: "Payment failed. Please check your payment method and try again.",
  },
  {
    regex: /invalid payment method/i,
    message: "Invalid payment method. Please update your payment information.",
  },

  // ===========================
  // Validation Errors
  // ===========================
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
    regex: /missing episode information/i,
    message: "Some episode details are missing. Please try another entry.",
  },
  {
    regex: /email.*invalide|adresse e-?mail.*invalide/i,
    message: "Please enter a valid email address.",
  },
  {
    regex:
      /mot de passe.*trop court|mot de passe.*au moins|mot de passe.*minimum/i,
    message: "Password must be at least 8 characters long.",
  },
  {
    regex:
      /les mots de passe ne correspondent pas|mots? de passe.*diff\u00e9rents/i,
    message: "Passwords do not match. Please try again.",
  },
  {
    regex: /champ.*requis|champ.*obligatoire/i,
    message: "Please fill in all required fields.",
  },
  {
    regex: /field.*required|required.*field|missing required field/i,
    message: "Please fill in all required fields.",
  },

  // ===========================
  // Permission Errors
  // ===========================
  {
    regex: /403|forbidden|not authorized|permission denied/i,
    message: "You don't have permission to perform this action.",
  },
  {
    regex: /non autoris|acc\u00e8s refus\u00e9|acces refus\u00e9|acces refuse/i,
    message: "You don't have permission to perform this action.",
  },

  // ===========================
  // Conflict Errors
  // ===========================
  {
    regex: /409|conflict/i,
    message:
      "This action conflicts with existing data. Please refresh and try again.",
  },
  {
    regex:
      /transcript is not available|transcript.*unavailable|transcript.*not ready|transcript is empty/i,
    message: "The transcript is not ready yet. Please try again shortly.",
  },

  // ===========================
  // Quota & Limit Errors
  // ===========================
  {
    regex: /maximum.*exceeded|limit exceeded/i,
    message: "Maximum limit reached. Please reduce the number of items.",
  },
  {
    regex: /quota exceeded/i,
    message:
      "Your quota has been exceeded. Please upgrade your plan or wait for the next period.",
  },

  // ===========================
  // Network & Retry Errors
  // ===========================
  {
    regex: /network error|failed to fetch|connection failed/i,
    message: "Network error. Please check your connection and try again.",
  },
  {
    regex: /timeout|timed out/i,
    message: "Request timed out. Please try again.",
  },

  // ===========================
  // Rate Limiting
  // ===========================
  {
    regex: /too many requests|rate limit/i,
    message: "Too many requests. Please wait a moment and try again.",
  },

  // ===========================
  // Content Errors
  // ===========================
  {
    regex: /not found(?!.*account)/i,
    message: "Content not found. Please try searching for something else.",
  },
  {
    regex: /already exists(?!.*email)/i,
    message:
      "This item already exists. Please choose a different name or check your existing items.",
  },

  // ===========================
  // File Upload Errors
  // ===========================
  {
    regex: /file too large/i,
    message: "File is too large. Please choose a smaller file.",
  },
  {
    regex: /invalid file type/i,
    message: "Invalid file type. Please choose a supported file format.",
  },

];

/**
 * Critical error patterns that should return generic "Error"
 * These indicate site bugs or technical issues users cannot fix
 */
const CRITICAL_ERROR_PATTERNS = [
  // Database errors
  /database|sql|query failed|postgres|mysql|mongodb|redis|memcache/i,

  // Server errors (generic 500)
  /internal server error|500|server error/i,

  // JavaScript/Code errors
  /undefined|null|cannot read property|is not a function/i,
  /reference error|type error|syntax error|unexpected token/i,
  /is not defined|is not iterable|is not callable/i,

  // Stack traces and exceptions
  /traceback|exception|stack trace/i,

  // Infrastructure errors
  /aws|s3|lambda|cloudfront|dynamodb/i,

  // Network/Connection errors (backend issues)
  /econnrefused|connection refused|enotfound/i,

  // CORS errors (configuration issue)
  /cors|cross-origin/i,

  // API/Routing errors (missing endpoints)
  /404.*api|endpoint not found|route not found/i,

  // Module/Build errors
  /webpack|module not found|cannot find module/i,
  /failed to compile|compilation error/i,

  // Parsing errors
  /json parse error|invalid json|unexpected end of json/i,

  // Cache errors
  /cache.*error|cache.*failed/i,
];

/**
 * Technical keywords that indicate a bug rather than user error
 */
const TECHNICAL_KEYWORDS = [
  "webpack",
  "module",
  "import",
  "export",
  "require",
  "async",
  "promise",
  "callback",
  "buffer",
  "stream",
  "prototype",
  "constructor",
  "instanceof",
  "stringify",
  "parse error",
  "compile",
];

/**
 * Maps error messages to user-friendly text.
 * Returns a user-friendly error message for actionable errors,
 * or "Error" for critical/technical errors that users cannot fix.
 *
 * @param error - The error object or message
 * @param options - Optional configuration
 * @returns A user-friendly error message or "Error" for critical errors
 */
export function getFriendlyErrorMessage(
  error: unknown,
  options: { fallback?: string; additionalRules?: FriendlyErrorRule[] } = {},
): string {
  const fallback = options.fallback ?? CRITICAL_ERROR;

  // Handle null/undefined
  if (!error) {
    return fallback;
  }

  const code =
    (error as { code?: string }).code ||
    (error as { error?: { code?: string } }).error?.code;
  if (code && ERROR_CODE_MESSAGES[code]) {
    return ERROR_CODE_MESSAGES[code];
  }

  // Extract the error message
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

  const rawMessage = errorMessage.trim();
  const normalized = rawMessage.toLowerCase();

  const missingCreditsMatch = rawMessage.match(
    /insufficient credits.*required:\s*([0-9]+(?:\.[0-9]+)?)/i,
  );
  if (missingCreditsMatch) {
    return `Insufficient credits. Missing ${missingCreditsMatch[1]} minutes.`;
  }

  // Check for critical errors first - these should always return fallback
  for (const pattern of CRITICAL_ERROR_PATTERNS) {
    if (pattern.test(normalized)) {
      return fallback;
    }
  }

  // Check for 5xx status codes
  const status = (error as { status?: number | string }).status;

  // Permanent server errors (site bugs)
  if (typeof status === "number" && status >= 500) {
    return fallback;
  }

  // Check against all rules (default + additional)
  const rules = [...DEFAULT_RULES, ...(options.additionalRules ?? [])];
  for (const rule of rules) {
    if (rule.regex.test(normalized)) {
      return rule.message;
    }
  }

  // Status-based fallbacks when no rule matched
  if (status === 401) {
    return "Your session has expired. Please sign in again.";
  }
  if (status === 402) {
    return "You need more minutes or credits to continue.";
  }
  if (status === 403) {
    return "You don't have permission to perform this action.";
  }
  if (status === 404) {
    return "Content not found. Please try searching for something else.";
  }
  if (status === 422) {
    return "Please fill in all required fields.";
  }
  if (status === 429) {
    return "Too many requests. Please wait a moment and try again.";
  }

  // Check for technical keywords that indicate a bug
  const hasTechnicalKeyword = TECHNICAL_KEYWORDS.some((keyword) =>
    normalized.includes(keyword),
  );

  if (hasTechnicalKeyword) {
    return fallback;
  }

  // If the error message is very short and doesn't contain technical jargon,
  // it might already be user-friendly
  if (
    rawMessage.length < 100 &&
    !normalized.includes("error") &&
    !normalized.includes("exception") &&
    !normalized.includes("failed") &&
    !normalized.includes("invalid") &&
    !normalized.includes("cannot")
  ) {
    return rawMessage;
  }

  // Default to generic error for anything we don't recognize
  // This prevents leaking technical details to users
  return fallback;
}

/**
 * Checks if an error is actionable (user can fix it)
 * vs critical (site bug, user cannot fix)
 *
 * @param error - The error object or message
 * @returns true if the error is actionable, false if critical
 */
export function isActionableError(error: unknown): boolean {
  const friendlyMessage = getFriendlyErrorMessage(error);
  return friendlyMessage !== CRITICAL_ERROR;
}

/**
 * Formats an error for logging/debugging purposes
 *
 * @param error - The error object
 * @returns A formatted error string for logging
 */
export function formatErrorForLogging(error: unknown): string {
  if (error instanceof Error) {
    return `${error.name}: ${error.message}\n${error.stack || ""}`;
  }
  if (typeof error === "object" && error !== null) {
    return JSON.stringify(error, null, 2);
  }
  return String(error);
}
