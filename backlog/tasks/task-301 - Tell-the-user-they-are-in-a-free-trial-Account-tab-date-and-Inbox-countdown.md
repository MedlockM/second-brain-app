---
id: task-301
title: 'Tell the user they are in a free trial: Account tab date and Inbox countdown'
status: To Do
assignee: []
created_date: '2026-08-19 20:42'
labels:
  - mobile
  - ui
  - copy
  - phase-6
dependencies:
  - task-300
  - task-299
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The app never tells a user they are in a free trial. `is_free_trial` is returned by `GET /api/v1/entitlements/status`, declared in `EntitlementStatus` (`mobile/src/contexts/PurchasesContext.tsx:37`) and read by nothing — a repo-wide grep finds no other use in `mobile/`. Consequences an owner hit on a fresh account created on 2026-08-19:

- The Account tab renders a trial exactly like a paid plan. `subscription_tier` is null during a trial, so `getTierLabel` returns null and `SubscriptionStatusCard.tsx` falls back to the heading **"Active plan"**. Nothing on the screen contains the word trial.
- The date next to it is labelled **"PERIOD ENDS"** — `getResetDateLabel` (`mobile/src/lib/subscriptionDisplay.ts`) returns that when `auto_renew_status` is null, which is always the case during a trial. It is the most ambiguous of its three labels and reads as "your access stops here", which is what the owner concluded. Combined with `task-300`, the date it points at *is* now the trial's end — so the fix is to say so, not to hide it.
- `MinutesWarningBanner.tsx` says "You've used X% of this month's minutes. They reset on <date>." During a trial, after `task-300`, those minutes do not reset at all: the trial ends. The sentence is false on that surface too.

## What to build

**Account tab.** During a trial the card identifies itself as a trial and labels the date as the trial's end rather than a period boundary or a refill. The tier it grants (`mix` → the Mix allowance) is worth stating since it is what the gauge above is measuring, but the heading must not read as a purchased plan.

**Inbox.** A small centred notice at the top of the Inbox, shown only while the trial is running, reading the remaining days — the owner's wording: `Free Trial - X days left`. Placement is the existing `ListHeader` in `mobile/app/(tabs)/inbox.tsx`, which already hosts `MinutesWarningBanner`; both must be able to appear without fighting for the same slot.

The countdown derives from `resets_at`, which after `task-300` is the trial's closing instant. The app does not know `created_at` and must not try to reconstruct the trial length: one date in, one countdown out. Decide and state in the code what the last day says — a notice reading "0 days left" while the user still has access is a bug, and so is "1 day left" for eleven more hours if the copy implies a full day.

## Constraints

- **The client decides nothing about entitlement.** Whether a trial is running is `is_free_trial` from the backend, never a date comparison the app makes to guess it; the existing header comment in `subscriptionDisplay.ts` is the rule. The countdown is presentation of a backend date, which is allowed; eligibility is not.
- Render nothing rather than guess: no notice while `entitlementStatus` is null, still loading, or errored, and none once `is_free_trial` is false (subscribed, or trial over).
- Timezone: `formatResetDate` formats in device-local time with no explicit zone, which is why a `2026-09-01T00:00Z` boundary displayed as "Aug 31" started this. A date the backend sends as an instant and the countdown derived from it must not disagree by a day on the same screen.
- `task-299` rewrites the paywall copy, including how the trial is worded there, and also touches `SubscriptionStatusCard.tsx` (its AC #9). This task runs after it and matches its vocabulary — the trial must not be called one thing on the paywall and another on Account.
- Give the Inbox notice a `testID` in the style of the neighbouring ones (`minutes-warning-banner`, `account-plan-*`) so a Maestro flow can assert it later.

## Owner notes (not acceptance criteria)

- The visual result — a *small centred* card, not a full-width banner — can only be judged on a simulator, which the implementer cannot run. Put the final copy and the component's style block in the implementation notes so it can be read without building.
- Worth checking on the owner's dev account after deploy: created 2026-08-19, so the Account tab should read 18 September and the Inbox should count down to it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Account tab card identifies a running trial as a trial instead of falling back to the 'Active plan' heading, and is_free_trial from the entitlement payload is what drives it — the field is no longer declared-but-unused in mobile/
- [ ] #2 The date shown on the Account tab during a trial is labelled as the end of the free trial, and getResetDateLabel no longer returns 'PERIOD ENDS' for a trial
- [ ] #3 A centred notice at the top of the Inbox shows 'Free Trial - X days left' while the trial runs, with X derived from the entitlement payload's resets_at and never from a locally reconstructed trial length
- [ ] #4 The remaining-days figure is never negative or zero while access is still granted, the last day of the trial reads as a true statement, and the rounding rule is stated in the component
- [ ] #5 The Inbox notice renders nothing when the entitlement status is missing, loading or errored, and disappears as soon as is_free_trial is false — a subscriber and a user past their trial both see no notice
- [ ] #6 The Inbox notice and MinutesWarningBanner can both be present without overlapping or displacing each other, and the existing greeting, digest button and section header of ListHeader are unchanged
- [ ] #7 MinutesWarningBanner no longer tells a trial user that this month's minutes 'reset on' a date, since a trial allowance does not refill
- [ ] #8 No entitlement decision is taken client-side: the app still reads tier, allowance and trial state from the backend payload and computes only display strings from them
- [ ] #9 The Inbox notice carries a testID consistent with the existing ones so it is assertable from Maestro
- [ ] #10 cd mobile && npm run typecheck && npm run lint are clean
<!-- AC:END -->
