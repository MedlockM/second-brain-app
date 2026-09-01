---
id: task-325
title: >-
  Replace the dead Android Google sign-in flow with a Credential Manager native
  module
status: Done
assignee: []
created_date: '2026-09-01 16:32'
updated_date: '2026-09-01 19:40'
labels:
  - mobile
  - android
  - auth
  - phase-6
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Google sign-in is broken on Android, and not by a misconfiguration: the flow the app uses no longer exists. Owner session of 2026-09-01, on the `versionCode` 5 AAB installed from the Play internal test track — tapping "Continue with Google" opens Chrome and lands on Google's `Accès bloqué : la demande de Second Brain Labs n'est pas valide` / `Erreur 400 : invalid_request`.

## What is actually wrong

`expo-auth-session/providers/google` opens the authorization endpoint in the browser with `redirect_uri = com.secondbrainlabs.core:/oauthredirect`, a custom URI scheme. Replaying that exact request from a workstation reproduces the failure and surfaces the reason the mobile screen hides:

```
Error 400: invalid_request
Access blocked: Second Brain Labs's request is invalid
→ Custom URI scheme is not enabled for your Android client.
```

Google's own documentation (`developers.google.com/identity/protocols/oauth2/native-app`) states it twice: « Custom URI schemes are no longer supported on Android and Chrome apps », and among the causes of `invalid_request`: « An unsupported custom scheme was used for the redirect uri. » The error message says "not enabled", the docs say "no longer supported" and describe no setting to turn on; the two Google support pages the error links to mention neither the error nor any toggle. Treat the path as closed, not as a configuration gap.

**iOS is not affected and must not be touched.** The same replay with the iOS client and its reversed-client-id scheme returns Google's consent screen with no error — the prohibition is worded for "Android and Chrome apps". Changing iOS would replace a proven flow with one nobody can test: no Mac, no current TestFlight build (`task-161`), and iOS billing is blocked on `task-261` anyway.

## Decision taken by the owner, 2026-09-01

Call Android's Credential Manager from a **local Expo module in this repo**. The two off-the-shelf alternatives were considered and rejected: `@react-native-google-signin/google-signin` is MIT and free but calls the Google Sign-In SDK that Google marks « deprecated and will be removed from the Google Play services Auth SDK in a future release »; the same author's Credential Manager build (`universal-sign-in.com`) is a paid licence at $79/year. Google charges nothing for the APIs themselves — `androidx.credentials`, `com.google.android.libraries.identity.googleid`, the OAuth clients and the console are all free — so the only thing money would buy here is a JS wrapper.

Shape to build:

- A local module under `mobile/modules/`, autolinked by `expo-modules-autolinking` (the CNG workflow regenerates `android/`, so the module lives in the repo and the generated project picks it up).
- Kotlin side on `androidx.credentials` + `credentials-play-services-auth` + `googleid`, pinned to released versions (no `-alpha`), using `GetSignInWithGoogleOption` — the option Google documents as « best triggered as a reaction to when user taps a sign in button », which is exactly this button. Return the `idToken` from `GoogleIdTokenCredential`.
- `serverClientId` is the **Web** client ID (`EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB`), which Google documents verbatim: « The `webClientId` is the Web Client ID you set up for OAuth in your Google Cloud Project ». The resulting token's audience is that Web client, and `media-summarizer-runtime-dev` already accepts it — `GOOGLE_CLIENT_ID`, `GOOGLE_NATIVE_AUDIENCE_IOS` and `GOOGLE_NATIVE_AUDIENCE_ANDROID` are all populated there (verified 2026-09-01). **No backend change, no deploy.**
- User cancellation must stay silent, like the current `cancel`/`dismiss` branch: map `GetCredentialCancellationException` to a cancelled result rather than an error, and give "no Google account on the device" (`NoCredentialException`) its own message.
- No nonce. The backend does not verify one, so passing it would be decoration; if it is ever wanted, it has to be checked in `auth_social.py` in the same change.

## Two traps that fail silently

1. **`mobile/.gitignore:12` is `android/`, which matches at any depth** — including `modules/<name>/android/`. Verified with `git check-ignore -v modules/foo/android/src/main/Test.kt`. Left as is, the Kotlin source is never committed, `main` looks fine, and the EAS cloud build produces an AAB with no module in it. A negation is required, and AC#4 exists only to catch this.
2. **The Android OAuth client's SHA-1 must match the certificate that signs the *installed* app.** Unlike the browser flow, Credential Manager has Play services check package name + signing fingerprint, so a mismatch fails at runtime with no useful message. Since the AAB goes through Play App Signing, the installed app carries Google's certificate, not the EAS upload keystore whose SHA-1 backs the current client (`task-162`). This is owner work, see below.

## Owner notes — not acceptance criteria

- Read the Play App Signing SHA-1 in **Play Console → Test et publication → Intégrité de l'application → onglet Signature de l'application → Certificat de clé de signature d'application**, then declare it in **Google Cloud Console → API et services → Identifiants → ID clients OAuth 2.0**. The Android client form takes one fingerprint, so this means a second Android OAuth client alongside the EAS-keystore one, same package name. Both are fine: with Credential Manager the token audience is the Web client, so the backend is indifferent to how many Android clients exist.
- Then an EAS build, an install from the internal track, and an actual sign-in on the phone. None of that is reachable from a worktree.
- This unblocks nothing on the billing side — `task-238` AC#6/#7 need a working sign-in first, since the paywall sits behind the account.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A local Expo module exists under mobile/modules/ with an expo-module.config.json declaring the android platform, and npx expo-modules-autolinking search -p android lists it among the resolved modules
- [x] #2 The module's Kotlin source calls androidx.credentials with GetSignInWithGoogleOption and returns the idToken from GoogleIdTokenCredential; the Gradle dependencies pin released versions with no -alpha or -beta suffix
- [x] #3 The module distinguishes three outcomes for the JS caller: an idToken, a user cancellation (GetCredentialCancellationException) and the absence of any Google account on the device (NoCredentialException)
- [x] #4 git check-ignore -v returns nothing for a Kotlin file inside the module, and git status lists the module's android sources as untracked or staged
- [x] #5 mobile/src/components/SocialAuthButtons.tsx calls the native module on Android and leaves the expo-auth-session path untouched on iOS; no custom-scheme redirect_uri is built for Android anywhere in mobile/
- [x] #6 The now-dead Android custom scheme is deleted: android.scheme in mobile/app.config.ts, and every comment claiming Google documents <package>:/oauthredirect for an Android client (SocialAuthButtons.tsx and src/lib/googleOAuth.ts) is corrected to state that custom URI schemes are refused on Android
- [x] #7 media_summarizer/api/endpoints/auth_social.py is not modified: the Web client ID is already an accepted audience for /google/native
- [x] #8 npx tsc --noEmit and npx eslint . are clean in mobile/
- [x] #9 docs/AUTHENTICATION_SETUP.md records the Android flow as Credential Manager with the Web client ID as serverClientId, and the requirement that the Play App Signing SHA-1 be declared on an Android OAuth client
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Android Google sign-in now goes through a local Expo module,
`mobile/modules/google-credential-manager` (name derived from the directory, no
`package.json` needed). `expo-module.config.json` declares `"platforms":
["android"]` only, which is what keeps iOS out of it — verified both ways:
`npx expo-modules-autolinking search -p android` lists it and `resolve -p android`
emits the Gradle project pointing at `modules/google-credential-manager/android`,
while `search -p apple` does not list it at all.

`GoogleCredentialManagerModule.kt` exposes one function,
`signInAsync(serverClientId)`, on `Queues.MAIN` (Credential Manager shows system UI
and needs `appContext.throwingActivity`). It builds a `GetCredentialRequest` with a
single `GetSignInWithGoogleOption`, and resolves a discriminated map rather than
throwing for the two non-failures: `{type: "success", idToken}`,
`{type: "cancelled"}` (`GetCredentialCancellationException`),
`{type: "noGoogleAccount"}` (`NoCredentialException`). Anything else rejects with a
`CodedException`. Two deliberate choices there: the failure message is built from the
exception class name and `message`, because `GetCredentialException.type` is
`@RestrictTo(LIBRARY_GROUP)`; and the returned credential's `type` string is not
compared, because googleid 1.2.0 ships two of them
(`TYPE_GOOGLE_ID_TOKEN_CREDENTIAL`, `TYPE_GOOGLE_ID_TOKEN_SIWG_CREDENTIAL`) and the
request carries a single option, so parsing the bundle with
`GoogleIdTokenCredential.createFrom` is both sufficient and version-proof. No nonce.

Dependencies are pinned to releases: `credentials:1.6.0`,
`credentials-play-services-auth:1.6.0`, `googleid:1.2.0`. `credentials` is declared
explicitly even though `googleid` pulls it in, because `googleid:1.2.0` asks for
`credentials:1.6.0-beta01`; the explicit `1.6.0` wins conflict resolution so no
pre-release artifact reaches the graph. The template's `lintOptions { abortOnError
false }` is omitted on purpose — `expo-module-gradle-plugin` already sets it via
`useDefaultAndroidSdkVersions`.

The `.gitignore` trap (AC#4) was real: `git check-ignore -v` blamed
`mobile/.gitignore:12:android/` for the module's Kotlin path. Fixed by **anchoring**
the prebuild entries (`/ios/`, `/android/`) rather than adding a negation — anchoring
cannot be undone by ordering, and still ignores the CNG output. Re-verified in both
directions: nothing is returned for the Kotlin file, and `android/app/build.gradle` /
`ios/Podfile` are still attributed to `/android/` / `/ios/`.

The platform split is a Metro platform extension, not a `Platform.OS` branch:
`src/hooks/useGoogleSignIn.ts` (iOS + web, the untouched expo-auth-session flow, with
`WebBrowser.maybeCompleteAuthSession()` and the iOS reversed-client-id redirect URI)
and `src/hooks/useGoogleSignIn.android.ts` (Credential Manager, `serverClientId =
Config.GOOGLE_CLIENT_ID_WEB`). Necessary because `Google.useAuthRequest` is a hook
and cannot be skipped conditionally: leaving it on Android would keep building
`com.secondbrainlabs.core:/oauthredirect`, which AC#5 forbids. Both return the same
`GoogleSignInOutcome` union (`src/lib/googleSignInOutcome.ts`), and
`SocialAuthButtons.tsx` only maps it to a message — new i18n key
`auth.google.noGoogleAccount` in the eleven catalogues.

Legacy removed in the same pass, since nothing reads an Android client ID any more:
`android.scheme` in `app.config.ts`, `extra.googleClientIdAndroid`,
`Config.GOOGLE_CLIENT_ID_ANDROID`, `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` in the four
`eas.json` profiles and in `mobile/.env.example`, and the now-empty `OPTIONAL_KEYS`
machinery of `scripts/mobile_release_check.sh`. The Android OAuth **client** stays
required on Google's side (package name + signing SHA-1) — documented, not deleted.

AC#7 holds with zero backend edits: `_google_native_accepted_audiences()` already
returns `GOOGLE_CLIENT_ID` (the Web client), so the Credential Manager audience is
accepted as-is. Left alone on purpose, and therefore still stale: that function's
docstring still describes the Android audience as the Android client, and
`GOOGLE_NATIVE_AUDIENCE_ANDROID` is now exercised by no flow. Both are one-line
follow-ups the AC forbade touching.

AC#8: `npx tsc --noEmit` is clean. `npm run lint` (`eslint . --ext .ts,.tsx`) reports
0 errors and 2 pre-existing warnings, in `app/(tabs)/digest.tsx` and
`src/services/purchaseService.ts` — neither touched here. The broader `npx eslint .`
additionally reports one pre-existing error in `metro.config.js`
(`no-var-requires` on a CommonJS config file), which the project's own lint script
excludes by extension; nothing in this change is implicated.

Not reachable from a worktree, and not attempted: the Gradle/Kotlin compile (no
Android SDK, and `expo prebuild` is owner territory), the EAS build, and the sign-in
on a physical phone. The Kotlin was validated statically instead — every symbol used
was checked against the installed `expo-modules-core` 55 sources
(`AsyncFunction(String, Promise)`, `Queues.MAIN`, `runOnQueue`,
`appContext.throwingActivity`, `CodedException(message, cause)`,
`Promise.resolve(Map<String, Any?>)`) and against the actual class entries of
`cred-1.6.0.aar` / `googleid-1.2.0.aar`.
<!-- SECTION:NOTES:END -->
