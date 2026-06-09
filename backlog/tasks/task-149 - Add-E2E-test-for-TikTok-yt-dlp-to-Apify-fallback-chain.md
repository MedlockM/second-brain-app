---
id: task-149
title: Add E2E test for TikTok yt-dlp → Apify fallback chain
status: To Do
assignee: []
created_date: '2026-06-09 22:30'
labels:
  - testing
  - tech-debt
  - tiktok
dependencies: []
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The current E2E suite at `tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion` validates only the **happy path** of the TikTok pipeline — yt-dlp from Lambda extracts the captions directly. The fallback chain introduced by **task-144** (yt-dlp blocked → Apify takes over) is never exercised, so a regression on Apify wiring would go undetected until a user submits an IP-blocked URL.

This task adds a single E2E test that **deliberately picks an IP-blocked URL** and asserts that the Apify fallback fires successfully.

## What to add

A new test in `tests/e2e/test_fallback_chains.py` (create the file if it doesn't exist):

```python
@pytest.mark.e2e
async def test_tiktok_apify_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """TikTok IP-blocked URL → yt-dlp fails → Apify fallback succeeds.

    Fixture: a TikTok URL known to trigger 'Your IP address is blocked
    from accessing this post' from Lambda. Picked from task-140 evidence.
    """
    media_item_id = await _ingest_and_wait(
        http_client, auth_headers,
        "https://www.tiktok.com/@bbc/video/7335731145619360992",
    )
    # Assert that the worker actually used the Apify fallback,
    # not yt-dlp directly.
    detail = await _get_media_item(http_client, auth_headers, media_item_id)
    assert detail.get("provider") == "apify" or \
           "apify" in (detail.get("transcription_metadata", {}) or {}).get("source", ""), \
           f"expected apify fallback marker, got: {detail}"
```

## Investigation step

Before writing the assertion: check what metadata the worker exposes today on `GET /api/media/{id}` to distinguish "yt-dlp captions" from "Apify fallback":

```bash
grep -nE "provider|transcript_source|fallback" \
  media_summarizer/workers/tiktok_ingestion_worker.py
```

If no field exists, expand the `MediaItemResponse` model (small additive change) so the test can verify the fallback fired.

## Cost

- Apify TikTok actor call: ~$0.005-0.01 per run
- Total wall-clock: should be < 30s (Apify return is fast)

## Out of scope

- Other source fallback chains (separate tasks 150, 151, 152)
- New TikTok features (V2 task-145 for residential proxy)
- yt-dlp retry tuning

## References

- task-140 (TikTok IP block benchmark)
- task-144 (Apify TikTok fallback implementation)
- `tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion` (happy path baseline)
- `media_summarizer/workers/tiktok_ingestion_worker.py`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New test `test_tiktok_apify_fallback` added in `tests/e2e/test_fallback_chains.py`
- [ ] #2 Test uses a fixture URL that empirically triggers Lambda IP block on yt-dlp
- [ ] #3 Test asserts BOTH `status == "completed"` AND a metadata field proving Apify (not yt-dlp) was used
- [ ] #4 If the metadata field doesn't exist, `GET /api/media/{id}` is extended to expose `provider` or equivalent
- [ ] #5 Wall-clock < 30s
- [ ] #6 No regression on existing TikTok happy-path test
<!-- AC:END -->
