---
id: task-151
title: Add E2E test for document LlamaParse → Unstructured fallback chain
status: Done
assignee: []
created_date: '2026-06-09 22:30'
labels:
  - testing
  - tech-debt
  - document
dependencies: []
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The document parsing pipeline has two providers:

- **Primary**: LlamaParse (free tier capped at 1000 pages/day)
- **Fallback**: Unstructured.io (15k pages free tier)

The current happy-path test `tests/e2e/test_phase4_other_sources.py::test_document_upload` uses a 1-page PDF that LlamaParse handles trivially. The fallback to Unstructured never fires. A regression breaking the Unstructured path would be invisible.

This task adds an E2E test that **forces LlamaParse to fail** so Unstructured takes over.

## What to add

A new test in `tests/e2e/test_fallback_chains.py`:

```python
@pytest.mark.e2e
async def test_document_unstructured_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Document upload that LlamaParse can't handle → Unstructured fallback.

    Fixture: a PDF or DOCX format/feature LlamaParse rejects but Unstructured
    parses successfully. Investigation needed to find such a file.
    """
    fixture = Path(__file__).parent / "fixtures" / "<TBD>.pdf"
    with fixture.open("rb") as f:
        files = {"file": (fixture.name, f, "application/pdf")}
        resp = await http_client.post(
            "/api/media/upload", files=files, headers=auth_headers,
        )
    media_item_id = resp.json()["media_item_id"]
    body = await poll_until(
        client=http_client, url=f"/api/media/{media_item_id}",
        headers=auth_headers,
        predicate=lambda b: b.get("status") in ("completed", "failed"),
        timeout_s=60, interval_s=3,
    )
    assert body.get("status") == "completed"
    detail = await _get_media_item(http_client, auth_headers, media_item_id)
    assert detail.get("provider") == "unstructured", \
           f"expected unstructured fallback, got: {detail}"
```

## Picking / generating the fixture

Three ways to force LlamaParse to fail:

1. **Empirical**: try various PDFs (scanned image-only, password-protected, vector-heavy CAD exports, esoteric encodings) and see which one LlamaParse rejects but Unstructured handles. Document why.
2. **Mock**: mock the LlamaParse response in the worker for this specific test so the fallback fires deterministically. Less E2E-pure but very reliable.
3. **Rate-limit synthesis**: simulate the LlamaParse rate-limit error response by mocking the HTTP client. This validates the rate-limit branch specifically.

Recommendation: **start with option 1** (empirical) — picking a real-world failing fixture is more meaningful for V1 user content. If no stable fixture is found, fall back to option 2.

## Cost

- LlamaParse attempt + failure: ~$0.001 or free tier
- Unstructured fallback: ~$0.001 / page
- Total < $0.01 per run

## Out of scope

- Other source fallback chains (separate tasks 149, 150, 152)
- DOCX / PPTX / XLSX coverage (PDF is enough to validate the chain)
- Performance comparison LlamaParse vs Unstructured (separate research task)

## References

- V1 launch plan §0 (LlamaParse primary + Unstructured fallback declared)
- `media_summarizer/workers/document_parsing/worker.py`
- `media_summarizer/infrastructure/resolvers/llamaparse_resolver.py`
- `media_summarizer/infrastructure/resolvers/unstructured_resolver.py`
- `tests/e2e/test_phase4_other_sources.py::test_document_upload` (happy path baseline)
- `tests/e2e/fixtures/sample.pdf` (existing trivial 1-page PDF used by happy path)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New test `test_document_unstructured_fallback` added in `tests/e2e/test_fallback_chains.py`
- [ ] #2 Fixture file added under `tests/e2e/fixtures/` and documented (origin, why LlamaParse rejects)
- [ ] #3 Test asserts BOTH `status == "completed"` AND `provider == "unstructured"`
- [ ] #4 If the metadata field doesn't exist, `GET /api/media/{id}` is extended to expose `provider`
- [ ] #5 Wall-clock < 30s
- [ ] #6 No regression on existing document happy-path test
<!-- AC:END -->
