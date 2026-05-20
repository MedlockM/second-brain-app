---
id: task-101
title: >-
  Wire Google and Apple OAuth into mobile app (Sign in with Apple required for
  iOS)
status: To Do
assignee: []
created_date: '2026-05-20 08:47'
labels:
  - feature
  - mobile
  - auth
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context
The backend already exposes working Google and Apple OAuth endpoints (`/api/v1/auth/google/login`, `/api/v1/auth/google/callback`, `/api/v1/auth/apple/login`, `/api/v1/auth/apple/callback`) in `media_summarizer/api/endpoints/auth_social.py`. They are wired into `main.py`. The `_link_or_create_user` helper handles new user creation and linking by email.

What is **missing** is the mobile-side integration. The current `mobile/app/(auth)/login.tsx` only supports email/password.

## Why it is a V1 blocker
Apple App Store Review Guideline 4.8 requires **Sign in with Apple** to be offered if any third-party social login (Google included) is offered in the app. Without it, the app will be rejected at review.

## What to implement

### 1. Mobile UI
- Add two buttons "Continue with Google" and "Sign in with Apple" on `mobile/app/(auth)/login.tsx` (and ideally on the register screen too).
- Use the official Apple button styling on iOS (black/white pill, Apple logo) — there is a community package `@invertase/react-native-apple-authentication` or use `expo-apple-authentication`. **`expo-apple-authentication` is the simpler choice for an Expo project.**
- For Google, use `expo-auth-session` with the Google provider, OR open the backend `/api/v1/auth/google/login` URL in an in-app browser (`expo-web-browser`) and listen for the deep-link callback.

### 2. Deep link callback wiring
- Configure a custom URL scheme in `app.config.ts` / `app.json` (e.g. `mediasummarizer://auth/callback-success` and `…/callback-error`).
- The current backend `_redirect_success` and `_redirect_error` redirect to `FRONTEND_URL/auth/callback-success?provider=…`. **For mobile, change the backend to detect a `client=mobile` query param on `/login` and switch the success/error redirect targets to the mobile URL scheme**. Keep web redirects working for any future web client.
- Implement a Linking listener in mobile that picks up the cookie/refresh token from the callback URL and stores the session via `AuthContext`.

### 3. Auth flow choice
**Option A (recommended): native SDK + ID token to backend.** Mobile uses native `expo-apple-authentication` (Apple) and `expo-auth-session/google` (Google) to obtain an ID token. Mobile POSTs the ID token to a NEW backend endpoint `POST /api/v1/auth/{provider}/native` that verifies the token (reuses the existing JWKS verification helper for Apple, the tokeninfo call for Google), creates/links the user, and returns a refresh token in JSON (not as a cookie — mobile will store it in `expo-secure-store`).

**Option B: web-based flow with deep link.** Use `expo-web-browser.openAuthSessionAsync` against the existing backend OAuth URLs. Backend redirects with a deep link carrying a one-time auth code that mobile exchanges for a session via a new `POST /api/v1/auth/{provider}/exchange` endpoint.

**Option A is preferred** because:
- Apple requires the native SDK on iOS for App Store approval.
- No browser context switch.
- Cleaner UX.

### 4. Backend changes (Option A path)
- Add `POST /api/v1/auth/google/native` accepting `{"id_token": "..."}` body, verifying via Google tokeninfo, calling `_link_or_create_user`, returning `{"refresh_token": "...", "access_token": "...", "user": {...}}`.
- Add `POST /api/v1/auth/apple/native` accepting `{"identity_token": "...", "user": {...}}` body, verifying via JWKS (reuse `_apple_verify_id_token`), returning the same payload shape.
- The mobile client calls `/refresh` on next launch using the stored refresh token.

### 5. Environment & config
- iOS: register the bundle ID in Apple Developer + create a Service ID + add `Sign In with Apple` capability in Xcode (Expo prebuild + EAS handles the entitlement when `expo-apple-authentication` is installed).
- Android: Sign in with Apple on Android is rare; we can hide the Apple button on Android (`Platform.OS === 'ios'`).
- Google: create OAuth 2.0 Client IDs in Google Cloud Console for **iOS, Android, AND Web** (the web one is reused by `expo-auth-session` on Expo Go and by the backend for token verification).
- Set env vars: `GOOGLE_CLIENT_ID` (web client ID, used by backend for `aud` check), `APPLE_CLIENT_ID` (Service ID).

### 6. AuthContext changes
- Extend `AuthContext` with `loginWithGoogle()` and `loginWithApple()` methods.
- On success, persist the refresh token to `expo-secure-store` (already used for the email/password flow).

## Files likely touched
- `mobile/app/(auth)/login.tsx` — add buttons
- `mobile/app/(auth)/register.tsx` — add buttons
- `mobile/src/contexts/AuthContext.tsx` — new methods
- `mobile/src/services/authService.ts` — new methods calling the native endpoints
- `mobile/app.config.ts` or `app.json` — URL scheme + Apple capability
- `mobile/package.json` — add `expo-apple-authentication`, `expo-auth-session`, `expo-web-browser`, `expo-crypto`
- `media_summarizer/api/endpoints/auth_social.py` — add `/native` endpoints, parametrize redirect targets per `client` query param

## Verification
- iOS sandbox build: tap "Sign in with Apple" → Apple modal → user accepts → app receives identity_token → `POST /api/v1/auth/apple/native` → user logged into inbox.
- iOS sandbox build: tap "Continue with Google" → Google sheet → app receives id_token → `POST /api/v1/auth/google/native` → user logged into inbox.
- Android: Google works (Apple button hidden).
- Existing email/password flow still works.

## Acceptance criteria are listed in the AC section.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Sign in with Apple button visible on iOS login and register screens (hidden on Android)
- [ ] #2 Continue with Google button visible on both iOS and Android login and register screens
- [ ] #3 Native iOS Apple flow works: tapping the button presents the Apple modal, identity_token is sent to backend, user is logged in
- [ ] #4 Native Google flow works on iOS and Android: id_token is sent to backend, user is logged in
- [ ] #5 Backend exposes POST /api/v1/auth/google/native and POST /api/v1/auth/apple/native that verify tokens and return refresh_token + access_token
- [ ] #6 Refresh token is persisted in expo-secure-store and reused on next launch
- [ ] #7 Existing email/password flow still works without regression
- [ ] #8 App.config registers the necessary Apple capability and bundle identifier
<!-- AC:END -->
