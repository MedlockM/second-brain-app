---
id: task-262
title: >-
  Resolve subscription tier from RevenueCat entitlements and delete the product
  ID map
status: Done
assignee: []
created_date: '2026-08-13 19:10'
updated_date: '2026-08-13 22:07'
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
- [x] #1 Three entitlements tier_text_only, tier_mix and tier_audio_heavy exist in RevenueCat project proj879a771a, verifiable via GET /v2/projects/proj879a771a/entitlements
- [x] #2 Entitlements pro (entlff2420092b) and Second Brain Labs Pro (entl753f74253d) no longer exist in the project
- [x] #3 Every product in the project, including the three Test Store products, is attached to exactly one tier entitlement
- [x] #4 The scaffolding products monthly and yearly are deleted, and packages $rc_monthly and $rc_annual are removed from the default offering, leaving only text_only, mix and audio_heavy
- [x] #5 PRODUCT_TIER_MAP and the product-ID branch of _resolve_tier are deleted: no store product identifier remains anywhere in media_summarizer/api/endpoints/revenucat_webhook.py
- [x] #6 The webhook resolves the tier from the event entitlement identifiers, handling both the entitlement_ids array and the singular entitlement_id shape, at all three call sites: initial purchase, renewal and product change
- [x] #7 When an event carries several tier entitlements, resolution returns the highest tier
- [x] #8 A tier that cannot be resolved is logged at error level with both the product ID and the entitlement IDs, replacing the current warning-then-return

- [x] #9 The mobile entitlement gate checks the three tier entitlements and no "pro" entitlement string remains under mobile/
- [x] #10 docs/V1_LAUNCH_PLAN.md records that tier resolution is entitlement-driven, and the RevenueCat entitlement layout is documented in a file an owner can read without opening the dashboard
- [x] #11 ruff check . and mypy media_summarizer are clean, and cd mobile && npm run typecheck && npm run lint are clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
All 11 ACs done. The RevenueCat side was applied live through the v2 REST API
(key read from the untracked root `.env` as an env var, never written anywhere).

### RevenueCat project `proj879a771a` (AC #1-#4)

Created, then verified by `GET`:

| Lookup key | Entitlement ID | Attached product |
|---|---|---|
| `tier_text_only` | `entlc5a41cba3a` | `prod7e3149d970` (`text_only_monthly_test`) |
| `tier_mix` | `entlde3fb9eb65` | `prod199b49706d` (`mix_monthly_test`) |
| `tier_audio_heavy` | `entlfa93d44749` | `prodfa048c9140` (`audio_heavy_monthly_test`) |

Deleted, in this order (packages before their products, products before the old
entitlements): packages `pkge782fa50436` (`$rc_monthly`) and `pkge18bce39469`
(`$rc_annual`), products `prodfc786e8210` (`monthly`) and `prod3fabb46c59`
(`yearly`), entitlements `entlff2420092b` (`pro`) and `entl753f74253d`
(`Second Brain Labs Pro`). All returned `HTTP 200`.

Re-read afterwards: the project holds exactly 3 entitlements, 3 products (all
Test Store `appa51ecf7585`, each on exactly one entitlement), and offering
`default` (`ofrng2c876c3f17`) holds exactly 3 packages — `text_only` /
`mix` / `audio_heavy`, which slid to positions 0/1/2 once the scaffolding
packages ahead of them were gone.

### Webhook (AC #5-#8)

`PRODUCT_TIER_MAP` and the product-ID `_resolve_tier` are gone.
`grep -E "com\.secondbrainlabs|monthly|yearly|_test"` on
`media_summarizer/api/endpoints/revenucat_webhook.py` returns nothing.

`_resolve_tier(event)` now maps `ENTITLEMENT_TIER_MAP` over
`_entitlement_ids(event)` and returns `max` by `_TIER_RANK`, so several tier
entitlements resolve to the highest one. `_entitlement_ids` reads both
`entitlement_ids` (array) and `entitlement_id` (string) and de-dupes; the field
names were checked against the current RevenueCat webhook reference, which lists
`entitlement_ids` as an Array and `entitlement_id` as "Deprecated. See
entitlement_ids", both marked Always present.

Unresolvable tier: structured `log_event(..., logging.ERROR,
"revenucat.tier_unresolved", ...)` carrying `revenucat_product_id`,
`revenucat_entitlement_ids`, `revenucat_event_type` and `app_user_id`.

One deliberate asymmetry at the three call sites. `INITIAL_PURCHASE` and
`PRODUCT_CHANGE` write the tier onto the subscription row, where it is a required
field, so they log and return. `RENEWAL` never writes the tier — it only extends
the period — so it logs and *keeps going*: refusing to extend a period the user
has just paid for because of a dashboard misconfiguration would cost them access
for no reason. That is the `return` the AC asked to remove, removed where removing
it is possible.

Also noted in the `_handle_product_change` comment: on App Store and deferred
Google Play changes the switch takes effect at the next renewal, so the event's
entitlements may still report the outgoing tier; the following `RENEWAL` carries
the new entitlement and settles it. `new_product_id` is still recorded on the row
for traceability, it is just no longer what the tier is read from.

### Mobile (AC #9)

`hasActiveEntitlement` now tests the exported `TIER_ENTITLEMENT_IDS` triple.
`grep -rniE "entitlement[s]?[.\["' ]*pro"` under `mobile/` (excluding
`node_modules`, `ios/`, `android/`) returns nothing. Nothing else under `mobile/`
was touched — a parallel agent held the share-intent files.

### Observability

The alarm fits the existing pattern, so it was wired rather than deferred. Note
that the `modules/platform/monitoring.tf` named in the description does not
exist; the pattern actually lives in `durable_media_alerts.tf` (metric filter
over the structured JSON log event, alarm gated on `var.enable_alarms`), and
`revenucat_alerts.tf` copies it exactly, on the API log group only since the
webhook only runs there. `terraform validate` and `terraform fmt -check` clean;
`terraform plan` on `envs/dev` is `1 to add, 0 to change, 0 to destroy` — the
metric filter alone, the alarm being gated off in dev.

The alarm could therefore not be driven to `ALARM` and back to `OK`: with
`enable_alarms = false` in dev it has `count = 0` and does not exist to be
driven. It will materialise on the first `prod` apply with alarms on.

### Gates (AC #11)

`ruff check .` all checks passed. `mypy media_summarizer` no issues in 164 files.
`npm run typecheck` clean. `npm run lint` exit 0 — 10 pre-existing warnings, 0
errors, none from this change (`purchaseService.ts:89` is the untouched
`error: any` of `purchasePackage`).

### Out of reach from the worktree

Deploy-dependent verification is not an AC here and stays with the owner: nothing
exercises the new code path until the branch is merged and pushed, and the
webhook still answers `500` in dev because `REVENUCAT_WEBHOOK_SECRET` is empty
(Phase 6 step 1 of `docs/V1_LAUNCH_PLAN.md`, unrelated to this task).

Downstream `task-238` (AC #4) and `task-261` (AC #3) already named the
`tier_*` entitlements and already depend on `task-262`, so neither needed
editing.

No automated tests were written, per the project rule.
<!-- SECTION:NOTES:END -->
