import { useCallback } from "react";
import { signInWithGoogleAsync } from "../../modules/google-credential-manager";
import { Config } from "../constants/config";
import type {
  GoogleSignInHandle,
  GoogleSignInOutcome,
} from "../lib/googleSignInOutcome";

/**
 * Google sign-in on Android, through the system Credential Manager sheet.
 *
 * Metro resolves this file instead of `useGoogleSignIn.ts` on Android, so the
 * browser flow of the other platforms is not even bundled here. It could not be
 * reused anyway: Google refuses a custom URI scheme `redirect_uri` for an Android
 * OAuth client (`Error 400: invalid_request`), which is the only redirect an
 * Android app can receive from an external browser.
 *
 * The `serverClientId` handed to the native module is the **Web** client ID, as
 * Google's Credential Manager documentation requires. It becomes the `aud` of the
 * returned id_token, and `/auth/google/native` already accepts that audience.
 *
 * The Android OAuth client is still needed on Google's side even though its ID
 * never appears in the app: Credential Manager checks the caller's package name
 * and signing fingerprint against it. See `mobile/docs/GOOGLE_SIGN_IN.md`.
 */
export function useGoogleSignIn(): GoogleSignInHandle {
  const signInAsync = useCallback(async (): Promise<GoogleSignInOutcome> => {
    const result = await signInWithGoogleAsync(Config.GOOGLE_CLIENT_ID_WEB);
    if (result.type !== "success") {
      // `cancelled` and `noGoogleAccount`, both resolved by the native module
      // rather than thrown: neither is an app failure.
      return result;
    }
    if (!result.idToken) {
      return { type: "noIdToken" };
    }
    return { type: "success", idToken: result.idToken };
  }, []);

  return { signInAsync };
}
