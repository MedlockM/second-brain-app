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
| `text_only_monthly_test` | `prod7e3149d970` | Test Store `appa51ecf7585` | `tier_text_only` |
| `mix_monthly_test` | `prod199b49706d` | Test Store `appa51ecf7585` | `tier_mix` |
| `audio_heavy_monthly_test` | `prodfa048c9140` | Test Store `appa51ecf7585` | `tier_audio_heavy` |

The three Test Store products stay: `mobile/.maestro/07_paywall.yaml` drives the
paywall through them via `E2E_REVENUECAT_TEST_KEY`.

The App Store app `app0d4b00c12f` (bundle `com.secondbrainlabs.core`) still
carries zero products, and no Google Play app is declared. Adding them is
`task-261` (iOS) and `task-238` (Android); both attach their products to the
entitlements above.

## Offering and packages

Current offering `default` (`ofrng2c876c3f17`), three packages, one per tier:

| Position | Lookup key | Package ID | Product |
|---|---|---|---|
| 0 | `text_only` | `pkgefd39fb892f` | `text_only_monthly_test` |
| 1 | `mix` | `pkge7df593bf70` | `mix_monthly_test` |
| 2 | `audio_heavy` | `pkge5843d287fa` | `audio_heavy_monthly_test` |

`mobile/app/paywall.tsx` matches a package to a tier card by substring on the
package or product identifier, so a package lookup key must keep containing its
tier id.

## Adding a store product

No code change. In the dashboard (or via the v2 API):

1. Import or create the product under its store app.
2. Attach it to the one tier entitlement it grants.
3. Attach it to the tier's package in the `default` offering.

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
