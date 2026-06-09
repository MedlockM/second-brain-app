"""E2E tests for provider fallback chains.

Each test forces the primary provider to fail (via environment variable or
fixture selection) and asserts that the fallback provider completes the job
successfully. This validates the resilience of the ingestion pipeline.

IMPORTANT: These tests require the FORCE_* environment variables to be set
on the **worker** process (Lambda or ECS task), not on the test runner. In
AWS dev, this means the Lambda/ECS env must have the variable set before
running the test. For local development, set it in the worker's .env file.

When running against AWS dev, the environment variable must be pre-configured
on the document-parsing worker Lambda (e.g. via terraform or manual console
update). The test will skip if the fallback does not fire (i.e. if the env
var is not set on the worker side).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import httpx
import pytest

from tests.e2e.conftest import poll_until


@pytest.mark.e2e
async def test_document_unstructured_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Document upload where LlamaParse fails -> Unstructured fallback succeeds.

    Prerequisites:
        The document-parsing worker must have FORCE_LLAMAPARSE_FAILURE=1 set
        in its environment. This causes LlamaParse to return a simulated
        rate-limit error, triggering the Unstructured fallback path.

    Assertions:
        - Job reaches status == "completed"
        - provider == "unstructured" (proving the fallback fired)

    Fixture:
        tests/e2e/fixtures/sample.pdf -- the same 1-page PDF used by the
        happy-path test. Any valid PDF works since the failure is forced via
        environment variable, not file content.
    """
    fixture = Path(__file__).parent / "fixtures" / "sample.pdf"
    assert fixture.exists(), f"Fixture not found: {fixture}"

    with fixture.open("rb") as f:
        files = {"file": ("sample.pdf", f, "application/pdf")}
        resp = await http_client.post(
            "/api/media/upload",
            files=files,
            headers=auth_headers,
        )

    assert resp.status_code == 202, (
        f"upload failed: {resp.status_code} {resp.text}"
    )
    media_item_id = resp.json()["media_item_id"]

    # Poll until terminal state (completed or failed)
    body = await poll_until(
        client=http_client,
        url=f"/api/media/{media_item_id}",
        headers=auth_headers,
        predicate=lambda b: b.get("status") in ("completed", "failed"),
        timeout_s=30,
        interval_s=3,
    )

    assert body.get("status") == "completed", (
        f"document parsing did not complete: status={body.get('status')}, "
        f"error={body.get('error_message')}"
    )

    # Verify the fallback provider was used
    provider = body.get("provider")
    assert provider == "unstructured", (
        f"Expected fallback provider 'unstructured', got: '{provider}'. "
        f"Ensure FORCE_LLAMAPARSE_FAILURE=1 is set on the document-parsing worker."
    )
