---
id: task-309
title: >-
  Delete the dead yt-dlp branch from the YouTube ingestion worker and make Apify
  the primary path
status: Done
assignee: []
created_date: '2026-08-20 19:38'
updated_date: '2026-08-20 23:40'
labels:
  - backend
  - ingestion
  - cleanup
  - youtube
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The YouTube worker is documented as "yt-dlp primary, Apify fallback for IP blocks". Measured on dev on 2026-08-20, the primary is structurally dead from Lambda:

- Of the 12 YouTube jobs in `processing_jobs-dev`, **10 succeeded with `extractor: apify_youtube_transcript`** and 2 failed outright. **Zero** carry a yt-dlp extractor.
- `/aws/lambda/media-summarizer-worker-youtube_ingestion-dev` shows the cause on every attempt: `ERROR: [youtube] <id>: Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication.`
- The cost is paid on every single save: the invocation that attempts yt-dlp before falling back bills ~6.4 s, against ~1.6-1.7 s for the pure-Apify invocations in the same job. Every YouTube ingestion carries that dead round-trip plus the extra Lambda invoke it forces.

There is no installed base and nothing to keep working during a transition, so this is a deletion, not a demotion: Apify becomes *the* YouTube transcript path and the yt-dlp branch goes away in the same run. The `yt_dlp` package itself stays in the image — the TikTok worker still uses it and still works (2/2 saves resolved via `native_subtitles` on 2026-08-20, zero IP blocks logged).

## Scope

Remove the yt-dlp attempt and everything that exists only to detect or recover from its failure in `media_summarizer/workers/youtube_ingestion_worker.py`: `_extract_youtube_info`, `_fetch_native_subtitles`, the `_is_ip_blocked_youtube_error` / `_is_geo_restricted_error` / `_is_age_restricted_error` / `_is_unavailable_error` predicates and the branches reading them, the `ip_blocked` plumbing through `process_youtube_message` and `process_message` (including `fallback_strategy="ip_blocked_apify_fallback"`), and the native-subtitle metadata builders.

Then make the Apify path the first thing the worker does, keeping its language handling, actor-dialect resolution, callback/backstop orchestration and quota debiting exactly as they are — those are the parts that work and carry every save today.

Two things to be careful about:

- **Failure taxonomy.** The yt-dlp predicates were how a geo-restricted, age-restricted or unavailable video got a specific user-facing error rather than a generic one. Once the predicates go, check what Apify reports for those videos and make sure the resulting `ApifyTranscriptFailure` still maps to a sensible user-facing message rather than degrading everything to a generic failure.
- **Dashboards and alarms.** Anything in `infrastructure/terraform` keyed on a yt-dlp-specific event or metric for YouTube goes with the code; a widget or alarm on a metric nobody emits is worse than no widget.

`media_summarizer/utils/ytdlp_helpers.py` is imported only by this worker and by the Instagram resolver, and becomes dead once both are done. It is deleted by the Instagram task (task-310), not here.

Also update `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`: the YouTube section describes a strategy that no longer exists. Mark it superseded and record the new one, with the bot-check measurement as the reason.

## Owner note (not an acceptance criterion)

Confirm after the deploy on `main` by saving a YouTube video and a YouTube short on dev, and checking the ingestion no longer logs the bot-check error and completes in a single Apify round-trip.

## References

- Worker: `media_summarizer/workers/youtube_ingestion_worker.py`.
- ADR: `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`.
- Instagram counterpart of the same finding: task-310. TikTok stays on yt-dlp, and its V2 proxy work is task-145.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The YouTube worker no longer imports yt_dlp and contains no yt-dlp extraction attempt, no IP-block/geo/age/unavailable predicate written against yt-dlp errors, and no ip_blocked fallback plumbing
- [x] #2 The Apify transcript path is the worker's first and only transcript path, with its language fallback, actor-dialect resolution, callback/backstop orchestration and quota debiting behaviourally unchanged
- [x] #3 Videos that are geo-restricted, age-restricted or unavailable still resolve to a specific user-facing error through the ApifyTranscriptFailure taxonomy, and the mapping used for each is documented in the code
- [x] #4 Every Terraform dashboard widget and alarm keyed on a yt-dlp-specific YouTube event or metric is removed, and terraform validate is clean
- [x] #5 grep for yt_dlp and ytdlp across the YouTube worker returns nothing, while the TikTok worker's yt-dlp path is untouched and the yt_dlp dependency remains declared for it
- [x] #6 docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md marks the previous YouTube strategy superseded and records Apify-only as the current one, citing the 2026-08-20 dev measurement (10/10 saves via Apify, bot-check on every yt-dlp attempt)
- [x] #7 ruff and mypy are clean on the changed Python files
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Apify is now the worker's only transcript path. The yt-dlp branch, the subtitle
candidate collection, the direct-media-URL resolution and the Deepgram push
hand-off are gone; `DEEPGRAM_TRANSCRIPTION_QUEUE`, `YTDLP_TIMEOUT_SECONDS` and
`YOUTUBE_SUBTITLE_FETCH_TIMEOUT_SECONDS` are no longer read by this worker.
The file went from 1046 to 468 lines.

**AC #3 required real work, not just deletion.** The yt-dlp branch carried the
geo / age / unavailable predicates (`_is_geo_restricted_error` and friends,
matched against yt-dlp exception strings) and their dedicated user messages.
Deleting it would have collapsed every actor refusal into a single generic
`apify_actor_error`. The specificity is restored on the Apify side by
`_classify_actor_error`, which matches substrings of the actor's
`error_category`: `geo`/`region`/`country`, `age`/`sign_in`/`login`,
`unavailable`/`private`/`deleted`/`removed`/`not_found`, else
`apify_actor_error:<category>`. Three members were added to
`ApifyTranscriptFailure` (`GEO_RESTRICTED`, `AGE_RESTRICTED`,
`VIDEO_UNAVAILABLE`) and the error codes `youtube_geo_restricted` /
`youtube_age_restricted` are preserved, so the observability contract is
unchanged. The mapping table lives in the function docstring and is mirrored in
`docs/INGESTION_WORKERS_PROVIDERS.md`.

**AC #4 was a no-op, verified rather than assumed.** `grep -rn
'ytdlp|yt_dlp|yt-dlp|ip_blocked|native_subtitles|strategy_used'` over
`infrastructure/` returns nothing under `terraform/`: the YouTube widgets in
`pipeline_dashboard.tf` are platform-generic (`IngestByPlatform`, queue depth,
`apify_calls`) and no alarm is keyed on a yt-dlp event. The only hit was prose
in `infrastructure/observability/runbooks/pipeline-alerts.md:299`, which blamed
"yt-dlp outdated" for youtube-ingestion failures; it now names the Apify failure
modes. `terraform validate` (envs/dev) and `terraform fmt -check -recursive` are
clean.

**Beyond the ACs, kept minimal:** `.env.example` lost the now-orphaned
`YOUTUBE_SUBTITLE_FETCH_TIMEOUT_SECONDS` (no reader left anywhere) and its stale
"transcript-first via youtube-transcript-api" header;
`scripts/check_env_example_complete.py` passes. `YTDLP_TIMEOUT_SECONDS` stays —
the TikTok worker and the Instagram resolver still read it.

**Noticed, deliberately not touched (out of scope):**
`YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS` is still defined in
`media_summarizer/core/config.py:52` but is a leftover of the
`youtube-transcript-api` era removed by task-129, unrelated to the yt-dlp
branch. Worth its own cleanup task.

Checks: `ruff check .` clean · `mypy media_summarizer/` clean (174 files) ·
`terraform validate` + `fmt -check` clean · `check_env_example_complete.py` OK
(236 vars). No automated tests written, per project rule.

**Owner note — the behaviour is only observable after the worker image is
redeployed on push to `main`.** Then save a YouTube URL on dev and check
`processing_jobs-dev` shows `extractor: apify_youtube_transcript` with a single
~1.6 s invocation and no `Sign in to confirm you're not a bot` line in
`/aws/lambda/media-summarizer-worker-youtube_ingestion-dev`.
<!-- SECTION:NOTES:END -->
