---
id: task-126
title: Benchmark YouTube transcript extraction strategies given Lambda IP blocking by YouTube
status: Done
assignee: []
created_date: '2026-06-09 01:30'
labels:
  - benchmark
  - backend
  - ingestion
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered during Phase 4 E2E validation on AWS dev (V1 launch plan §4). Article ingestion + on-demand artifact generation (summary, notes, flashcards, quiz) work end-to-end. **YouTube ingestion fails systematically** — the `youtube_ingestion_worker` cannot fetch transcripts from a Lambda execution environment.

## Symptom

Ingesting a YouTube URL via `POST /api/media/ingest-url` enqueues correctly, but the `youtube_ingestion_worker` Lambda fails at the transcript fetch step. The job stays in `pending` indefinitely (no retry recovery; eventually goes to DLQ).

CloudWatch logs `/aws/lambda/media-summarizer-worker-youtube_ingestion`:

```
YouTubeIngestionError: RequestBlocked
Could not retrieve a transcript for the video https://www.youtube.com/watch?v=arj7oStGLkU!
This is most likely caused by:

YouTube is blocking requests from your IP. This usually is due to one of the following reasons:
- You have done too many requests and your IP has been blocked by YouTube
- You are doing requests from an IP belonging to a cloud provider (like AWS, Google
  Cloud Platform, Azure, etc.). Unfortunately, most IPs from cloud providers are blocked
  by YouTube.
```

The block is from the `youtube-transcript-api` Python library (`/var/lang/lib/python3.11/site-packages/youtube_transcript_api/_transcripts.py:404`), which detects the blocked-IP response from YouTube's internal endpoints and raises `RequestBlocked`.

## Why this matters for V1

YouTube is a **declared V1 source** (`docs/V1_LAUNCH_PLAN.md` §0 — "YouTube (transcript natif + fallback Deepgram)"). Without a working YouTube path, V1 ships with a broken core feature. Mobile users will share YouTube URLs from the iOS share sheet on day 1 — this is a top-3 expected source.

The current code path attempts native transcript first via `youtube-transcript-api`, then falls back to Deepgram. The native path is now blocked entirely from Lambda IPs, and the fallback path (audio download via yt-dlp + Deepgram) **may or may not** be subject to similar blocking — needs investigation as part of this benchmark.

## Goal

Decide and document the strategy the V1 backend will use to extract YouTube transcripts reliably, given that the Lambda runtime cannot directly call YouTube endpoints from cloud IPs.

## What this benchmark must cover

1. **Confirm the scope of the block**: does it apply only to `youtube-transcript-api` (which uses YouTube's internal innertube/timedtext endpoints), or also to `yt-dlp` audio downloads? Test both from a Lambda environment in this AWS account/region.
2. **Inventory candidate strategies** (open-ended — find what's available in 2026): proxy services, third-party transcript APIs, official YouTube Data API v3, audio-only fallback via Deepgram, client-side extraction delegated to the mobile app, hybrid combinations, etc. **Do not pre-filter.** Each candidate gets a fair evaluation.
3. **For each candidate, evaluate**:
   - Reliability: how often does it succeed in 2026? Known blocking patterns? Vendor SLAs?
   - Coverage: which YouTube URLs work? (videos with captions vs. without, age-restricted, premium, livestreams, music channels, regional restrictions, etc.)
   - Latency added per request
   - Cost model: per-request, per-minute, monthly subscription, free tier limits
   - Operational complexity: how many moving parts, how does it fail, how do we monitor it
   - Legal/ToS exposure: which approaches respect YouTube's ToS, which are gray-area, which risk a takedown
   - Fit with the existing pipeline: how much of `youtube_ingestion_worker.py` needs to change
4. **Provide a recommendation** with the reasoning chain, ready for owner validation. The recommendation must clearly state what trade-offs the owner is accepting.
5. **Sketch the migration plan** for the recommended strategy: what code changes, what infra changes (proxy config, secrets, Terraform), what testing.

## Constraints

- Solution must work from AWS Lambda in `eu-west-3` (the V1 backend region)
- Must handle a reasonable scale (V1 free tier: a few hundred YouTube URLs/day; later growth)
- Must not require user authentication with YouTube (no Google sign-in flow per video)
- Must respect YouTube's ToS to a level the owner is comfortable with at V1 launch
- Solution must produce a transcript usable by the existing `summarization` / `notes` / `flashcards` / `quiz` artifact workers (i.e. plain text or timed segments)
- Cost upper bound for V1 launch: leave the owner room to choose; surface the actual numbers per strategy

## Out of scope

- Implementation of the chosen strategy — that's a follow-up task gated on owner decision
- Re-architecting the entire YouTube worker; only the extraction step is in question
- Other sources (TikTok, Instagram, X, podcasts) — they have their own resolvers and pipelines

## References

- V1 launch plan §0 (sources d'ingestion supportées en V1)
- `media_summarizer/workers/youtube_ingestion_worker.py:218-260` (native transcript fetch + RequestBlocked handling)
- `media_summarizer/workers/youtube_ingestion_worker.py:600-660` (process_youtube_message orchestration with native + Deepgram fallback)
- CloudWatch logs `/aws/lambda/media-summarizer-worker-youtube_ingestion` (real production blocking observed 2026-06-09)
- `youtube-transcript-api` library readme on IP bans (linked in error message): https://github.com/jdepoix/youtube-transcript-api?tab=readme-ov-file#working-around-ip-bans-requestblocked-or-ipblocked-exception
- `CLAUDE.md` §"Does this task need a benchmark?" — this task qualifies (external service / strategy choice)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Confirmed empirically from a Lambda in this AWS account whether `yt-dlp` audio download is also blocked, partially blocked, or unaffected (Deepgram fallback viability)
- [ ] #2 Candidate strategies enumerated comprehensively in `docs/research/task-126-youtube-extraction/README.md` with no pre-filtering
- [ ] #3 Each candidate evaluated against reliability, coverage, latency, cost, operational complexity, legal/ToS posture, and fit with existing pipeline
- [ ] #4 Recommendation made with explicit reasoning and owner trade-offs surfaced
- [ ] #5 README.md front-matter contains `owner_decision: pending` and the standard `Owner Validation` block per `CLAUDE.md` benchmark workflow
- [ ] #6 Sketch of migration plan for the recommended strategy: code changes, infra changes, testing, rollback
- [ ] #7 README explicitly addresses what happens for YouTube URLs that no strategy can handle (graceful failure UX, error messaging, retry semantics)
<!-- AC:END -->

## Implementation Notes

**Mode**: initial (no prior research existed for this task).

**Research produced**: `docs/research/task-126-youtube-extraction/README.md`

**Summary**: Comprehensive benchmark of 10 candidate strategies for YouTube transcript extraction from AWS Lambda, given that YouTube blocks all major cloud provider IP ranges. The benchmark confirms that both `youtube-transcript-api` and `yt-dlp` are non-functional from Lambda without external infrastructure. Strategies evaluated include residential proxies (Webshare, Decodo), managed transcript APIs (Supadata), PO Token servers, audio+Deepgram fallback, YouTube Data API v3, client-side extraction, headless browser, and feature removal.

**Recommendation**: Supadata transcript API (managed third-party, $47/month Mega plan for V1 scale) as primary, with existing Deepgram fallback retained for edge cases. Supadata handles all anti-blocking infrastructure, provides AI (Whisper) fallback for videos without native captions, and requires minimal code changes.

**Recommendation awaits owner validation** — the owner should review the trade-offs surfaced in the README (particularly the Supadata vendor dependency and cost vs. the self-managed Webshare proxy alternative at $4-7/month but without AI fallback coverage).
