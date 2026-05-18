/**
 * Validates email address format.
 */
export function isValidEmail(email: string): boolean {
  if (!email || typeof email !== "string") {
    return false;
  }

  const trimmedEmail = email.trim();
  if (trimmedEmail.length === 0) {
    return false;
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(trimmedEmail)) {
    return false;
  }

  const parts = trimmedEmail.split("@");
  if (parts.length !== 2) {
    return false;
  }

  const [localPart, domainPart] = parts;
  if (localPart.length === 0 || localPart.length > 64) {
    return false;
  }
  if (domainPart.length === 0 || domainPart.length > 255) {
    return false;
  }

  const domainParts = domainPart.split(".");
  if (domainParts.length < 2) {
    return false;
  }

  const extension = domainParts[domainParts.length - 1];
  if (extension.length < 2) {
    return false;
  }

  return true;
}

/**
 * Validates password strength.
 */
export function isValidPassword(
  password: string,
  minLength: number = 6,
): boolean {
  if (!password || typeof password !== "string") {
    return false;
  }
  if (password.length < minLength) {
    return false;
  }
  if (password !== password.trim()) {
    return false;
  }
  return true;
}

/**
 * Gets a user-friendly validation error message for email.
 */
export function getEmailValidationError(email: string): string | null {
  if (!email || email.trim().length === 0) {
    return "Email address is required.";
  }

  const trimmedEmail = email.trim();
  if (!trimmedEmail.includes("@")) {
    return "Email address must contain an @ symbol.";
  }

  if (!isValidEmail(trimmedEmail)) {
    return "Please enter a valid email address.";
  }

  return null;
}

/**
 * Gets a user-friendly validation error message for password.
 */
export function getPasswordValidationError(
  password: string,
  minLength: number = 6,
): string | null {
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
