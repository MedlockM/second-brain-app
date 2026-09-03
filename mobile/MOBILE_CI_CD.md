# Mobile CI/CD: Build, Sign & Distribute

This document describes the mobile build and distribution pipeline for Media Summarizer.

## Overview

The pipeline uses **EAS Build** (Expo Application Services) for cloud-based native builds,
**EAS Submit** for publishing to TestFlight (iOS) and Google Play Internal Testing (Android),
and **EAS Update** to push JS-only changes to already-installed binaries without a build.

Two workflows, two jobs. They do not overlap.

```
Push to main touching mobile/    Push of a mobile-v* tag      Manual workflow_dispatch
    |                                |                            |
    v                                | profile=production         | profile + submit chosen
mobile-ota-or-build.yml              | submit=true                | (defaults: preview, false)
    |                                v                            v
    +-- per platform:            GitHub Actions (.github/workflows/mobile-build-distribute.yml)
    |   fingerprint moved?           |
    |     no  -> eas update          +-- Pre-flight: scripts/mobile_release_check.sh <profile>
    |            (channel internal)  |     `-- BLOCKS the production profile today (no DNS)
    |     yes -> eas build           |
    |            --profile internal  +-- iOS: EAS Build -> EAS Submit -> TestFlight (internal)
    |            --auto-submit       |
    |                                +-- Android: EAS Build -> EAS Submit -> Play (internal)
    |                                |
    |                                +-- On failure: Slack + GitHub Issue (tag runs only)
```

A push to `main` no longer *always* spends a build, and no longer *never* ships either:
`mobile-ota-or-build.yml` decides per platform from the native fingerprint. Read
[Shipping JS Over The Air](#shipping-js-over-the-air) for the decision rule and
[Workflow Triggers](#workflow-triggers) for the full contract.

**Pushing a `mobile-v*` tag fails on purpose today**, in seconds, before any EAS
build starts: it selects the `production` profile and that profile is unusable.
Read [Why a `mobile-v*` tag push is blocked today](#why-a-mobile-v-tag-push-is-blocked-today)
before reaching for it. The usable route to testers is
`workflow_dispatch` with `profile=internal`, or the two commands in
[Running Builds From Your Machine](#running-builds-from-your-machine).

GitHub Actions is not the only path either. `EXPO_TOKEN` was provisioned on
2026-09-02 so the workflow is no longer blocked on secrets (see
[Required Secrets & Variables](#required-secrets--variables)), but it has never
been exercised end to end through Actions. The same two commands run from a
laptop, Linux included — that is the route documented in
[Running Builds From Your Machine](#running-builds-from-your-machine).

## Required Secrets & Variables

Configure these in GitHub repository Settings > Secrets and variables > Actions:

### Secrets (required)

**`EXPO_TOKEN` is the only one, and it was provisioned on 2026-09-02** at
`17:13:47Z` — verified with `gh secret list`, which now returns seven secrets.
The last blocker on this workflow is therefore lifted for `eas build`. It has not
been exercised through Actions yet: every `Mobile Build & Distribute` run on
record is a `failure` from 2026-08-13 or earlier, all of them push-triggered
under the old trigger contract and all of them dead on authentication.

| Secret | Description | Status |
|--------|-------------|--------|
| `EXPO_TOKEN` | Expo access token for EAS CLI authentication. Both build jobs assert it in their first step | **Set 2026-09-02.** Rotation procedure in [Owner prerequisite](#owner-prerequisite-expo_token) |

Four secrets that used to be listed here are gone, none of them replaced:

- `GOOGLE_PLAY_SERVICE_ACCOUNT_KEY` — the Play key was uploaded to the EAS servers
  on 2026-09-01 (see
  [Google Play Service Account Key](#google-play-service-account-key)), so nothing
  needs to hold its JSON any more.
- `APPLE_ID`, `ASC_APP_ID`, `APPLE_TEAM_ID` — they never worked. See
  [Submit Profiles](#submit-profiles): `eas.json` referenced them as `${APPLE_ID}`
  and friends, and a submit profile does not interpolate those three fields. Apple
  authentication comes from the App Store Connect API key held by EAS.

### Variables (optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `SLACK_WEBHOOK_URL` | Slack incoming webhook for failure notifications | (none - Slack alerts disabled if unset) |

## Initial Setup

### 1. Expo / EAS Setup

```bash
cd mobile

# Install EAS CLI — pinned, same version the workflows pin (see
# "Pinning the EAS CLI" below). A bare `npm install -g eas-cli` puts your laptop
# on a different major from CI, which is how flag drift goes unnoticed.
npm install -g eas-cli@22.0.0

# Log in to Expo
eas login

# Link the project (first time only)
eas init --id <your-expo-project-id>

# Configure credentials (interactive - follow prompts)
eas credentials
```

### 2. iOS Signing (Apple)

EAS manages iOS signing via its credentials service, storing everything on Expo's
servers — nothing signing-related belongs in this repo. On a first build of a given
distribution type it logs into your Apple account interactively and provisions what
is missing; the Apple session is then cached under
`~/.app-store/auth/<apple-id>/cookie`, so later builds do not re-prompt.

**One certificate, two provisioning profiles.** The scheme builds two targets and
they are not interchangeable:

| Target | Bundle identifier |
|---|---|
| `MediaSummarizer` | `com.secondbrainlabs.core` |
| `ShareMedia` | `com.secondbrainlabs.core.share-extension` |

Both share a single **Distribution Certificate** (valid to 2027-06-10), but each
needs **its own Provisioning Profile**, and a profile is specific to a distribution
type as well as to a target. So the ad hoc profiles behind the `development` and
`preview` builds could not serve a store submission: the first `internal` build —
run on 2026-09-01, the first store-distribution build this project has ever done —
had to generate two **App Store** profiles, one per target. Both now exist and are
`active`, expiring 2027-06-10 alongside the certificate. That build produced
`1.0.0 (2)`, the first App Store-signed ipa of this project.

If a future run asks again, answer `Y` to *Generate a new Apple Provisioning
Profile?* and **yes** to *Reuse this distribution certificate?*. Apple allows only
two distribution certificates per account; generating a second one would burn a slot
for nothing, since the existing one already covers both targets and both
distribution types.

**An App Store-signed ipa cannot be sideloaded.** `eas build` prints an artifact URL
at the end, and for `development`/`preview` (ad hoc) that URL does install on an
allow-listed device. For `internal`/`production` it does not: the binary is signed
for store distribution and only Apple can install it, through TestFlight. The
artifact URL is input to `eas submit`, not a link for a tester.

To inspect or replace any of it:
```bash
eas credentials --platform ios
```
Note the profile it asks for at startup only decides which bundle identifier to
resolve — see the App Store Connect API key caveat in section 4.

### 3. Android Signing (Google Play)

#### Keystore (managed by EAS)
EAS generates and manages the upload keystore automatically. To use your own:
```bash
eas credentials --platform android
# Choose "Manage credentials" > "Set up manually" > upload your .jks
```

#### Google Play Service Account Key

**Done on 2026-09-01: the key lives on the EAS servers.** A service account
dedicated to publishing was created in the `media-summarizer` Google Cloud project,
its JSON key uploaded through `eas credentials --platform android` >
*Google Service Account* > *Manage your Google Service Account Key for Play Store
Submissions* > *Set up a ...*, and the local file shredded. `eas credentials` now
reports the key as assigned to `com.secondbrainlabs.core` for submissions. Its
email and key id are deliberately not recorded here (public repo) — read them back
from the EAS dashboard or the Cloud Console.

Two consequences, both already applied:

- The three `submit` profiles in `eas.json` carry **no** `serviceAccountKeyPath`.
  A path there takes precedence over the stored key, so re-adding one would send
  `eas submit` looking for a local file that no longer exists.
- The workflow no longer writes a key file, and `GOOGLE_PLAY_SERVICE_ACCOUNT_KEY`
  is no longer a required secret.

To redo it from scratch, the steps that actually exist in the current consoles:

1. Google Cloud Console > **IAM & Admin** > **Service Accounts** > **Create service
   account**. Leave step 2 (*Grant this service account access to the project*) and
   step 3 empty — publishing needs **no IAM role**. The two roles the RevenueCat
   service account holds (Pub/Sub Editor, Monitoring Viewer) are for Pub/Sub
   notifications and have nothing to do with submitting.
2. On the account row: **⋮** > **Manage keys** > **Add key** > **Create new key** >
   **JSON**.
3. The **Google Play Android Developer API** must be enabled on the project. It
   already is — RevenueCat's catalogue checks pass against it (`task-238`).
4. Play Console > **Users and permissions** > **Invite new users**, paste the
   account email, and grant: *View app information (read-only)*, *Edit and delete
   draft apps*, *Release to production, exclude devices, and use Play App Signing*,
   *Release apps to testing tracks*, *Manage testing tracks and edit tester lists*,
   *Manage store presence*. Not *Admin*, not the financial permissions.
5. Upload it with `eas credentials`, then delete the local file.

**A freshly invited account can publish immediately.** `task-238` records a 24-to-36
hour credential propagation window and concludes that `eas submit` is unusable until
it closes; that is wrong for the publishing permissions. On 2026-09-01 the account
was invited and `eas submit --profile internal` pushed `versionCode` 6 to the
internal track minutes later, first try. Do not plan around a waiting period — try
the submit.

Use a **dedicated** account rather than the RevenueCat one: Play permissions attach
to the account, not to the key, so widening them would hand RevenueCat's existing
key the right to publish and to use Play App Signing.

### 4. App Store Connect Setup

**State as of 2026-09-02.** The Apple Developer Program is paid and validated
(2026-06-01). An **App Store Connect API key with the Admin role** was created by
hand that day, its `.p8` parked at
`~/.appstoreconnect/private_keys/AuthKey_<KeyID>.p8`, and it is **registered with
EAS**: the `second-brain-labs` Expo account holds exactly one ASC API key and it is
bound as the submission key of the `com.secondbrainlabs.core` iOS app credentials
(2026-09-01 17:43 UTC). It is **also uploaded to RevenueCat** since 2026-09-02, which
is a separate act on the same key — see the table below.

**iOS shipped to TestFlight on 2026-09-02.** The `internal` build `1.0.0 (2)` was
submitted and Apple accepted it: the App Store Connect API reports one build on the
app record, `version: 2`, `processingState: VALID`, `expired: false`, uploaded
2026-09-02T03:01:44-07:00 — and a beta tester has installed and used it. The five
builds preceding 2026-09-01 were all on the `development` profile (dev client, ad
hoc, EAS expires those after 14 days), including the one that lapsed on 2026-06-25.
Android reached its own internal track the day before (`1.0.0 (5)`, 2026-09-01).
Nothing is published: the single `appStoreVersions` entry, `1.0`, sits in
`PREPARE_FOR_SUBMISSION`.

The share-extension bundle (`com.secondbrainlabs.core.share-extension`) has its own
iOS credentials entry and carries **no** submission key. That is correct, not a
gap: a submission key is attached to the app being uploaded, and an app extension
ships inside its container app.

**Three** `.p8` files exist around this project and none is interchangeable with
another:

| File | What it is | Consumed by |
|------|-----------|-------------|
| `AuthKey_97D94A5ZKM.p8` | *Sign in with Apple* key | `APPLE_PRIVATE_KEY` / `APPLE_KEY_ID` in `.env`, auth backend |
| `AuthKey_F5622R22D5.p8` | *App Store Connect API* key (Admin) | EAS Submit, and RevenueCat iOS since 2026-09-02 |
| `SubscriptionKey_*.p8` | *In-App Purchase* key (Apple's naming for it) | RevenueCat: `subscription_key_configured: true` (2026-09-02) |

All three are covered by the `*.p8` rule, present in `.gitignore` at the repo root
and in `mobile/.gitignore`. Only the ASC API key works for `eas submit`; picking
either of the other two fails.

**Do not read RevenueCat's two iOS key flags as one.** Both are `true` on
`app0d4b00c12f` since 2026-09-02, but they answer different questions and only one of
them can ever break a purchase. The In-App Purchase key validates StoreKit
transactions (`subscription_key_configured`); the App Store Connect API key merely
lets RevenueCat *read* the catalogue out of App Store Connect, and its absence showed
as `Could not check` on the dashboard (`app_store_connect_api_key_configured`).
Neither is what made iOS purchases impossible before that date — the missing App
Store subscriptions were, because StoreKit then resolves no product at all. Full
disposition and the flags to read back: `docs/REVENUECAT_ENTITLEMENTS.md`.

> **The `.p8` downloads once.** Apple keeps no copy. If it was not saved at
> creation time the key is dead weight: revoke it and generate another. The **Key
> ID** and the **Issuer ID** are also needed and are not recoverable from the
> file — both are readable from **App Store Connect → Users and Access →
> Integrations → App Store Connect API** (the issuer ID is shared by the whole
> team, the key ID sits on the key's row). Neither is written down here: the repo
> is public.

> **Answer `n` to "Generate a new App Store Connect API Key?"** when a key already
> exists. `Y` makes EAS mint a *second* key through Apple and keep it server-side —
> you never get that `.p8`, so it cannot be pasted into RevenueCat, and the
> hand-made key is left orphaned with an Admin role. One key, two consumers.
>
> **EAS then asks for less than you expect, and that is not a failure.** It derives
> the key ID from the file name — `AuthKey_<KeyID>.p8`, so keep Apple's name — and
> looks the issuer ID up in the authenticated App Store Connect session, printing
> `Detected Issuer ID: …` instead of prompting
> (`AscApiKeyUtils.promptForAscApiKeyPathAsync`). It only prompts for the issuer ID
> when that lookup comes back empty.

**The key is not scoped to a build profile.** `eas credentials` opens by asking
which profile to work under, but that only tells it which bundle identifier to
resolve — the key is then stored on the iOS app credentials, keyed by bundle
identifier. Answering `production` therefore binds it for `internal` too, and for
every other profile that builds `com.secondbrainlabs.core`. Verified 2026-09-01:
the account holds exactly one ASC API key and it comes back as
`appStoreConnectApiKeyForSubmissions` on the `com.secondbrainlabs.core` entry,
with no profile anywhere in the response.

`eas credentials` is interactive-only, so it cannot report the result in a script.
What the key is bound to reads back from the Expo API instead — `POST
https://api.expo.dev/graphql` with the `expo-session` secret from
`~/.expo/state.json`, header `User-Agent: eas-cli/<version>` (the API answers `403`
without one), querying `app.byId(appId: <extra.eas.projectId>)` for
`ownerAccount.appStoreConnectApiKeys` and
`iosAppCredentials.appStoreConnectApiKeyForSubmissions`.

**Nothing remains to configure here.** Two facts about this app record are still
worth keeping straight:

- **The app record already exists** — it was created in App Store Connect long before
  this runbook, so no `New App` dialog is involved. An app record existing and an app
  record having received a build are two different things: `eas build:list` proves the
  second had never happened before 2026-09-01, it says nothing about the first. Its
  Apple ID is **6778072060**, now in `eas.json` as `ascAppId` (see
  [Submit Profiles](#submit-profiles)); the app page is
  `https://appstoreconnect.apple.com/apps/6778072060/distribution/info`. Its
  store-facing name reads **`Second Brain Labs - Core`** (SKU `SBL-CORE`), not the
  legacy `Media Summarizer` that the app binary still carries — `task-186` is about
  the app itself, not this record. The name stays editable from that page for as long
  as the app is unpublished. Metadata to paste:
  `docs/store-listing/app-store-connect.md`.
- **The tester group is set up**, on Internal Testing rather than an external group,
  decided 2026-09-02 — including the App Store Connect seat each tester costs and the
  privileges that seat carries. Rationale and expiry condition:
  [Distributing a Build to Testers](#ios--testflight-with-a-public-link).

**Distribution and monetization both closed on 2026-09-02.** The three subscriptions
exist in App Store Connect under the group `Second Brain Plans`, the ASC API key is in
RevenueCat, StoreKit resolves the three products on the TestFlight build, and a real
sandbox purchase went through — `INITIAL_PURCHASE`, a `PRODUCT_CHANGE` exercising a
switch inside the subscription group, then a `RENEWAL`. That evidence is what closed
`task-261`. Disposition and the flags to read back:
`docs/REVENUECAT_ENTITLEMENTS.md`.

Two things that cost time getting there, worth keeping:

- **TestFlight never needed the catalogue.** `1.0.0 (2)` reached a beta tester while
  the app record still had zero `subscriptionGroups` and zero `inAppPurchasesV2`. A
  paywall with nothing to show is not a distribution blocker; the paywall is the only
  screen that needs a store product at all.
- **The order was not interchangeable, and it is the reverse of what this section once
  implied.** The subscriptions had to exist in App Store Connect *before* the ASC API
  key was of any use, since there was otherwise nothing for it to read. And
  **registering that key with EAS did not register it with RevenueCat** — the two are
  unrelated stores of the same key, which is why the `.p8` had to stay in hand rather
  than be minted by EAS.

Bring-your-own alternatives, if you would rather not let EAS hold the key:
`ascApiKeyPath` / `ascApiKeyId` / `ascApiKeyIssuerId` in the submit profile, or an
Apple ID with an app-specific password passed through
`EXPO_APPLE_APP_SPECIFIC_PASSWORD`.

#### App Review note: the app has no Restore Purchases button

Paste this into **App Store Connect → the version → App Review Information → Notes**
on any submission that goes to review, and into the equivalent Play Console review
notes:

> Purchases are tied to the user account. Signing in on any device restores the
> active subscription; there is no separate restore step.

Why it is worth a sentence to a reviewer: guideline **3.1.1** asks that you *"make
sure you have a restore mechanism for any restorable in-app purchases"* — a
mechanism, not a button. The binding one here is the account. The app logs the user
in to RevenueCat under the backend user id (`identifyUser()` in
`src/services/purchaseService.ts`), and entitlements are served by
`GET /api/entitlements/status` off the `subscriptions` table, so a reinstall or a
second device recovers the subscription by signing in. The hard requirement,
**3.1.2(a)** — *"Subscriptions must work on all of the user's devices"* — is
satisfied by the server, not by a button.

The button that used to sit on the paywall was deleted in `task-336`: no purchase can
be made anonymously (the paywall only opens for a signed-in user), so there was never
an orphan receipt to reattach, and it read its success/failure verdict from
RevenueCat while the paywall reads access from the backend — which let it announce
"Purchases restored" on a paywall that then stayed shut. If a reviewer ever pushes
back on its absence, re-adding one costs less than maintaining a dead control, so
this is not pre-empted any further.

### 5. Google Play Console Setup

1. Create the app in Google Play Console (package: `com.secondbrainlabs.core`)
2. Complete the app content declarations
3. Create an Internal Testing track
4. Add internal testers (email list or Google Group)

## No Metro Server Is Needed to Hand a Build to a Tester

Only the `development` profile needs `npx expo start` running on your machine:
`developmentClient: true` produces a shell that fetches the JS bundle from Metro
over the local network, which is why a tester using it has to be on the same
Wi-Fi as your PC. Every other profile builds a **Release** binary with the bundle
baked in — no server, no shared network, no cable.

For testers, use `internal`. Never `development`.

## Running Builds From Your Machine

`eas build` compiles **in the cloud** by default, so an iOS build needs no Mac.
`eas submit` also runs on macOS, Linux and Windows — which matters, because App
Store Connect only accepts an `.ipa` through Xcode or Transporter (macOS only).
`eas submit` is the Linux-friendly replacement for the drag-and-drop upload you
would do by hand in Play Console.

```bash
cd mobile

# Build in the cloud (no Mac required for iOS)
eas build --platform ios --profile internal
eas build --platform android --profile internal

# Then hand the artifact to the store
eas submit --platform ios --profile internal --latest
eas submit --platform android --profile internal --latest

# Or a specific build
eas submit --platform ios --profile internal --id <build-id>

# Build and submit in one shot
eas build --platform ios --profile internal --auto-submit
```

Add `--local` to `eas build` to compile on this machine instead — but a local iOS
build then does require macOS with Xcode.

The `submit` profiles need no Apple identifiers from you: the App Store Connect API
key registered with EAS (see
[App Store Connect Setup](#4-app-store-connect-setup)) authenticates the upload,
and an interactive run resolves the app record from the bundle identifier. There is
nothing to export — the three `${…}` placeholders that used to live there were
never substituted, see [Submit Profiles](#submit-profiles).

## Build Profiles

| Profile | Purpose | iOS output | Android output | Metro needed | Update channel | EAS environment |
|---------|---------|-----------|----------------|--------------|----------------|-----------------|
| `development` | Local dev with dev client | Dev-client IPA (ad hoc) | Dev-client APK | **Yes** | none | `development` |
| `development-simulator` | Same, iOS simulator | Simulator build | — | **Yes** | none (inherited) | `development` (inherited) |
| `preview` | Ad hoc share, no store round-trip | IPA (ad hoc, UDID-gated) | APK (shareable) | No | `preview` | `preview` |
| `internal` | Testers via TestFlight / Play internal track | IPA (App Store) | AAB | No | `internal` | `production` |
| `production` | **Unusable** — see below | IPA (App Store) | AAB | No | `production` | `production` |

`internal` and `production` differ only in `EXPO_PUBLIC_API_BASE_URL`: `internal`
points at the **dev** API, `production` at a host that does not exist. Every
build and every submission goes through `internal` today, testers included.

### Why a `mobile-v*` tag push is blocked today

`production` is not mis-configured, it is unusable by construction, and both of
its halves are missing:

- **The host has no DNS.** `EXPO_PUBLIC_API_BASE_URL` for `production` is
  `https://api.mediasummarizer.com`. Measured 2026-09-03: no A record, and — the
  load-bearing part — `dig +short mediasummarizer.com NS` is **empty**. There is no
  delegated zone at all for the apex, so this is not a record someone forgot to add
  inside an existing zone.
- **There is no production API behind it either.** AWS `prod` is a dormant shell
  that has never served traffic. Repointing the profile at the dev
  `execute-api` host is *not* the fix: it would silently redefine "production" as
  "the dev backend".

Why that combination is a trap rather than a stale value: `EXPO_PUBLIC_*`
variables are **inlined into the JS bundle at build time** by Expo's babel
transform. A wrong value produces no build error, no submission error and no
runtime signal — the store accepts the artifact and every network call of the
installed app fails on DNS. That is exactly what made AAB `versionCode` 4
unusable.

And it was one command away: a `mobile-v*` tag push resolves
`PROFILE="production"` **and** `SUBMIT="true"`, so a single tag built two inert
binaries and shipped them to TestFlight and the Play `internal` track in the same
run.

**The guard.** `scripts/mobile_release_check.sh` takes an optional build profile.
Given one, it reads that profile's `EXPO_PUBLIC_API_BASE_URL` out of `eas.json`,
extracts the host, resolves it with `getent hosts` (glibc — `dig` and `nslookup`
come from `dnsutils`, which `ubuntu-latest` does not guarantee) and exits
non-zero if the host has no address. Both `ios-build` and `android-build` run it
right after the profile is resolved and before `eas build`, so a tag push now
fails in seconds instead of spending two of the 15 monthly builds of the free
tier. The host is read from `eas.json` at run time and never hardcoded: the day
the value changes, the guard follows.

Run it by hand the same way:

```bash
bash scripts/mobile_release_check.sh production   # fails today
bash scripts/mobile_release_check.sh internal     # passes
bash scripts/mobile_release_check.sh              # general pre-flight, DNS as a warning
```

**Two conditions unblock the `mobile-v*` path**, both owner work and neither in
this repo:

1. `mediasummarizer.com` (or whichever domain is chosen instead) is **registered
   and delegated** — a zone answering `NS`, with `api.<domain>` resolving to the
   production API Gateway.
2. A **production API actually serves** on that host: the AWS `prod` environment
   deployed and answering, not the dormant shell it is today.

Until both hold, do not push a `mobile-v*` tag and do not select `production` in
a manual dispatch.

## Shipping JS Over The Air

`expo-updates` (`~55.0.30`, installed 2026-09-03 by `task-340`) lets a JS-only
change reach an installed binary without a build. Two fields in `app.config.ts`
carry the whole mechanism:

```ts
updates: { url: `https://u.expo.dev/${easProjectId}` },
runtimeVersion: { policy: "fingerprint" },
```

`updates.url` is where the app asks for a newer bundle. `runtimeVersion` is what
stops it from accepting one it cannot run. The `fingerprint` policy makes the
runtime version a **hash of the native project** — the autolinked native modules,
the local `modules/google-credential-manager` module, the share extension target
generated by `expo-share-intent`, its iOS activation rules and Android intent
filters, the plugin list, the resolved native config. An update is only ever
served to a binary whose fingerprint matches the one it was published under, so a
JS bundle calling into a native module the installed app does not have can never
reach it.

The project id is declared **once** in `app.config.ts`, as the `easProjectId`
constant read by both `updates.url` and `extra.eas.projectId`. Do not paste a
second copy of the UUID: a stale `updates.url` is silent, the app simply polls a
project that publishes nothing and never updates.

A fingerprint runtime version is independent of `version` and of the
`autoIncrement` build numbers, which is why it coexists with
`appVersionSource: "remote"` without interfering. Nothing about version management
changed.

### One channel per build profile

| Build profile | Channel |
|---|---|
| `development` | **none** |
| `development-simulator` | **none** (inherits `development`) |
| `preview` | `preview` |
| `internal` | `internal` |
| `production` | `production` |

**No two build profiles share a channel**, and the rule matters because the
failure it prevents is silent: publish to a channel a store binary listens on and
that JS is on testers' phones minutes later with nobody's approval. The push-to-
`main` automation therefore targets **`internal` only** — never `production`.

**The two dev-client profiles get no channel, deliberately.** They set
`developmentClient: true`, which produces a debug binary that fetches its bundle
from Metro over the local network; `expo-updates` is disabled in debug builds, so
a channel there would be a value nothing reads. Leaving it unset also keeps the
"no two profiles on one channel" rule true, which `development-simulator`
extending `development` would otherwise break by inheritance.

### The decision rule, and the exact commands

Every push to `main` that touches `mobile/` runs
`.github/workflows/mobile-ota-or-build.yml`. Per platform, three commands:

```bash
# 1. Hash the native project. Needs NO Expo login. `-e internal` matters:
#    EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS decides `ios.scheme` in app.config.ts, so
#    the iOS fingerprint depends on the profile's env block.
eas fingerprint:generate --json --non-interactive --platform <android|ios> -e internal

# 2. Does a finished `internal` build already run that native surface?
#    This one DOES need EXPO_TOKEN.
eas build:list --platform <p> -e internal --status finished \
  --fingerprint-hash <hash> --limit 1 --json --non-interactive

# 3a. Empty array -> the native surface moved -> spend a build.
eas build --platform <p> --profile internal --auto-submit --non-interactive --json --no-wait

# 3b. Non-empty -> JS-only change -> publish, cost nothing.
eas update --channel internal --platform <p> --environment production \
  --message "<commit subject>" --non-interactive
```

**Verified against eas-cli 22.0.0 on 2026-09-03**, by running `--help` on the
binary and by reading its source — not assumed. `--fingerprint-hash` is a real
filter flag on `build:list`; `-e` means `--build-profile` on `build:list` and
`fingerprint:generate` but `--profile` on `build`; `--auto-submit` schedules the
submission server-side the moment the build starts
(`build/runBuildAndSubmit.js`), which is why it survives `--no-wait` and the
submission still happens. That is also why the workflow does not wait: the Free
plan's low-priority queue served jobs after 3 h+ on 2026-09-02, and EAS keeps a
queued job for 30 days.

The trigger excludes `**/*.md` and `mobile/.maestro/**`. Without those
exclusions, editing this very file would publish an update whose bundle is
byte-identical to the previous one. The workflow also declares a `concurrency`
group so two pushes cannot race two publishes.

**Watch the first runs for one specific mismatch.** The hash the workflow
computes comes from the CLI on a GitHub runner; the hash recorded on a build is
computed by the EAS build server. If the two ever diverge, `build:list
--fingerprint-hash` returns empty forever and every push builds. That fails in the
safe direction — it spends quota, it does not ship a mismatched update — but it
defeats the point, so if two consecutive JS-only pushes both build, compare with
`eas fingerprint:compare` before touching the workflow.

### `--environment` is mandatory on SDK 55, and the two paths disagree on precedence

`eas update --help` on 22.0.0 says of `--environment`: *"Required for projects
using Expo SDK 55 or greater."* This project is SDK 55.

**Which environment feeds an OTA bundle: `production`.** The `internal` build
profile declares `"environment": "production"` in `eas.json`, so `eas update
--environment production` reads the same server-side variables the build reads.
That key used to be absent and the value was resolved implicitly — eas-cli's
`resolveSuggestedEnvironmentForBuildProfileConfiguration` maps
`distribution: "store"` (the default, so `internal` qualifies) to `production`,
`developmentClient: true` to `development`, and everything else to `preview`. All
five build profiles now state it explicitly so it cannot drift when a
`distribution` value changes.

Now the trap, because it is the same silent failure class as the DNS one above.
`EXPO_PUBLIC_*` values are **inlined into the JS bundle at bundle time**. A build
bundles on the EAS servers from the profile's `env` block; `eas update` bundles
**on the runner**, from that process's environment plus the EAS environment. And
the two merge in opposite orders — read out of eas-cli 22.0.0, not assumed:

| Path | Merge | Winner |
|---|---|---|
| `eas build` | `build/evaluateConfigWithEnvVarsAsync.js`: `{ ...serverEnvVars, ...buildProfile.env }` | **`eas.json`** |
| `eas update` | `utils/expoCli.js` `spawnExpoCommand`: `{ ...process.env, ...serverEnvVars }` | **EAS environment** |

So the two paths inline the same values only while **no `EXPO_PUBLIC_*` key is
defined on both sides**. Today none is, and that is what makes the setup sound:

- `EXPO_PUBLIC_API_BASE_URL`, `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`,
  `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB` live **only** in `eas.json`. The workflow
  copies them out of `build.internal.env` with `jq` into `$GITHUB_ENV` before
  publishing, so the update path reads them from the one source the build path
  reads.
- The RevenueCat keys live **only** in the EAS environments. Both paths get them
  from the server side, automatically.

If that ever stops holding, the symptom is an update that publishes cleanly,
installs cleanly, and fails every network call. The workflow catches the common
case by grepping the export `eas update` leaves in `mobile/dist/` for the expected
`EXPO_PUBLIC_API_BASE_URL` and failing the run with the rollback command in the
error message — but it fails **after** the publish, because that is the only point
at which the real bytes exist.

**Owner check, once, by hand:** `eas env:list production` and confirm it does not
define any of the three keys above. `eas env:list` needs authentication and has
neither `--json` nor `--non-interactive` in 22.0.0, so it cannot be a CI gate.

### Rolling back an update

Three commands, all present in 22.0.0. None is wired to run automatically — an
automatic rollback on a signal nobody has defined would be a second way to ship
something unreviewed.

| Command | What it does | Reach for it when |
|---|---|---|
| `eas update:rollback` | Republishes the update *before* the latest one on the branch. Falls back to a roll-back-to-embedded if there is none. Takes a group id, **required in non-interactive mode** | The previous OTA update was fine and this one is not |
| `eas update:roll-back-to-embedded` | Publishes a directive that sends clients back to the bundle **baked into the binary** | The whole OTA lineage is suspect, or you want testers on exactly what TestFlight/Play shipped |
| `eas update:republish` | Re-publishes a specific, named older update group | You know which good update to go back to and it is not simply the previous one |

Run them from `mobile/`. Find the group to name with `eas update:list --channel internal`.

### What the free tier actually gives you

This is the whole reason the decision rule exists rather than "always build".

| | Free tier |
|---|---|
| EAS Build | **15 Android + 15 iOS builds per month**, **1 concurrency slot**, low-priority queue (3 h+ waits measured 2026-09-02), 45-minute build timeout |
| EAS Update | **1 000 MAUs**, **unlimited updates** |

A dozen JS-only commits in one day would exhaust a month of build quota. Over OTA
they cost nothing. Full queue measurements:
[Why jobs wait](#why-jobs-wait-one-linux-queue-one-slot--measured-2026-090203).

### Every binary installed before 2026-09-03 has to be replaced once

Installing `expo-updates` is itself a native change, so:

- The fingerprint moved on both platforms. The **first** run of
  `mobile-ota-or-build.yml` after this lands produces one build per platform. That
  is the decision logic working, not a bug.
- Binaries installed **before** it have no updates runtime at all. The TestFlight
  install (`1.0.0 (2)`) and the Play internal-track install (`1.0.0 (5)`) will
  **never** receive an OTA. They have to be replaced once, by hand, by whoever
  holds them.

This is why the sequencing decision of 2026-09-02 puts OTA **before** Play closed
testing recruitment (`task-260`): the twelve testers should install an OTA-capable
binary on day one and never reinstall, rather than be asked to reinstall in the
middle of the 14-day clock.

Measured fingerprints, `eas fingerprint:generate --json --non-interactive
--platform <p> -e internal`, eas-cli 22.0.0:

| Platform | Before `expo-updates` | After |
|---|---|---|
| Android | `cdde50c777525d5ff172cfbb2ad9f95bd40b40d0` | `e53f6e78308ff4aa250fdc1eefa2675bb5329e92` |
| iOS | `0a282d80eac7580548cc4bc600bf83433a0de793` | `045400802019f4b94fee1bcf46b2963445b94d7c` |

### Pinning the EAS CLI

Every workflow that installs the CLI pins an explicit version — `EAS_CLI_VERSION:
"22.0.0"` in `mobile-ota-or-build.yml`, `mobile-build-distribute.yml` and
`mobile-store-promote.yml`. **Do not go back to a bare `npm install -g eas-cli`.**
The latest published version is 23.2.0 while the owner's machine runs 22.0.0, so
CI drifting to latest would put the pipeline on a different major from the machine
every decision here was verified on.

The flags each pin protects are named in a comment next to it. For the OTA
workflow they are the four the decision rule rests on: `fingerprint:generate
--json` emitting a top-level `hash` on stdout, `build:list --fingerprint-hash`,
`update --environment`, and `build --auto-submit` remaining compatible with
`--no-wait`. Bump the pin deliberately, after re-reading `--help` on the new
version — not by deleting it.

## Submit Profiles

| Profile | iOS destination | Android destination |
|---------|-----------------|---------------------|
| `internal` | TestFlight | Play `internal` track |
| `production` | TestFlight | Play `internal` track |
| `production-store` | TestFlight | Play `production` track |

Nothing reaches the public App Store without a separate, manual **submit for
review** in App Store Connect — `eas submit` only ever gets a build into
TestFlight.

**The `production` *submit* profile has nothing to do with the `production`
*build* profile.** `eas.json` has two independent maps, `build` and `submit`, and
a name may appear in both. The submit profile named `production` is alive and in
daily use — it is what the workflow passes to `eas submit` for an `internal`
build, since both submit profiles target the same destinations. The *build*
profile named `production` is the blocked one.

### The iOS blocks carry one field, and that is deliberate

Each holds `"ascAppId": "6778072060"` and nothing else. That number is the app
record's Apple ID, read from the App Store Connect URL
(`https://appstoreconnect.apple.com/apps/6778072060/distribution/info`). It is not
a secret — the same number appears in every public App Store link — and it is
hardcoded rather than templated for the reason below.

Until 2026-09-01 all three blocks carried `appleId`, `ascAppId` and `appleTeamId` as
`${APPLE_ID}` / `${ASC_APP_ID}` / `${APPLE_TEAM_ID}`. **That never worked.**
`@expo/eas-json` interpolates exactly three iOS submit fields —
`ascApiKeyPath`, `ascApiKeyIssuerId`, `ascApiKeyId` — so the other three reached
the Joi validator verbatim and it rejected all of them at once:

```
Invalid Apple ID was specified. It should be a valid email address.
Invalid Apple App Store Connect App ID ("ascAppId") was specified. It should consist only of digits.
Invalid Apple Team ID was specified. It should consist of 10 uppercase letters or digits.
```

Exporting the variables does not help — nothing reads them for these fields. What
replaces each one:

| Field | What happened to it |
|---|---|
| `appleId` | Removed. Apple auth comes from the App Store Connect API key held by EAS. If it is ever needed, `EXPO_APPLE_ID` is a real env var EAS reads. |
| `appleTeamId` | Removed. Same, plus EAS derives it from the Apple session. `EXPO_APPLE_TEAM_ID` exists too. |
| `ascAppId` | Kept, hardcoded. Per the docs it only "results in skipping the app creation step", so an interactive run does without it — but see below. |

`ascAppId` is the one field with **no** env-var equivalent, and the one thing
`--non-interactive` cannot do without: it fails with *"Set ascAppId in the submit
profile (eas.json) or re-run this command in interactive mode."* That is why it is
written literally rather than templated — a CI-driven iOS submission would be
impossible otherwise.

Either way EAS calls `ensureTestFlightGroupExistsAsync`, which creates an internal
TestFlight group with automatic access to all builds and invites every Admin of the
Apple account into it. Best-effort: a failure there warns and does not fail the
submission.

## Distributing a Build to Testers

### Android

`eas build --platform android --profile internal` produces the AAB, then either
`eas submit --platform android --profile internal` or a manual upload in Play
Console. Testers on the internal track install from the URL the track exposes.
This is the path in use today (`1.0.0 (5)`, 2026-09-01) and the iOS one below is
built to match it — same build profile, same submit profile, both platforms.

### iOS — TestFlight with a public link

The closest equivalent to the Play internal track. Tester caps and rules below
come from App Store Connect Help (*Test a beta version*), checked 2026-09-01.

| | Internal Testing | External Testing |
|---|---|---|
| Who | up to **100 App Store Connect users with access to your content** — but see the 50-user individual cap below | up to **10,000 people per app** |
| How they are added | each tester must be an invited App Store Connect user | email invite, CSV import, or a **public link** |
| TestFlight App Review | not required | required — but once per **version**, not per build (see below) |
| Account access granted | **yes** — every tester becomes an App Store Connect user with a role | **none** |
| Use it for | yourself and actual collaborators | **beta testers — this is the one you want** |

#### The review is a per-version toll, not a per-build one

This is the part that decides whether external testing is usable day to day, so it is
quoted rather than paraphrased. From *Invite external testers*, checked 2026-09-01 —
note that Apple's own page never writes "Beta App Review", it writes **TestFlight App
Review**:

> "After you submit your build to TestFlight App Review, Apple reviews the build and
> its accompanying metadata. The first build you submit requires a full review, but
> later builds for the same version might not."

So the toll is attached to the **version**, and *"might not"* is Apple's hedge, not a
guarantee: they reserve the right to look again at any build. In practice you pay it
once when `1.0.0` first goes external, then `1.0.0 (3)`, `(4)`, `(5)`… normally go
straight to testers, and you pay it again at `1.0.1`. Two throttles bound the loop,
both verbatim from the same page:

> "You can only have one build of each version in review at a time. Once that build
> is approved, you can submit additional builds."

> "You can submit up to six builds for TestFlight App Review within a 24-hour period."

The page states **no SLA and no expected duration** — the only figure it gives is that
six-per-24 h cap. Any "24-48 h" you read elsewhere is an estimate, not something Apple
commits to, and the Apple Developer Forums carry a steady stream of threads titled
*"TestFlight External Testing Build Stuck in 'Waiting for Review' for Several Days"*
(threads 829400, 829431, 770004, 759651). Budget days, not hours, for the first build
of a version, and never put it on the critical path of a demo.

**The practice this drives, straight from the forums** (thread 109085, the clearest
statement anyone has written of the rule):

> "Each new version of the App must go through this process, however subsequent builds
> for the same version will not require review once the initial review process
> succeeds. Internal Testers do not have this limitation."

So the working technique is: **freeze the marketing version, iterate the build number.**
`1.0.0 (3)` → `1.0.0 (4)` → `1.0.0 (5)` reach external testers without re-review; bump
to `1.0.1` only when you are willing to buy another round. This repo is already set up
that way and should stay that way: `version: "1.0.0"` is hardcoded in `app.config.ts`,
while `appVersionSource: "remote"` plus `autoIncrement: true` in `eas.json` increments
only the build number. Do not add version bumping to the build profiles.

Same thread, on how the review is actually triggered — there is often **no button**:

> "Since it's not exactly obvious, you can trigger a TestFlight build to be submitted
> for the Beta App Review process by adding an external tester to the build."

Forum thread 784013 is someone stuck on exactly that ("I don't see any buttons like
submit for review"). Assigning the build to the external group *is* the submission.

Approval and rejection both come back through the account: *"users on the App Store
Connect account with the Admin role will receive an email notifying them of the
approval"*; a rejection sets the build to **Rejected** and the reason is under
**General → App Review** in the sidebar. Rejections are appealable through the
TestFlight App Review contact form.

One trap specific to this app: **it has a login wall.** Apple's *App Review
information* reference makes the demo account required *"If your app requires a login
to use it"*, and says *"The demo account is used during the App Review process and
must not expire"*; the **Notes** field is described as the place for *"test
registration or account details"*. Apple's TestFlight pages do not restate that
requirement, so whether TestFlight App Review enforces it here is unverified — but
`docs/store-listing/app-store-connect.md` already promises *"A test account will be
provided in the review submission"* and **no such account exists yet**. Create one
before submitting, on the backend the submitted build talks to — which today is
always the **dev** API, since every shippable profile (`internal` included) points
there and `production` cannot be built at all (see
[Why a `mobile-v*` tag push is blocked today](#why-a-mobile-v-tag-push-is-blocked-today)).
The day a prod backend exists, the reviewer account has to exist on it too: one
that only lives in dev fails a `production` build.

#### The chosen path: Internal Testing, decided 2026-09-02

**Internal Testing is the route in use for beta testers**, taken deliberately to avoid
TestFlight App Review entirely. It buys the two properties that matter — *any email
address* and *no review* — and the bill is one App Store Connect seat per tester, plus
no public link.

The seat is not free of privileges. There is no view-only or tester-only role; the
narrowest on offer, **Assistance client** (Customer Support), still grants — verbatim
from the *Nouvel utilisateur* dialog, checked 2026-09-01:

- *"Répondre aux avis des utilisateurs et modifier les réponses qui leur sont apportées"*
- *"Afficher les indicateurs et les rapports de diagnostic dans Xcode Organizer"*

The first one lets the person post publicly under the app's name. **Today that
privilege is inert**: the app is not published, so it has no reviews to reply to. That
is what makes this trade acceptable for now, and it is also its expiry condition — once
the app ships, either drop the testers' roles or move beta testing to an External group.
Note it also burns one of the **50** seats an individual enrolment gets.

**External Testing remains the only route to a public link**, and stays documented above
for when the app is live: testers by email alone, no App Store Connect account, no role,
at the price of TestFlight App Review on the first build of each version.

#### Turning an email address into an internal tester

Two invitations: one onto the account, one into the TestFlight group. Nothing in this
repo needs changing for it — see the checklist at the end of this section.

1. **Users and Access → People → plus (+) button on the top left.** Enter first
   name, last name, email. Apple: *"Any email can activate the account. The email
   doesn't have to be associated with an Apple Account"* — if it is not, the person
   creates one while activating, so you are not restricted to people who already own
   an Apple Account. Doing this needs **Account Holder, Admin, or App Manager**.
2. Assign a role, click **Next**, pick the apps they may access, click **Invite**.
   App access can only be restricted for **App Manager, Developer, Marketing, Sales,
   Customer Support**, and only if you withhold reports access; *"Admin and Finance
   roles can view all app info and can't have access limited."* So grant the
   narrowest role that still works, scoped to this app alone.
3. **Apps → [app] → TestFlight tab → sidebar, under Internal Testing → the group →
   Invite Testers** → tick the users → **Add**. Apple does not publish which roles
   are tester-eligible; the page only says *"Eligible internal testers appear in a
   dialog. If a user you want to add isn't listed, change their user role."* So this
   is empirical: start narrow, widen if the person does not appear.

Constraints that bite, all from App Store Connect Help (checked 2026-09-01):

- **This account is an individual enrolment**, and Apple caps those: *"you can give
  up to 50 additional users access to your content in App Store Connect. These users
  only access App Store Connect — they're not part of your team and won't receive
  other membership benefits."* The real internal ceiling here is therefore **50**,
  not 100. They get no Apple Developer portal access, no certificates.
- **User invitations expire 3 days after being sent**, and can be resent.
- **Managed Apple Accounts created in reserved domains cannot test builds.**
- Internal testers can install every build for **90 days**.
- Deleting a user takes up to **10 minutes** of cache before access is really
  revoked.
- A group needs automatic access to new builds, otherwise every build has to be added
  to it by hand. The group EAS creates already has it — see below.

#### What `eas submit` does for you, from the eas-cli source

Read out of `eas-cli` on 2026-09-02 rather than inferred, because it decides how much
of this is manual. `submit` runs `ensureTestFlightSetupForExistingAppAsync`, whose flag
`--auto-testflight-setup` is `default: true` — so it happens unless you pass
`--no-auto-testflight-setup`. It then calls `ensureTestFlightGroupExistsAsync`, which:

- creates an internal group named **`Team (Expo)`** — the constant is commented *"this
  should probably never change"* — with `isInternalGroup: true` and
  `hasAccessToAllBuilds: true`, i.e. **every future build reaches the group with no
  further action**. That is the Android-internal-track behaviour, obtained for free;
- skips creation entirely if the app already has *any* beta group;
- invites **only users whose role is `ADMIN`**. Every other tester must be added by
  hand in App Store Connect. Do not expect `eas submit` to onboard your testers;
- retries for up to 15 × 10 s because Apple rejects group creation on a freshly created
  app;
- never blocks the submission: the whole thing is wrapped in a `try/catch` that logs
  *"Skipping TestFlight group setup"* and carries on. **If the group is missing after a
  submit, look for that warning in the output** rather than assuming it worked.

The source also proves role eligibility is real: adding a tester can come back
`NOT_QUALIFIED_FOR_INTERNAL_GROUP`, and `ADMIN` is the only role EAS trusts enough to
add automatically.

Because the group carries `hasAccessToAllBuilds: true`, the `groups` field of the iOS
submit profile — documented by Expo as *"An array of TestFlight internal group names to
add the build to"* — is **redundant here and deliberately left unset**. Setting it would
add a name that must be kept in sync with App Store Connect for no gain.

#### Checklist to run this workflow

Repo side: **nothing left to do.** Verified 2026-09-02 — `ascAppId` is literal in the
`internal` submit profile, export compliance is declared in `app.config.ts` so no build
or upload prompts for it, the App Store Connect API key lives on the EAS servers, both
App Store provisioning profiles are active, and an App Store-signed ipa already exists:
build `790af106-040c-4798-9599-68ad5b6f0770`, `1.0.0 (2)`, `distribution: STORE`,
profile `internal`. Its artifact URL **expires 2026-10-01**; submit it before then or
rebuild.

The `internal` profile's environment is settled, and since 2026-09-03 it is also
**written down**: `"environment": "production"` in `eas.json`. `eas env:list` shows
`development`, `preview` and `production` all carrying the *same* RevenueCat keys, and
`EXPO_PUBLIC_API_BASE_URL` is in **none** of them — it comes only from the profile's own
`env` block. So `internal` means "dev API, same RevenueCat project as everything else",
with no hidden collision, and internal testers exercise the dev backend on purpose.
Nothing reads `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` (grepped), so its absence from
`preview`/`production` is harmless.

That split — API URL and Google client IDs in `eas.json`, RevenueCat keys in the EAS
environment — stopped being a detail when OTA landed: it is the invariant that makes a
build and an update inline the same values, because the two paths merge those two sources
in **opposite** orders. Do not move a key across the line without reading
[`--environment` is mandatory on SDK 55](#--environment-is-mandatory-on-sdk-55-and-the-two-paths-disagree-on-precedence)
first.

Owner side, in order:

1. `cd mobile && npx eas-cli@latest submit --platform ios --profile internal --latest`.
   This uploads to TestFlight *and* creates `Team (Expo)`. First run is interactive —
   let it be, so you see the group-creation output.
2. If it fails with `BETA_CONTRACT_MISSING`, stop and read the troubleshooting entry
   below. Do not retry or rebuild; open a Developer Support case.
3. Wait for Apple to finish processing the build. No export-compliance question will be
   asked, and no review is involved.
4. Per tester: **Users and Access → People → (+)** → first name, last name, email →
   narrowest role that works → scope to this app → **Invite**. Invitations expire in
   3 days.
5. **Apps → [app] → TestFlight → Internal Testing → Team (Expo) → Testers → (+)** →
   tick the invited users → **Add**. If someone is not listed, their role is not
   eligible: widen it.
6. Tester installs **TestFlight** from the App Store and accepts the emailed invite.
   Builds stay installable for **90 days**.

Net effect: internal testing reproduces the "list of emails" half of the Play
internal track without any review, but each address costs an App Store Connect
seat, and there is **no public link** — only per-tester email invitations. The
public link needs External Testing, hence TestFlight App Review.

A public link is what gives you the shareable URL: anyone who has it can join,
so no UDID collection and no rebuild per device. Two consequences to accept:
testers who join through a link show up as **anonymous** in the *Testers*
section (you still get installs, sessions and crashes), and anyone can forward
the link — disable it from **Manage** next to **Public Link** if that becomes a
problem.

Every build can be tested for **up to 90 days**, then it becomes unavailable and
you have to ship a new one. Do not confuse this with the 14-day expiry EAS puts on
`development` artifacts, which is what killed the iOS builds listed by
`eas build:list`.

Owner steps, once per group:

1. **App Store Connect → Apps → [app] → TestFlight tab → sidebar, under Additional
   → Test Information.** Pick a language on the right, then fill *Beta App
   Description* — Apple: *"This field is required"* — and *Feedback Email*, *"the
   email address where testers can contact you through the TestFlight app… also the
   reply-to address in email invitations to testers"* (not marked required, but
   testers have no other channel without it). Needs **Account Holder, Admin, App
   Manager, Developer, or Marketing**. Leave the *App Information* checkbox under
   *Invitation Experience* ticked unless you do not want your screenshots and
   category shown in the invite — but it pulls from *"the latest approved version in
   the Ready for Distribution state"*, of which there is none yet, so it shows
   nothing today. Export compliance needs no action:
   `ios.config.usesNonExemptEncryption = false` in `app.config.ts` writes
   `ITSAppUsesNonExemptEncryption` into the ipa, so neither `eas build` nor App Store
   Connect asks about it.
2. The **Internal Testing** group Apple requires before any external group can
   exist is created for you: `eas submit` calls
   `ensureTestFlightGroupExistsAsync`, which makes one with automatic access to all
   builds and invites every Admin of the Apple account. Check it is there rather
   than creating it by hand.
3. Sidebar, **(+)** next to **External Testing** → group name → **Create**.
4. Group selected → **Add Builds** → pick platform and version → select the
   build → **Add**. One build at a time.
5. **What to Test** dialog → *"enter what you want testers to focus on"* → tick
   *Automatically notify testers* → **Submit Review** (the button reads **Start
   Testing** instead when the build needs no review). Leaving the notify checkbox
   unticked means *"you must manually distribute the build to testers after it's
   approved"*, from the build row's **Notify Testers** link. Also enter *Feedback
   Email* and *Contact Information* here if step 1 was skipped. See the per-version
   review rules above for what this costs and how often. **If no such button appears**,
   you have not missed a step: adding the build to an external group, or adding an
   external tester to it, is itself the submission — the status flips to *Waiting for
   Review* on its own.
6. Once approved, group → **Testers** tab → **Create Public Link** → **Open to
   Anyone** (or **Filter by Criteria** to restrict by device/OS, with an optional
   **Tester Limit** between 1 and 10,000) → **Confirm** → copy the link.
7. To name your testers instead, use **(+)** next to **Testers** → **Email** /
   **Existing** / **Import** on that same external group.

Once a group exists, its name can go in the `groups` field of the iOS submit
profile in `eas.json` so `eas submit` attaches every build to it automatically.
Expo documents that field as taking *internal* group names, so for an external group
step 4 above stays manual until proven otherwise: *Invite external testers* describes
no automatic-distribution toggle for external groups, only *"Automatically notify
testers"*, which controls the notification and not the attachment — and even then
distribution still happens **after** approval. Try `groups` with the external group
name on the next submit and check whether the build lands in it; if it does, this
paragraph is wrong and should be deleted.

### iOS — the ad hoc alternative, and why it is not used here

`distribution: "internal"` (the `preview` profile) makes EAS host an install page
with a QR code, which sounds like the Android APK story. It is not: iOS ad hoc
provisioning embeds an **allow-list of device UDIDs**, so you need each tester's
UDID (`eas device:create`), the Apple account is capped at **100 iPhones per
year**, and adding a device requires a rebuild or an `eas build:resign`. Expo's
own docs call collecting UDIDs "challenging if you try to share with someone who
is not a developer". In CI it additionally needs
`--refresh-ad-hoc-provisioning-profile` (EAS CLI 19.1.0+), otherwise
`--non-interactive` silently reuses a profile whose device list is stale.

Registering a device with Expo does not register it with Apple: the device only
lands on the Apple Developer Portal when it is first included in a provisioning
profile, and Apple may take 24-72 h on a recently renewed membership.

## Workflow Triggers

Two workflows can spend EAS quota or reach a tester, and they take different
entry points on purpose.

`mobile-build-distribute.yml` spends EAS build quota and can push binaries to the
stores, so it has exactly two entry points:

| Event | Builds | Profile | `eas submit` |
|-------|--------|---------|--------------|
| Push of a `mobile-v*` tag | **Nothing today** — both jobs fail on the pre-flight | `production` (unusable, [why](#why-a-mobile-v-tag-push-is-blocked-today)) | No — the run never reaches it |
| `workflow_dispatch` | Operator's choice of platform | Operator's choice, default `preview` | Only if the operator sets `submit=true` (default `false`) |
| Push to a branch (`main` included) | **Nothing** | — | — |

Both jobs run `bash scripts/mobile_release_check.sh <profile>` between resolving
the profile and calling `eas build`. It hard-fails when the profile's
`EXPO_PUBLIC_API_BASE_URL` host resolves to no address, which is the state of
`production`. A manual dispatch with `profile=production` fails there too, by
design.

`mobile-ota-or-build.yml` has exactly one:

| Event | Result |
|-------|--------|
| Push to `main` touching `mobile/**` or that workflow file, excluding `**/*.md` and `mobile/.maestro/**` | Per platform: an OTA publish on the `internal` channel if the native fingerprint is unchanged, `eas build --profile internal --auto-submit` if it moved. Never `production`, on either side. Exact commands: [Shipping JS Over The Air](#shipping-js-over-the-air) |
| Anything else, including a `mobile-v*` tag | Nothing |

It runs the same `scripts/mobile_release_check.sh internal` pre-flight, and it
declares a `concurrency` group so two pushes cannot race two publishes. Decision
rule and commands: [Shipping JS Over The Air](#shipping-js-over-the-air).

### What happens on push to `main`, and what still must not

Until 2026-08-13 the `push` trigger of `mobile-build-distribute.yml` combined
`branches: [main]` + `paths: ["mobile/**"]` with `tags: ["mobile-v*"]`. GitHub
applies `branches` to branch pushes and `tags` to tag pushes: the tag filter was
an *additional* trigger, not an extra condition. Every commit on `main` touching
`mobile/` therefore started a **`production`** build on both platforms and an
unattended store submission. The `branches`/`paths` filters were removed
(`task-258`); that workflow's `push` trigger now only matches `mobile-v*` tags.
**Do not re-add a branch filter to `mobile-build-distribute.yml`.**

What replaced it since 2026-09-03 is not the same thing and does not reopen that
hole. `mobile-ota-or-build.yml` does trigger on push to `main`, but it is pinned to
the **`internal`** profile and channel, it spends a build **only** when the native
fingerprint moved, and it can never touch `production` — no input selects a
profile, the strings are literal in the workflow. The old failure was "every
commit ships to production unattended"; this one is "every commit reaches internal
testers, by the cheapest of the two mechanisms that can".

Per-commit static mobile feedback still comes from `pr.yml` / `main.yml`
(`npm run typecheck`, `npm run lint`). To exercise a build outside a release, use
`workflow_dispatch` with `profile=preview` and `submit=false`:

```bash
gh workflow run mobile-build-distribute.yml \
  -f platform=android -f profile=preview -f submit=false
```

Both build jobs also guard the submission steps with
`github.event_name == 'workflow_dispatch' || startsWith(github.ref, 'refs/tags/mobile-v')`,
so a store submission stays impossible from a branch push even if the trigger is
loosened again by mistake.

### Manual Trigger Options

| Input | Options | Default |
|-------|---------|---------|
| Platform | ios, android, all | all |
| Profile | preview, internal, ~~production~~ (fails the pre-flight) | preview |
| Submit | true, false | false |

Whatever build profile is picked, both submission steps run
`eas submit --profile production`: the `internal` and `production` submit profiles
target the same destinations (TestFlight, Play `internal` track), so there is
nothing to switch between. `production-store` is deliberately unreachable from
this workflow — pushing to the Play `production` track stays a manual act.

### Owner prerequisite: `EXPO_TOKEN`

Every `eas` invocation in both mobile workflows authenticates with the
`EXPO_TOKEN` repository secret. Without it, `eas build --non-interactive` dies
immediately with `An Expo user account is required to proceed`, so no build or
submission can succeed regardless of the trigger.

**Provisioned 2026-09-02 at `17:13:47Z`** (`gh secret list`). What remains is
proving it end to end: the guard passing is not the same as `eas build`
authenticating, since the guard only checks that the string is non-empty. A
revoked or mistyped token clears the guard and dies later inside `eas build` with
`An Expo user account is required to proceed`.

Both build jobs start with a `Require EXPO_TOKEN` step that fails the run in a
couple of seconds with an explicit error message, before Node, `npm ci` or the
EAS CLI are installed.

The project is `@second-brain-labs/media-summarizer`
(`fad6e877-590d-4143-bbaa-fdd013b01c43`), owned by the account
`second-brain-labs`. To create or rotate the secret:

1. On <https://expo.dev>, open the avatar menu (top right) → **Settings** →
   **Access tokens** — direct URL <https://expo.dev/settings/access-tokens>.
   Create a **personal access token**, name it after the consumer (e.g.
   `github-actions-second-brain-app`), and copy the value **at that moment**: it
   is shown once and never again.
2. From the repo root, `gh secret set EXPO_TOKEN` and paste the value at the
   prompt. Never `echo` it into the command line — it would land in the shell
   history of a machine that also holds the repo.
3. Verify with `gh secret list` — the secret name and its timestamp are the only
   things the API returns, values are write-only.

A **robot access token** is the tighter alternative and is what a shared account
should use: robot users cannot sign in to Expo, cannot own projects, and
authenticate by token only, so revoking one does not touch the human account.
They live under the account (not the user): the entry point is
<https://expo.dev/accounts/second-brain-labs/settings/access-tokens>. Expo's docs
do not document that screen's navigation labels, so use the URL. For a solo
account either token works identically from the workflow's point of view — the
`EXPO_TOKEN` env var takes precedence over any stored login either way.

Never commit the token value; the workflows only ever reference it as
`secrets.EXPO_TOKEN`. **This repository is public**, so a token pasted into a
tracked file is a public leak the moment it is pushed.

**First run after setting it** — a deliberately harmless manual dispatch:
`Actions` → `Mobile Build & Distribute` → `Run workflow`, keeping the defaults
(`platform: all`, `profile: preview`, `submit: false`). That exercises
authentication and the build path without spending a store submission. Note that
`EXPO_TOKEN` only unblocks `eas build`; `eas submit` additionally needs the App
Store Connect API key and the Google Play service account, which live on EAS's
side (`eas credentials`), not in GitHub secrets.

## Observability & Failure Handling

### Automatic Notifications

When a build or submission fails:
1. **GitHub Step Summary** - Detailed failure info in the workflow run
2. **Slack notification** - Posted to configured webhook (if `SLACK_WEBHOOK_URL` is set)
3. **GitHub Issue** - Auto-created for tag-triggered failures, labeled `bug`

The issue is only labeled `bug` on purpose: `gh issue create` hard-fails on a
label that does not exist in the repository, and the repo currently only carries
the 9 default GitHub labels (`gh label list`). The workflow used to pass
`bug,ci/cd` and the notification job died on it, hiding the actual build failure.
If you want a dedicated label, create it first
(`gh label create ci/cd --description "CI/CD pipeline" --color 0e8a16`) and then
add it to the `--label` flag. The `notify-failure` job declares
`permissions: issues: write` so the default `GITHUB_TOKEN` is allowed to open
the issue.

### Monitoring Build Status

```bash
# List recent builds
eas build:list --platform all --limit 10

# View specific build
eas build:view <build-id>

# View submission status — see the note below, there is no read-only CLI command
```

**`eas submission:view` does not exist**, and `eas submit ... --latest` is not a
read: it *creates another submission*. The status of a submission already in
flight reads from the Expo GraphQL API instead, with the `expo-session` secret
from `~/.expo/state.json` and a `User-Agent: eas-cli/<version>` header (the API
answers `403` without one) — the same access pattern as the credentials lookup
in [App Store Connect Setup](#4-app-store-connect-setup):

```graphql
query($s: ID!) { submissions { byId(submissionId: $s) { status updatedAt } } }
```

### Why jobs wait: one Linux queue, one slot — measured 2026-09-02/03

The Free plan gives the account **one concurrency slot in total**
(`subscription.concurrencies` reads `{ total: 1, android: 1, ios: 1 }`), and the
low-priority queue that comes with it is what actually sets the wait. Expo
documents "wait times of 90+ minutes" on it at busy times. Three facts decide how
to schedule work, and none of them is guessable from the CLI:

- **EAS Submit runs on Linux, not on the platform being submitted to.** The
  `JobRun` behind an *iOS* TestFlight submission reports
  `resourceClassDisplayName: "Linux Medium"`. A submission therefore competes with
  Android builds for the same workers, and a TestFlight upload is in no way
  insulated from Android contention.
- **iOS builds are the exception** — they run on macOS hosts, a separate pool.
  Every iOS build of this project got a worker in **0.4 min**, on every day
  sampled, including while Android was starved.
- **A submission consumes the single slot exactly like a build does.** On
  2026-09-02 an iOS submission sat `IN_QUEUE` for 2 h 51 purely because an Android
  build held the slot ahead of it. Cancelling the build released the slot — and
  changed nothing, because the Linux pool was the binding constraint, not the slot.

Wait before a worker was assigned, by time of enqueue in **US Pacific** (where the
demand is):

| Enqueued (PT) | Job | Wait |
|---|---|---|
| 01:26 | Android build | 0.2 min |
| 02:49 | iOS submission | 4.9 min end to end |
| 03:46 | Android build | 5.3 min |
| 09:21 | Android build | 25.6 min |
| 11:55 | Android build | 15.3 min |
| 10:13 | Android build | **never served in 5 h 50, cancelled** |
| 14:16 | iOS submission | **3 h 30** — served at 17:45 PT |
| 14:38 | Android build | **3 h 17** — served at 17:55 PT, then built in 7 min |

**The queue drains when the US workday ends.** Both jobs left queued through the
afternoon of 2026-09-02 were picked up between 17:45 and 17:55 PT, within ten
minutes of each other, and both succeeded. Nothing was retried and nothing was
touched: they simply waited out the contention.

**Practical rule: queue anything that needs Linux — an Android build, or a
submission to either store — outside US working hours.** Early morning (01:00 to
04:00 PT) and after 17:45 PT both served jobs in minutes; 09:00 to 15:00 PT is
where the multi-hour waits live.

**A queued job is not lost and does not need babysitting.** `JobRun.expiresAt`
sits 30 days out, so a job left `IN_QUEUE` will run when capacity returns.
Cancelling and re-submitting buys nothing and costs the queue position: a fresh
submission queued at 14:16 PT behaved exactly like the one it replaced, and the
Android build cancelled at 14:13 PT had to start over — the replacement waited
3 h 17 where the original might have been served at the same 17:45 PT.

### Never let two Android submissions overlap

`eas submit --platform android` drives Fastlane `supply`, which opens an **Edit**
on the Play Console app record. Two submissions running at once fight over it and
the loser dies with:

```
Google Api Error: Invalid request - This Edit has been deleted. - Retrying...
[!] Google Api Error: Invalid request - This Edit has been deleted.
Fastlane supply failed
```

Seen on 2026-09-03: two submissions of the same AAB started two seconds apart
(one by hand, one by a watcher script). One finished normally, the other errored
this way. **The error is the collision, not the artifact** — check whether a
sibling submission finished before re-uploading anything, because the build is
already on the track when it did.

Other Free-plan ceilings worth knowing: a **45-minute build timeout**
(`maxRunTimeSeconds: 2700`) and **15 Android + 15 iOS builds per month**. Usage on
2026-09-02 for the 2026-09-01 → 2026-10-01 period was 5/15 Android and 2/15 iOS,
so the quota has never been the constraint here. The paid escape is **Starter at
$19/month**, which buys the high-priority queue while still granting a single
concurrency; **Production at $199/month** is the first tier with 2 concurrencies,
and therefore the first that stops serialising a build against a submission.

### EAS Build Dashboard

Visit [expo.dev](https://expo.dev) > Your project > Builds for a web-based view of
all builds, logs, and artifacts.

## Troubleshooting

### iOS: `BETA_CONTRACT_MISSING` — read this *before* the first TestFlight submit

There is a live, unfixed Apple backend bug that breaks TestFlight for whole accounts,
and it disproportionately hits **brand-new accounts and brand-new apps** — which is
exactly what this project is. Recorded here from the Apple Developer Forums on
2026-09-02 so that nobody burns days re-uploading builds against it.

The signature:

```
POST /v1/betaAppReviewSubmissions
  -> HTTP 422 ENTITY_UNPROCESSABLE.BETA_CONTRACT_MISSING
     "Beta contract is missing for the app." / "Beta Contract is missing."
```

and/or, on device, an install that dies with *"The requested app is not available or
doesn't exist"* / *"Error Downloading Install Data"* (`POST
testflight.apple.com/v2/.../install` → 404, `installd` never runs).

What makes it recognisable rather than a config error: **App Store uploads keep working
— only TestFlight breaks.** Every reporter had Free *and* Paid agreements Active,
banking and tax Active, nothing pending, export compliance and App Privacy filled in,
and builds at `processingState: VALID`. One of them traced it precisely (thread 814565):

> "every request returns 200 … Only the final POST /v1/betaAppReviewSubmissions returns
> 422. Notably, GET /v1/apps/{id}/betaLicenseAgreement returns 200 with a valid object,
> so the per-app agreement is intact. This isolates the problem to a missing team-level
> beta contract on Apple's backend – which developers cannot recreate via the public
> API (read/update only, no create)."

**There is no workaround.** The thread runs Feb 2026 → Aug 2026 with 34 replies and 29
participants; Apple's DTS said in Feb 2026 that it "should be resolved now", the
reporter came back a day later with the same failure, and the staff position since is
"open a case with Developer Support". Things reporters tried that did **not** help:
uploading new builds, removing and re-adding testers, reinstalling TestFlight, signing
out and in of the Apple Account, changing device, setting a free price point across all
territories then waiting 24 h+, waiting a week.

Scope confirmed on both sides: long-standing accounts breaking mid-stream, *and* fresh
ones — including a brand-new app on **Expo EAS**, i.e. this exact stack. Related
threads: 814565 (master), 844066, 841920, 841429, 841782, 837299, 835530, 835321,
826046, 839591.

If it happens here:

1. Confirm it is this bug and not configuration — `GET /v1/apps/6778072060/betaLicenseAgreement`
   returns 200 while only `POST /v1/betaAppReviewSubmissions` returns 422.
2. Open a case at <https://developer.apple.com/contact> with Team ID, the app's Apple ID
   (6778072060), the bundle ID, the build ID and the 422 error `id` from the response.
   That is DTS's own instruction; the forum is not a fix channel.
3. Do **not** spend build quota on re-uploads. Fall back to the `preview` profile with
   ad hoc distribution for anyone whose device UDID you can collect (see *the ad hoc
   alternative* above), and keep the App Store path — which is unaffected — for the
   actual release.

### iOS: "No matching provisioning profile"

```bash
# Regenerate credentials
eas credentials --platform ios
# Select: Remove existing > Set up new
```

### iOS: "App version already exists in TestFlight"

The `autoIncrement: true` in `eas.json` handles this automatically. If it still occurs:
```bash
# Check current version
eas build:version:get --platform ios

# Set a specific version
eas build:version:set --platform ios --build-number 42
```

### Android: "Upload failed - version code already used"

```bash
# Check current version
eas build:version:get --platform android

# Set a specific version
eas build:version:set --platform android --version-code 42
```

### Android: "Service account key invalid"

1. Verify the JSON key is complete (not truncated) in the GitHub secret
2. Verify the service account has "Release manager" permission in Play Console
3. Verify the API access is enabled: Play Console > Setup > API access

### EAS Build: "Queue timeout"

Free EAS plans have limited concurrent builds. Options:
- Wait and retry (builds are queued)
- Upgrade to EAS Production plan for priority queue
- Use `--local` flag for local builds

### Generic: "API host … resolves to no address" (job fails before `eas build`)

The pre-flight gate tripped: the build profile's `EXPO_PUBLIC_API_BASE_URL` points
at a host with no DNS record, so the binary would be inert. This is the expected
outcome for the `production` profile, tag pushes included — see
[Why a `mobile-v*` tag push is blocked today](#why-a-mobile-v-tag-push-is-blocked-today).
Do not "fix" it by editing the URL to the dev host; build `internal` instead, which
is what testers use. If the host *should* resolve, check it locally with
`getent hosts <host>` before touching anything in the repo.

### Generic: "EXPO_TOKEN secret is empty" (job fails in seconds)

The `Require EXPO_TOKEN` guard tripped: the secret is missing or empty. Create a
robot token at <https://expo.dev/settings/access-tokens> and run
`gh secret set EXPO_TOKEN`.

### Generic: "An Expo user account is required to proceed" / "EXPO_TOKEN invalid"

1. Verify the token exists and is not expired at expo.dev
2. Create a new Robot token if needed
3. Update the `EXPO_TOKEN` secret in GitHub

## Version Management

Version numbers are managed via EAS remote version source (`appVersionSource: "remote"` in eas.json):

- `autoIncrement: true` on the `internal` and `production` profiles bumps the build
  number automatically, which is what keeps TestFlight from rejecting a duplicate
- App version (semver) is set in `app.config.ts` (`version` field)
- To release a new marketing version, update `version` in `app.config.ts`

`runtimeVersion` is **not** part of this. It is `{ policy: "fingerprint" }`, i.e. a
hash of the native project, and it moves independently of both the semver and the
build number — which is exactly why it can coexist with `appVersionSource:
"remote"`. See [Shipping JS Over The Air](#shipping-js-over-the-air).

## Security Notes

- iOS signing credentials are stored in EAS servers (encrypted at rest)
- Android keystore is stored in EAS servers (encrypted at rest)
- The Google Play service account key is stored in EAS servers too, since
  2026-09-01. It is never written to disk, by the CI job or by anyone else
- Never commit signing credentials to the repository
- `google-services-key.json` stays in `.gitignore` even though nothing writes it
  any more — the name is the one `eas.json` used to point at, and a stray download
  landing there must not become committable
