---
id: task-238
title: Provision Google Play subscriptions and connect the Android app to RevenueCat
status: To Do
assignee: []
created_date: '2026-08-09 21:05'
updated_date: '2026-08-20 03:11'
labels:
  - phase-6
  - mobile
  - release
  - android
  - revenuecat
  - iap
dependencies:
  - task-163
  - task-262
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Complete the production-like Android billing configuration that is intentionally absent today. The Android application must exist in Google Play Console and RevenueCat, expose the three validated V1 monthly tiers through the current offering, and use a real Google Play public SDK key instead of the Test Store key or the current placeholder. This work involves owner-controlled Google Play Console credentials and billing setup; an agent may automate verifiable RevenueCat/API portions but must not handle or expose private service-account material.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Google Play application for package com.secondbrainlabs.core exists and is eligible for Internal Testing
- [ ] #2 A Google Play app is connected in the RevenueCat project and its Google service credentials validate successfully
- [ ] #3 The Text-Only, Mix, and Audio-Heavy monthly subscriptions exist in Google Play with the validated V1 prices and active base plans
- [ ] #4 All three Google Play products are imported into RevenueCat, attached to their matching tier entitlement from task-262 (tier_text_only, tier_mix, tier_audio_heavy), and mapped to packages text_only, mix and audio_heavy in the current offering
- [ ] #5 The real RevenueCat Google public SDK key is configured securely for Android development, preview, CI, and production profiles, while the Test Store key remains restricted to tests
- [ ] #6 An Internal Testing build fetches all three packages through Google Play without configuration errors
- [ ] #7 A Google Play license tester completes a sandbox purchase and restore, and RevenueCat Customer Info reports the matching tier entitlement as active
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Progress — 2026-08-20 (owner session, no code involved)

Where the Android/RevenueCat wiring actually stands, and why it stops where it does.

**Done**

- Google Play developer account exists. Its setup is **not finished** — Play Console still shows the "finish setting up your developer account" banner, which gates publishing.
- Google Cloud service account created with the two roles RevenueCat requires (Pub/Sub Editor, Monitoring Viewer), JSON key generated, and the account invited in Play Console under **Users & permissions** with the app-information (read-only), financial-data and orders-and-subscriptions permissions. Its email, its GCP project id and the key id are deliberately not recorded here (public repo) — read them back from the RevenueCat app's Service credentials panel.
- Play Store app created in the RevenueCat project: `appb253c0f75a`, package `com.secondbrainlabs.core`. Service account JSON uploaded.
- Because RevenueCat mints a public SDK key at app creation, the real `goog_` key exists independently of everything below, and it is **set in `mobile/.env`** — the `your_revenucat_google_api_key_here` placeholder is gone, so Android now configures the SDK for real. It still cannot resolve an offering: that waits on the Play products. AC#5 stays unticked because it asks for the key to be configured across the development, preview, CI and production profiles, not only in the local `.env` (which is gitignored, so no EAS cloud build sees it).

**Blocked, and the ordering this reveals (AC#2)**

RevenueCat authenticates against the credentials without trouble, then fails all three checks with *"the Google Play package name was not found"*. Cause: a package name only exists for the Google Play Developer API once a **signed bundle carrying that applicationId has been uploaded to a test track**. Creating the app in Play Console is not enough — at creation you supply an app *name*, and the package name is fixed by the first AAB.

So AC#2 cannot pass before AC#1, and AC#1 needs the Android build of `task-163`. The real order is: `task-163` → AC#1 → AC#2 → AC#3-4 → AC#5-7. Nothing between them can be done out of sequence.

**Two practical notes for whoever runs AC#1**

- `mobile/eas.json` profile `preview` builds an **APK** (`buildType: "apk"`), which Play Console refuses for a new app — new applications only accept **AAB**. Use `production` (`app-bundle`) or add a dedicated profile.
- The bundle needs to be neither functional nor public. An internal or closed track is enough to make the package name exist, which is all AC#2 is waiting on.

**Deferred until the credentials validate**

Connect **Google developer notifications** (Pub/Sub topic) on the RevenueCat Play Store app, so Android purchase events reach `media_summarizer/api/endpoints/revenucat_webhook.py` in real time rather than by polling. RevenueCat surfaces it on the same app settings page and recommends it strongly.
<!-- SECTION:NOTES:END -->
