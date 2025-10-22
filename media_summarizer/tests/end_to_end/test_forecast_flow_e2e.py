import os
import time
from datetime import datetime, timezone, timedelta
import boto3
import pytest
from fastapi.testclient import TestClient

from media_summarizer.api.main import app

# Mark entire module as forecast-only
pytestmark = pytest.mark.forecast


@pytest.mark.e2e
class TestForecastFlowE2E:
    def _ensure_env(self):
        os.environ.setdefault("AWS_REGION", "us-east-1")
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
        os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")

    def _ensure_tables(self):
        endpoint = os.environ["AWS_ENDPOINT_URL"]
        region = os.environ["AWS_REGION"]
        ddb = boto3.client(
            "dynamodb",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        def ensure_table(name, cfg):
            try:
                ddb.describe_table(TableName=name)
                return
            except Exception:
                pass
            ddb.create_table(TableName=name, **cfg)
            waiter = ddb.get_waiter("table_exists")
            waiter.wait(TableName=name)
        # Ensure feed_forecasts exists
        feed_forecasts_cfg = dict(
            KeySchema=[
                {"AttributeName": "feed_id", "KeyType": "HASH"},
                {"AttributeName": "month_key", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "feed_id", "AttributeType": "S"},
                {"AttributeName": "month_key", "AttributeType": "S"},
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        ensure_table("feed_forecasts", feed_forecasts_cfg)

    def _wipe_table(self, name: str):
        endpoint = os.environ["AWS_ENDPOINT_URL"]
        region = os.environ["AWS_REGION"]
        ddb = boto3.client(
            "dynamodb",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        start_key = None
        while True:
            if start_key:
                resp = ddb.scan(TableName=name, ExclusiveStartKey=start_key)
            else:
                resp = ddb.scan(TableName=name)
            items = resp.get('Items', [])
            for it in items:
                key = {"feed_id": it["feed_id"], "month_key": it["month_key"]}
                ddb.delete_item(TableName=name, Key=key)
            start_key = resp.get('LastEvaluatedKey')
            if not start_key:
                break

    @pytest.mark.asyncio
    async def test_forecast_persist_and_follow_reads_cache(self, monkeypatch):
        self._ensure_env()
        self._ensure_tables()
        self._wipe_table("feed_forecasts")
        client = TestClient(app)

        # Create user
        email = f"fc-user-{int(time.time())}@example.com"
        r = client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
        assert r.status_code in (200,201)
        r2 = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
        assert r2.status_code == 200
        token = r2.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        # Verify email directly in DB for simplicity
        ddb = boto3.client(
            "dynamodb",
            endpoint_url=os.environ["AWS_ENDPOINT_URL"],
            region_name=os.environ["AWS_REGION"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        users_table = "users"
        user_id = r2.json()["user"]["id"]
        now_iso = datetime.now(timezone.utc).isoformat()
        ddb.update_item(TableName=users_table, Key={"id": {"S": user_id}}, UpdateExpression="SET email_verified_at = :ts, updated_at = :ts", ExpressionAttributeValues={":ts": {"S": now_iso}})

        # Monkeypatch PodcastIndex episodes to create a deterministic forecast
        from datetime import datetime as _dt
        feed_id = 999001
        m0 = _dt(datetime.now(timezone.utc).year, datetime.now(timezone.utc).month, 1, tzinfo=timezone.utc)
        items = [
            {
                "id": 1,
                "guid": "a",
                "title": "Ep A",
                "datePublished": int(m0.timestamp()) + 60,
                "duration": 600,
                "enclosureUrl": "https://example.com/a.mp3",
                "feedTitle": "Test Podcast",
                "feedId": feed_id,
            },
            {
                "id": 2,
                "guid": "b",
                "title": "Ep B",
                "datePublished": int(m0.timestamp()) + 120,
                "duration": 120,
                "enclosureUrl": "https://example.com/b.mp3",
                "feedTitle": "Test Podcast",
                "feedId": feed_id,
            },
        ]
        async def fake_get_episodes_by_feed_id(feed_id: int, max_results: int = 10, since=None, http_client=None):
            return {"items": items, "status": "true", "count": len(items)}
        from media_summarizer.utils import podcast_index as pi
        monkeypatch.setattr(pi, "get_episodes_by_feed_id", fake_get_episodes_by_feed_id)

        # Call episodes to compute and persist forecast
        resp = client.post("/api/v1/podcast-search/episodes", json={"feed_id": feed_id, "max_results": 50})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("forecast", {}).get("minutes_per_month") >= 12  # 10 + 2

        # Check feed_forecasts row exists with ttl
        out = ddb.scan(TableName="feed_forecasts")
        items_db = out.get("Items", [])
        assert any(i.get("feed_id",{}).get("S")==str(feed_id) for i in items_db)
        row = next(i for i in items_db if i["feed_id"]["S"] == str(feed_id))
        assert "ttl" in row
        ttlv = int(row["ttl"]["N"])
        assert ttlv > int(datetime.now(timezone.utc).timestamp())

        # Now follow (should read cache-only and set reserved_minutes accordingly)
        rfollow = client.post("/api/v1/follows", json={"feed_id": feed_id}, headers=headers)
        assert rfollow.status_code == 200, rfollow.text
        fr = rfollow.json()
        assert fr["forecast_minutes"] >= 12
        assert fr["reserved_minutes"] == fr["forecast_minutes"]

        # /billing/me reservations should aggregate
        me = client.get("/api/v1/billing/me", headers=headers)
        assert me.status_code == 200
        m = me.json()
        assert m["reservations"]["reserved_minutes"] >= fr["reserved_minutes"]

