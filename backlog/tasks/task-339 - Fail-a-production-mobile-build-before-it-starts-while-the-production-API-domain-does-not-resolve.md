---
id: task-339
title: >-
  Fail a production mobile build before it starts while the production API
  domain does not resolve
status: Done
assignee: []
created_date: '2026-09-03 10:14'
updated_date: '2026-09-03 08:36'
labels:
  - mobile
  - release
  - ci
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`mobile/eas.json` line 61 sets `production.env.EXPO_PUBLIC_API_BASE_URL` to
`https://api.mediasummarizer.com`. That host does not exist.

Measured 2026-09-03:

- `dig +short api.mediasummarizer.com A` → empty.
- `dig +short mediasummarizer.com NS` → **empty**.

The second measurement is the load-bearing one: this is not a missing record inside a
zone somebody forgot to fill, there is **no delegated zone at all** for the apex. The
four other build profiles (`development`, `development-simulator`, `preview`,
`internal`) all point at `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`,
which resolves and is the only live API this project has.

## Why this is a trap rather than a stale value

`EXPO_PUBLIC_*` variables are **inlined into the JS bundle at build time** by Expo's
babel transform. A wrong value is therefore baked into the binary with no runtime
signal at all: the build succeeds, the submit succeeds, the store accepts the
artifact, and every network call in the installed app fails on DNS. This is the exact
failure that made AAB `versionCode` 4 unusable.

And it is reachable by one command. In
`.github/workflows/mobile-build-distribute.yml`, the step *Resolve build profile and
submit flag* has two branches, and the non-`workflow_dispatch` one — a push of a
`mobile-v*` tag — sets `PROFILE="production"` **and** `SUBMIT="true"`. So a single tag
push today builds two inert binaries and submits them to TestFlight and to the Play
`internal` track in the same run. Nothing in the workflow looks at whether the URL it
is about to inline resolves.

Note the scope of the claim: `production` is not merely mis-configured, it is
*unusable by construction* — there is no prod API either (AWS `prod` is a dormant
shell that has never served traffic). So the fix is a guard, not a new value. Do not
repoint `production` at the dev `execute-api` host: that would silently redefine
"production" as "the dev backend", which is worse than failing.

## Scope

1. **Put the check where the project already keeps its pre-flight checks.**
   `scripts/mobile_release_check.sh` opens with "Run this before any `eas build`
   invocation to catch config issues early" and already requires `jq`. Add a DNS
   resolution check there:
   - The script takes an **optional build-profile argument**. When given, it reads
     that profile's `EXPO_PUBLIC_API_BASE_URL` out of `mobile/eas.json`, extracts the
     host, and **hard-fails** if the host resolves to no address.
   - With no argument, the existing behaviour is preserved: report a non-resolving
     host as a `warn`, do not change the exit status. That keeps a plain
     `bash scripts/mobile_release_check.sh` usable as a general pre-flight.
   - Read the host from `eas.json`. Do not hardcode `api.mediasummarizer.com`: the
     guard must stop guarding on its own the day the value changes.
   - **Resolve with `getent hosts`, not `dig`.** Both build jobs run on
     `ubuntu-latest`, where `dnsutils` is not something to rely on; `getent` is glibc
     and always present. `getent hosts <host>` covers A and AAAA and uses the system
     resolver.

2. **Wire it into the workflow.** In both `ios-build` and `android-build` of
   `.github/workflows/mobile-build-distribute.yml`, run the pre-flight with
   `${{ steps.plan.outputs.profile }}` in a step placed **after** *Resolve build
   profile and submit flag* and **before** *Run EAS Build for …*. Failing there costs
   nothing; failing after `eas build` burns one of the 15 monthly builds of the free
   tier and, worse, may still submit.

3. **Document it in `mobile/MOBILE_CI_CD.md`**: pushing a `mobile-v*` tag is blocked
   today, the reason (the inlined URL has no DNS, and there is no prod API behind it
   anyway), and the two conditions that unblock it — the domain registered and
   delegated, and a prod API actually serving. Correct any line that presents the
   `production` profile or the `mobile-v*` tag as a usable release path without that
   caveat.

## Owner notes — not acceptance criteria

- Registering `mediasummarizer.com` and delegating it is owner work and is **not** in
  this task. This task only makes the failure loud and early.
- Nothing here needs a deploy, an EAS build or a device.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 scripts/mobile_release_check.sh accepts an optional build-profile argument and, when given, exits non-zero if the host of that profile's EXPO_PUBLIC_API_BASE_URL in mobile/eas.json resolves to no address
- [x] #2 The host is read out of mobile/eas.json at runtime; git grep finds no literal api.mediasummarizer.com in scripts/mobile_release_check.sh
- [x] #3 Resolution uses getent hosts (or another glibc-only mechanism), not dig or nslookup
- [x] #4 bash scripts/mobile_release_check.sh production exits non-zero and names the unresolvable host; bash scripts/mobile_release_check.sh internal exits 0; both runs are pasted into the Implementation Notes
- [x] #5 bash scripts/mobile_release_check.sh with no argument keeps its pre-existing exit status and reports the production host as a warning rather than a failure
- [x] #6 Both ios-build and android-build in .github/workflows/mobile-build-distribute.yml invoke the pre-flight with the resolved profile, in a step placed after Resolve build profile and submit flag and before the eas build step
- [x] #7 production.env.EXPO_PUBLIC_API_BASE_URL in mobile/eas.json and the extra.apiBaseUrl fallback in mobile/app.config.ts are both unchanged
- [x] #8 mobile/MOBILE_CI_CD.md states that a mobile-v* tag push is blocked, why, and the two conditions that unblock it; no remaining line in that file presents the production profile as usable without the caveat
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### What was built

`scripts/mobile_release_check.sh` grew a sixth check and an optional argument:

- `bash scripts/mobile_release_check.sh [<build-profile>]`, plus `-h/--help`
  (exit 0) and exit 2 on a bad flag or a second argument.
- The profile's `EXPO_PUBLIC_API_BASE_URL` is read from `mobile/eas.json` with a
  recursive `jq` function that follows `extends`, so `development-simulator`
  resolves through `development` instead of looking like a profile with no URL.
  Nothing is hardcoded — `grep -n mediasummarizer scripts/mobile_release_check.sh`
  returns nothing (AC#2).
- Host extraction is pure bash parameter expansion (scheme, path, userinfo, port
  stripped). Resolution is `getent hosts` only — glibc, present on
  `ubuntu-latest`, covers A and AAAA — with 3 attempts 2 s apart in gate mode so a
  transient resolver hiccup does not fail a release (AC#3).
- **Profile mode** hard-fails on: unknown profile, profile with no
  `EXPO_PUBLIC_API_BASE_URL` (it would fall back to the `app.config.ts` default),
  and a host that resolves to no address (AC#1).
- **No-argument mode** iterates every build profile, de-duplicates by URL and
  emits a `warn` per non-resolving host without touching `ERRORS` (AC#5).

One adjustment was required to make both AC#4 and AC#5 hold at once: the existing
`mobile/.env` check hard-fails when the file is absent, which is the state of this
worktree *and* of any CI runner (`mobile/.env` is gitignored). It is now a `warn`
**in profile mode only** — that mode is the cloud-build form, where the
environment comes from the profile's `env` block in `eas.json` plus the EAS env
vars, never from a local dotenv. The no-argument mode still hard-fails on it, so
its exit status is unchanged (1 here). Without this, the new CI step would have
failed every `preview`/`internal` build for a missing file that CI is not supposed
to have.

### AC#4 — command outputs

ANSI colour codes stripped; text otherwise verbatim.

```
$ bash scripts/mobile_release_check.sh production; echo "EXIT=$?"
=== Mobile Release Pre-flight Check ===
Target build profile: production (API host DNS is a hard gate)

[PASS] mobile/eas.json is valid JSON
[PASS] mobile/app.config.ts exists
[WARN] mobile/.env not found — skipped: profile 'production' takes its env from eas.json and the EAS env vars
[PASS] Bundle ID 'com.secondbrainlabs.core' present in all config files
  Expo SDK version: ^55
[PASS] Expo SDK is on expected major version (55)
[FAIL] API host 'api.mediasummarizer.com' of profile 'production' resolves to no address
       EXPO_PUBLIC_API_BASE_URL=https://api.mediasummarizer.com (mobile/eas.json)
       That value is inlined into the JS bundle: the build would succeed, the
       submission would succeed, and every network call of the installed app
       would fail on DNS. Refusing to build.

1 check(s) failed. Fix the issues above before running eas build.
EXIT=1
```

```
$ bash scripts/mobile_release_check.sh internal; echo "EXIT=$?"
=== Mobile Release Pre-flight Check ===
Target build profile: internal (API host DNS is a hard gate)

[PASS] mobile/eas.json is valid JSON
[PASS] mobile/app.config.ts exists
[WARN] mobile/.env not found — skipped: profile 'internal' takes its env from eas.json and the EAS env vars
[PASS] Bundle ID 'com.secondbrainlabs.core' present in all config files
  Expo SDK version: ^55
[PASS] Expo SDK is on expected major version (55)
[PASS] API host 'jji077bi8e.execute-api.eu-west-3.amazonaws.com' of profile 'internal' resolves (https://jji077bi8e.execute-api.eu-west-3.amazonaws.com)

All checks passed.
EXIT=0
```

### AC#5 — no-argument run, exit status unchanged

Before this task the bare run exited **1** (`mobile/.env` absent). It still does,
and the production host is a `warn`:

```
$ bash scripts/mobile_release_check.sh; echo "EXIT=$?"
=== Mobile Release Pre-flight Check ===
No build profile given: DNS problems are reported, not gated.

[PASS] mobile/eas.json is valid JSON
[PASS] mobile/app.config.ts exists
[FAIL] mobile/.env not found — copy from .env.example and fill in values
[PASS] Bundle ID 'com.secondbrainlabs.core' present in all config files
  Expo SDK version: ^55
[PASS] Expo SDK is on expected major version (55)
[WARN] API host 'api.mediasummarizer.com' resolves to no address — used by profile(s): production
       Run this script with that profile name to gate a build on it.

1 check(s) failed. Fix the issues above before running eas build.
EXIT=1
```

Other runs checked: `development-simulator` → exit 0, host resolved through
`extends`; `nope` → exit 1, *"Build profile 'nope' is not defined in
mobile/eas.json (known: development, development-simulator, internal, preview,
production)"*; `-x` → exit 2 + usage; two arguments → exit 2; `--help` → exit 0.

### AC#6 — workflow wiring

Step order verified by parsing the YAML with `yaml.safe_load`; identical in both
jobs:

```
Resolve build profile and submit flag
Pre-flight check for profile ${{ steps.plan.outputs.profile }}
Run EAS Build for iOS | Run EAS Build for Android
```

The step is `bash scripts/mobile_release_check.sh "${{ steps.plan.outputs.profile }}"`
at the repo root (checkout already happened; `jq` is preinstalled on
`ubuntu-latest` and the workflow already relied on it).

### AC#7

`mobile/eas.json` and `mobile/app.config.ts` are absent from `git status`. The
guard reads the broken value, it does not repair it: repointing `production` at
the dev `execute-api` host would redefine "production" as "the dev backend".

### Docs

- `mobile/MOBILE_CI_CD.md`: new section *Why a `mobile-v*` tag push is blocked
  today* (no DNS, no delegated zone, no prod API, why inlining makes it silent,
  the guard, the two unblock conditions). Corrected: the overview diagram and
  intro, the Build Profiles table row for `production`, the reviewer-test-account
  paragraph, the Workflow Triggers table, the Manual Trigger Options table. Added
  a warning that the `production` **submit** profile is unrelated to the
  `production` **build** profile (the former is in daily use), plus a
  troubleshooting entry for the new failure message. Also refreshed the stale
  "GitHub Actions … is not a working path: the Apple and Expo secrets are
  missing" line, which contradicted the `EXPO_TOKEN` section two paragraphs below.
- `docs/PRODUCTION_RELEASE_RUNBOOK.md`: one admonition at the top of *Release
  Overview*. Every step of that runbook builds `production`, so leaving it silent
  would have contradicted the new guard. It points at `MOBILE_CI_CD.md` rather
  than duplicating the reasoning.

### Not done

No automated tests, per the project rule. Nothing here needs a deploy, an EAS
build or a device — the guard was exercised directly against real DNS, which is
what it does in CI.
<!-- SECTION:NOTES:END -->
