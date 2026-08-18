"""Health check smoke test against AWS dev API."""

import httpx
import pytest


@pytest.mark.e2e
async def test_health_endpoint_returns_200(http_client: httpx.AsyncClient) -> None:
    resp = await http_client.get("/api/health/")
    assert resp.status_code == 200, f"unexpected status {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("status") == "healthy", f"unexpected payload: {body}"
    assert body.get("database") == "connected", f"db not connected: {body}"
