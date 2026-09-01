import { requireOptionalNativeModule } from "expo";

/**
 * Local Expo module wrapping Android's Credential Manager for "Sign in with
 * Google". Android only: the browser-based OAuth flow is closed there because
 * Google refuses a custom URI scheme `redirect_uri` for an Android client, so
 * there is nothing to fall back to. iOS keeps the `expo-auth-session` flow and
 * never links this module (`expo-module.config.json` declares `android` only).
 */

/** What the native side resolves. Cancellation is a result, not an error. */
export type GoogleCredentialManagerResult =
  | { type: "success"; idToken: string }
  /** The user dismissed the account sheet. */
  | { type: "cancelled" }
  /** No Google account on the device, so there was nothing to pick. */
  | { type: "noGoogleAccount" };

interface GoogleCredentialManagerNativeModule {
  /**
   * Shows the system account sheet and resolves with the Google ID token.
   *
   * @param serverClientId the **Web** OAuth client ID. It becomes the `aud` of
   * the returned id_token, which is what `/auth/google/native` verifies against.
   */
  signInAsync(serverClientId: string): Promise<GoogleCredentialManagerResult>;
}

const nativeModule =
  requireOptionalNativeModule<GoogleCredentialManagerNativeModule>(
    "GoogleCredentialManager",
  );

/** False on any platform where the module is not linked (that is, everywhere but Android). */
export const isGoogleCredentialManagerAvailable = nativeModule !== null;

export async function signInWithGoogleAsync(
  serverClientId: string,
): Promise<GoogleCredentialManagerResult> {
  if (!nativeModule) {
    throw new Error(
      "GoogleCredentialManager is not available on this platform. It is an Android-only module.",
    );
  }
  return nativeModule.signInAsync(serverClientId);
}
