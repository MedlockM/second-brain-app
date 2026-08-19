---
id: task-299
title: 'Make the Choose Your Plan paywall exact, complete and non-redundant'
status: To Do
assignee: []
created_date: '2026-08-19 20:24'
labels:
  - mobile
  - ui
  - paywall
  - copy
  - phase-6
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The paywall (`mobile/app/paywall.tsx`, title "Choose Your Plan") is the last screen a user reads before paying, and today it states things the backend does not do, omits two facts that change which tier someone should buy, and says "reading is unlimited" five times. It has to become exactly true, complete, and say each thing once.

Source of truth for every figure below: `DEFAULT_PRICING_CONFIG` in `media_summarizer/core/services/pricing_config_service.py` (seeded into DynamoDB, editable at runtime through `PUT /api/pricing/admin`) and the conversions in `media_summarizer/core/services/quota_enforcer.py`. Both implement the validated consumption model of `docs/research/task-287-consumption-model/README.md` (`owner_decision: ok`). Where the screen and that config disagree, the config is right and the screen is wrong.

## 1. What the screen says that is false

- **"Unlimited articles, web pages and documents"** (all three cards) — documents are metered. `quota_enforcer.minutes_for_document_pages()` charges one minute per five pages (`unit_conversion.document_pages_per_minute: 5`). The card contradicts the legend printed a few lines below it ("a PDF counts a minute per five pages").
- **"Unlimited flashcards, notes and summaries"** (all three cards) — only generations over a *single item* are free. `quota_enforcer.minutes_for_collection_sources()` charges one minute per five sources for a generation over a collection, and nothing on the paywall mentions that a metered unit exists there at all.
- **"articles, web pages and short clips are free"** (`MINUTES_LEGEND`) — "short clips" is not a category the backend has. TikToks and Instagram photo posts are free whatever their length; a Reel, a short YouTube video without bought captions, or a 40-second voice note are charged their real duration rounded up to at least one minute (`minutes_for_seconds`). As written, the sentence promises free where we bill.
- **The header comment of `paywall.tsx`** asserts "Minutes are the only thing a plan limits" and "the three tiers have exactly the same features". Both are false — see item 2 — and the comment is what will keep the copy wrong after the next edit.

## 2. What the screen omits, and that changes the purchase decision

- **The longest single import differs per tier**: `max_minutes_per_item` is **60 min on Reader, 180 min on Mix, 240 min on Audio-Heavy**. Over it, the submission is refused with `item_too_long` and there is no workaround — "Split it into shorter parts" (`quota_enforcer._item_too_long_message`). Someone who buys Reader for two-hour podcasts cannot process a single one, and learns it only after paying.
- **A 30-day free trial is already live**: `free_trial` is `enabled: True`, 30 days, on the **Mix** tier with **300 min** and a 180-min per-import ceiling, granted by account age (`quota_enforcer._is_free_trial_active` — every account younger than 30 days has it, no purchase involved). The paywall never mentions it, so a user in their trial window sees three "Subscribe" buttons and no indication that they already hold Mix-level access, or when it stops. `GET /api/v1/entitlements/status` already reports `is_free_trial` and `subscription_status: "free_trial"`, so this can be stated from real state rather than as a static line that would be wrong for everyone past day 30. Note for whoever writes the copy: per `task-261`, there is deliberately **no App Store introductory offer** — the trial is server-side only, so the wording must not read as a store trial attached to a purchase.

## 3. What the screen repeats

- The allowance is printed twice per card: `tier.minutes` ("300 min (5 h)") then the first bullet ("5 hours of audio and video a month").
- Six of the nine bullets are byte-identical across the three cards, so they triple the reading length while carrying zero information about the choice being made.
- "Reading is unlimited" is stated in the subtitle, in a bullet on each of the three cards, and again in the legend — five times on one screen, plus a sixth on the Account tab.
- The subtitle quantifies Mix and Audio-Heavy and ignores Reader, which repeats two card values and makes the third tier look like an afterthought.

## 4. The same numbers are written three times in the repo

`pricing_config_service.DEFAULT_PRICING_CONFIG` (authoritative), `OFFERINGS_CONFIG` + `MINUTES_LEGEND` in `media_summarizer/api/endpoints/entitlements.py` (a hardcoded second copy, sent to the app as `offerings_config` / `minutes_legend` when the caller has no plan), and `TIER_INFO` + `MINUTES_LEGEND` in `mobile/app/paywall.tsx` (a third). The mobile app declares the payload in `mobile/src/contexts/PurchasesContext.tsx` and never reads it, and `GET /api/pricing` — public, already returning `minutes_per_month`, `max_minutes_per_item` and `free_trial` — is called by nobody. Three copies of one fact is how the screen got stale, and fixing the wording without collapsing them just resets the clock.

Nothing is deployed and there are no users: delete the copies that lose, do not keep them as fallbacks. Pick one runtime source the app reads and one place the strings live; the implementer chooses which, and states the choice in the code.

## 5. Do not break

- Store-mandated legal text (charge on confirmation, auto-renewal, 24-hour cancellation window) and **Restore Purchases** must stay. Say the renewal terms once.
- Prices on screen must keep coming from the store package (`pkg.product.priceString`) when offerings are loaded, so a localized store price is never overwritten by a hardcoded "3 EUR/mo". If a pre-load fallback remains, it must not be a second hardcoded price list.
- `mobile/.maestro/07_paywall.yaml` asserts the texts `Choose Your Plan`, `Reader`, `Mix`, `Audio-Heavy`, the absence of `Unavailable`, and the ids `paywall-screen` / `paywall-close-button`. Keep them or update the flow in the same change.
- Concision is a constraint, not a bonus: the two facts added in item 2 must be paid for by the deduplication of item 3, not stacked on top of it.

## Owner notes (not acceptance criteria)

- The visual result can only be judged on a device or simulator; the agent cannot run one. Attach the final copy for each card in the implementation notes so it can be read without building.
- The wording is what App Review reads on the subscription screen. Once this lands, re-check `docs/store-listing/app-store-connect.md` for the same claims before submitting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No claim on the paywall contradicts pricing_config_service.DEFAULT_PRICING_CONFIG or the quota_enforcer conversions: nothing that debits minutes (documents at one minute per five pages, collection-level generations at one minute per five sources, any transcribed audio or video) is described as unlimited or free anywhere on the screen
- [ ] #2 The paths presented as costing nothing are exactly the ones that debit zero minutes in quota_enforcer (articles, web pages, TikToks, Instagram photo posts, single-item generations) and the copy no longer uses the category 'short clips', which does not exist in the backend
- [ ] #3 Each tier communicates its own longest single import with the value from its tier config (60 min on Reader, 180 min on Mix, 240 min on Audio-Heavy) and says that going over it is a refusal, not an upgrade prompt
- [ ] #4 The 30-day Mix free trial is communicated from the live entitlement state returned by GET /api/v1/entitlements/status (is_free_trial / subscription_status) so the screen is true both inside and outside the trial window, and the wording does not present it as a store introductory offer
- [ ] #5 Every fact appears once on the screen: no card prints its allowance twice, no line is identical across two tier cards, the subtitle no longer restates a value already on a card, and 'reading is unlimited' is stated exactly once
- [ ] #6 The tier facts (name, monthly allowance, per-import ceiling, trial terms) reach the screen from one runtime source that the app reads, and the now-redundant copies are deleted rather than kept as fallbacks — a repo-wide grep for the figures 60, 300, 720, 180, 240 and for the prices 3/5/9 finds each tier's numbers in one authoritative place only
- [ ] #7 Prices displayed come from the store package priceString when offerings are loaded, and no second hardcoded EUR price list survives in mobile/
- [ ] #8 The store-mandated renewal and charge disclosure is present once, and the Restore Purchases action is still on the screen
- [ ] #9 The Account tab hint in mobile/src/components/SubscriptionStatusCard.tsx and the refusal messages in quota_enforcer state the same rules in the same words as the new paywall copy, with no claim on one surface that the other contradicts
- [ ] #10 The total user-visible character count of the paywall copy does not exceed today's, and the implementation notes record the before/after figures
- [ ] #11 mobile/.maestro/07_paywall.yaml still matches the screen (texts Choose Your Plan, Reader, Mix, Audio-Heavy, absence of Unavailable, ids paywall-screen and paywall-close-button) or is updated in the same change
- [ ] #12 cd mobile && npm run typecheck && npm run lint are clean, and if any Python file was touched, ruff check . and mypy media_summarizer are clean too
- [ ] #13 The header comment of mobile/app/paywall.tsx no longer claims the three tiers have identical features and records where the plan figures now come from
<!-- AC:END -->
