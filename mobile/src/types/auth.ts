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
   * ISO 8601 instant at which the reading language may be changed again, when a
   * change is currently barred by the backend's once-a-month guard-rail. Null
   * (or absent) means a change is possible now — the answer for every account
   * that has never changed its language. The interval itself lives on the
   * server only: the app renders the date it is given and computes nothing.
   */
  reading_language_change_available_at?: string | null;
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
