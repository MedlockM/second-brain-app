/**
 * Validation Utilities
 *
 * Provides client-side validation functions to catch errors early
 * before sending requests to the backend.
 */

/**
 * Validates email address format
 *
 * Rules:
 * - Must contain exactly one @
 * - Must have text before and after @
 * - Must have a domain extension (e.g., .com, .org)
 * - No spaces allowed
 *
 * @param email - The email address to validate
 * @returns true if valid, false otherwise
 */
export function isValidEmail(email: string): boolean {
  if (!email || typeof email !== 'string') {
    return false;
  }

  // Trim whitespace
  const trimmedEmail = email.trim();

  // Basic checks
  if (trimmedEmail.length === 0) {
    return false;
  }

  // Email regex pattern
  // Requires: text@domain.extension
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if (!emailRegex.test(trimmedEmail)) {
    return false;
  }

  // Additional checks
  const parts = trimmedEmail.split('@');
  if (parts.length !== 2) {
    return false;
  }

  const [localPart, domainPart] = parts;

  // Local part (before @) checks
  if (localPart.length === 0 || localPart.length > 64) {
    return false;
  }

  // Domain part (after @) checks
  if (domainPart.length === 0 || domainPart.length > 255) {
    return false;
  }

  // Must have a domain extension
  const domainParts = domainPart.split('.');
  if (domainParts.length < 2) {
    return false;
  }

  // Extension must be at least 2 characters
  const extension = domainParts[domainParts.length - 1];
  if (extension.length < 2) {
    return false;
  }

  // Check for common invalid patterns
  const invalidPatterns = [
    /^\./, // starts with dot
    /\.$/, // ends with dot
    /\.\./, // consecutive dots
    /@\./, // dot immediately after @
    /\.@/, // dot immediately before @
  ];

  for (const pattern of invalidPatterns) {
    if (pattern.test(trimmedEmail)) {
      return false;
    }
  }

  return true;
}

/**
 * Validates password strength
 *
 * Rules:
 * - Minimum 6 characters (configurable)
 * - No leading/trailing spaces
 *
 * @param password - The password to validate
 * @param minLength - Minimum password length (default: 6)
 * @returns true if valid, false otherwise
 */
export function isValidPassword(password: string, minLength: number = 6): boolean {
  if (!password || typeof password !== 'string') {
    return false;
  }

  // Check minimum length
  if (password.length < minLength) {
    return false;
  }

  // Check for leading/trailing spaces
  if (password !== password.trim()) {
    return false;
  }

  return true;
}

/**
 * Gets a user-friendly validation error message for email
 *
 * @param email - The email to validate
 * @returns Error message or null if valid
 */
export function getEmailValidationError(email: string): string | null {
  if (!email || email.trim().length === 0) {
    return "Email address is required.";
  }

  const trimmedEmail = email.trim();

  if (trimmedEmail.includes(' ')) {
    return "Email address cannot contain spaces.";
  }

  if (!trimmedEmail.includes('@')) {
    return "Email address must contain an @ symbol.";
  }

  const parts = trimmedEmail.split('@');
  if (parts.length > 2) {
    return "Email address can only contain one @ symbol.";
  }

  if (parts.length === 2) {
    const [localPart, domainPart] = parts;

    if (localPart.length === 0) {
      return "Email address must have text before the @ symbol.";
    }

    if (domainPart.length === 0) {
      return "Email address must have a domain after the @ symbol.";
    }

    if (!domainPart.includes('.')) {
      return "Email domain must include a period (e.g., example.com).";
    }

    const domainParts = domainPart.split('.');
    const extension = domainParts[domainParts.length - 1];

    if (extension.length < 2) {
      return "Email domain extension must be at least 2 characters (e.g., .com, .org).";
    }
  }

  if (!isValidEmail(trimmedEmail)) {
    return "Please enter a valid email address.";
  }

  return null;
}

/**
 * Gets a user-friendly validation error message for password
 *
 * @param password - The password to validate
 * @param minLength - Minimum password length (default: 6)
 * @returns Error message or null if valid
 */
export function getPasswordValidationError(password: string, minLength: number = 6): string | null {
  if (!password || password.length === 0) {
    return "Password is required.";
  }

  if (password.length < minLength) {
    return `Password must be at least ${minLength} characters long.`;
  }

  if (password !== password.trim()) {
    return "Password cannot start or end with spaces.";
  }

  return null;
}

/**
 * Validates that two passwords match
 *
 * @param password - The password
 * @param confirmPassword - The confirmation password
 * @returns true if they match, false otherwise
 */
export function passwordsMatch(password: string, confirmPassword: string): boolean {
  return password === confirmPassword;
}

/**
 * Gets error message for password mismatch
 *
 * @param password - The password
 * @param confirmPassword - The confirmation password
 * @returns Error message or null if they match
 */
export function getPasswordMatchError(password: string, confirmPassword: string): string | null {
  if (!passwordsMatch(password, confirmPassword)) {
    return "Passwords do not match. Please try again.";
  }
  return null;
}
