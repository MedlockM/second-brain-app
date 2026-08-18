---
id: task-285
title: >-
  Charge the audio quota wherever Deepgram minutes are actually spent, Instagram
  included
status: To Do
assignee: []
created_date: '2026-08-18 04:07'
labels:
  - ingestion
  - backend
  - quota
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every Instagram reel we ingest is transcribed by Deepgram, and none of it is charged to anyone. The enqueue in `instagram_ingestion_worker.py` passes `quota_source_platform="instagram"`, which `classify_media_type` maps to the `article` category, and `_settle_audio_quota` in `deepgram_worker.py` then skips the settlement outright. The provider is billed per minute, the user is charged one article. Instagram is the only platform where "minutes transcribed" and "minutes counted" diverge.

It is also the platform where the divergence is structural rather than occasional. YouTube and TikTok reach Deepgram only when no captions exist; Instagram has no native transcript path at all (`instagram_apify_resolver.py`: "There is no native transcript path"), so *every* reel spends real minutes. On the IP-blocked branch it spends Apify *and* Deepgram, since the Apify actor there returns a media URL rather than a transcript.

**The code's justification for the exemption is false.** The comment reads "Instagram is metered in its own quota category, not in audio minutes (validated task-250 decision)". `docs/research/task-250-audio-minutes-quota-accuracy/README.md` says no such thing: its per-platform table lists Instagram as `article` with the reason "no Deepgram path today — nothing to gate", and adds that `videoDuration` is "already in `metadata['duration_seconds']` **if a Deepgram path is added later**". The Deepgram path was added later. This is an uncovered case, not a decision to reverse — which is why the task needs no new benchmark: the rule to apply is already the validated one, stated verbatim in `quota_enforcer.py`, that every path spending Deepgram minutes classifies as `audio` whatever URL it came from.

**Apify needs no minute accounting.** The owner framed the asymmetry as covering Deepgram *or* Apify; the investigation says only Deepgram is affected. Apify bills per result (~$1.00-2.60 / 1K reels per the task-107 benchmark), not per minute, so a transcript it returns for YouTube or TikTok costs the same whether the video runs one minute or sixty. Those paths already debit one unit in a per-item counter, which matches the cost shape. Nothing to change there — but state it in the code so the next reader does not re-open the question.

Watch for the double debit: `POST /api/media/ingest-url` already debits an article for Instagram at submission, guarded by `classify_media_type(...) != QUOTA_CATEGORY_AUDIO`. Reclassifying Instagram makes that guard drop the article debit on its own — verify it does, rather than adding a second subtraction.

**Product consequence to be aware of**: once Instagram classifies as `audio`, the `text_only` tier stops accepting reels and reel minutes count against the monthly audio cap. That follows directly from the fact that reels cost Deepgram minutes, and it is the intended outcome.

**Out of scope, worth its own task**: short-form video currently falls into the `article` counter (TikTok with captions, and Instagram before this change) because `classify_media_type` defaults there. Calling a reel an article is wrong in a way this task does not fix — it only moves the paths that spend audio minutes into `audio`. Whether short video deserves its own counter is a pricing question, and it is a real one since the task-250 owner validation already flagged the `task-65` cost assumptions as understating the Deepgram rate by 47%.

**Owner note — not an acceptance criterion**: the quota paths only run in the deployed API and workers, so confirming the end-to-end behaviour (save a reel on `-dev`, watch `audio_minutes_used` move by the reel's real duration, save the same reel again and watch it stay put) requires a merge to `main` and a deploy, long after the implementing agent is gone.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Ingesting an Instagram reel debits the user's audio minutes: the worker calls the shared audio quota gate before the Deepgram enqueue, and the enqueue no longer opts the message out of the settlement
- [ ] #2 The gate is fed the duration the resolver already produced, on both the yt-dlp branch and the Apify branch, so it never falls back to a provisional minute when the real duration was available
- [ ] #3 A user who already holds the reel is exempt exactly as every other audio path is: the gate's already-held check runs and the exemption reaches the settlement, so a re-save adds nothing to the counter
- [ ] #4 A reel is refused before the Deepgram enqueue when the user is over their audio cap or on a tier without audio, with the same stable error code the other audio paths return
- [ ] #5 An Instagram submission is debited once, not twice: the article debit at submission no longer fires for Instagram, and the code shows why rather than leaving it to be re-derived
- [ ] #6 The code comment claiming the exemption was a validated task-250 decision is gone, replaced by what that benchmark actually says about Instagram
- [ ] #7 The reason Apify-sourced transcripts carry no minute accounting -- billed per result, not per minute -- is written down where a reader meets the opt-out, so it is not mistaken for the same bug
- [ ] #8 No producer that enqueues a Deepgram transcription is left without a quota gate: the audit covers every call site and its outcome is recorded in the task's implementation notes
- [ ] #9 ruff and mypy are clean on the touched files
<!-- AC:END -->
