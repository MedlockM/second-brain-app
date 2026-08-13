---
id: task-262
title: >-
  Resolve subscription tier from RevenueCat entitlements and delete the product
  ID map
status: To Do
assignee: []
created_date: '2026-08-13 19:10'
updated_date: '2026-08-13 19:14'
labels:
  - phase-6
  - backend
  - revenuecat
  - iap
  - refactor
  - tech-debt
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Restructure the RevenueCat entitlement layout around one entitlement per tier, and resolve the subscription tier from entitlements only. No compatibility layer: the app has never been deployed — no customers, no production data, no active subscriptions — so there is nothing to preserve and every legacy artifact is deleted outright.

**Do this before `task-238` and `task-261`.** Both attach store products to entitlements; running them first would wire products to a layout this task then dismantles. Nothing here is blocked by them: the three Test Store products that exist today are enough to build and verify the new layout.

## Why

`PRODUCT_TIER_MAP` in `media_summarizer/api/endpoints/revenucat_webhook.py:33-42` maps raw store product IDs onto `SubscriptionTier`. It holds six entries for three tiers, because iOS and Android name products differently. That list grows combinatorially: one entry per store, per platform, per billing duration (a yearly tier doubles it), per price experiment. Every addition is a code change plus a Lambda deploy, and a product that reaches a store before the map is updated fails **silently** — `_resolve_tier` returns `None`, the handler logs `Unknown product_id, skipping` and returns, so the purchase is dropped with nothing surfacing to the user and no alarm firing.

RevenueCat's recommendation for multi-tier apps is one entitlement per access level, with the backend reading the entitlement rather than the product. The entitlement is stable across stores, platforms and durations, and adding a product becomes a dashboard operation.

## Current state in project `proj879a771a`

Everything below is legacy or scaffolding, and all of it goes:

- **Entitlements**: `pro` (`entlff2420092b`) and `Second Brain Labs Pro` (`entl753f74253d`, a lookup key with spaces, referenced by no code). All three tiers currently share `pro`, so an entitlement cannot today tell Reader from Audio-Heavy — that is exactly what this task fixes.
- **Products**: the three real ones (`text_only_monthly_test`, `mix_monthly_test`, `audio_heavy_monthly_test`) plus RevenueCat's default scaffolding `monthly` (`prod...`) and `yearly` (`prod3fabb46c59`), which no code reads.
- **Packages** in the current `default` offering (`ofrng2c876c3f17`): `text_only` (`pkgefd39fb892f`), `mix` (`pkge7df593bf70`), `audio_heavy` (`pkge5843d287fa`), plus scaffolding `$rc_monthly` (`pkge782fa50436`, position 0) and `$rc_annual` (`pkge18bce39469`, position 1). The two scaffolding packages sit ahead of the real tiers in the offering and are returned by `getOfferings()`; `paywall.tsx` ignores them only because `getTierPackage()` happens not to substring-match them.

Code touch points:

- Backend: `_resolve_tier` (`:86`) is called from `_handle_initial_purchase` (`:134`), `_handle_renewal` (`:214`) and `_handle_product_change` (`:305`, on `new_product_id`).
- Mobile: `hasActiveEntitlement` reads `customerInfo.entitlements.active["pro"]` (`mobile/src/services/purchaseService.ts:130`), feeding `isSubscribed` (`mobile/src/contexts/PurchasesContext.tsx:157`), consumed by `app/(tabs)/account.tsx:41`, `app/settings/delete-account.tsx:60` and `app/paywall.tsx:74`. It is a boolean gate only — it never reads the tier, which comes from `GET /api/v1/entitlements/status`.

## Target design

Three entitlements, one per tier, lookup keys `tier_text_only`, `tier_mix`, `tier_audio_heavy`. Align them with the config tier names of `pricing_config_service.py` rather than with the `S`/`M`/`L` enum of `billing.py:31`: the config names are what the pricing benchmark, the paywall and `_SUBSCRIPTION_TIER_TO_CONFIG` (`quota_enforcer.py:28`) already use. Each product attaches to exactly one tier entitlement.

`pro` and `Second Brain Labs Pro` are **deleted**, not kept alongside. The mobile boolean gate becomes "any of the three tier entitlements is active", so no `"pro"` string survives in `mobile/`. The scaffolding products `monthly` / `yearly` and packages `$rc_monthly` / `$rc_annual` are deleted too.

`PRODUCT_TIER_MAP` is **deleted**, along with the product-ID branch of `_resolve_tier`. No store product identifier remains in the webhook module. The tier comes from the event's entitlement identifiers, nothing else.

Verify the exact payload field against current RevenueCat webhook docs before implementing: `entitlement_ids` (array) is the current field, `entitlement_id` (singular) is legacy on older payload versions — handle both shapes, since that is the webhook's input contract and not an internal compatibility layer. When an event carries several tier entitlements, resolve to the highest tier: that is the safe direction for the user.

With the fallback gone, an unresolvable tier must be **loud**: log at `error` with the product ID and the entitlement IDs, replacing today's `warning`-then-`return`. This is the real defect being fixed — a dropped purchase must be visible. Wire a CloudWatch metric filter and alarm for that line only if it fits the existing pattern in `modules/platform/monitoring.tf`; otherwise note it for a follow-up rather than inventing a new alarm shape.

## Not in scope

- No data migration. `subscriptions-dev` holds a single row (tier `L`, period end 2029) that is a manual UI-testing fixture from 2026-08-02, not a purchase; `revenucat_events-dev` holds 0 items. Delete the fixture row or leave it, it gates nothing.
- No change to `GET /api/v1/entitlements/status`, to quota enforcement, or to the paywall UI beyond the entitlement gate.
- No yearly tier. This makes one cheap to add later; it does not add one.

## Downstream

`task-238` (Android) and `task-261` (iOS) both carry an acceptance criterion naming entitlement `pro`. Once this task lands, those criteria mean "attached to its tier entitlement" — they are updated to say so, and both tasks depend on this one.

Keep the Test Store app (`appa51ecf7585`) and its three `*_test` products: `mobile/.maestro/07_paywall.yaml` depends on them through `E2E_REVENUECAT_TEST_KEY`. They must be attached to the tier entitlements like any other product.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Three entitlements tier_text_only, tier_mix and tier_audio_heavy exist in RevenueCat project proj879a771a, verifiable via GET /v2/projects/proj879a771a/entitlements
- [ ] #2 Entitlements pro (entlff2420092b) and Second Brain Labs Pro (entl753f74253d) no longer exist in the project
- [ ] #3 Every product in the project, including the three Test Store products, is attached to exactly one tier entitlement
- [ ] #4 The scaffolding products monthly and yearly are deleted, and packages $rc_monthly and $rc_annual are removed from the default offering, leaving only text_only, mix and audio_heavy
- [ ] #5 PRODUCT_TIER_MAP and the product-ID branch of _resolve_tier are deleted: no store product identifier remains anywhere in media_summarizer/api/endpoints/revenucat_webhook.py
- [ ] #6 The webhook resolves the tier from the event entitlement identifiers, handling both the entitlement_ids array and the singular entitlement_id shape, at all three call sites: initial purchase, renewal and product change
- [ ] #7 When an event carries several tier entitlements, resolution returns the highest tier
- [ ] #8 A tier that cannot be resolved is logged at error level with both the product ID and the entitlement IDs, replacing the current warning-then-return

- [ ] #9 The mobile entitlement gate checks the three tier entitlements and no "pro" entitlement string remains under mobile/
- [ ] #10 docs/V1_LAUNCH_PLAN.md records that tier resolution is entitlement-driven, and the RevenueCat entitlement layout is documented in a file an owner can read without opening the dashboard
- [ ] #11 ruff check . and mypy media_summarizer are clean, and cd mobile && npm run typecheck && npm run lint are clean
<!-- AC:END -->
