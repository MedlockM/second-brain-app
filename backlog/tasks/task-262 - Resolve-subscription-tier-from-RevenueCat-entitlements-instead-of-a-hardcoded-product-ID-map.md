---
id: task-262
title: >-
  Resolve subscription tier from RevenueCat entitlements instead of a hardcoded
  product ID map
status: To Do
assignee: []
created_date: '2026-08-13 19:10'
labels:
  - phase-6
  - backend
  - revenuecat
  - iap
  - refactor
  - tech-debt
dependencies:
  - task-238
  - task-261
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace the product-ID-to-tier lookup in the RevenueCat webhook with entitlement-based resolution, so adding a product becomes a dashboard operation instead of a backend deployment.

## Why

`PRODUCT_TIER_MAP` in `media_summarizer/api/endpoints/revenucat_webhook.py:33-42` maps raw store product IDs onto `SubscriptionTier`. It currently holds six entries for three tiers, because iOS and Android name products differently. That list grows combinatorially: one entry per store, per platform, per billing duration (a yearly tier doubles it), and per price experiment. Every addition is a code change plus a Lambda deploy, and a product that reaches the store before the map is updated fails **silently** — `_resolve_tier` returns `None` and the handler logs `Unknown product_id, skipping` then returns, so the purchase is dropped without any error surfacing to the user or an alarm firing.

RevenueCat's own recommendation for multi-tier apps is one entitlement per access level, with the backend reading the entitlement rather than the product. The entitlement is stable across stores, platforms and durations.

## Current state

- Entitlements in project `proj879a771a`: `pro` (`entlff2420092b`) and a legacy `Second Brain Labs Pro` (`entl753f74253d`, lookup key with spaces, unused by code).
- All three tiers share the single `pro` entitlement, so an entitlement alone cannot currently tell Reader from Audio-Heavy — this task is what makes the entitlement carry the tier.
- Backend: `_resolve_tier` (`:86`) is called from three places — `_handle_initial_purchase` (`:134`), `_handle_renewal` (`:214`) and `_handle_product_change` (`:305`, on `new_product_id`).
- Mobile: `hasActiveEntitlement` reads `customerInfo.entitlements.active["pro"]` (`mobile/src/services/purchaseService.ts:130`), feeding `isSubscribed` (`mobile/src/contexts/PurchasesContext.tsx:157`), consumed by `app/(tabs)/account.tsx`, `app/settings/delete-account.tsx` and indirectly `app/paywall.tsx`. It is a boolean gate only — it never reads the tier, which comes from `GET /api/v1/entitlements/status`.

## Target design

Create three entitlements whose lookup keys map one-to-one onto `SubscriptionTier` (`billing.py:31`, values `S`/`M`/`L`) and onto the config tiers in `pricing_config_service.py` (`text_only`/`mix`/`audio_heavy`, already bridged by `_SUBSCRIPTION_TIER_TO_CONFIG` in `quota_enforcer.py:28`). Suggested keys `tier_text_only`, `tier_mix`, `tier_audio_heavy` — keep them aligned with the config tier names rather than with the S/M/L enum, since the config names are what the pricing benchmark and the paywall already use.

Resolution order in the webhook: read the event's entitlement identifiers first, fall back to the product ID map second. Do **not** delete `PRODUCT_TIER_MAP` — keep it as the fallback so a purchase is never dropped if a product reaches a store before its entitlement is attached. Verify the exact payload field against current RevenueCat webhook docs before implementing: `entitlement_ids` (array) is the current field and `entitlement_id` (singular) is legacy, so handle both. When several tier entitlements appear on one event, resolve to the highest tier rather than picking the first — that is the safe direction for the user.

Keep `pro` in place and keep attaching products to it: it is what the mobile boolean gate reads, and detaching it would silently unsubscribe every existing customer. The tier entitlements are additive.

Make the unresolvable case loud instead of silent: when neither the entitlements nor the fallback map resolve a tier, log at `error` with the product ID and the entitlement IDs. Wiring a CloudWatch metric filter and alarm for that line is in scope only if it fits the existing pattern in `modules/platform/monitoring.tf`; otherwise note it for a follow-up rather than inventing a new alarm shape.

## Not in scope

- No data migration of `subscriptions-dev`: rows already store a resolved `tier`, and readers go through that field, not through the product ID.
- No change to `GET /api/v1/entitlements/status`, to quota enforcement, or to the paywall UI.
- No yearly tier. This task makes one cheap to add later; it does not add one.

## Ordering note

Depends on `task-238` and `task-261` deliberately, though nothing in it is technically blocked by them. Both tasks attach store products to entitlement `pro`; doing the entitlement restructure first would mean attaching every product twice and would make their acceptance criteria stale. This is acknowledged V1 debt, not a launch blocker — the six-entry map is functional for three monthly products.

## OWNER NOTE

LAUNCH PREREQUISITE, after this merges and `main` is pushed: on the next real sandbox purchase, confirm `subscriptions-dev` carries the tier resolved from the entitlement path by checking the API log line, not just that a row exists. A row written by the fallback map is indistinguishable from one written by the entitlement path in the table itself.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Three tier entitlements exist in RevenueCat project proj879a771a, one per SubscriptionTier, verifiable via GET /v2/projects/proj879a771a/entitlements, and each store product is attached to exactly one of them
- [ ] #2 Entitlement pro (entlff2420092b) still exists and still carries every store product, so the mobile boolean gate and existing customers are unaffected
- [ ] #3 The webhook resolves the tier from the event entitlement identifiers, handling both the entitlement_ids array and the legacy singular entitlement_id field, for all three call sites in revenucat_webhook.py: initial purchase, renewal and product change
- [ ] #4 PRODUCT_TIER_MAP is retained as an explicit fallback and the code documents that ordering, so a purchase is never dropped when an entitlement is missing
- [ ] #5 When an event carries several tier entitlements, resolution returns the highest tier
- [ ] #6 A tier that resolves through neither entitlements nor the fallback map is logged at error level with both the product ID and the entitlement IDs, instead of the current warning-then-return
- [ ] #7 docs/V1_LAUNCH_PLAN.md records that tier resolution is entitlement-driven, and the RevenueCat entitlement layout is documented in a file an owner can read without opening the dashboard
- [ ] #8 ruff check . and mypy media_summarizer are clean, and cd mobile && npm run typecheck && npm run lint are clean
<!-- AC:END -->
