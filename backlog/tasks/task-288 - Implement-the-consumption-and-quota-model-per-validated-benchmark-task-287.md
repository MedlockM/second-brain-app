---
id: task-288
title: Implement the consumption and quota model per validated benchmark (task-287)
status: To Do
assignee: []
created_date: '2026-08-18 04:35'
labels:
  - ingestion
  - backend
  - mobile
  - quota
  - pricing
dependencies:
  - task-287
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rebuild how ingestion consumption is metered, capped, guarded and shown to the user, following the model the owner validated in the task-287 benchmark.

**Read `docs/research/task-287-consumption-model/README.md` first.** The `Decision` field under `Owner Validation` is authoritative — not the Recommendation section, which the owner may have overridden, narrowed or replaced. If the Decision references complement files in the same directory, follow those references too. Build what the Decision says, not what this description guesses at: the shape of the work is deliberately not restated here, because the owner's answer may differ from the benchmark's recommendation.

The scope spans four layers that have to move together, whatever model is chosen:

- **Metering** — what each ingestion path debits, and in what unit.
- **Caps and tiers** — what limits exist, per tier, and how the pricing config expresses them.
- **The safety net** — what stops a runaway user, and at what threshold.
- **What the user sees** — the entitlements contract, the subscription card, the paywall copy, and the message shown when a submission is refused.

Nothing is deployed and there are no users, so the old model is deleted rather than kept alongside the new one. No dual-running counters, no compatibility shims, no deprecation window: whatever the validated model replaces should leave no trace behind it, including obsolete DynamoDB attributes, unused pricing config keys, and the `action` field that declares a throttle nothing implements.

Coordinate with the two tasks already open on the same surface. task-285 moves Instagram into audio metering and task-286 realigns the category counters; if either is still open when this starts, reconcile rather than re-litigate — this task's model supersedes both, and any of their acceptance criteria the new model makes moot should be recorded as such rather than silently dropped.

**Owner note — not an acceptance criterion**: quota enforcement only runs in the deployed API and workers, so verifying the end-to-end behaviour (consumption moving as expected across podcast, reel, YouTube and article saves, the gauge matching in the app, the wall arriving where it should) requires a merge to `main` and a deploy, plus a mobile build for the user-visible half.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The consumption model the owner validated in the task-287 README is what the enforcement path implements, in the unit that Decision names
- [ ] #2 Every ingestion path debits consumption consistently with the validated model, with no path left unmetered and none debited twice for one ingestion
- [ ] #3 The runaway-user safety net is in place at the threshold the Decision sets, and refuses before a user can cost more than their tier's net revenue
- [ ] #4 The pricing config expresses the validated caps for every tier and for the free trial, with no leftover keys from the superseded model
- [ ] #5 The API exposes exactly the consumption information the validated model requires the app to show, and no longer exposes fields the model drops
- [ ] #6 The mobile app shows the user's remaining consumption per the validated model, on the screens the benchmark identified
- [ ] #7 A refused submission tells the user which limit stopped them and what it means, in the app's language rather than a raw backend string
- [ ] #8 Everything the validated model replaces is deleted -- superseded counters, unused config keys, and the declared-but-unimplemented throttle action -- with no compatibility layer left behind
- [ ] #9 Any task-285 or task-286 acceptance criterion the new model makes moot is recorded as superseded in this task's implementation notes rather than left silently unmet
- [ ] #10 ruff and mypy are clean on the touched Python, and the mobile app typechecks
<!-- AC:END -->
