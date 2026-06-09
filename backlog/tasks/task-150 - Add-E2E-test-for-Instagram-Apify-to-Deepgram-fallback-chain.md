---
id: task-150
title: Add E2E test for Instagram Apify transcript → Deepgram fallback chain
status: Done
assignee: []
created_date: '2026-06-09 22:30'
labels:
  - testing
  - tech-debt
  - instagram
dependencies:
  - task-146
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Once **task-146** (migrate Instagram worker from GetInsaver to Apify) lands, the Instagram pipeline has a two-tier extraction:

1. **Primary**: Apify Reel scraper returns a `caption`/transcript field if Instagram already exposes one (auto-captions or creator-provided)
2. **Fallback**: if Apify's transcript field is empty, the worker should download the Reel's audio via the `downloadedVideo` URL and send it to Deepgram

The current happy-path test `tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` uses a fixture where Apify returns a transcript directly — Deepgram never fires. The fallback chain is therefore untested.

This task adds an E2E test that picks a Reel **without an Apify-provided transcript** to exercise the Deepgram fallback.

## What to add

A new test in `tests/e2e/test_fallback_chains.py`:

```python
@pytest.mark.e2e
async def test_instagram_deepgram_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Instagram Reel without Apify auto-caption → Deepgram fallback succeeds.

    Fixture: a Reel with spoken English audio but NO native captions in the
    Apify response. Owner needs to provide the URL after task-146 lands and
    the actual Apify behavior can be probed.
    """
    media_item_id = await _ingest_and_wait(
        http_client, auth_headers,
        "<TBD: Reel URL where Apify caption is empty>",
    )
    detail = await _get_media_item(http_client, auth_headers, media_item_id)
    assert detail.get("transcript_source") == "deepgram", \
           f"expected deepgram fallback, got: {detail}"
```

## Picking the fixture

The Apify Reel scraper's `caption` field is non-deterministic. Before activating the test:

1. Probe a few candidate Reels via the actor's API (or the Apify console) to find one with an empty `caption` but spoken audio
2. Or: ingest a Reel via the happy-path test, inspect the worker logs, find one where `transcript_source: deepgram` is logged
3. Document the chosen URL with rationale (why we expect this Reel to trigger the fallback)

Stable candidates:
- Music-only Reels rarely have transcripts (but they fail at Deepgram too — empty transcript)
- Stories migrated to Reels (but Apify might not extract them)
- Educational Reels from official accounts that don't add captions (rare but exists)

If no stable URL is found, fall back to mocking the Apify response in the worker for this specific test (less E2E-pure).

## Cost

- Apify call: ~$0.005-0.01
- Deepgram fallback: ~$0.005 (Reels capped at 90s)
- Total: ~$0.01-0.02 per run

## Out of scope

- Other source fallback chains (separate tasks 149, 151, 152)
- Handling Apify response with corrupted `downloadedVideo` URL (separate edge case)

## References

- task-146 (Instagram migration to Apify — must land before this task can run)
- task-127 (Apify per-source token split)
- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`
- `tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion` (happy path baseline)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New test `test_instagram_deepgram_fallback` added in `tests/e2e/test_fallback_chains.py`
- [ ] #2 Fixture URL chosen and documented (rationale for why this Reel triggers Deepgram fallback)
- [ ] #3 Test asserts BOTH `status == "completed"` AND `transcript_source == "deepgram"` (or equivalent metadata)
- [ ] #4 If the metadata field doesn't exist, `GET /api/media/{id}` is extended to expose `transcript_source`
- [ ] #5 Wall-clock < 60s (allows Deepgram round-trip)
- [ ] #6 No regression on existing Instagram happy-path test
<!-- AC:END -->
