# Google sign-in — redirect URIs and client wiring

Reference for matching the app against the Google Cloud Console entries without
reading the code. Fixed in task-296 after `Error 400: redirect_uri_mismatch` on iOS.

## How the flow works

Sign in with Google in the app is a **client-side** flow. `SocialAuthButtons`
negotiates directly with Google through `expo-auth-session/providers/google`
(authorization code + PKCE), then posts the resulting `id_token` to
`POST /api/auth/google/native`. The backend never takes part in the redirect.

Consequence: `GOOGLE_REDIRECT_URI` in Secrets Manager and `/api/auth/google/callback`
belong to the **separate web flow** (`/api/auth/google/login`). They have no effect
on the app, and the redirect URIs below are never registered there.

## Exact redirect URI the app sends

| Platform | `redirect_uri` sent to Google | Where it comes from |
| --- | --- | --- |
| iOS | `com.googleusercontent.apps.285796240127-ljujk2ubnq4bgav0s97vgcg19plaldgd:/oauthredirect` | Derived at runtime from `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS` by `src/lib/googleOAuth.ts` |
| Android | `com.secondbrainlabs.core:/oauthredirect` | `expo-auth-session` default (`Application.applicationId`), which matches the package name Google keys the Android client on |
| Web | `Linking.createURL("")` origin | `makeRedirectUri` default; not used by the shipped app |

Note the **single slash** after the colon — that is the form Google publishes for
native apps, and changing it to `://` breaks the match.

The iOS value is the *reversed client ID*: the iOS client ID with its
`.apps.googleusercontent.com` suffix moved to the front. If the iOS OAuth client is
ever rotated, nothing has to be edited here: the redirect URI and the declared URL
scheme are both derived from `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`.

## Declared URL schemes

Both redirect schemes are declared in `app.config.ts`, alongside — never in place
of — `scheme: "media-summarizer"` used by expo-router deep links:

- `ios.scheme` = `["com.googleusercontent.apps.<reversed iOS client ID>"]`
- `android.scheme` = `["com.secondbrainlabs.core"]`

The reversed-client-ID transformation appears twice on purpose — inline in
`app.config.ts` and in `src/lib/googleOAuth.ts` — because `@expo/config`
transpiles `app.config.ts` on its own and cannot resolve a relative `.ts` import.
Both read `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`, so the declared scheme and the sent
`redirect_uri` cannot drift apart.

They are declared through `ios.scheme` / `android.scheme` rather than
`ios.infoPlist.CFBundleURLTypes` on purpose: `@expo/config-plugins` *merges* those
fields into the generated `CFBundleURLTypes` and Android intent filters, whereas
writing `ios.infoPlist.CFBundleURLTypes` directly makes its scheme plugin bail out
(`createInfoPlistPluginWithPropertyGuard`) and would silently drop
`media-summarizer` from the iOS build.

Verify the resolved values with:

```bash
cd mobile && npx expo config --type public   # ios.scheme / android.scheme
cd mobile && npx expo config --type prefix   # after prebuild: CFBundleURLTypes
```

Android needs the scheme declared because there is no native
`ASWebAuthenticationSession` there: `expo-web-browser` falls back to a Custom Tab
plus a `Linking` listener, so without an intent filter the callback cannot re-enter
the app.

## Public client IDs

OAuth **client IDs** are public identifiers and are committed. The Google **client
secret** is server-side only and must never appear anywhere under `mobile/`.

| Variable | Client type |
| --- | --- |
| `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS` | iOS (bundle ID `com.secondbrainlabs.core`) |
| `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` | Android (package `com.secondbrainlabs.core` + signing SHA-1) |
| `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB` | Web application |

They are injected in three places, all of which must stay in sync:

1. `mobile/.env` — local Metro / `expo start` (gitignored).
2. `mobile/eas.json` — `env` block of the `development`, `preview` and `production`
   build profiles. `development-simulator` inherits them via `extends: development`.
3. Nothing else. There is no EAS server-side environment variable for them, since
   they are not secrets.

Before task-296 no build profile carried them, so every EAS-built binary resolved
them to the empty string and `useAuthRequest` tripped its `invariantClientId`
guard. That was invisible locally because `app.config.ts` re-reads `.env`.

## Google Cloud Console checklist

If iOS sign-in still returns `redirect_uri_mismatch`, check in
APIs & Services → Credentials that the client referenced by
`EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`:

- has type **iOS** (a *Web application* client rejects every custom scheme by
  construction — no client-side change can fix that);
- has **Bundle ID** exactly `com.secondbrainlabs.core`.

An iOS client needs no redirect URI to be registered by hand: Google accepts its
own reversed-client-ID scheme implicitly. Same for the Android client, which is
validated on package name + SHA-1 fingerprint instead.
