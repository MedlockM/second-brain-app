/**
 * Helpers to derive Google's OAuth redirect target for the **iOS** sign-in flow.
 *
 * `expo-auth-session/providers/google` defaults the native redirect URI to
 * `<applicationId>:/oauthredirect`, i.e. `com.secondbrainlabs.core:/oauthredirect`.
 * Google rejects that value for an iOS OAuth client with
 * `Error 400: redirect_uri_mismatch`: an iOS client only accepts its reserved
 * custom scheme, the reversed client ID. So the iOS redirect URI is built here
 * from the configured client ID instead of being hardcoded, which keeps it valid
 * when the client is rotated.
 *
 * Nothing here applies to Android: Google refuses custom URI schemes outright for
 * an Android OAuth client (`Error 400: invalid_request`, "Custom URI scheme is not
 * enabled for your Android client"), so there is no redirect URI to build. Android
 * signs in through Credential Manager instead — see
 * `modules/google-credential-manager` and `src/hooks/useGoogleSignIn.android.ts`.
 *
 * `app.config.ts` needs the same scheme transformation to register the iOS URL
 * scheme, but inlines its own copy: `@expo/config` transpiles that file alone, so
 * it cannot import this one. Both derive from the same env var.
 */

const GOOGLE_CLIENT_ID_SUFFIX = ".apps.googleusercontent.com";

/**
 * Google's reserved custom URL scheme for an OAuth client ID: the client ID with
 * its `.apps.googleusercontent.com` suffix moved to the front.
 *
 * `123-abc.apps.googleusercontent.com` -> `com.googleusercontent.apps.123-abc`
 *
 * Returns `null` when the client ID is missing or is not a Google client ID, so
 * a build without the env var declares no scheme rather than a broken one.
 */
export function getGoogleReservedClientScheme(
  clientId: string | undefined | null,
): string | null {
  const trimmed = clientId?.trim();
  if (!trimmed || !trimmed.endsWith(GOOGLE_CLIENT_ID_SUFFIX)) {
    return null;
  }
  const guid = trimmed.slice(0, -GOOGLE_CLIENT_ID_SUFFIX.length);
  if (!guid) {
    return null;
  }
  return `com.googleusercontent.apps.${guid}`;
}

/**
 * The redirect URI Google documents for iOS OAuth clients:
 * `com.googleusercontent.apps.<reversed-client-id>:/oauthredirect`.
 *
 * The single slash is intentional — it is the form Google publishes, and the one
 * `expo-auth-session` keeps as a commented-out reference in its own provider.
 */
export function getGoogleIosRedirectUri(
  iosClientId: string | undefined | null,
): string | null {
  const scheme = getGoogleReservedClientScheme(iosClientId);
  return scheme ? `${scheme}:/oauthredirect` : null;
}
