---
id: task-340
title: >-
  Ship JS changes over the air with expo-updates and build only when the native
  fingerprint changes
status: To Do
assignee: []
created_date: '2026-09-03 10:14'
labels:
  - mobile
  - release
  - ci
dependencies:
  - task-339
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The owner asked for the mobile cadence to be automated: every push to `main` should
get the change onto the testers' devices without a manual command, **and only spend a
native build when a native build is actually required**. Decision taken 2026-09-02:
`expo-updates`. The technology is settled — no benchmark, this is the implementation.

## Where the project stands

`mobile/package.json` has `expo: ^55`, `react-native: 0.83.6`, `expo-dev-client:
~55.0.35`, and **no `expo-updates`**. Nothing anywhere declares `updates`,
`runtimeVersion`, `channel` or a fingerprint policy. So today there is exactly one way
to change what a tester runs: a full native build. `.github/workflows/mobile-build-distribute.yml`
has two entry points, a `mobile-v*` tag and `workflow_dispatch`, and **no push-on-`main`
path at all**.

That is also why "build only when necessary" is not answerable without OTA: with only
one delivery mechanism, *necessary* means *always*. With `expo-updates` the question
becomes machine-decidable — the native fingerprint either changed or it did not.

The free tier is what makes this load-bearing rather than a nicety. EAS Free gives
**15 Android + 15 iOS builds per month, 1 concurrency, low-priority queue**; EAS Update
Free gives **1 000 MAUs and unlimited updates**. A dozen JS-only commits in a day would
exhaust a month of builds; over OTA they cost nothing.

## What to build

### 1. Install and configure `expo-updates`

- `npx expo install expo-updates` from `mobile/`, so the version resolved is the one
  SDK 55 pins.
- `eas update:configure` exists (eas-cli 22.0.0) but **cannot write into a dynamic
  `app.config.ts`** — it will print what to add. Add it by hand to
  `mobile/app.config.ts`:
  - `updates.url` = `https://u.expo.dev/<projectId>`, built from the **same**
    `projectId` constant already used by `extra.eas.projectId` (`app.config.ts:242`).
    Do not paste a second copy of the UUID; two copies is one copy that can go stale.
  - `runtimeVersion: { policy: "fingerprint" }`. This is the whole mechanism: the
    runtime version becomes a hash of the native project, so an update can only ever
    land on a binary whose native surface matches it.
- Keep `expo-updates`' defaults for check/apply behaviour. There is no requirement here
  for a custom update-gate UI, and inventing one is out of scope.

### 2. One channel per build profile, and never two profiles on one channel

In `mobile/eas.json`: `internal` → `"channel": "internal"`, `production` →
`"channel": "production"`, `preview` → its own channel. The two dev-client profiles
(`development`, `development-simulator`) load from a dev server and get an explicit,
documented choice rather than an accidental one.

The rule matters because the failure it prevents is silent: publish to a channel a
store binary listens on and that JS reaches the store binary. The automation in step 3
must target **`internal` only** — never `production`.

### 3. The conditional workflow

Trigger: `push` on `main`, `paths` covering `mobile/**` and the workflow file itself,
**excluding** markdown and `mobile/.maestro/**` — otherwise editing
`mobile/MOBILE_CI_CD.md` publishes an update whose bundle is byte-identical to the
previous one. Declare a `concurrency` group so two pushes do not race two publishes.

Per platform, the decision is three commands. All flags below were verified against
**eas-cli 22.0.0** on 2026-09-03 by running `--help` on the actual binary; none of them
is assumed:

1. `eas fingerprint:generate --json --non-interactive --platform <android|ios> -e internal`
   → JSON with a top-level `hash`. **This one needs no Expo login** — verified by
   running it from a clean worktree; the Android hash of the tree at `de6c91b`, before
   `expo-updates`, is `cdde50c777525d5ff172cfbb2ad9f95bd40b40d0`.
2. `eas build:list --platform <p> -e internal --status finished --fingerprint-hash <hash> --limit 1 --json --non-interactive`
   → `--fingerprint-hash` is a real filter flag on `build:list`. An empty result means
   no finished build matches the current native surface. This one **does** need
   `EXPO_TOKEN`, which the workflow has since 2026-09-02.
3. Empty result → the native surface moved →
   `eas build --platform <p> --profile internal --auto-submit --non-interactive`.
   Non-empty → JS-only change →
   `eas update --channel internal --platform <p> --environment <env> --message "<commit subject>" --non-interactive`.

### 4. `--environment` is not optional, and getting it wrong is silent

`eas update --help` on 22.0.0 says of `--environment`: *"Required for projects using
Expo SDK 55 or greater."* This project is SDK 55.

The trap underneath it: `EXPO_PUBLIC_*` values are **inlined at bundle time**, and this
repo declares them in the per-profile `env` blocks of `eas.json`, which is what feeds a
*build*. `eas update --environment X` reads the **EAS server-side environment** `X`. If
that environment does not hold the same `EXPO_PUBLIC_*` keys, the OTA bundle inlines
empty values and every network call in the updated app fails — with no build error, no
submit error and no runtime hint. Same failure class as `task-339`, delivered faster.

So part of this task is reconciling the two sources: decide and document which EAS
environment corresponds to the `internal` profile, and make the values the update path
inlines provably the same set the build path inlines (either by declaring them in that
EAS environment, or by having the profile carry an `environment` key so both read one
source). `eas env:list` needs authentication, so the final confirmation is an owner
check — see the notes below.

### 5. Rollback story, documented not automated

`eas update:rollback`, `eas update:roll-back-to-embedded` and `eas update:republish`
all exist in 22.0.0. Write down which one to reach for; do not wire an automatic
rollback.

### 6. Pin the EAS CLI

`.github/workflows/mobile-build-distribute.yml` installs it as bare
`npm install -g eas-cli`. The latest published version is 23.2.0 while the owner's
machine runs 22.0.0 — the workflow and the laptop already disagree, and the whole
decision rule in step 3 rests on flags a CLI major bump can move. Pin an explicit
version in every workflow that installs the CLI, with a comment naming the flags the
pin protects.

## Do not regress

The native surface this project carries is not the default one, and the fingerprint
covers all of it: the local Expo module `mobile/modules/google-credential-manager`
(Android Google sign-in, `task-325`), the `mobile/ios-share-extension/` target, and the
`expo-share-intent` Android intent filters that `task-338` reshaped — including
`application/pdf` and `image/*`. Verify they all survive the config edit.
`appVersionSource: "remote"` with `autoIncrement` stays as is: a fingerprint
`runtimeVersion` is independent of the version string, which is exactly why the two can
coexist.

## Owner notes — not acceptance criteria

- **Installing `expo-updates` is itself a native change.** The fingerprint moves, so
  the first run after this lands produces one build per platform — that is expected,
  not a bug in the decision logic. And every binary installed *before* it has no
  updates runtime: the TestFlight install and the Play internal-track install will
  never receive an OTA and have to be replaced once. This is the reason the sequencing
  decision of 2026-09-02 puts this task **before** the Play closed testing recruitment
  (`task-260`, étape 4): the 12 testers should install an OTA-capable binary on day one
  and never reinstall, rather than be asked to reinstall mid-clock.
- **Confirm the environment mapping once, by hand**: `eas env:list` for the environment
  chosen in step 4, and check it holds the same `EXPO_PUBLIC_*` keys as the `internal`
  profile of `eas.json`. An empty environment ships a working-looking update that
  cannot reach the API.
- The first automated run is worth watching end to end: which branch it took, and
  whether the update actually appears on a device.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 expo-updates is in mobile/package.json dependencies at the version npx expo install resolves for SDK 55, and npx expo install --check reports no version mismatch for it
- [x] #2 mobile/app.config.ts declares updates.url derived from the same projectId constant used by extra.eas.projectId (the UUID appears once in the file) and runtimeVersion policy fingerprint; npx expo config --type introspect shows both
- [x] #3 mobile/eas.json gives internal the channel internal, production the channel production, and preview its own channel; no two build profiles share a channel, and the choice made for the two dev-client profiles is stated in a comment or in MOBILE_CI_CD.md
- [x] #4 A workflow triggers on push to main with paths covering mobile/** while excluding markdown files and mobile/.maestro/**, and declares a concurrency group
- [x] #5 That workflow computes the fingerprint per platform with eas fingerprint:generate --json --non-interactive --platform <p> -e internal, queries eas build:list with --fingerprint-hash --status finished --limit 1 --json --non-interactive, and branches to eas build --profile internal --auto-submit --non-interactive on an empty result or to eas update --channel internal otherwise
- [x] #6 Every eas update invocation in the repository passes --environment; git grep for eas update returns no invocation without it
- [x] #7 No workflow installs the EAS CLI unpinned; each install pins an explicit version and carries a comment naming the flags the pin protects
- [x] #8 eas fingerprint:generate is run from the worktree for both platforms after the change and the two hashes are pasted into the Implementation Notes next to the pre-change Android hash cdde50c777525d5ff172cfbb2ad9f95bd40b40d0, showing the fingerprint moved
- [x] #9 npx expo config --type introspect still lists the expo-share-intent Android intent filters including application/pdf and image/*, and npx expo-modules-autolinking search -p android still resolves google-credential-manager
- [x] #10 npx tsc --noEmit and npm run lint are clean in mobile/
- [x] #11 mobile/MOBILE_CI_CD.md documents the profile-to-channel map, the fingerprint decision rule with the exact commands and the eas-cli version they were verified against, the --environment requirement on SDK 55 and which EAS environment feeds an OTA bundle, the three rollback commands, the free-tier build and MAU limits, and the one-time reinstall for binaries installed before this change
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### The fingerprint moved, measured

`eas fingerprint:generate --json --non-interactive --platform <p> -e internal`, run from
this worktree. The pre-change Android hash in the description was measured at `de6c91b`,
before `expo-updates`:

| Platform | Before `expo-updates` | After |
|---|---|---|
| Android | `cdde50c777525d5ff172cfbb2ad9f95bd40b40d0` | `e53f6e78308ff4aa250fdc1eefa2675bb5329e92` |
| iOS | not measured before the change | `045400802019f4b94fee1bcf46b2963445b94d7c` |

That movement is the reason the **first** automated run produces one build per platform
instead of an OTA update — expected, and the strongest available proof the decision rule
reads the native surface rather than a heuristic. The command needs no Expo login.

### What was changed

- `mobile/app.config.ts` — `const easProjectId` declared once at module scope, feeding
  both `updates.url` (`https://u.expo.dev/${easProjectId}`) and `extra.eas.projectId`;
  `runtimeVersion: { policy: "fingerprint" }`. `npx expo config --type introspect`
  confirms the plugin lands the native keys on both platforms: `EXUpdatesURL`,
  `EXUpdatesRuntimeVersion`, `EXUpdatesEnabled`, and
  `expo.modules.updates.EXPO_UPDATE_URL` / `EXPO_RUNTIME_VERSION` / `ENABLED`.
- `mobile/eas.json` — `channel` and `environment` added to the build profiles:
  `preview` → `preview`/`preview`, `internal` → `internal`/`production`, `production` →
  `production`/`production`. `development` gets `"environment": "development"` and
  **deliberately no channel**; `development-simulator` extends it and inherits that
  absence. Rationale in MOBILE_CI_CD.md: a dev-client binary is a debug build loading
  from Metro, `expo-updates` is disabled in debug, and giving the pair a channel would
  either break the one-profile-per-channel rule through inheritance or hand them a
  channel nothing publishes to.
- `.github/workflows/mobile-ota-or-build.yml` — new. Push to `main` on `mobile/**` minus
  `**/*.md` and `mobile/.maestro/**`, `concurrency` group, matrix over both platforms
  with `fail-fast: false`. Steps: EXPO_TOKEN gate → `npm ci` → pinned CLI →
  `scripts/mobile_release_check.sh internal` (task-339's DNS guard, reused) → load env →
  fingerprint → `build:list --fingerprint-hash` → `eas update` or
  `eas build --auto-submit --no-wait`.
- `.github/workflows/mobile-build-distribute.yml`, `.github/workflows/mobile-store-promote.yml`
  — `EAS_CLI_VERSION: "22.0.0"`, five install sites in total now pinned across three
  workflows. `mobile-e2e-maestro.yml` installs no eas-cli, so nothing to pin there.
- `mobile/MOBILE_CI_CD.md` — new "Shipping JS Over The Air" section (AC #11), channel and
  environment columns on the profiles table, rewritten "Workflow Triggers".
- `docs/DEVBOX_SETUP.md` — the `eas-cli` prerequisite row now says 22.0.0 exactly, to
  match the CI pin.

### The env-var precedence trap, resolved by reading the CLI

The task flagged that `EXPO_PUBLIC_*` values are inlined at bundle time and that this
repo declares them in per-profile `env` blocks of `eas.json`, which feeds a *build* — so
an `eas update` could inline empty values with no error anywhere. Read out of eas-cli
22.0.0's own source, the two paths merge in **opposite** order:

| Path | Merge | Winner |
|---|---|---|
| `eas build` | `build/evaluateConfigWithEnvVarsAsync.js`: `{ ...serverEnvVars, ...buildProfile.env }` | `eas.json` |
| `eas update` | `utils/expoCli.js` `spawnExpoCommand`: `{ ...process.env, ...serverEnvVars }` | EAS environment |

So the resolution is not "put the values in the EAS environment" but "make sure no
`EXPO_PUBLIC_*` key is defined on both sides". Today none is: the API base URL and the
two Google client IDs live only in `eas.json`; the RevenueCat keys only in the EAS
environments. The workflow therefore copies `.build.internal.env` out of `eas.json` into
`$GITHUB_ENV` with `jq` before publishing — one source of truth, no owner action — and
then **greps the published bytes** in `mobile/dist/` for the expected API base URL,
turning a silent failure into a red job that prints the rollback command. `grep -a`
because Hermes bytecode is binary.

`--environment production` for the OTA path: eas-cli's
`resolveSuggestedEnvironmentForBuildProfileConfiguration` maps `distribution: "store"`
(the schema default, which `internal` takes) to `production`, so this matches what a
build of the same profile already resolves. The residual check —
that the EAS `production` environment does not itself define one of those three keys —
needs authentication and stays an owner step.

### Not regressed

`npx expo config --type introspect` still lists the `expo-share-intent` intent filters
with `application/pdf`, `image/*`, `audio/*`, `text/*` and the three Office MIME types;
`npx expo-modules-autolinking search -p android` still resolves
`google-credential-manager` (and now `expo-updates`); `mobile/ios-share-extension/` is
untouched; no diff line adds or removes the bundle ID `com.secondbrainlabs.core`.
`appVersionSource: "remote"` + `autoIncrement` left as is — a fingerprint
`runtimeVersion` is independent of the version string.

### Checks

`npx tsc --noEmit` exit 0. `npm run lint` 0 errors (2 pre-existing warnings in
`app/(tabs)/digest.tsx` and `src/services/purchaseService.ts`, files not touched here).
`cat mobile/eas.json | jq .` parses. All eight workflow YAMLs load. `bash
scripts/mobile_release_check.sh internal` passes. `npx expo install --check` does not
flag `expo-updates` (it reports 18 unrelated pre-existing mismatches; bumping
`expo`/`react-native` would move the fingerprint massively and is out of scope).

### Owner-dependent, by construction

- `eas env:list production` — confirm it defines none of `EXPO_PUBLIC_API_BASE_URL`,
  `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`, `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB`. Needs auth.
- The first `mobile-ota-or-build.yml` run, which only exists after this lands on `main`.
- Replacing the pre-OTA installs once: TestFlight `1.0.0 (2)` and Play internal-track
  `1.0.0 (5)` have no updates runtime and will never receive an OTA. Do this before the
  task-260 closed-testing recruitment.
- No automated test was added, per the project rule.
<!-- SECTION:NOTES:END -->

