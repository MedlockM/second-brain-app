import { useCallback } from "react";
import { Platform } from "react-native";
import { exchangeCodeAsync } from "expo-auth-session";
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";
import { Config } from "../constants/config";
import { getGoogleIosRedirectUri } from "../lib/googleOAuth";
import type {
  GoogleSignInHandle,
  GoogleSignInOutcome,
} from "../lib/googleSignInOutcome";

/**
 * Google sign-in through a browser authorization flow — iOS and web.
 *
 * Android has its own implementation in `useGoogleSignIn.android.ts`, which Metro
 * resolves in place of this file (platform extensions win over the bare `.ts`).
 * That split is not cosmetic: this flow cannot work on Android at all, because
 * `Google.useAuthRequest` builds `com.secondbrainlabs.core:/oauthredirect` there
 * and Google refuses a custom URI scheme for an Android OAuth client. Keeping the
 * two apart means no authorization request is even constructed on Android — and
 * `useAuthRequest` is a hook, so it could not have been skipped with a condition.
 */

// Required for expo-auth-session to dismiss the web browser on redirect.
WebBrowser.maybeCompleteAuthSession();

/**
 * Redirect URI for the native Google flow, or `undefined` to keep the
 * expo-auth-session default.
 *
 * iOS: the library would default to `<bundleId>:/oauthredirect`, which an iOS
 * OAuth client rejects with `Error 400: redirect_uri_mismatch` — such a client
 * only accepts its reserved scheme. It is therefore derived from the configured
 * iOS client ID (never hardcoded, so rotating the client keeps it valid) and the
 * matching scheme is declared in `ios.scheme` in app.config.ts.
 *
 * Web: no override — `makeRedirectUri` produces the right origin.
 */
const GOOGLE_REDIRECT_URI =
  Platform.OS === "ios"
    ? (getGoogleIosRedirectUri(Config.GOOGLE_CLIENT_ID_IOS) ?? undefined)
    : undefined;

export function useGoogleSignIn(): GoogleSignInHandle {
  /**
   * `shouldAutoExchangeCode: false` turns off the hook's own background code
   * exchange. Left on, it would race the explicit exchange below for the same
   * single-use authorization code — whichever request lands second gets
   * `invalid_grant` from Google — and it publishes its outcome only through the
   * second tuple element, which nothing reads.
   */
  const [googleRequest, , googlePromptAsync] = Google.useAuthRequest({
    iosClientId: Config.GOOGLE_CLIENT_ID_IOS,
    webClientId: Config.GOOGLE_CLIENT_ID_WEB,
    redirectUri: GOOGLE_REDIRECT_URI,
    shouldAutoExchangeCode: false,
  });

  const signInAsync = useCallback(async (): Promise<GoogleSignInOutcome> => {
    const result = await googlePromptAsync();

    // `cancel` (browser closed) and `dismiss` (session dismissed) are the user
    // backing out, not a failure.
    if (result.type === "cancel" || result.type === "dismiss") {
      return { type: "cancelled" };
    }
    if (result.type !== "success") {
      return { type: "notCompleted" };
    }

    // Off the web, the Google provider forces `responseType: Code`, so the
    // authorization result carries a code and `authentication` is null. The
    // id_token only exists after exchanging that code against the token
    // endpoint, with the PKCE verifier of the request that produced it — and
    // the client the exchange runs against is the audience the id_token is
    // minted for.
    const code = result.params.code;
    if (!code || !googleRequest) {
      return { type: "notCompleted" };
    }

    const tokens = await exchangeCodeAsync(
      {
        clientId: googleRequest.clientId,
        redirectUri: googleRequest.redirectUri,
        code,
        extraParams: googleRequest.codeVerifier
          ? { code_verifier: googleRequest.codeVerifier }
          : {},
      },
      Google.discovery,
    );

    if (!tokens.idToken) {
      return { type: "noIdToken" };
    }
    return { type: "success", idToken: tokens.idToken };
  }, [googlePromptAsync, googleRequest]);

  return { signInAsync };
}
