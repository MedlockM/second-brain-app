---
id: task-339
title: >-
  Fail a production mobile build before it starts while the production API domain
  does not resolve
status: To Do
assignee: []
created_date: '2026-09-03 10:14'
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
- [ ] #1 scripts/mobile_release_check.sh accepts an optional build-profile argument and, when given, exits non-zero if the host of that profile's EXPO_PUBLIC_API_BASE_URL in mobile/eas.json resolves to no address
- [ ] #2 The host is read out of mobile/eas.json at runtime; git grep finds no literal api.mediasummarizer.com in scripts/mobile_release_check.sh
- [ ] #3 Resolution uses getent hosts (or another glibc-only mechanism), not dig or nslookup
- [ ] #4 bash scripts/mobile_release_check.sh production exits non-zero and names the unresolvable host; bash scripts/mobile_release_check.sh internal exits 0; both runs are pasted into the Implementation Notes
- [ ] #5 bash scripts/mobile_release_check.sh with no argument keeps its pre-existing exit status and reports the production host as a warning rather than a failure
- [ ] #6 Both ios-build and android-build in .github/workflows/mobile-build-distribute.yml invoke the pre-flight with the resolved profile, in a step placed after Resolve build profile and submit flag and before the eas build step
- [ ] #7 production.env.EXPO_PUBLIC_API_BASE_URL in mobile/eas.json and the extra.apiBaseUrl fallback in mobile/app.config.ts are both unchanged
- [ ] #8 mobile/MOBILE_CI_CD.md states that a mobile-v* tag push is blocked, why, and the two conditions that unblock it; no remaining line in that file presents the production profile as usable without the caveat
<!-- AC:END -->
