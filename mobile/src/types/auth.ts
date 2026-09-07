export interface RegisterRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthUser {
  id: string;
  email: string;
  reading_language?: string | null;
  /**
   * IANA zone name of the device ("Europe/Paris"), never a UTC offset. Absent
   * until a foreground pass has reported one, which is a valid state: the
   * Digest waits for a known zone rather than assuming UTC.
   */
  iana_timezone?: string | null;
}

export interface TokenVerificationResponse {
  access_token: string;
  /** Opaque 30-day refresh token, returned by register, login and refresh. */
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface NativeAuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface AuthError {
  message: string;
  field?: string;
  raw?: string;
  code?: string;
}
