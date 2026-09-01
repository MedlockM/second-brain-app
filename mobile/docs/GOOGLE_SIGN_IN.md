# Google sign-in — one flow per platform, and the client wiring behind each

Reference for matching the app against the Google Cloud Console entries without
reading the code. Fixed in task-296 after `Error 400: redirect_uri_mismatch` on iOS,
then in task-298 for the code exchange and the accepted audience, then in task-325
when Android moved off the browser flow entirely.

## Two flows, split by platform

| Platform | Flow | Entry point |
| --- | --- | --- |
| iOS, web | Browser authorization code + PKCE, `expo-auth-session/providers/google` | `src/hooks/useGoogleSignIn.ts` |
| Android | System **Credential Manager** sheet, local Expo module | `src/hooks/useGoogleSignIn.android.ts` → `modules/google-credential-manager` |

Both are **client-side**: the app negotiates directly with Google and posts the
resulting `id_token` to `POST /api/auth/google/native`. The backend never takes part.

Consequence: `GOOGLE_REDIRECT_URI` in Secrets Manager and `/api/auth/google/callback`
belong to the **separate web flow** (`/api/auth/google/login`). They have no effect
on the app, and the redirect URI below is never registered there.

The split is a Metro platform extension (`useGoogleSignIn.android.ts` wins over
`useGoogleSignIn.ts` on Android), not a runtime `Platform.OS` branch. Two reasons:
`Google.useAuthRequest` is a hook and cannot be skipped with a condition, and merely
calling it on Android builds the custom-scheme `redirect_uri` that section below
explains is refused. Keeping the files apart means that code is not even bundled
there. `SocialAuthButtons` imports `../hooks/useGoogleSignIn` and only maps the
outcome (`success` / `cancelled` / `noGoogleAccount` / `noIdToken` / `notCompleted`)
to a message.

## Android: Credential Manager

### Why the browser flow is dead on Android

Google refuses a custom URI scheme `redirect_uri` for an Android OAuth client —
`Error 400: invalid_request`, "Custom URI scheme is not enabled for your Android
client" — and its documentation states custom URI schemes are no longer supported
for Android apps. There is no console setting to turn it back on. Since a custom
scheme is the only redirect an Android app can receive from an external browser,
`expo-auth-session` has nothing left to work with there. The dead
`android.scheme: ["com.secondbrainlabs.core"]` intent filter was removed with the
flow it served.

### What the module does

`modules/google-credential-manager` is a **local Expo module**, autolinked from
`mobile/modules/` by `expo-modules-autolinking` (`nativeModulesDir` defaults to
`./modules`). Its `expo-module.config.json` declares `"platforms": ["android"]`, so
the Apple autolinking pass skips it and the iOS project is untouched.

```bash
cd mobile && npx expo-modules-autolinking search -p android   # lists google-credential-manager
cd mobile && npx expo-modules-autolinking search -p apple     # does not
```

The Kotlin side calls `androidx.credentials` with `GetSignInWithGoogleOption` (the
option Google documents for an explicit button press, as opposed to
`GetGoogleIdOption` for a bottom sheet offered on load) and returns
`GoogleIdTokenCredential.createFrom(credential.data).idToken`.

Gradle dependencies are pinned to **released** versions —
`androidx.credentials:credentials:1.6.0`,
`androidx.credentials:credentials-play-services-auth:1.6.0`,
`com.google.android.libraries.identity.googleid:googleid:1.2.0`. `credentials` is
declared explicitly even though `googleid` already pulls it in, because
`googleid:1.2.0` asks for `credentials:1.6.0-beta01`; the explicit `1.6.0` wins
conflict resolution and keeps pre-release artifacts out of the graph.
`credentials-play-services-auth` is imported by nothing in the source but is what
answers the request on the device.

Three outcomes reach JavaScript. Two of them are resolved, not thrown, because
neither is an app failure:

| Native | JS outcome | UI |
| --- | --- | --- |
| `GoogleIdTokenCredential` with an `idToken` | `success` | signs in |
| `GetCredentialCancellationException` | `cancelled` | nothing shown |
| `NoCredentialException` | `noGoogleAccount` | "No Google account on this device…" |
| any other `GetCredentialException` | rejected promise | generic sign-in error |

No nonce is requested: the API does not verify one, so sending it would be
decoration. Adding one means checking it in `auth_social.py` too.

### The module's native sources must not be gitignored

`mobile/.gitignore` ignores the CNG prebuild output. Those entries are **anchored**
(`/android/`, `/ios/`) on purpose: an unanchored `android/` matches at any depth, so
it also swallowed `modules/<name>/android/` — the hand-written Kotlin. Left
unanchored, the working tree looks fine and the EAS build produces a binary with no
module in it. Check with:

```bash
cd mobile && git check-ignore -v modules/google-credential-manager/android/src/main/java/expo/modules/googlecredentialmanager/GoogleCredentialManagerModule.kt
# must print nothing (exit 1)
```

### Which client, and which fingerprint

The `serverClientId` handed to the module is the **Web** client ID
(`EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB`), as Credential Manager requires. It becomes the
`aud` of the returned id_token, and the API already accepts it: it is the same value
as the backend's `GOOGLE_CLIENT_ID`. Nothing to add to the API environment.

`GOOGLE_NATIVE_AUDIENCE_ANDROID` is therefore no longer exercised by any flow —
`GOOGLE_NATIVE_AUDIENCE_IOS` still is.

No Android client ID enters the app. But an **Android OAuth client must still exist**
on Google's side: Credential Manager checks the calling app on its package name
(`com.secondbrainlabs.core`) *and* the SHA-1 fingerprint of the certificate that
signed the installed binary.

For anything distributed by Google Play — the internal track included — that
certificate is **not** the EAS upload keystore: Play re-signs the served artifact.
So the **Play App Signing SHA-1 must be declared on an Android OAuth client** as
well, next to the EAS-keystore one (two Android clients, same package name).
Otherwise the account sheet fails on the Play-installed app while working on a
locally installed build.

- Read it: Play Console → *Test and release* (*Test et publication*) → *App integrity*
  (*Intégrité de l'application*) → *App signing* tab (*Signature de l'application*) →
  *App signing key certificate* (*Certificat de clé de signature d'application*),
  SHA-1 line.
- Declare it: Google Cloud Console → *APIs & Services* (*API et services*) →
  *Credentials* (*Identifiants*) → *Create credentials* (*Créer des identifiants*) →
  *OAuth client ID* (*ID client OAuth*) → application type *Android*.

## iOS: `promptAsync()` returns a code, not an id_token

Off the web, the provider forces `responseType: Code`, so the value `promptAsync()`
resolves with is the *raw* authorization result — `{type: 'success', params: {code},
authentication: null}`. Reading `authentication?.idToken` off it always yields
`undefined`; the hook's own auto-exchange publishes its result only through the
second tuple element (`fullResult`).

`useGoogleSignIn` therefore:

1. passes `shouldAutoExchangeCode: false`, so the hook does not fire a competing
   exchange for the same single-use code (whichever request lands second gets
   `invalid_grant`), and
2. calls `exchangeCodeAsync` itself with `googleRequest.clientId`,
   `googleRequest.redirectUri` and `googleRequest.codeVerifier`.

No client secret is involved: the iOS client is a public client and PKCE is what
proves the exchange belongs to the request.

The exchange runs against the iOS client, so that client is the `aud` of the
id_token, and the API must accept it through `GOOGLE_NATIVE_AUDIENCE_IOS` (same value
as `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`). Without it the request is refused with
`401 Invalid audience or issuer`. The web `/auth/google/callback` keeps its
single-audience check against the web client.

### Exact redirect URI the app sends

| Platform | `redirect_uri` sent to Google | Where it comes from |
| --- | --- | --- |
| iOS | `com.googleusercontent.apps.285796240127-ljujk2ubnq4bgav0s97vgcg19plaldgd:/oauthredirect` | Derived at runtime from `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS` by `src/lib/googleOAuth.ts` |
| Android | none — there is no redirect in a Credential Manager call | — |
| Web | `Linking.createURL("")` origin | `makeRedirectUri` default; not used by the shipped app |

Note the **single slash** after the colon — that is the form Google publishes for
native apps, and changing it to `://` breaks the match.

The iOS value is the *reversed client ID*: the iOS client ID with its
`.apps.googleusercontent.com` suffix moved to the front. If the iOS OAuth client is
ever rotated, nothing has to be edited here: the redirect URI and the declared URL
scheme are both derived from `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`.

### Declared URL scheme

`ios.scheme` in `app.config.ts` carries
`["com.googleusercontent.apps.<reversed iOS client ID>"]`, alongside — never in place
of — `scheme: "media-summarizer"` used by expo-router deep links. There is no Google
scheme on Android any more.

The reversed-client-ID transformation appears twice on purpose — inline in
`app.config.ts` and in `src/lib/googleOAuth.ts` — because `@expo/config`
transpiles `app.config.ts` on its own and cannot resolve a relative `.ts` import.
Both read `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`, so the declared scheme and the sent
`redirect_uri` cannot drift apart.

It is declared through `ios.scheme` rather than `ios.infoPlist.CFBundleURLTypes` on
purpose: `@expo/config-plugins` *merges* that field into the generated
`CFBundleURLTypes`, whereas writing `ios.infoPlist.CFBundleURLTypes` directly makes
its scheme plugin bail out (`createInfoPlistPluginWithPropertyGuard`) and would
silently drop `media-summarizer` from the iOS build.

Verify the resolved values with:

```bash
cd mobile && npx expo config --type public   # ios.scheme
cd mobile && npx expo config --type prefix   # after prebuild: CFBundleURLTypes
```

## Public client IDs

OAuth **client IDs** are public identifiers and are committed. The Google **client
secret** is server-side only and must never appear anywhere under `mobile/`.

| Variable | Client type |
| --- | --- |
| `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS` | iOS (bundle ID `com.secondbrainlabs.core`) |
| `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB` | Web application — also the Android `serverClientId` |

There is no `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`: the Android client exists in the
console (package name + SHA-1, see above) but its ID is not an app input.

The two variables are injected in two places, which must stay in sync:

1. `mobile/.env` — local Metro / `expo start` (gitignored).
2. `mobile/eas.json` — `env` block of the `development`, `preview`, `internal` and
   `production` build profiles. `development-simulator` inherits them via
   `extends: development`.

There is no EAS server-side environment variable for them, since they are not
secrets.

Before task-296 no build profile carried them, so every EAS-built binary resolved
them to the empty string and `useAuthRequest` tripped its `invariantClientId`
guard. That was invisible locally because `app.config.ts` re-reads `.env`.

## Google Cloud Console checklist

If iOS sign-in returns `redirect_uri_mismatch`, check in
APIs & Services → Credentials that the client referenced by
`EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`:

- has type **iOS** (a *Web application* client rejects every custom scheme by
  construction — no client-side change can fix that);
- has **Bundle ID** exactly `com.secondbrainlabs.core`.

If the Android account sheet closes immediately or reports a developer error, check
that an **Android** client exists with package name `com.secondbrainlabs.core` and
the SHA-1 of the certificate that signed *the binary under test* — the EAS keystore
for a directly installed build, the Play App Signing certificate for anything
installed from a Play track.

Neither client needs a redirect URI registered by hand: an iOS client accepts its own
reversed-client-ID scheme implicitly, and an Android client has no redirect at all.
