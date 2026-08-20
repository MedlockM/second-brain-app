---
id: task-310
title: >-
  Delete the dead yt-dlp branch from Instagram reel resolution and make Apify
  the primary path
status: To Do
assignee: []
created_date: '2026-08-20 19:39'
labels:
  - backend
  - ingestion
  - cleanup
  - instagram
dependencies:
  - task-309
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Same finding as task-309, on the other platform where yt-dlp is tried first. Measured on dev on 2026-08-20:

- All 10 Instagram jobs in `processing_jobs-dev` resolved through `apify~instagram-reel-scraper`. **None** resolved through yt-dlp.
- `/aws/lambda/media-summarizer-worker-instagram_ingestion-dev` logs `instagram.reel.ytdlp_ip_blocked` — "yt-dlp IP-blocked on Instagram, starting async Apify fallback" — on **6 attempts out of 6**, spanning 2026-08-18 to 2026-08-20.

task-145 already recorded this at 6/6 on 2026-08-17 and the owner chose to hold the residential-proxy answer to V2. Three days and a fresh set of saves later the rate is still 100%, so the branch is not a fallback that fires occasionally — it is dead code that every reel ingestion pays for before Apify does the actual work.

The owner's decision on 2026-08-20 is to delete it. There is no installed base to keep working, so Apify becomes *the* Instagram resolution path and the yt-dlp attempt goes away in the same run.

## Relationship to task-145 (must be handled, not ignored)

task-145 §3 is written as "on `_InstagramYtdlpBlocked`, retry yt-dlp through the residential proxy". After this task there is no such branch and no yt-dlp call site to retry. That does not invalidate task-145 — a proxied yt-dlp path is still the cheap primary it argues for — but it changes it from *modify the existing branch* to *introduce a proxied path where none remains*, for Instagram specifically. Its TikTok half is unaffected: TikTok still resolves via yt-dlp and works (2/2 saves in `native_subtitles`, zero IP blocks logged on 2026-08-20).

So update task-145's description and acceptance criteria to match reality rather than leaving them pointing at deleted code.

## Scope

In `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`, remove `_resolve_reel_via_ytdlp`, the `_InstagramYtdlpBlocked` exception and every branch raising or catching it, the `instagram.reel.ytdlp_ip_blocked` event, and the yt-dlp import. Reels take the same `InstagramApifyRequired` route posts already take, so the queue worker starts the Apify run directly.

Then check the metadata contract downstream: the yt-dlp path set `audio_url_kind: audio_ytdlp` and `resolution_mode: deepgram_via_ytdlp_audio_url`. If any consumer branches on those values, it must be reconciled with what the Apify path actually writes (observed on dev: `provider: apify`, `transcript_source: deepgram_pending`, then a Deepgram push on the `cdninstagram` URL).

`media_summarizer/utils/ytdlp_helpers.py` is imported only by this resolver and by the YouTube worker, and task-309 removes the other importer. Delete the module here, once it has no remaining importer. If task-309 has not landed, this task's dependency ordering is wrong — check before deleting rather than leaving a broken import.

Anything in `infrastructure/terraform` keyed on the `instagram.reel.ytdlp_ip_blocked` event or a yt-dlp-specific Instagram metric goes with the code.

Update `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`: mark the Instagram section superseded and record Apify-only as the current strategy, with the 6/6 measurement as the reason. The ADR's TikTok section stays as it is — it still describes what runs.

## Owner note (not an acceptance criterion)

Confirm after the deploy on `main` by saving a reel and a non-reel Instagram post on dev, and checking the worker no longer logs `instagram.reel.ytdlp_ip_blocked` and that the Deepgram transcript still lands.

## References

- Resolver: `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`.
- Worker: `media_summarizer/workers/instagram_ingestion_worker.py`.
- Shared module to delete: `media_summarizer/utils/ytdlp_helpers.py`.
- YouTube counterpart: task-309. V2 proxy work to amend: task-145. Prior measurement of the same block: task-274.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Instagram resolver no longer imports yt_dlp and contains no yt-dlp resolution attempt, no _InstagramYtdlpBlocked exception and no instagram.reel.ytdlp_ip_blocked event
- [ ] #2 Reels and non-reel posts both resolve through the Apify path, with the queue worker starting the Apify run directly and no branch left that distinguishes them by extraction strategy
- [ ] #3 Any consumer that branched on audio_url_kind or resolution_mode values produced only by the yt-dlp path is reconciled with the values the Apify path writes, or the check is removed if no consumer reads them
- [ ] #4 media_summarizer/utils/ytdlp_helpers.py is deleted and a repo-wide grep confirms no remaining importer
- [ ] #5 Every Terraform dashboard widget and alarm keyed on the instagram.reel.ytdlp_ip_blocked event or a yt-dlp-specific Instagram metric is removed, and terraform validate is clean
- [ ] #6 task-145's description and acceptance criteria are updated so its Instagram half describes introducing a proxied yt-dlp path rather than modifying a branch that no longer exists, and its TikTok half is left unchanged
- [ ] #7 docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md marks the previous Instagram strategy superseded and records Apify-only as the current one, citing the 2026-08-20 dev measurement (6/6 ytdlp_ip_blocked, 10/10 saves via Apify), with the TikTok section left unchanged
- [ ] #8 The TikTok worker's yt-dlp path is untouched and the yt_dlp dependency remains declared for it
- [ ] #9 ruff and mypy are clean on the changed Python files
<!-- AC:END -->
