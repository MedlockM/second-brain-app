---
id: task-298
title: >-
  Fix the mobile Google sign-in: exchange the auth code for an id_token, and
  accept the native audiences server-side
status: To Do
assignee: []
created_date: '2026-08-19 19:16'
labels:
  - mobile
  - bug
  - auth
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Sign in with Google from the app still fails after task-296 fixed the `redirect_uri`. Owner-reported on 2026-08-19. Sign in with Apple works. Two further defects stack up on the same flow; both live in the repo, and the second one only becomes visible once the first is fixed.

## The evidence: the backend is still never called

`media-summarizer-api-dev` CloudWatch logs over the 3 days to 2026-08-19 contain **zero** `POST /api/auth/google/native` or `/api/v1/auth/google/native`, while `POST /api/v1/auth/apple/native` answers `200` sixteen times. The only Google lines are `GET /api/auth/google/login 307`, which belong to the web flow the app never invokes. So the failure is entirely client-side, upstream of any network call to us — same shape as task-296, different cause.

## Defect 1 — `promptAsync()` never returns an id_token on native

`mobile/src/components/SocialAuthButtons.tsx:70` discards the hook's `response`:

```ts
const [, , googlePromptAsync] = Google.useAuthRequest({...});
const result = await googlePromptAsync();
const idToken = result.authentication?.idToken;   // always undefined
```

In `expo-auth-session@~55.0.16`, the Google provider forces `responseType: Code` on every non-web platform (`mobile/node_modules/expo-auth-session/build/providers/Google.js:125-139`, `isInstalledApp`). `promptAsync()` resolves with the *raw* authorization result — `{type: 'success', params: {code, …}, authentication: null}` (`build/AuthRequestHooks.js:91-93`, which only calls `setResult(result)` and returns it). The code→token exchange happens later, inside a `useEffect` that populates `fullResult`, and `fullResult` is exposed **only** as the second tuple element (`providers/Google.js:224`: `return [request, fullResult, promptAsync]`) — the one the component throws away.

So `idToken` is `undefined`, the handler takes its `onError("Failed to obtain Google ID token. Please try again.")` branch, and `loginWithGoogle` is never called. Apple has no such detour: `AppleAuthentication.signInAsync` hands back `identityToken` directly, which is why it answers 200.

Two viable shapes, both acceptable: consume the hook's `response` from a `useEffect` (the pattern Expo documents), or perform the exchange explicitly with `exchangeCodeAsync` using `request.codeVerifier` (keeps the current linear `await` handler, no restructuring of the component). Pick one and say why in the implementation notes. Whichever is chosen, the user-visible cancel path and the loading-state reset must keep working.

## Defect 2 — the backend accepts a single audience, and it is the wrong one

`media_summarizer/api/endpoints/auth_social.py:506` rejects the token unless `aud == GOOGLE_CLIENT_ID`, a single value. The backend's `GOOGLE_CLIENT_ID` is the **web** client (`…-pbq954l1010v0fce5o0smklvvju6o7de`), but the token the app obtains is issued to the client the exchange ran against — the iOS client (`…-ljujk2ubnq4bgav0s97vgcg19plaldgd`) or the Android one (`…-hk6j6351rcc0oqljcfm4ttfs2idcg8c7`), per `providers/Google.js:116-121`. Its `aud` can therefore never equal the web client ID, and defect 1's fix would only move the failure to `401 Invalid audience or issuer`.

`docs/V1_LAUNCH_PLAN.md:264` states the opposite ("Web client ID — vérifie l'`aud` des id_tokens mobiles iOS/Android"). That premise is false for `expo-auth-session`; it holds only for the native Google Sign-In SDK, where a `serverClientId`/`webClientId` makes Google mint the id_token for the web client. The doc line is misleading and should be corrected as part of this task.

The shape to follow already exists a few lines up, for Apple: `APPLE_NATIVE_AUDIENCE` widens `accepted_audiences` alongside `APPLE_CLIENT_ID` (`auth_social.py:340-358`). Mirror it for Google. Only `/google/native` needs the widened check — the web `/google/callback` legitimately expects the web client ID and must keep its single-audience check.

## Owner notes (not ACs)

- **The deploy is yours.** The backend change only takes effect once `main` is pushed and the Lambda image is rebuilt; the implementer cannot verify it against `-dev`.
- **The new runtime variable is yours to provision.** Terraform does not manage the secret payload (task-221 §7.3), so after merge you must add the new key(s) to `media-summarizer-runtime-dev` in Secrets Manager yourself, with the iOS and Android client IDs already present in `mobile/eas.json`. Until then the widened check falls back to the web client ID alone and Google sign-in keeps returning 401.
- **Only you can confirm the felt result** — running Sign in with Google on a device or simulator is out of reach from the worktree. After deploying, the log line to look for is a `POST /api/auth/google/native 200`; its absence means the flow still dies client-side, a `401` means the audience list did not reach the Lambda.
- These OAuth client IDs are public identifiers, not secrets — unlike `GOOGLE_CLIENT_SECRET`, which must never leave the server side.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `mobile/src/components/SocialAuthButtons.tsx` obtains a real Google `id_token` before calling `loginWithGoogle`: the authorization code returned by `promptAsync()` is exchanged for tokens (either by consuming the hook's `response`, or via an explicit `exchangeCodeAsync` with the request's `codeVerifier`), and the chosen approach and its rationale are recorded in the implementation notes.
- [x] #2 The component no longer reads `id_token` off the immediate return value of `promptAsync()` — a `grep` for `authentication?.idToken` on the raw `promptAsync` result in `mobile/src/` returns nothing, or the remaining occurrence is provably on the exchanged result.
- [x] #3 The user-cancel path still shows no error, and `isGoogleLoading` is reset on every exit path of the Google handler including the exchange failing.
- [x] #4 `/google/native` in `media_summarizer/api/endpoints/auth_social.py` accepts the token when its `aud` matches any configured native Google audience (iOS, Android) in addition to `GOOGLE_CLIENT_ID`, mirroring the `APPLE_NATIVE_AUDIENCE` pattern; a token whose `aud` matches none of them is still rejected with 401, and the `iss` check is unchanged.
- [x] #5 The web `/google/callback` handler keeps its single-audience check against `GOOGLE_CLIENT_ID` — the widened audience list is not applied to the web flow.
- [x] #6 The new backend audience variable(s) are declared in `.env.example` with a comment stating which Google client each holds and that they are public identifiers, and `python scripts/check_env_example_complete.py` passes.
- [x] #7 The false claim in `docs/V1_LAUNCH_PLAN.md:264` that the web client ID verifies the `aud` of mobile id_tokens is corrected, stating which client actually mints the token under `expo-auth-session`.
- [x] #8 No Google client secret is added to `mobile/`, to `eas.json`, or to any file the app bundles.
- [x] #9 `ruff check` and `mypy` pass on the changed Python files, and `npx tsc --noEmit` plus the lint command declared in `mobile/package.json` pass from `mobile/`.
- [x] #10 Any `console.log`/`print` added while diagnosing is removed before the task is handed back (AGENTS.md, "Debug instrumentation is temporary").
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### AC #1 — explicit `exchangeCodeAsync`, not the hook's `response`

Both shapes were viable; the explicit exchange won on three counts.

1. **The loading state stays provable.** The handler remains a single linear
   `async` function, so `isGoogleLoading` is released in one `finally` that every
   exit path goes through — cancel, a missing code, a token response without an
   `id_token`, a rejected exchange, a backend refusal (AC #3). The `useEffect`
   shape has to release it from a second place and correlate the effect firing
   with the handler that started the flow.
2. **The hook's exchange has no failure path.** `providers/Google.js` runs
   `exchangeRequest.performAsync(discovery).then(...)` with no `catch`: a failed
   exchange leaves `fullResult` at `null` forever and produces an unhandled
   rejection. Nothing would ever wake the effect, so the spinner would spin until
   the user kills the app — the exact behaviour AC #3 forbids.
3. **It reads where the value is.** The exchanged `TokenResponse.idToken` is what
   gets posted, instead of `fullResult.params.id_token`, a field the provider
   synthesises.

The cost is that the hook's own auto-exchange must be switched off, which is why
the config now carries `shouldAutoExchangeCode: false`. Left on, two requests
would race for the same single-use authorization code and Google would answer
`invalid_grant` to whichever landed second.

The exchange reuses the request object rather than re-deriving anything:
`googleRequest.clientId` (already `Platform.select`-ed by the provider),
`googleRequest.redirectUri` (the task-296 reversed-client-ID URI on iOS) and
`googleRequest.codeVerifier` (the PKCE verifier of the request that produced the
code). No client secret: iOS and Android OAuth clients are public clients and PKCE
is what binds the exchange to the authorization request (AC #8).

`dismiss` joined `cancel` on the silent path — both are the user backing out, and
neither deserves an error banner.

### AC #4/#5 — widened audiences on the native endpoint only

`GOOGLE_NATIVE_AUDIENCE_IOS` and `GOOGLE_NATIVE_AUDIENCE_ANDROID` hold the iOS and
Android OAuth client IDs. `_google_native_accepted_audiences()` builds the accepted
list from them plus `GOOGLE_CLIENT_ID`, de-duplicated, skipping the unset ones —
the same shape `_apple_verify_id_token` uses for `APPLE_NATIVE_AUDIENCE`. An `aud`
outside that list still returns `401 Invalid audience or issuer`, and the `iss`
check is byte-for-byte the one that was there.

Named `*_NATIVE_AUDIENCE_*` rather than `GOOGLE_CLIENT_ID_IOS/ANDROID` on purpose:
the server never initiates a flow with them and never exchanges a code against
them, it only compares an `aud`. The name says so.

Two follow-on details:

- The endpoint's configuration guard moved from `if not GOOGLE_CLIENT_ID` to
  `if not accepted_audiences`, which is the condition that actually matters now.
- A rejection logs `aud`, `iss` and the accepted list at WARNING. Client IDs are
  public identifiers, so nothing leaks, and it is the only way to tell "the native
  audience keys were never provisioned in Secrets Manager" apart from "a token
  from another project reached us" — the two shapes the owner will be looking at
  after deploying. This is operational logging on a refusal path, not diagnostic
  instrumentation, so it stays (AC #10).

### AC #7 — the corrected claim

`docs/V1_LAUNCH_PLAN.md` §3.2 no longer says the web client verifies mobile
`aud`s. It now states that `expo-auth-session` runs the authorization *and* the
exchange against the platform client (iOS on iOS, Android on Android, per
`Platform.select` in `providers/Google.js`), so Google mints the id_token for that
client; the web client ID is only used when the app runs on the web platform. The
inverse arrangement exists only with the native Google Sign-In SDK, where a
`serverClientId`/`webClientId` asks for it explicitly — not the SDK used here.

Same correction applied to the misleading comment in `mobile/.env.example`, and
`mobile/docs/GOOGLE_SIGN_IN.md` gained two sections: why `promptAsync()` returns a
code and not an id_token, and which client mints the token.

### Verification

`ruff check` and `mypy` clean on `auth_social.py`;
`python scripts/check_env_example_complete.py` OK (234 variables);
`npx tsc --noEmit` clean; `npm run lint` 0 errors (6 warnings, all pre-existing
and in files this task does not touch).

`ruff format --check` still wants to reformat `auth_social.py`, but every hunk it
proposes is pre-existing (the file is wrapped at 88 columns, the project sets
`line-length = 135`) and none touches a line added here. AC #9 asks for
`ruff check`, which passes.

Not verifiable from the worktree, and left to the owner as the task's own notes
say: the deploy, provisioning the two new keys in `media-summarizer-runtime-dev`,
and running the flow on a device to see `POST /api/auth/google/native 200`.
<!-- SECTION:NOTES:END -->
