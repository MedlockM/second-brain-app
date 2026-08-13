---
id: task-261
title: Provision App Store subscriptions and connect the iOS app to RevenueCat
status: To Do
assignee: []
created_date: '2026-08-13 19:04'
labels:
  - phase-6
  - mobile
  - release
  - ios
  - revenuecat
  - iap
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Complete the iOS billing configuration, which is the symmetric counterpart of task-238 for Android. Today the RevenueCat project `proj879a771a` has an iOS app declared (`app0d4b00c12f`, bundle `com.secondbrainlabs.core`, In-App Purchase key configured) but **zero products attached to it**: the three products backing the current `default` offering (`text_only_monthly_test`, `mix_monthly_test`, `audio_heavy_monthly_test`) all belong to the **Test Store** app `appa51ecf7585`. The whole offering/entitlement chain is therefore wired to RevenueCat's simulator, never to StoreKit, and no real sandbox purchase can be exercised.

Scope splits into owner-only store work and an agent-verifiable RevenueCat wiring step. An agent may automate the RevenueCat portion via the v2 REST API using `REVENUCAT_API_KEY` from the root `.env`, but must never handle App Store Connect private key material (`.p8`), sandbox tester passwords, or trigger a TestFlight build.

## Prices to use (validated benchmark, `docs/research/task-65-pricing-v1-benchmark/README.md`, `owner_decision: ok`)

- Reader / Text-Only — 3 EUR/month — product ID `com.secondbrainlabs.core.text_only_monthly`
- Mix — 5 EUR/month — product ID `com.secondbrainlabs.core.mix_monthly`
- Audio-Heavy — 9 EUR/month — product ID `com.secondbrainlabs.core.audio_heavy_monthly`

Those exact product IDs are already expected by `PRODUCT_TIER_MAP` in `media_summarizer/api/endpoints/revenucat_webhook.py:33-42`. Do **not** rename them and do **not** add the `*_test` IDs to that map: Apple sandbox purchases emit the production product IDs, so the existing mapping is already correct for sandbox validation. The `*_test` IDs exist only because those products live in the Test Store, which is UI-test scaffolding (`mobile/.maestro/07_paywall.yaml` never taps Subscribe).

The three products must be attached to entitlement `pro` (`entlff2420092b`) and to packages `text_only` (`pkgefd39fb892f`), `mix` (`pkge7df593bf70`) and `audio_heavy` (`pkge5843d287fa`) of the current `default` offering (`ofrng2c876c3f17`) — the same lookup keys `getTierPackage()` searches in `mobile/app/paywall.tsx:160`, and the same entitlement `hasActiveEntitlement()` reads in `mobile/src/services/purchaseService.ts:126`.

## Deliberately out of scope: StoreKit configuration file

`docs/V1_LAUNCH_PLAN.md` Phase 6 lists `mobile/ios/StoreKit.storekit` as a remaining item. It is **not** in this task's scope: a StoreKit configuration file only serves local StoreKit testing in the Xcode simulator, and the owner has no Mac (see Phase 7, "Contrainte de budget CI"). iOS purchase validation goes through TestFlight plus a sandbox tester account instead. That plan line should be dropped rather than carried as outstanding work.

## OWNER NOTES — steps no agent can perform

1. **App Store Connect → Apps → Subscriptions**: create a subscription group, then the three monthly subscriptions with the product IDs and prices above. Each needs a localized display name, description and a review screenshot, otherwise it stays `Missing Metadata` and RevenueCat cannot import it.
2. **App Store Connect → Users and Access → Integrations → App Store Connect API**: generate an API key (Admin or App Manager role), then paste the issuer ID, key ID and `.p8` into the RevenueCat iOS app configuration. This is what flips `app_store_connect_api_key_configured` from `false` to `true` and lets RevenueCat read and validate the products. The `.p8` must never be written to a tracked file — the repo is public.
3. **App Store Connect → Users and Access → Sandbox → Test Accounts**: create at least one sandbox tester with an email address you control, not tied to an existing Apple ID.
4. **TestFlight build** — depends on an EAS iOS build; the last one expired 2026-06-25 (see `task-161` and Phase 5). Install it, sign in on the device with the sandbox tester, buy one tier and then exercise Restore Purchases.
5. **LAUNCH PREREQUISITE, after the sandbox purchase**: verify the webhook round trip end to end — `revenucat_events-dev` records the event (it holds 0 items today, the circuit has never run), `subscriptions-dev` carries the right tier for the buying user, and `GET /api/v1/entitlements/status` reports `is_active: true` with the matching `minutes_remaining`. This requires `REVENUCAT_WEBHOOK_SECRET`, which is empty in both `.env` and `media-summarizer-runtime-dev` — the webhook answers HTTP 500 `Webhook secret not configured` until it is filled. Note that the single row currently in `subscriptions-dev` (tier `L`, period end 2029) is a manual UI-testing fixture from 2026-08-02, not a purchase.
6. Keep the Test Store app and its `*_test` products in place: the Maestro paywall flow depends on them through `E2E_REVENUECAT_TEST_KEY`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The three monthly subscriptions com.secondbrainlabs.core.text_only_monthly, com.secondbrainlabs.core.mix_monthly and com.secondbrainlabs.core.audio_heavy_monthly exist in App Store Connect at 3, 5 and 9 EUR per month and are readable through the RevenueCat API as products of the iOS app app0d4b00c12f
- [ ] #2 The RevenueCat iOS app app0d4b00c12f reports app_store_connect_api_key_configured true, so RevenueCat can validate App Store products
- [ ] #3 The three iOS products are attached to entitlement pro (entlff2420092b), verifiable via GET /v2/projects/proj879a771a/entitlements/entlff2420092b/products
- [ ] #4 The three iOS products are attached to packages text_only, mix and audio_heavy of the current default offering, verifiable via GET /v2/projects/proj879a771a/packages/<id>/products
- [ ] #5 PRODUCT_TIER_MAP in media_summarizer/api/endpoints/revenucat_webhook.py still resolves the three production iOS product IDs and carries no *_test identifier
- [ ] #6 docs/V1_LAUNCH_PLAN.md Phase 6 no longer lists mobile/ios/StoreKit.storekit as outstanding work, and records why it does not apply
- [ ] #7 ruff check . and mypy media_summarizer are clean
<!-- AC:END -->
