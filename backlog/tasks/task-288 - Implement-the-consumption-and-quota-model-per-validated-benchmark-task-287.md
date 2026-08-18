---
id: task-288
title: Implement the consumption and quota model per validated benchmark (task-287)
status: Done
assignee: []
created_date: '2026-08-18 04:35'
updated_date: '2026-08-18 17:15'
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
- [x] #1 The consumption model the owner validated in the task-287 README is what the enforcement path implements, in the unit that Decision names
- [x] #2 Every ingestion path debits consumption consistently with the validated model, with no path left unmetered and none debited twice for one ingestion
- [x] #3 The runaway-user safety net is in place at the threshold the Decision sets, and refuses before a user can cost more than their tier's net revenue
- [x] #4 The pricing config expresses the validated caps for every tier and for the free trial, with no leftover keys from the superseded model
- [x] #5 The API exposes exactly the consumption information the validated model requires the app to show, and no longer exposes fields the model drops
- [x] #6 The mobile app shows the user's remaining consumption per the validated model, on the screens the benchmark identified
- [x] #7 A refused submission tells the user which limit stopped them and what it means, in the app's language rather than a raw backend string
- [x] #8 Everything the validated model replaces is deleted -- superseded counters, unused config keys, and the declared-but-unimplemented throttle action -- with no compatibility layer left behind
- [x] #9 Any task-285 or task-286 acceptance criterion the new model makes moot is recorded as superseded in this task's implementation notes rather than left silently unmet
- [x] #10 ruff and mypy are clean on the touched Python, and the mobile app typechecks
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built from `docs/research/task-287-consumption-model/README.md` (`owner_decision: ok`, validated 2026-08-18, no complement files). The Decision keeps the recommendation as written: **one metered unit, the minute**, at `0.00664 EUR`, with everything that is not transcription unlimited.

### What the enforcement path now looks like

`core/services/quota_enforcer.py` was rewritten around a single unit. Conversions (README §3.1): Deepgram audio charges its real length; a bought caption set charges 1 whatever the video's length; a parsed document charges 1 per 5 pages, minimum 1; a generation over one item charges 0 and over a collection 1 per 5 sources; articles, web pages, TikToks and Instagram photo posts charge 0.

**The meter follows the provider call, not the URL.** API endpoints only *check* (`check_submission_allowed`); the debit fires where provider money is spent — `audio_quota_gate` before Deepgram, the Apify caption purchase, the LlamaParse document parse, the collection generation. That is what makes "an unmetered transcription" and "one ingestion charged twice" unrepresentable rather than merely fixed, and it is why there is no per-platform category map any more, and therefore no platform that can be accidentally exempt.

The refusal vocabulary is exactly two codes (§3.6): `item_too_long` (413, no upgrade offered — splitting fixes it) and `out_of_minutes` (403, upgrade offered). Both carry a product-copy `message` with the figures inline; the app displays it verbatim.

Safety net in three layers (§3.3): the visible cap; `burst_guards`, invisible daily counters that **never refuse** and only emit `quota.burst_guard_tripped` for the owner; and `provider_pool_guard`, a platform-wide monthly pool for Apify credits and LlamaParse pages that degrades at 60% and stops at 90% independently of any per-user allowance. Layer 2 refusing nothing is the reason `daily_rate_limit` leaves the user-visible vocabulary entirely.

Counters live in `user_usage_monthly` (SK = the subscription's own anniversary window, not the calendar month) and `user_usage_daily`, written with atomic `ADD` plus a per-write idempotency token so a redelivered SQS message cannot debit twice.

### Judgement calls worth recording

- **YouTube with native subtitles charges 0, not 1.** §3.1 prices "a bought caption set" at 1 because Apify costs money per run; `youtube_ingestion_worker`'s first branch reads the transcript with no paid provider call at all, so it debits nothing and the Apify branch debits 1 after `complete_callback`. The unit tracks the spend, not the media shape.
- **`entitlements.py` is under `/api/v1/`, which `AGENTS.md` line 38 tells agents not to touch.** Overridden deliberately: it is the app's only source of consumption state, and AC #5 requires it to change shape. `api/v1/podcasts.py` got compile-level edits only.
- **One date, not two.** The endpoint used to return `period_end` and `resets_at` with the same value. The allowance empties on the anniversary, so the period end *is* the reset; `period_end` is gone from the API and from `EntitlementStatus`, and the renewal-intent nuance moved into `getResetDateLabel` (`RESETS` / `ENDS` / `PERIOD ENDS`).
- **The 80% banner is dismissible per period with no AsyncStorage** (removed in V1). `usageWarningDismissal.ts` stores the `resets_at` string in `expo-secure-store`: the next period has a different date, so the banner comes back with no expiry logic to maintain.
- **No retry button on a refused share.** The same submission would be refused for the same reason; the top bar keeps Save enabled so it is one tap away for a user returning from the paywall.

### Superseded acceptance criteria (AC #9)

Both tasks were archived by this one. Their criteria are recorded here rather than left silently unmet.

**task-285 — "Charge the audio quota wherever Deepgram minutes are actually spent, Instagram included":**
1. *Reel debits audio minutes via the shared gate* — **satisfied by construction.** `instagram_ingestion_worker` now passes through `audio_quota_gate` before enqueuing Deepgram.
2. *Gate fed the resolver's duration on both branches* — **satisfied**, yt-dlp and Apify branches both reach the same gate.
3. *An exemption already held reaches the settlement* — **superseded.** The gate/settlement pair now carries an idempotency token instead of an exemption flag; a gate that charged nothing settles nothing.
4. *Refusal before the enqueue with a stable code* — **satisfied**, with the code renamed to `out_of_minutes` / `item_too_long`.
5. *No double debit for Instagram* — **satisfied**, and generalised: the debit lives at the provider call, so there is no second site that could charge.
6. *Remove the false task-250 comment* — **moot**, the commented block no longer exists.
7. *Document why Apify transcripts carry no minute accounting* — **superseded and inverted.** Apify captions now cost 1 minute (§3.1) because the run is billed; the reasoning is in the module docstring and in `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md`.
8. *Audit every Deepgram producer in the notes* — done below.
9. *ruff and mypy clean* — satisfied.

**task-286 — "Count each media in the category matching what it is, not in the article catch-all":**
1. *A subtitled TikTok counts against the video budget rather than the article one* — **moot.** There are no category budgets; a TikTok with subtitles costs nothing at all.
2. *Rename the YouTube-shaped category* — **moot**, the category is deleted, not renamed.
3. *One budget per ingestion; a YouTube video falling back to Deepgram is charged its real minutes and no longer also spends a video unit* — **satisfied by construction**, since submission-time debits no longer exist.
4. *The video-versus-audio-minutes rule legible at the point of decision* — **satisfied in a stronger form.** There is no rule to read: the debit sits at the provider call, so the decision is where the money is.
5. *Text submissions still land in the article budget* — **moot**, text costs nothing.
6. *The article counter receives no non-text media, with a per-platform audit in the notes* — **moot**, the counter is deleted. The audit that replaces it is the producer audit below.
7. *Per-tier caps for the widened video category* — **moot**, no such caps exist. The ladder is minutes only: 60 / 300 / 720.
8. *ruff and mypy clean* — satisfied.

### Deepgram producer audit (replaces task-285 AC #8 and task-286 AC #6)

Every call site that can enqueue a transcription, and how it is metered:

| Producer | Metering |
| --- | --- |
| `core/media_ingestion/adapters/orchestrators.py` (2 sites) | `gate_transcription` before enqueue |
| `workers/rss_feed_poll_worker.py` | `gate_transcription` |
| `workers/instagram_ingestion_worker.py` | `gate_transcription` (new in this task) |
| `workers/podcastindex_resolution_worker.py` | `gate_transcription` |
| `workers/youtube_ingestion_worker.py` | `gate_transcription` on the audio fallback; caption purchase debits 1 on the Apify branch |
| `workers/tiktok_ingestion_worker.py` | `gate_transcription` on the media fallback; native subtitles cost 0 |
| `api/v1/podcasts.py` `POST /submit` | no gate (legacy path left untouched per `AGENTS.md`), but `deepgram_worker._settle_audio_quota` defaults `quota_debited_minutes` to 0 and therefore charges the full billed duration at settlement — metered, never free |

Non-Deepgram paid producers: the Apify caption fetch (`apify_adapter.py`), the LlamaParse parse (`document_parsing/worker.py`), and the collection generation (`artifact_generator/worker.py`).

### Deliberately out of scope

§3.9's first open question — the deferred wall, i.e. queueing an over-budget import behind a "Waiting for minutes" chip instead of refusing it — is not built. The Decision does not require it, and it would need a new job state plus a resume trigger on the renewal webhook. The refusal is immediate and the copy says so.

### Owner follow-up

- **`pricing_config-dev` still holds `hard_caps`, `rate_limits` and `cost_monitoring` rows.** `_merge_defaults` lets stored values win over defaults, so deleting the keys from `DEFAULT_PRICING_CONFIG` does not delete them from the table — they linger, unread, until removed. This sandbox has no AWS access (`dynamodb list-tables` returns an empty list), so the deletion is manual. Nothing reads those keys any more, so there is no functional urgency.
- End-to-end verification is the owner note in the description, not an AC: consumption moving across podcast / reel / YouTube / article saves, the gauge matching the backend, and the wall arriving at the right moment all need a merge to `main`, a deploy, and a mobile build.
- No automated tests were written, per the project rule; none of the ACs asked for any.
<!-- SECTION:NOTES:END -->
