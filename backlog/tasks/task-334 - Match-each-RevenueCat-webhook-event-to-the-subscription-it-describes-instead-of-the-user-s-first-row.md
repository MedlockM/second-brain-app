---
id: task-334
title: >-
  Match each RevenueCat webhook event to the subscription it describes, instead
  of the user's first row
status: To Do
assignee: []
created_date: '2026-09-02 07:29'
labels:
  - billing
  - revenuecat
  - backend
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Observed

The Android billing circuit ran for the first time on 2026-09-01 (two license-tester
lifecycles, 17 events in `revenucat_events-dev`, see `task-238`). Two runs of the *same*
lifecycle on the same product left `subscriptions-dev` in **two different final states**,
purely because the last two events arrived in a different order:

| Run | Order received | Final row |
|---|---|---|
| 16:54 → 17:37 | `CANCELLATION` then `EXPIRATION` | `status: expired`, `cancel_at_period_end: true` |
| 21:01 → 21:42 | `EXPIRATION` then `CANCELLATION` | `status: expired`, `cancel_at_period_end: **false**` |

RevenueCat delivers the pair within ~50 ms and does not promise an order. In run 2
`EXPIRATION` set `status: expired` first, so `_handle_cancellation` found no row in
`active`/`grace_period`, fell through its loop and logged
`CANCELLATION: no active subscription found` — a silent no-op on an event that was not
noise. That divergence is only cosmetic here (both runs end `expired`, so access is
correctly off), but it is the visible symptom of a selection rule that is wrong everywhere.

## Root cause: every handler takes the user's first matching row

All five handlers ask `get_subscriptions_by_user_id(app_user_id)` and then act on the
**first** row whose status is in a set, with no filter on the product, the store or the
subscription the event is actually about:

- `_handle_initial_purchase` (`media_summarizer/api/endpoints/revenucat_webhook.py:226-231`)
  is the worst: its predicate is `s.revenucat_app_user_id == app_user_id or s.user_id ==
  app_user_id`, which is **a tautology** — the rows were just queried by that same user id.
  So it always overwrites row #1, whatever its store, product or status.
- `_handle_renewal` (`:309-318`), `_handle_cancellation` (`:331-342`),
  `_handle_expiration` (`:350-358`), `_handle_product_change` (`:409-421`) each iterate and
  take the first row in `active` / `canceled` / `grace_period`.

### Four consequences that bite

1. **A purchase on one store destroys the row of the other.** `_handle_initial_purchase`'s
   update branch rewrites `platform`, `revenucat_product_id`, `tier` and the period on
   whatever row came first. A user holding an iOS subscription who buys on Android loses the
   iOS record — same row id, iOS data gone. It also means a user can effectively never hold
   two subscription rows, which is not a rule anybody decided.
2. **`created_at` is silently reset.** That same update branch builds a fresh
   `Subscription(...)` without passing `created_at`, so the model's
   `default_factory=now` overwrites the row's real creation date on every re-purchase.
3. **A deferred downgrade never lands, and that is a revenue leak.**
   `_handle_product_change`'s own comment (`:395-400`) states the design: on App Store and
   deferred Google Play changes the tier may still read as the outgoing one, and « the
   RENEWAL event that follows carries the new entitlement and settles the tier ».
   `_handle_renewal` resolves that tier, **logs** it (`:302`, `:320-323`) and never assigns
   `s.tier`. So the mechanism the comment relies on does not exist: a user who downgrades
   Audio-Heavy → Reader keeps 720 minutes a month while paying 3 EUR.
4. **Cross-store expiry.** An Android `EXPIRATION` can expire a user's iOS row. Not
   hypothetical: `subscriptions-dev` currently holds an `active` iOS row for user
   `4cd1abcb` with `current_period_end` in **2029**.

The same "first row wins" rule is repeated one layer up in
`media_summarizer/core/services/quota_enforcer.py:246-266`: `_active_subscription()` returns
the first row in `active`/`grace_period` (or a `canceled` one still inside its period),
which with two rows is arbitrary — and it is what decides the user's whole allowance.

## Scope

Give the handlers a real matching rule, and make the row that entitles the user a
deterministic choice rather than a scan order.

The matching key available today is `(revenucat_product_id, platform)` — the model
(`media_summarizer/core/models/billing.py:37-51`) stores no store subscription identifier,
and the event's `product_id` + `store` are what we have. `PRODUCT_CHANGE` is the case where
the product on the row is expected to differ from the event's, so it matches on the store
and on `new_product_id` falling back to the outgoing `product_id`. Adding a stable store
identifier to the row (RevenueCat sends `original_transaction_id` / the store subscription
id) is a legitimate way to make the key exact and is in scope, provided nothing is written
that needs a backfill — there is no installed base, so a new field is simply populated
going forward and the old rows on `-dev` can be deleted.

Ordering must stop mattering. `CANCELLATION` carries information (« this will not renew »)
that is still true when it arrives after `EXPIRATION`, so it must be recorded on the matched
row without resurrecting it: set `cancel_at_period_end` and `auto_renew_status`, and only
move `status` to `canceled` when the row is not already `expired`. Symmetrically an event
that matches no row of that user is an anomaly worth an ERROR log, not a `warning` nobody
reads — the project already has that pattern in `_log_tier_unresolved` and its metric filter
in `infrastructure/terraform/modules/platform/revenucat_alerts.tf`.

`_handle_initial_purchase`'s update-vs-create decision follows from the same key: an event
for a `(product, store)` the user already has updates that row and preserves its
`created_at`; anything else creates a row.

## Not in scope

The trial-versus-paid allowance rule. That is `task-335`, which builds on the deterministic
`_active_subscription()` this task delivers.

Also out of scope, but do not make it worse: **the tier catalogue is data, not code.** Prices
and allowances live in the DynamoDB `pricing_config` table and the owner will change them,
including how many tiers exist. Two hardcoded maps in this very module already stand in the way
— `ENTITLEMENT_TIER_MAP` (`:45-49`, three entitlement lookup keys) and `_TIER_RANK` (`:54`,
a fixed S/M/L ordering used by `_resolve_tier`) — and so does the `SubscriptionTier` enum
itself. Retiring them is its own task. What this task must not do is add a fourth place that
knows a tier by name: where it needs to compare two tiers, it compares the allowances the
pricing config gives them.

## Owner note

Nothing here is verifiable against the deployed dev API from a worktree — the Lambda image
is rebuilt on push to `main`, long after the implementing agent is gone. What the owner
should re-run after the deploy, on the next license-tester purchase (5-minute renewals, so
a full lifecycle costs ~40 minutes): buy a tier, change tier in Play, let it renew once, and
check that `subscriptions-dev` carries the **new** tier after the renewal, then cancel and
confirm the final row is the same whichever of `CANCELLATION` / `EXPIRATION` lands first.
The two rows currently in `subscriptions-dev` for users `07055fd9` and `039ea8cf`, and the
2029 iOS fixture row for `4cd1abcb`, are all disposable test data.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No handler in revenucat_webhook.py selects a subscription by taking the first row of the user: each one matches the row the event describes on the store and the product, and _handle_initial_purchase no longer uses a predicate that is true for every row of that user
- [ ] #2 An event whose store and product match no row of the user logs at ERROR under a named event, with the event type, the app user id, the product and the store, instead of returning silently — and that event has a metric filter next to revenucat.tier_unresolved in infrastructure/terraform/modules/platform/revenucat_alerts.tf
- [ ] #3 A purchase on one store can no longer overwrite the row of another store: a user holding an iOS row and buying on Android ends with two rows, each carrying its own platform, product, tier and period
- [ ] #4 The update branch of _handle_initial_purchase preserves the row's original created_at instead of letting the model default it to now
- [ ] #5 _handle_renewal assigns the tier it resolves to the matched row, so the deferred tier change that _handle_product_change documents actually lands on the following renewal
- [ ] #6 The final state of a subscription is identical whether CANCELLATION arrives before or after EXPIRATION: CANCELLATION records cancel_at_period_end and auto_renew_status on the matched row even when it is already expired, and never moves an expired row back to canceled
- [ ] #7 quota_enforcer._active_subscription returns a deterministic row when the user has several entitled ones — the one whose tier carries the larger allowance in the pricing config, never a ranking hardcoded in the code — rather than whichever the scan yields first, and its docstring says so
- [ ] #8 aws logs test-metric-filter against the real CloudWatch confirms the unmatched-event log line matches the pattern declared for it in revenucat_alerts.tf, and terraform validate passes on the platform module
- [ ] #9 ruff check . and mypy media_summarizer are clean
<!-- AC:END -->
