---
id: task-296
title: >-
  Fix the mobile Google sign-in redirect_uri, the missing URL scheme and the EAS
  client-ID injection gap
status: To Do
assignee: []
created_date: '2026-08-18 17:38'
labels:
  - mobile
  - bug
  - auth
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Sign in with Google from the app fails at Google with `Erreur 400 : redirect_uri_mismatch` ("Accès bloqué : la demande de cette appli n'est pas valide"), owner-reported on iOS on 2026-08-18. Sign in with Apple works. Three distinct defects stack up; this task fixes the two that live in the repo.

## This is not a regression of the /api/ consolidation (task-289)

The app's Google flow never reaches the backend. `media-summarizer-api-dev` logs show no `POST /api/auth/google/native` at all — the rejection happens at Google, upstream of any call to us. The reason is structural: `mobile/src/components/SocialAuthButtons.tsx:47-51` runs a **client-side** flow through `expo-auth-session/providers/google` `useAuthRequest`, which negotiates directly with Google using its own `redirect_uri`. The backend is only called afterwards with the resulting `idToken` (`mobile/src/services/authService.ts:182`). `GOOGLE_REDIRECT_URI` in Secrets Manager and the `/api/auth/google/callback` route are used **only** by the web flow `/api/auth/google/login` + `/callback`, which the app never invokes. Google sign-in from the app has most likely never worked; it had simply never been exercised.

## Defect 1 — the redirect_uri is built on the bundle id, not the reversed client ID

`mobile/node_modules/expo-auth-session/build/providers/Google.js:144-148` defaults to:

```js
native: `${Application.applicationId}:/oauthredirect`
// native: `com.googleusercontent.apps.${guid}:/oauthredirect`   <- the form Google documents, left commented out
```

`app.config.ts:59` sets `bundleIdentifier: "com.secondbrainlabs.core"` with no variant suffix, so the app sends `com.secondbrainlabs.core:/oauthredirect`. The client selected is the iOS one (`Google.js:116-121`, `Platform.select({ ios: 'iosClientId' })`) — `285796240127-ljujk2ubnq4bg…`, a value confirmed present in the bundle Metro serves, so this is not a missing-env problem. Expo Go is also ruled out: `expo-apple-authentication` does not run there, and Apple sign-in answered 200.

Fix: pass an explicit `redirectUri` to `Google.useAuthRequest` in the reversed-client-ID form Google documents, derived from the iOS client ID rather than hardcoded, so it stays correct if the client is rotated.

## Defect 2 — the redirect scheme is not declared, so the callback could not come back

Even once Google accepts the request, the redirect cannot re-enter the app: neither `com.secondbrainlabs.core` nor any `com.googleusercontent.apps.*` scheme is declared anywhere. `app.config.ts:51` declares only `scheme: "media-summarizer"`, and there is no `CFBundleURLTypes` in the config or in `mobile/plugins/`. Whichever scheme defect 1 settles on must be declared alongside it.

## Defect 3 — no EAS profile injects the Google client IDs

`mobile/eas.json` declares only `EXPO_PUBLIC_API_BASE_URL` in all four build profiles (`development`, `development-simulator`, `preview`, `production`), and `mobile/.env` is gitignored (`mobile/.gitignore:15`). Any EAS-built binary therefore has `GOOGLE_CLIENT_ID_IOS` / `ANDROID` / `WEB` empty — `useAuthRequest` would then hit its `invariantClientId` guard. This is invisible while Metro serves the bundle locally, because `app.config.ts` re-reads `.env`. Note that `.env` being gitignored means the values cannot simply be committed: use EAS environment variables, or declare them in the profiles' `env` blocks with the same non-secret client IDs already present in `.env` (OAuth client IDs are public identifiers, unlike the client secret, which must stay server-side).

## Owner notes (not ACs)

- **A console check may be needed and only you can do it.** In Google Cloud Console → APIs & Services → Credentials, open client `285796240127-ljujk2ubnq4bg…` and confirm two things: its type is **iOS** (if it was created as *Web application*, it rejects every custom scheme by construction and no code change will help), and its registered **Bundle ID** is exactly `com.secondbrainlabs.core`. Report back if either is wrong — the fix would then be partly in the console.
- Only you can confirm the felt result: the implementer cannot run Sign in with Google on a device.
- The web flow (`/api/auth/google/login`) is separately confirmed working: a differential probe on 2026-08-18 returned the Google sign-in page for the registered `redirect_uri` and `Error 400: redirect_uri_mismatch` for a deliberately unregistered one. Do not change `GOOGLE_REDIRECT_URI` or the backend routes as part of this task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `Google.useAuthRequest` in `mobile/src/components/SocialAuthButtons.tsx` is passed an explicit `redirectUri` in the `com.googleusercontent.apps.<reversed-client-id>:/oauthredirect` form, derived at runtime from the configured iOS client ID rather than hardcoded, so rotating the client does not silently break the flow.
- [ ] #2 The redirect scheme the app now sends is declared in the app's iOS URL schemes through `app.config.ts` (a `CFBundleURLTypes` entry in `ios.infoPlist`, or an equivalent config plugin under `mobile/plugins/`), and `npx expo config --type prefix` or `--type public` shows it in the resolved config.
- [ ] #3 `scheme: "media-summarizer"` and the existing `expo-router` deep-link behaviour are left intact: the new scheme is added alongside it, not in place of it.
- [ ] #4 The Android path is handled consistently with iOS: either it uses the same explicit-`redirectUri` treatment with the Android client ID, or a comment states why Android needs no change.
- [ ] #5 All four build profiles in `mobile/eas.json` that ship a runnable app carry `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`, `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` and `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB`, or an equivalent EAS environment-variable wiring documented in the task's implementation notes; no build profile can resolve them to the empty string.
- [ ] #6 No Google **client secret** is added to `mobile/`, to `eas.json` or to any file the app bundles: only the public client IDs.
- [ ] #7 The backend is untouched: `git diff` shows no change under `media_summarizer/`, and `GOOGLE_REDIRECT_URI` is not referenced by any new mobile code.
- [ ] #8 `npx tsc --noEmit` and the lint command declared in `mobile/package.json` both pass from `mobile/`.
- [ ] #9 `mobile/docs/` or the task's implementation notes record the exact redirect URI the app now sends, so the owner can match it against the Google Cloud Console entry without reading the code.
<!-- AC:END -->
