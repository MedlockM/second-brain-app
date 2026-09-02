# RevenueCat entitlement layout

The live layout of RevenueCat project `proj879a771a`, so it can be read without
opening the dashboard. Restructured by `task-262` on 2026-08-13.

**One entitlement per subscription tier.** The backend reads the tier from the
entitlement identifiers carried by the webhook event, never from the store
product ID. An entitlement is stable across stores, platforms and billing
durations, so shipping a new store product is a dashboard operation with no code
change and no Lambda deploy.

## Entitlements

| Lookup key | Display name | Entitlement ID | Backend tier | Pricing config tier |
|---|---|---|---|---|
| `tier_text_only` | Reader (text only) | `entlc5a41cba3a` | `S` | `text_only` |
| `tier_mix` | Mix | `entlde3fb9eb65` | `M` | `mix` |
| `tier_audio_heavy` | Audio-Heavy | `entlfa93d44749` | `L` | `audio_heavy` |

The lookup keys mirror the tier ids of
`media_summarizer/core/services/pricing_config_service.py`, which are also what
`quota_enforcer._SUBSCRIPTION_TIER_TO_CONFIG` maps the `S`/`M`/`L` enum onto.
Three places must agree on these three strings, and nothing else has to:

- `ENTITLEMENT_TIER_MAP` in `media_summarizer/api/endpoints/revenucat_webhook.py`
- `TIER_ENTITLEMENT_IDS` in `mobile/src/services/purchaseService.ts`
- the entitlement lookup keys in the dashboard

## Products

Every product is attached to exactly one tier entitlement.

| Store product identifier | Product ID | App | Entitlement |
|---|---|---|---|
| `com.secondbrainlabs.core.text_only_monthly` | `proda3433ca23d` | App Store `app0d4b00c12f` | `tier_text_only` |
| `com.secondbrainlabs.core.mix_monthly` | `prodd7204320b0` | App Store `app0d4b00c12f` | `tier_mix` |
| `com.secondbrainlabs.core.audio_heavy_monthly` | `prod1c519e5d72` | App Store `app0d4b00c12f` | `tier_audio_heavy` |
| `text_only_monthly:monthly` | `prod8f49b59dbe` | Play Store `appb253c0f75a` | `tier_text_only` |
| `mix_monthly:monthly` | `prod4f6a12db3f` | Play Store `appb253c0f75a` | `tier_mix` |
| `audio_heavy_monthly:monthly` | `proda57a23a69e` | Play Store `appb253c0f75a` | `tier_audio_heavy` |
| `text_only_monthly_test` | `prod7e3149d970` | Test Store `appa51ecf7585` | `tier_text_only` |
| `mix_monthly_test` | `prod199b49706d` | Test Store `appa51ecf7585` | `tier_mix` |
| `audio_heavy_monthly_test` | `prodfa048c9140` | Test Store `appa51ecf7585` | `tier_audio_heavy` |

The three Test Store products stay: `mobile/.maestro/07_paywall.yaml` drives the
paywall through them via `E2E_REVENUECAT_TEST_KEY`.

The three App Store products were created by `task-261` (2026-08-13) with the
identifiers frozen by `docs/research/task-65-pricing-v1-benchmark/README.md`
(3 / 5 / 9 EUR per month). They read back with `subscription.duration: null`,
because `app_store_connect_api_key_configured` is still `false` on
`app0d4b00c12f`: RevenueCat holds the identifier but has never read the
subscription from App Store Connect. Two owner steps close that gap — create the
three subscriptions in App Store Connect and upload the App Store Connect API
key to RevenueCat — and neither needs a code change: the identifiers and the
package lookup keys already match. Checklist:
`docs/V1_LAUNCH_PLAN.md` Phase 6, item 3.

**They come in that order, and the App Store side is genuinely empty.** Queried
against the App Store Connect API on 2026-09-02 with the Admin key: the app record
`6778072060` has **zero** `subscriptionGroups` and zero `inAppPurchasesV2`. So there
is nothing for the ASC API key to read yet, and uploading it first would change
nothing — create the subscriptions, then upload the key.

**`app0d4b00c12f` is missing one iOS key, not both.** The *In-App Purchase* key —
the one that validates StoreKit transactions — is already uploaded:
`subscription_key_configured: true` (read back 2026-09-02). It is the *App Store
Connect API* key that is absent, and that one only gates catalogue reads and the
dashboard's `Could not check` status. A missing ASC API key is therefore not what
would make an iOS purchase fail; a missing subscription in App Store Connect is,
because StoreKit resolves no product at all. The same distinction, with the three
`.p8` files that carry it: `mobile/MOBILE_CI_CD.md` § 4.

None of this blocks distribution. The iOS `1.0.0 (2)` build reached TestFlight on
2026-09-02 and a beta tester used it with the catalogue in exactly this state — the
paywall is the only screen that needs a store product.

The Google Play app `appb253c0f75a` (package `com.secondbrainlabs.core`, added
2026-08-20) carries its three products since 2026-09-01, and its service account
credentials read `Valid credentials`. The one thing that had been missing was an
artifact: a package name only becomes visible to the Google Play Developer API
once a signed bundle carrying that `applicationId` has been uploaded to a test
track, so creating the app in Play Console was not enough.

**A Play store identifier is `subscriptionId:basePlanId`.** The three Play
subscriptions each carry one activated monthly base plan named `monthly`, hence
the `:monthly` suffix in the table above. RevenueCat's docs only say « you will
need to add both the subscription ID and the base plan ID » without showing the
separator, so the products were brought in through the dashboard's **Import
Products** rather than typed; the import produced that form. Play caps a product
ID at 40 characters, which is why the Play subscription IDs are the bare tier
names and not the reverse-DNS iOS ones — `com.secondbrainlabs.core.text_only_monthly`
is 42 characters. Nothing in the code reads a store product identifier, so the two
stores carrying different identifiers costs nothing.

## Offering and packages

Current offering `default` (`ofrng2c876c3f17`), three packages, one per tier.
Each package holds one product per store, which is how one offering serves the
App Store and the Test Store from a single set of lookup keys:

| Position | Lookup key | Package ID | App Store product | Play Store product | Test Store product |
|---|---|---|---|---|---|
| 0 | `text_only` | `pkgefd39fb892f` | `com.secondbrainlabs.core.text_only_monthly` | `text_only_monthly:monthly` | `text_only_monthly_test` |
| 1 | `mix` | `pkge7df593bf70` | `com.secondbrainlabs.core.mix_monthly` | `mix_monthly:monthly` | `mix_monthly_test` |
| 2 | `audio_heavy` | `pkge5843d287fa` | `com.secondbrainlabs.core.audio_heavy_monthly` | `audio_heavy_monthly:monthly` | `audio_heavy_monthly_test` |

The SDK only ever returns the product matching the store it was configured for,
so the Test Store path the Maestro paywall flow drives is untouched by the App
Store products sitting in the same packages. Symmetrically, until the three
subscriptions exist in App Store Connect, StoreKit resolves none of them and an
iOS build configured with the real iOS SDK key gets an offering whose packages
have no purchasable product — which was already the case when those packages held
Test Store products only.

`mobile/app/paywall.tsx` matches a package to a tier card by substring on the
package or product identifier, so a package lookup key must keep containing its
tier id.

An offering that resolves no purchasable product is therefore the *normal* state
of an iOS build today, and the paywall treats it as such rather than as a
failure: it still describes every plan from `GET /api/pricing` — allowance,
per-import ceiling, everything included — and only switches off the prices, the
selection and the purchase button, since a price may come from the store or not
at all. The screen logs `[Paywall] No purchasable tier` with the identifiers the
store did return, which separates the two causes: zero packages means the SDK
key is missing or the offering is empty, while packages whose identifiers carry
no tier id means the store products are named something the pricing config does
not know.

Where the SDK keys come from, since none of them is in `mobile/eas.json`: the
iOS one lives in `mobile/.env`, which is gitignored, so a local build reads it
and an EAS cloud build does not; the Maestro job injects the Test Store key
through the environment and never reads `eas.json` either, building with
`expo prebuild` + `xcodebuild`. The Android key is the exception since
2026-09-01: the real `goog_` key is set in the three EAS environments
(`production`, `preview`, `development`), so a cloud build resolves it. That
matters more than it looks — the `internal` build profile resolves the
`production` environment, and `EXPO_PUBLIC_*` values are inlined at build time,
so every AAB produced before that date carried the literal string
`your_revenucat_google_api_key_here` and could not have resolved an offering
whatever the dashboard said.

## Adding a store product

No code change. In the dashboard, or with these three v2 API calls (bearer token
= `REVENUCAT_API_KEY` from the root `.env`, never written down anywhere):

1. `POST /v2/projects/proj879a771a/products`
   — `{"app_id": "<store app>", "store_identifier": "<store product id>", "type": "subscription", "display_name": "…"}`
2. `POST /v2/projects/proj879a771a/entitlements/<entitlement>/actions/attach_products`
   — `{"product_ids": ["<product>"]}`, the one tier entitlement it grants.
3. `POST /v2/projects/proj879a771a/packages/<package>/actions/attach_products`
   — `{"products": [{"product_id": "<product>", "eligibility_criteria": "all"}]}`,
   the tier's package in the `default` offering.

Step 1 succeeds even when the product does not exist in the store yet: RevenueCat
records the identifier and reconciles it with the store later. So the wiring can
be done before the store metadata is ready, and the store side is what has to
catch up.

The backend picks the tier up from the entitlement on the next event.

## When a tier cannot be resolved

If an event carries no known tier entitlement, the webhook logs
`revenucat.tier_unresolved` at ERROR with the product ID, the entitlement IDs and
the app user ID, and drops the event (`INITIAL_PURCHASE`, `PRODUCT_CHANGE`) or
extends the period without touching the tier (`RENEWAL`). The metric filter and
alarm are in
`infrastructure/terraform/modules/platform/revenucat_alerts.tf`; the alarm is
gated on `enable_alarms`, which is off in dev, so in dev the metric and the log
are the signal.

In practice it means one thing: a product reached a store without being attached
to its tier entitlement. The fix is step 2 above, no deploy involved.

## Which subscription an event applies to (task-334)

A user holds **one `subscriptions` row per store and per product**, so every
webhook handler resolves which row the event describes before writing anything.
Until task-334 they all took the user's *first* row, which let an Android purchase
overwrite an iOS row's platform, product and period, and let an Android expiry
close an iOS subscription.

The match uses three keys, sharpest first
(`_match_subscription` in `media_summarizer/api/endpoints/revenucat_webhook.py`):

1. `original_transaction_id` — the store's own subscription identifier, stored on
   the row as `revenucat_store_subscription_id` and refreshed from every event
   that carries one, since Google Play issues a new purchase token when a
   subscription is replaced. `transaction_id` is deliberately never used: it
   changes on every renewal, so it names a payment, not a subscription.
2. the `(platform, product)` pair, `platform` being what `_get_platform` maps the
   event's `store` to.
3. for `PRODUCT_CHANGE` only, the *outgoing* `product_id` — that is the one event
   whose product is expected not to match the row yet.

Two consequences worth knowing when reading a row:

- **Event order does not matter.** RevenueCat delivers `CANCELLATION` and
  `EXPIRATION` within milliseconds and promises no order, so `CANCELLATION`
  writes `cancel_at_period_end` and `auto_renew_status` whatever the row's status
  and only moves `status` to `canceled` when the row is not already `expired`.
  `RENEWAL` is the only event allowed to bring an expired row back — it is the
  only one that means money moved for a new period.
- **`RENEWAL` settles the tier.** A downgrade on the App Store, or a deferred one
  on Google Play, still reports the outgoing tier on `PRODUCT_CHANGE`; the
  following `RENEWAL` carries the new entitlement and assigns it.

An event matching none of the user's rows logs `revenucat.subscription_unmatched`
at ERROR with the event type, the app user ID, the product, the store and how many
rows that user has, and is alarmed beside the tier one in `revenucat_alerts.tf`.
Zero rows means the `INITIAL_PURCHASE` never landed (look for a
`revenucat.tier_unresolved` before it); rows present means they carry another
product than the one the store is talking about.

When several rows still entitle the user, the one that decides their allowance is
the one whose tier carries the larger allowance **in the pricing config**
(`quota_enforcer._active_subscription`) — never a ranking written in the code, so
moving an allowance in the `pricing_config` table moves that choice with it.

## Deleted by task-262

Nothing read any of this, and nothing had ever been purchased through it — the
app has never shipped, `revenucat_events-dev` held zero items.

- Entitlement `pro` (`entlff2420092b`). All three tiers shared it, so an
  entitlement could not tell Reader from Audio-Heavy.
- Entitlement `Second Brain Labs Pro` (`entl753f74253d`), a lookup key with
  spaces referenced by no code.
- RevenueCat's default scaffolding products `monthly` (`prodfc786e8210`) and
  `yearly` (`prod3fabb46c59`).
- Its scaffolding packages `$rc_monthly` (`pkge782fa50436`) and `$rc_annual`
  (`pkge18bce39469`), which sat at positions 0 and 1 of the `default` offering,
  ahead of the real tiers, and were returned by `getOfferings()`.
- `PRODUCT_TIER_MAP` in the webhook module: six store product IDs for three
  tiers, one entry per store x platform x duration, which dropped any purchase
  whose product was not in the map.

There is no yearly tier. Adding one is now one product plus one package attached
to an existing entitlement.
