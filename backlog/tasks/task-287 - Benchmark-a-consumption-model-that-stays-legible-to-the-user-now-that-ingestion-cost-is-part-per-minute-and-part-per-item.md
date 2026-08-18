---
id: task-287
title: >-
  Benchmark a consumption model that stays legible to the user now that
  ingestion cost is part per-minute and part per-item
status: To Do
assignee: []
created_date: '2026-08-18 04:35'
updated_date: '2026-08-18 04:38'
labels:
  - benchmark
  - pricing
  - product
  - quota
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The whole price story rests on one number. Mix is "5h/month of transcription", Audio-Heavy is "15h/month", and audio minutes are the only quantity the app ever shows (`/api/v1/entitlements` returns `minutes_remaining` and nothing else; `SubscriptionStatusCard` displays it). That story was true when Deepgram was the only variable cost.

It is not true anymore. Apify bills **per result**, not per minute: a scraped transcript costs the same whether the video runs one minute or sixty. And Apify is not a marginal path — production logs show yt-dlp is systematically IP-blocked on Lambda ("Sign in to confirm you're not a bot"), so Apify carries effectively all YouTube traffic, while every Instagram reel spends Deepgram minutes and, on the IP-blocked branch, Apify on top. Two cost shapes now coexist, and the one the user is shown covers only part of the bill.

The obvious fix — show the minutes *and* a counter per Apify-backed source — is the one thing that must not happen. Nobody manages a budget with five dials. The user needs to answer "how much have I got left" with a glance, and that has to stay true whatever mix of podcasts, reels and articles they save. **Design for that constraint first; the accounting has to bend to it, not the other way round.**

## What the current system actually does

Five gates run before an ingestion (`quota_enforcer._evaluate_submission_allowed`): active subscription, tier audio gating, per-import duration, monthly category cap, daily rate limit, cumulative euro ceiling. Behind them:

- **Four counters**: `audio_minutes_used`, `articles_count`, `documents_count`, `youtube_count`. Only the first is ever shown to the user. Someone who saturates one of the other three is refused with no way to understand why.
- **A flat cost model**: audio is `minutes x 0.008 EUR`; **everything else is 0.005 EUR per item**, one number for a web article (free scrape), a YouTube transcript (Apify fee) and an Instagram reel (Apify + Deepgram minutes). Apify's per-result fee appears nowhere.
- **Two contradictory sources of truth for the Deepgram rate**: `providers.transcription.cost_per_minute_eur = 0.003` in the pricing config, `_AUDIO_COST_EUR_PER_MINUTE = 0.008` hardcoded in the enforcer. The task-250 owner validation separately flagged that 0.003 understates the real PAYG rate by 47%.
- **A euro ceiling set above net revenue in all three tiers**: text_only blocks at 3.50 EUR against 2.125 EUR of net revenue, mix at 6.00 against 3.542, audio_heavy at 10.00 against 6.375. Reaching the ceiling means the user has already cost more than they pay. The ceiling guarantees the loss rather than preventing it.
- **A declared throttle that does not exist**: each tier names an `action` (`throttle_5_imports_per_day`, `throttle_1_audio_per_hour`, `throttle_and_contact_owner`). The code reads it, logs it, and hard-blocks regardless. There is no throttling.

## Four accounting defects to fix or make irrelevant

These were scoped as separate tasks (task-285, task-286) and archived into this one: whatever model comes out of this benchmark must either fix them or make them meaningless. They are also evidence of how the current model fails, so treat them as inputs rather than as a to-do list.

1. **Instagram reels are transcribed by Deepgram and charged to nobody.** The enqueue passes `quota_source_platform="instagram"`, which `classify_media_type` maps to `article`, and the settlement in `deepgram_worker` then skips outright. Worse than the missing minutes: `estimate_submission_cost` returns the flat 0.005 EUR instead of `minutes x 0.008`, so a three-minute reel costing 0.024 EUR is booked at 0.005 EUR. The euro ceiling — the last line of defence — is understated by roughly 5x on every reel.
2. **The code justifies that exemption with a decision that was never taken.** The comment reads "validated task-250 decision"; the task-250 README says the opposite — Instagram is listed as `article` for the reason "no Deepgram path today — nothing to gate", adding that the duration is available "if a Deepgram path is added later". It was added later. Whatever model wins, do not inherit this reasoning.
3. **A YouTube video without captions is counted twice.** The API debits one YouTube unit at submission, then the worker debits the real minutes at its gate. One ingestion, two budgets — against a task-250 table that reads as an exclusive choice.
4. **Short video has no budget of its own.** TikTok and Instagram fall through the `article` catch-all, so the reading budget silently absorbs them and the `articles` counter no longer measures articles.

## What to answer

The mandate is the whole chain — what is metered, what is capped, what stops a runaway user, and what the user sees — not a patch on any one of them. Specifically:

1. What unit of consumption can absorb both cost shapes and still be explainable in one sentence? A single abstract unit that converts per-minute and per-item cost into one budget is the obvious candidate, but it trades honesty for simplicity and needs its conversion rates justified against real provider bills. Weigh it against the alternatives rather than assuming it.
2. What actually separates Mix from Audio-Heavy once minutes are no longer the whole cost? The gap has to stay describable on a paywall in one line.
3. Where does the safety net belong, and at what level? A per-user ceiling that sits above net revenue protects nothing. Consider whether the ceiling should be a product-visible cap, an invisible anti-abuse guard, a graduated throttle (the one already declared but never built), or something else entirely.
4. What does the user see, and when? One gauge, a monthly reset, a warning before the wall — and what happens at the wall, given the current answer is a 403 with an untranslated message.
5. What is the real per-item cost of each ingestion path today, Apify fees included, measured rather than assumed? Everything else depends on this number, and the 0.003/0.008 contradiction says nobody currently knows it.

**Disruptive proposals are welcome and explicitly invited.** Nothing in the current design is protected: the four counters, the per-category caps, the daily rate limits, the euro ceiling, the three-tier ladder and the "minutes" framing itself are all open to being replaced. If the honest recommendation is that the tier boundaries should move, that a tier should disappear, that prices are wrong, or that metering should be abandoned in favour of a different mechanism entirely, say so and show the numbers. A recommendation that keeps the current shape because it is the current shape is not a useful answer.

Ground the work in what comparable products do — read-later and transcription apps facing the same mixed-cost problem — and in the actual provider pricing pages, not in the assumptions already baked into `task-65`, which the task-250 validation has already called into question.

## Constraints the recommendation must respect

- Nothing is deployed and there are no users, so migration paths, dual-running counters and backward compatibility are out of scope. Recommend the destination, not a transition.
- The recommendation must be implementable against the existing enforcement points; it does not need to preserve their current shape.
- Any user-visible change has a mobile cost (paywall copy, subscription card, quota refusal messages) that belongs in the comparison.

## Deliverable

`docs/research/task-287-consumption-model/README.md`, with `owner_decision: pending` in the front-matter and the comparison, measurements and recommendation the owner needs to choose. No implementation, no code changes: task-288 applies whatever the owner validates.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The research README exists at docs/research/task-287-consumption-model/README.md with owner_decision: pending in its front-matter and the Owner Validation section left empty for the owner to fill
- [ ] #2 The real cost of every ingestion path is measured and tabulated -- Deepgram per minute, Apify per result per actor, LLM per item -- sourced from current provider pricing pages with the date and URL of each figure
- [ ] #3 The contradiction between the two Deepgram rates recorded in the codebase is resolved against the provider's published rate, and the correct figure is stated explicitly
- [ ] #4 At least three genuinely different consumption models are compared, including at least one that abandons the current counter-and-cap shape rather than refining it
- [ ] #5 Each candidate model is scored on what the user has to hold in their head to answer 'how much have I got left', with the answer written out as the user would see it
- [ ] #6 Each candidate states where the runaway-user safety net sits and demonstrates, with figures, that it triggers before the user costs more than their tier's net revenue
- [ ] #7 The recommendation says what separates Mix from Audio-Heavy under the proposed model, in one sentence usable as paywall copy
- [ ] #8 The mobile-side consequences of the recommended model are listed concretely: which screens, which copy, which API fields change
- [ ] #9 The recommendation states plainly whether current prices and tier boundaries survive it, and shows the numbers behind that verdict rather than assuming them
- [ ] #10 Comparable products facing the same mixed per-minute and per-item cost are surveyed, with what they show their users and what they meter behind it

- [ ] #11 The four accounting defects listed in the description are each either fixed by the recommended model or shown to be meaningless under it, with the reasoning stated
<!-- AC:END -->
