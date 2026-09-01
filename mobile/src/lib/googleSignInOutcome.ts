/**
 * The platform-independent result of a Google sign-in attempt.
 *
 * The two platforms reach it by completely different routes — a browser
 * authorization flow on iOS, the system Credential Manager sheet on Android (see
 * `src/hooks/useGoogleSignIn.ts` and its `.android.ts` counterpart) — but the UI
 * only ever needs these five cases, so it stays platform-agnostic.
 *
 * A thrown error is a sixth, implicit case: something unexpected broke, and the
 * caller renders it through `getFriendlyErrorMessage`.
 */
export type GoogleSignInOutcome =
  /** An ID token to post to `/auth/google/native`. */
  | { type: "success"; idToken: string }
  /** The user backed out. Not an error: show nothing. */
  | { type: "cancelled" }
  /** Android only: the device has no Google account, so there was nothing to pick. */
  | { type: "noGoogleAccount" }
  /** The flow completed but produced no ID token. */
  | { type: "noIdToken" }
  /** The flow ended without a usable authorization result. */
  | { type: "notCompleted" };

/** What `useGoogleSignIn()` returns on every platform. */
export interface GoogleSignInHandle {
  signInAsync: () => Promise<GoogleSignInOutcome>;
}
