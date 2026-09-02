---
id: task-335
title: Never let a paid subscription grant less than the running free trial
status: To Do
assignee: []
created_date: '2026-09-02 07:29'
labels:
  - billing
  - quota
  - backend
dependencies:
  - task-334
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Observed

`media_summarizer/core/services/quota_enforcer.py:330-338` consults the free trial **only**
when there is no active subscription:

```python
subscription = await _active_subscription(user_id)
trial_window = await _free_trial_window(user_id, config) if subscription is None else None
if subscription is not None:
    ...  # the paid tier wins, with no comparison
```

So a paid tier replaces the trial's allowance instead of being compared to it.

**Every figure below is the state of the pricing config on 2026-09-02, read from DynamoDB
`pricing_config` (seeded from `pricing_config_service.py:42-89`). It is an illustration of the
defect, never an input to the fix — see « Nothing about a tier belongs in the code ».**

| | minutes per period | max per import |
|---|---|---|
| Free trial (30 days, tier `mix`) | 300 | 180 min |
| Reader / `text_only` bought at 3 EUR | **60** | **60 min** |

A user inside their first 30 days who buys Reader pays 3 EUR to **lose 240 minutes** and to
lose the ability to import anything longer than one hour. `mobile/app/paywall.tsx` makes it
easy to walk into: the Reader card sits directly above the one labelled « VOTRE FORMULE
D'ESSAI ». Reader happens to be the only tier currently below the trial, which is why nobody
hit this yet: both manual Android purchases on 2026-09-01 were Audio-Heavy, on accounts inside
their trial window.

## Decision (owner, 2026-09-02): `max(trial, paid)`

While the trial window is still open, the allowance is the better of the two, so buying a
plan can never take anything away.

The rule, precisely:

- `minutes_included` and `max_minutes_per_item` are each the maximum of the paid tier's value
  and the trial's, taken **independently**. Independently and not "the better tier wholesale"
  because the two numbers answer different questions and the user should never lose on either
  axis; with the current config both approaches coincide, and the independent form stays right
  if a future tier is better on one axis only.
- The trial's side of the comparison resolves exactly as the trial branch already does
  (`:370-379`): the `free_trial` keys first, its tier's config as fallback.
- The comparison applies only while `_is_free_trial_active()` holds. When the window closes,
  the paid tier stands alone — so a Reader subscriber's allowance drops 300 → 60 and 180 → 60
  on the trial's end date. That is the intended consequence of the decision, not a defect, and
  the snapshot has to carry enough for the app to explain it rather than look broken.
- `subscription_tier`, `subscription_status` and `tier` keep describing the **paid**
  subscription. The user did buy Reader; relabelling them Mix would be a lie, and the account
  screen reads those fields. What changes is the allowance and the fact that the trial is what
  is raising it.
- The billing period stays the subscription's: `period_key = sub:<period_end>` and
  `period_end = current_period_end`. Not the trial's window, because that is the period the
  user keeps after the trial closes, and switching keys mid-flight would hand out a second
  helping of minutes — the exact thing `_trial_period_key`'s docstring is written to prevent.

Two consequences of that last point, both accepted, both worth writing down so the next
reader does not "fix" them:

- Inside the trial window, a Reader subscriber gets 300 minutes **per subscription period**
  rather than 300 once. Bounded by at most 30 days, and generous in the user's favour.
- A user who has already spent trial minutes and then subscribes starts a fresh counter,
  because the period key changes. That is today's behaviour and this task does not alter it.

## Nothing about a tier belongs in the code

Owner constraint, 2026-09-02: **tiers will change** — prices, allowances, how many there are,
whether a given one still exists. The tier catalogue lives in the DynamoDB `pricing_config`
table (`pricing_config_service.get_pricing_config()`, 5-minute TTL, written by
`update_config_values()`), so a price or an allowance is a data edit with no deploy. Code this
task adds must not take that away.

Concretely, the rule is a comparison between two config-derived pairs of numbers and nothing
else. Not allowed anywhere in what this task writes:

- a tier id (`text_only`, `mix`, `audio_heavy`), a tier display name, a price or a minute figure;
- a branch on which tier is being compared, or on how many tiers exist;
- an assumption that the tiers are ordered, that the trial's tier is the middle one, or that
  exactly one tier sits below the trial.

Three degradations the rule must survive, because each becomes possible the day a tier moves:

- `free_trial.tier` names a tier that no longer exists in `tiers` — the trial contributes
  whatever `free_trial` states directly, and no allowance is invented.
- A stored subscription carries a tier the config no longer describes. Today
  `quota_enforcer.py:338` reads `SUBSCRIPTION_TIER_TO_CONFIG.get(subscription_tier, "mix")`:
  an unknown tier silently becomes **Mix**, so a subscriber whose tier was retired would be
  handed a stranger's allowance without a single log line. That default sits on the exact line
  this task rewrites, so it is fixed here: an unresolvable tier is an ERROR, and the user is
  treated as un-entitled rather than as an arbitrary tier.
- `tiers` holds more or fewer entries than three.

## Cost, and how to avoid paying it

`_free_trial_window()` reads the user row (`database_async.get_user_by_id`), a read currently
skipped for every subscriber. Making it unconditional would add one `GetItem` to every
entitlement check — and `get_entitlement_snapshot()` is on the path of every import and every
paywall render.

It is avoidable, and without naming a single tier: the trial can only ever raise the allowance
when the paid tier is below it on at least one axis. Compare the paid tier's two numbers with
the trial's first — both come from the pricing config, already in memory — and only look the
trial window up when that comparison says it could matter. Which tiers that spares is then
whatever the config happens to say, and it changes on its own when the config does.

## Not in scope

- The paywall's presentation. Whether the app should keep offering Reader to a user whose
  trial already gives more is a product question, and after this task the answer costs the
  user nothing. Any mobile copy explaining the end-of-trial drop is a separate task.
- Which subscription row entitles the user when there are several. That is `task-334`, which
  this task depends on: it makes `_active_subscription()` return the highest entitled tier
  deterministically, and this rule reads whatever that returns.

## Owner note

Not verifiable against the deployed dev API from a worktree. After the deploy, the check is
three minutes on a license tester: read `GET /api/v1/entitlements/status` on an account still
inside its 30 days (expect `subscription_status: free_trial`, 300, 180), buy **Reader**, read
again — the allowance must stay 300 / 180 while `subscription_tier` reads the Reader tier —
then confirm an import between 60 and 180 minutes is still accepted. Accounts `07055fd9`
(created 2026-09-01) and `039ea8cf` (created 2026-08-19) are both inside their window; on the
second the trial closes around 2026-09-18.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 get_entitlement_snapshot no longer makes the free trial conditional on there being no subscription: a subscriber inside the trial window gets minutes_included and max_minutes_per_item as the maximum of the paid tier's value and the trial's, each compared independently
- [ ] #2 The trial side of the comparison resolves the same way as the trial branch already does — the free_trial config keys first, the trial tier's config as fallback — from one code path rather than two copies of that resolution
- [ ] #3 Once the trial window has closed the paid tier stands alone, with no trace of the trial in the allowance
- [ ] #4 tier, subscription_tier and subscription_status keep describing the paid subscription, and the snapshot exposes that the running trial is what is raising the allowance, so the app can explain the drop on the trial end date
- [ ] #5 period_key stays the subscription's sub:<period_end> and period_end stays current_period_end for a subscriber, whether or not the trial is raising the allowance, so no second allowance is handed out mid-window
- [ ] #6 The trial window is not looked up for subscribers whose paid tier already matches or beats the trial on both axes, so the entitlement path gains no GetItem for them, and which tiers those are is decided by the config at read time and by nothing written in the code
- [ ] #7 No tier id, tier name, price or minute figure appears in the code this task adds, and nothing branches on which tier is being compared, on how many tiers exist, or on the tiers being ordered
- [ ] #8 The rule holds when free_trial.tier names a tier absent from tiers (the trial contributes what free_trial states, no allowance is invented) and when tiers holds a number of entries other than three
- [ ] #9 A subscription whose tier the pricing config no longer describes no longer resolves to a hardcoded tier: the SUBSCRIPTION_TIER_TO_CONFIG.get(..., "mix") default is gone, the case logs at ERROR, and the user is treated as un-entitled rather than as an arbitrary tier
- [ ] #10 The docstring of the function that applies the rule states it as max(trial, paid), says the allowance drops when the window closes, and records that a subscriber inside the window gets the trial allowance per subscription period rather than once
- [ ] #11 ruff check . and mypy media_summarizer are clean
<!-- AC:END -->
