---
id: task-261
title: Provision App Store subscriptions and connect the iOS app to RevenueCat
status: To Do
assignee: []
created_date: '2026-08-13 19:04'
updated_date: '2026-08-13 22:40'
labels:
  - phase-6
  - mobile
  - release
  - ios
  - revenuecat
  - iap
dependencies:
  - task-262
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Complete the iOS billing configuration, which is the symmetric counterpart of task-238 for Android. When this task was written, the RevenueCat project `proj879a771a` had an iOS app declared (`app0d4b00c12f`, bundle `com.secondbrainlabs.core`, In-App Purchase key configured) but **zero products attached to it**: the three products backing the current `default` offering (`text_only_monthly_test`, `mix_monthly_test`, `audio_heavy_monthly_test`) all belonged to the **Test Store** app `appa51ecf7585`. The whole offering/entitlement chain was therefore wired to RevenueCat's simulator, never to StoreKit, and no real sandbox purchase could be exercised.

**RevenueCat side, done 2026-08-13** — the three App Store products now exist on `app0d4b00c12f`, each attached to its tier entitlement and to its tier package:

| Store identifier | RevenueCat product | Entitlement | Package |
|---|---|---|---|
| `com.secondbrainlabs.core.text_only_monthly` | `proda3433ca23d` | `tier_text_only` | `text_only` |
| `com.secondbrainlabs.core.mix_monthly` | `prodd7204320b0` | `tier_mix` | `mix` |
| `com.secondbrainlabs.core.audio_heavy_monthly` | `prod1c519e5d72` | `tier_audio_heavy` | `audio_heavy` |

They read back with `subscription.duration: null` and `app_store_connect_api_key_configured` is still `false`: RevenueCat holds the identifiers but has never read the subscriptions from App Store Connect, because they do not exist there yet. Everything left is owner work in App Store Connect — see OWNER GATES below.

Depends on `task-262`, which restructured the entitlement layout to one entitlement per tier and deleted the product-ID map. It landed on `main` on 2026-08-13.

Scope splits into owner-only store work and an agent-verifiable RevenueCat wiring step. An agent may automate the RevenueCat portion via the v2 REST API using `REVENUCAT_API_KEY` from the root `.env`, but must never handle App Store Connect private key material (`.p8`), sandbox tester passwords, or trigger a TestFlight build.

## Prices to use (validated benchmark, `docs/research/task-65-pricing-v1-benchmark/README.md`, `owner_decision: ok`)

- Reader / Text-Only — 3 EUR/month — product ID `com.secondbrainlabs.core.text_only_monthly`
- Mix — 5 EUR/month — product ID `com.secondbrainlabs.core.mix_monthly`
- Audio-Heavy — 9 EUR/month — product ID `com.secondbrainlabs.core.audio_heavy_monthly`

Use these exact product IDs and do not rename them. They carry no behavioural meaning after `task-262` — the backend resolves the tier from entitlements, never from the product identifier — but they are the IDs the pricing benchmark and this plan reference, and a store product ID cannot be changed once created.

Each product attaches to its matching tier entitlement from `task-262` (`tier_text_only`, `tier_mix`, `tier_audio_heavy`) and to the matching package of the current `default` offering (`ofrng2c876c3f17`): `text_only` (`pkgefd39fb892f`), `mix` (`pkge7df593bf70`), `audio_heavy` (`pkge5843d287fa`) — the lookup keys `getTierPackage()` searches in `mobile/app/paywall.tsx:160`.

## Deliberately out of scope: StoreKit configuration file

`docs/V1_LAUNCH_PLAN.md` Phase 6 used to list `mobile/ios/StoreKit.storekit` as a remaining item. It is **not** in this task's scope: a StoreKit configuration file only serves local StoreKit testing in the Xcode simulator, and the owner has no Mac (see Phase 7, "Contrainte de budget CI"). iOS purchase validation goes through TestFlight plus a sandbox tester account instead. That plan line should be dropped rather than carried as outstanding work.

## OWNER GATES — steps no agent can perform, and where they are tracked

None of the six items below is an acceptance criterion: each one needs an App Store Connect session, an Apple credential or a TestFlight build, so an agent in a worktree cannot reach any of them. They are the owner's checklist, and the ordered version lives in `docs/V1_LAUNCH_PLAN.md` Phase 6, execution item 3. **The iOS billing setup is not finished until they are done**, whatever the state of this file's ACs — the ACs only cover the RevenueCat wiring and the preparation the agent could deliver.

1. **App Store Connect → Apps → Subscriptions**: create one subscription group, then the three monthly subscriptions with the product IDs and prices above. Each needs a localized display name, description and a review screenshot, otherwise it stays `Missing Metadata` and RevenueCat cannot import it. Ready-to-paste values: `docs/store-listing/app-store-connect.md`, section "Subscriptions (In-App Purchases)". Do **not** add an App Store introductory offer — the 30-day Mix trial is granted server-side by account age (`quota_enforcer._is_free_trial_active`), so an ASC offer would hand out a second, billed free month.
2. **App Store Connect → Users and Access → Integrations → App Store Connect API**: generate an API key (Admin or App Manager role), then paste the issuer ID, key ID and `.p8` into the RevenueCat iOS app configuration. This is what flips `app_store_connect_api_key_configured` from `false` to `true` and lets RevenueCat read and validate the products. The `.p8` must never be written to a tracked file — the repo is public.
3. **App Store Connect → Users and Access → Sandbox → Test Accounts**: create at least one sandbox tester with an email address you control, not tied to an existing Apple ID.
4. **TestFlight build** — depends on an EAS iOS build; the last one expired 2026-06-25 (see `task-161` and Phase 5). Install it, sign in on the device with the sandbox tester, buy one tier and then exercise Restore Purchases.
5. **LAUNCH PREREQUISITE, after the sandbox purchase**: verify the webhook round trip end to end — `revenucat_events-dev` records the event (it holds 0 items today, the circuit has never run), `subscriptions-dev` carries the right tier for the buying user, and `GET /api/v1/entitlements/status` reports `is_active: true` with the matching `minutes_remaining`. This requires `REVENUCAT_WEBHOOK_SECRET`, which is empty in both `.env` and `media-summarizer-runtime-dev` — the webhook answers HTTP 500 `Webhook secret not configured` until it is filled.
6. Keep the Test Store app and its three `*_test` products in place: the Maestro paywall flow depends on them through `E2E_REVENUECAT_TEST_KEY`. `task-262` attaches them to the tier entitlements like any other product.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The three products com.secondbrainlabs.core.text_only_monthly, com.secondbrainlabs.core.mix_monthly and com.secondbrainlabs.core.audio_heavy_monthly exist in RevenueCat under the iOS app app0d4b00c12f, readable via GET /v2/projects/proj879a771a/products?app_id=app0d4b00c12f
- [x] #2 docs/store-listing/app-store-connect.md carries the exact App Store Connect subscription configuration the owner has to paste: one subscription group, the three frozen product IDs, 3/5/9 EUR prices, subscription levels, display names and descriptions within Apple's character limits, and the review-screenshot requirement
- [x] #3 Each iOS product is attached to its matching tier entitlement created by task-262 (tier_text_only, tier_mix, tier_audio_heavy), verifiable via GET /v2/projects/proj879a771a/entitlements/<id>/products
- [x] #4 The three iOS products are attached to packages text_only, mix and audio_heavy of the current default offering, verifiable via GET /v2/projects/proj879a771a/packages/<id>/products
- [x] #5 No store product identifier is added to media_summarizer/api/endpoints/revenucat_webhook.py: tier resolution stays entitlement-driven as delivered by task-262
- [x] #6 docs/V1_LAUNCH_PLAN.md Phase 6 no longer lists mobile/ios/StoreKit.storekit as outstanding work, and records why it does not apply
- [x] #7 ruff check . and mypy media_summarizer are clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Two ACs were rewritten, and why

The original #1 and #2 were not satisfiable by an agent: #1 required the three subscriptions to exist **in App Store Connect** at 3/5/9 EUR, #2 required `app_store_connect_api_key_configured: true`, which is set by uploading a `.p8` in an ASC session. Both are owner-only by nature, and per `AGENTS.md` ("An acceptance criterion must be satisfiable by the agent that implements the task") they belong in the description as owner checklist items, not in the AC list. They now live in OWNER GATES 1 and 2 above, with the ordered procedure in `docs/V1_LAUNCH_PLAN.md` Phase 6 item 3, and nothing was lost: the prices, the frozen identifiers, the "no introductory offer" rule and the ASC-key gate are all written down in a place the owner reads.

In their place, #1 states the half an agent can reach (the products exist in RevenueCat under the iOS app) and #2 covers the preparation that makes the owner's ASC step mechanical instead of a design exercise. #3 to #7 are unchanged.

**This task's ACs being ticked does not mean iOS billing works.** No sandbox purchase is possible until the owner finishes OWNER GATES 1-4. The `Bloquants pré-soumission stores` row of the launch plan still carries that, and it should not be dropped when this task is marked Done.

### RevenueCat wiring, via the v2 REST API

Nine calls with `REVENUCAT_API_KEY` passed as a bearer token from the environment (read from the root `.env`, never written to a file, never echoed):

- `POST /v2/projects/proj879a771a/products` x3 → `proda3433ca23d` (`com.secondbrainlabs.core.text_only_monthly`), `prodd7204320b0` (`…mix_monthly`), `prod1c519e5d72` (`…audio_heavy_monthly`), all `app_id: app0d4b00c12f`, `type: subscription`, HTTP 201.
- `POST …/entitlements/{entlc5a41cba3a,entlde3fb9eb65,entlfa93d44749}/actions/attach_products` x3, HTTP 200.
- `POST …/packages/{pkgefd39fb892f,pkge7df593bf70,pkge5843d287fa}/actions/attach_products` x3 with `eligibility_criteria: all`, HTTP 200.

Verified by re-reading the exact endpoints the ACs name: each `entitlements/<id>/products` now lists its Test Store product **and** its App Store product; each `packages/<id>/products` likewise. `products?app_id=app0d4b00c12f` returns exactly the three new products.

Two facts worth keeping:

- **A product can be created in RevenueCat before it exists in the store.** RevenueCat accepted the three `store_identifier`s with no ASC key configured; it records the identifier and reconciles it with App Store Connect later. That is what made the wiring half of this task agent-doable at all, and it is the same trick `task-238` can use for Play.
- **The three products read `subscription.duration: null`**, unlike the Test Store products which read `P1M`. That is the visible symptom of `app_store_connect_api_key_configured: false` — RevenueCat has never fetched the subscription. It will flip to `P1M` once OWNER GATES 1 and 2 are done, and that is a cheap way to check them.

### No regression on the Maestro paywall path

Packages hold one product per store, and the SDK only returns the product matching the store it was configured for, so the Test Store products that `mobile/.maestro/07_paywall.yaml` drives through `E2E_REVENUECAT_TEST_KEY` are untouched. Symmetrically, an iOS build using the real iOS SDK key still gets packages with no purchasable product until the subscriptions exist in ASC — which was already true when the packages held Test Store products only, so nothing got worse.

### No code change, deliberately

`mobile/app/paywall.tsx` matches a package to a tier card by substring on the package or product identifier; `text_only` / `mix` / `audio_heavy` are all contained in both the package lookup keys and the new product IDs, so `getTierPackage()` resolves the new products with no edit. `purchaseService.ts` reads entitlement lookup keys, not products. `revenucat_webhook.py` was not touched at all (AC #5): `grep` for `com.secondbrainlabs`, `_monthly` and `PRODUCT_TIER` in it returns nothing.

### Documentation

- `docs/REVENUECAT_ENTITLEMENTS.md`: products table now lists the six products with their app, the packages table has one column per store, and the "adding a store product" section carries the three concrete v2 endpoints (`task-238` can follow them verbatim).
- `docs/V1_LAUNCH_PLAN.md`: Phase 6 state lines corrected (the iOS app no longer "carries 0 product"; the remaining gap is the ASC key and the ASC subscriptions), Phase 6 execution item 3 rewritten as a seven-step owner checklist, and the two status tables (§1 pre-submission blockers, §2 accounts) plus the §5 owner-only list updated. AC #6 was already satisfied on `main` — the "`StoreKit.storekit` is out of scope, the owner has no Mac, validation goes through TestFlight" paragraph was added when this task was created; it was kept and the surrounding claims were brought back in line with reality.
- `docs/store-listing/app-store-connect.md`: new "Subscriptions (In-App Purchases)" section (AC #2).

### Out of reach from the worktree

Everything in OWNER GATES. Also unreachable and not an AC: the webhook round trip, which needs `REVENUCAT_WEBHOOK_SECRET` (empty in `.env` and in `media-summarizer-runtime-dev`, so the endpoint answers 500) plus a real sandbox purchase.

No automated tests were written, per the project rule.
<!-- SECTION:NOTES:END -->
