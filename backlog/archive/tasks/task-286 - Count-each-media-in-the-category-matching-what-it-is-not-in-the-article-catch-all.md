---
id: task-286
title: >-
  Count each media in the category matching what it is, not in the article
  catch-all
status: To Do
assignee: []
created_date: '2026-08-18 04:19'
labels:
  - ingestion
  - backend
  - quota
dependencies:
  - task-285
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A TikTok is counted as an article. So is an Instagram reel, an X post and a shared note: `classify_media_type` recognises audio, document and YouTube, and everything else falls through a `return` that was chosen as the safe default — "a wrong guess must not silently open the audio budget". Safe for the audio budget, but it means the `articles` counter no longer measures articles, and short-form video has no budget of its own while quietly eating the reading one.

**This needs no new category.** The taxonomy already has the right shape: `audio` for anything billed per minute, `article` for text, `document` for files, and a fourth for video whose transcript can be had without paying for transcription. That fourth one is merely named after the only platform that used it at the time — and `_YOUTUBE_PLATFORMS` in `quota_enforcer.py` already accepts `"video"` alongside `"youtube"`, so the intent was there from the start. Widening it to cover the caption/subtitle paths of every video platform restores the symmetry with a rename and a mapping change: no new cap key in `pricing_config_service`, no new column, and nothing to recompute in the paywall, which shows marketing copy rather than cap values.

The dividing line stays the one task-250 validated, and it is about cost rather than about media shape: a video whose transcript is scraped costs a per-item fee and belongs in the video counter, while the same video sent to Deepgram costs per minute and belongs in `audio`. Short video therefore lands in the video category only on its caption path — which is why Instagram is not part of this task at all: it has no caption path, so task-285 puts all of it in `audio`.

**The second asymmetry, found while scoping this**: a YouTube video without captions is currently counted twice. The API debits one YouTube unit at submission (`classify_media_type("youtube")` is not `audio`, so the debit fires), and the worker then debits the real minutes at its gate. One ingestion, two budgets. The task-250 table reads as an exclusive choice — "keep `youtube` for the caption path; **`audio` for the Deepgram fallback**" — so the submission-time debit should not survive a fallback to Deepgram. TikTok will inherit the same problem the moment its subtitle path starts debiting a video unit, so the two are worth fixing together.

**Cap values are a judgement call, not a computation**: the video budget (100 / 100 / 200 per tier) would serve two platforms instead of one. A subtitled TikTok costs about what a captioned YouTube costs — a per-item scrape plus the same LLM pass — so the existing values remain defensible and this task does not require re-deriving them. Raise them if you want the headroom; the owner note below is the place to say so.

**Owner note — not an acceptance criterion**: whether the video cap should be raised now that it covers two platforms is yours to call, and can be changed in the pricing config without touching code. Separately, the `task-65` cost assumptions behind every cap in this file were flagged during the task-250 validation as understating the real Deepgram rate by 47%; revisiting them is its own task and this one deliberately does not.

Depends on task-285 so the Instagram reclassification lands first: both touch `classify_media_type`, and task-285 closes an active financial hole while this one corrects an accounting label.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Saving a TikTok that has usable subtitles counts against the video budget rather than the article one, and the reader budget it used to consume is left untouched
- [ ] #2 The quota category formerly named after YouTube carries a name that describes what it holds, and no reference to the old name survives anywhere -- enforcement, usage counters, pricing config, API contracts
- [ ] #3 A media is counted in one budget per ingestion: a YouTube video that falls back to Deepgram is charged its real minutes and no longer also spends a video unit at submission
- [ ] #4 The rule that decides between the video category and audio minutes is legible at the point of decision: transcript scraped per item versus transcription billed per minute, not a per-platform list a reader has to reverse-engineer
- [ ] #5 Text-shaped submissions that legitimately belong in the article budget -- X posts, shared text, web pages -- still land there, so the fix narrows the catch-all rather than emptying it
- [ ] #6 The article counter no longer receives any media that is not text: the audit lists every source platform and the category it now resolves to, recorded in the task's implementation notes
- [ ] #7 The per-tier caps for the widened video category are present and coherent in the pricing config for every tier and for the free trial
- [ ] #8 ruff and mypy are clean on the touched files
<!-- AC:END -->
