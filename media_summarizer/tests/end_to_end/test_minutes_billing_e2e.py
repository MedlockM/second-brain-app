"""
E2E tests for the minutes-based billing system (subscriptions and packs).

Validates:
- Checkout creation for packs and subscriptions
- Webhook handling to credit minute buckets
- Aggregation via /billing/me and /billing/history
- Minute consumption flow (hold + finalize) via submit endpoint and minute_pool
"""
import os
import json
import time
from datetime import datetime, timezone, timedelta

import boto3
import pytest
from fastapi.testclient import TestClient

from media_summarizer.api.main import app


@pytest.mark.e2e
class TestMinutesBillingE2E:
    def _ensure_env(self):
        # LocalStack endpoints
        os.environ.setdefault("AWS_REGION", "us-east-1")
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
        os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")
        # Stripe env
        os.environ.setdefault("STRIPE_API_KEY", "sk_test_dummy")
        os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")
        # Stripe prices (dummy IDs)
        os.environ.setdefault("STRIPE_PRICE_ID_SUB_S", "price_sub_s_test")
        os.environ.setdefault("STRIPE_PRICE_ID_SUB_M", "price_sub_m_test")
        os.environ.setdefault("STRIPE_PRICE_ID_SUB_L", "price_sub_l_test")
        os.environ.setdefault("STRIPE_PRICE_ID_PACK_100", "price_pack_100_test")
        os.environ.setdefault("STRIPE_PRICE_ID_PACK_300", "price_pack_300_test")
        os.environ.setdefault("STRIPE_PRICE_ID_PACK_600", "price_pack_600_test")
        os.environ.setdefault("STRIPE_PRICE_ID_PACK_1200", "price_pack_1200_test")
        # Redirects
        os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

    def _ensure_localstack_resources(self):
        endpoint = os.environ["AWS_ENDPOINT_URL"]
        region = os.environ["AWS_REGION"]
        # Clients
        ddb = boto3.client(
            "dynamodb",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        sqs = boto3.client(
            "sqs",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        # Queues required by submit endpoints/workflow
        for q in [
            "audio-download-queue",
            "transcription-queue",
            "summarization-queue",
            "email-notification-queue",
        ]:
            try:
                sqs.create_queue(QueueName=q)
            except Exception:
                pass
        # Buckets (not strictly needed for billing tests but harmless)
        for b in [
            "media-summarizer-audio",
            "media-summarizer-transcriptions",
            "media-summarizer-summaries",
        ]:
            try:
                s3.create_bucket(Bucket=b)
            except Exception:
                pass
        # Tables: users, auth_tokens, processing_jobs, stripe_events, subscriptions, minute_buckets, minute_usage, follows, feed_forecasts
        def ensure_table(name, cfg):
            try:
                ddb.describe_table(TableName=name)
                return
            except Exception:
                pass
            ddb.create_table(TableName=name, **cfg)
            waiter = ddb.get_waiter("table_exists")
            waiter.wait(TableName=name)
        # Minimal definitions for required tables
        users_cfg = dict(
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "email", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "email-index",
                    "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        auth_tokens_cfg = dict(
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "token", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "token_type", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "token-index",
                    "KeySchema": [{"AttributeName": "token", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
                {
                    "IndexName": "user-index",
                    "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        processing_jobs_cfg = dict(
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user-index",
                    "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        stripe_events_cfg = dict(
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        subscriptions_cfg = dict(
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "stripe_subscription_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user-index",
                    "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
                {
                    "IndexName": "stripe-index",
                    "KeySchema": [
                        {"AttributeName": "stripe_subscription_id", "KeyType": "HASH"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        minute_buckets_cfg = dict(
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "expires_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user-index",
                    "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
                {
                    "IndexName": "expiry-index",
                    "KeySchema": [{"AttributeName": "expires_at", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        minute_usage_cfg = dict(
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "job_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user-index",
                    "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
                {
                    "IndexName": "job-index",
                    "KeySchema": [{"AttributeName": "job_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        follows_cfg = dict(
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "feed_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "feed_id", "AttributeType": "S"},
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        ensure_table("users", users_cfg)
        ensure_table("auth_tokens", auth_tokens_cfg)
        ensure_table("processing_jobs", processing_jobs_cfg)
        ensure_table("stripe_events", stripe_events_cfg)
        ensure_table("subscriptions", subscriptions_cfg)
        ensure_table("minute_buckets", minute_buckets_cfg)
        ensure_table("minute_usage", minute_usage_cfg)
        ensure_table("follows", follows_cfg)
        # Feed forecasts table (shared cache)
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

    def _register_and_login(self, client: TestClient, email: str, password: str) -> tuple[str, str]:
        # Register
        r = client.post("/api/v1/auth/register", json={"email": email, "password": password})
        assert r.status_code in (200, 201), r.text
        # Login to get token
        r2 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r2.status_code == 200, r2.text
        data = r2.json()
        return data["access_token"], data["user"]["id"]

    def _verify_email(self, user_id: str):
        # Directly set email_verified_at on user row in DynamoDB
        ddb = boto3.client(
            "dynamodb",
            endpoint_url=os.environ["AWS_ENDPOINT_URL"],
            region_name=os.environ["AWS_REGION"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        now = datetime.now(timezone.utc).isoformat()
        ddb.update_item(
            TableName="users",
            Key={"id": {"S": user_id}},
            UpdateExpression="SET email_verified_at = :ts, updated_at = :ts",
            ExpressionAttributeValues={":ts": {"S": now}},
        )

    def test_pack_checkout_webhook_and_consumption(self, monkeypatch):
        self._ensure_env()
        self._ensure_localstack_resources()
        client = TestClient(app)
        # Create user + verify email
        email = f"pack-user-{int(time.time())}@example.com"
        token, user_id = self._register_and_login(client, email, "Password123!")
        self._verify_email(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        # Patch stripe checkout session creation
        class _Session:
            def __init__(self, sid, url):
                self.id = sid
                self.url = url
        def fake_session_create(mode=None, customer=None, line_items=None, success_url=None, cancel_url=None, metadata=None, payment_intent_data=None, allow_promotion_codes=None, payment_method_types=None):
            return _Session("cs_test_123", "https://checkout.stripe.com/test")
        import stripe
        # Patch Stripe network calls
        monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(fake_session_create))
        class _CusList:
            def __init__(self, data):
                self.data = data
        def fake_customer_list(email=None, limit=None):
            # No existing customer
            return _CusList([])
        def fake_customer_create(email=None):
            class C: pass
            c = C()
            c.id = "cus_test_local"
            return c
        monkeypatch.setattr(stripe.Customer, "list", staticmethod(fake_customer_list))
        monkeypatch.setattr(stripe.Customer, "create", staticmethod(fake_customer_create))

        # Create pack checkout
        resp = client.post("/api/v1/billing/packs/checkout", json={"minutes": 300}, headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("session_id")
        assert body.get("url")

        # Simulate Stripe webhook: checkout.session.completed (mode=payment)
        event = {
            "id": "evt_test_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "payment",
                    "metadata": {"user_id": user_id, "type": "pack", "minutes": "300"},
                }
            },
        }
        def fake_construct_event(payload, sig_header, secret):
            # Return our event regardless of signature
            return json.loads(payload.decode("utf-8"))
        monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(fake_construct_event))
        rwh = client.post(
            "/api/v1/payments/webhook",
            data=json.dumps(event),
            headers={"stripe-signature": "t=1,v1=test"},
        )
        assert rwh.status_code == 200, rwh.text

        # Check /billing/me totals
        me = client.get("/api/v1/billing/me", headers=headers)
        assert me.status_code == 200, me.text
        m = me.json()
        assert m["minutes"]["by_source"]["packs"] >= 300
        total_free_before = m["minutes"]["total_free"]

        # Submit a podcast (creates a hold)
        submit = client.post(
            "/api/v1/podcasts/submit",
            json={"podcast_url": "https://example.com/feed.xml", "user_email": email},
            headers=headers,
        )
        assert submit.status_code in (200, 201), submit.text
        job_id = submit.json().get("job_id")
        assert job_id

        # Finalize usage for 5 minutes (simulate worker)
        from media_summarizer.core.services.minute_pool import finalize_usage
        import asyncio
        ok = asyncio.get_event_loop().run_until_complete(finalize_usage(job_id, 5))
        assert ok is True

        # Verify minutes decreased
        me2 = client.get("/api/v1/billing/me", headers=headers)
        assert me2.status_code == 200
        m2 = me2.json()
        assert m2["minutes"]["total_free"] == total_free_before - 5

    def test_subscription_checkout_and_monthly_credit(self, monkeypatch):
        self._ensure_env()
        self._ensure_localstack_resources()
        client = TestClient(app)
        # Create user + verify email
        email = f"sub-user-{int(time.time())}@example.com"
        token, user_id = self._register_and_login(client, email, "Password123!")
        self._verify_email(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        # Patch stripe checkout session creation (subscription)
        class _Session:
            def __init__(self, sid, url, subscription):
                self.id = sid
                self.url = url
                self.subscription = subscription
        def fake_session_create(mode=None, customer=None, line_items=None, success_url=None, cancel_url=None, metadata=None, allow_promotion_codes=None, payment_method_types=None):
            return _Session("cs_test_456", "https://checkout.stripe.com/test", "sub_test_1")
        import stripe
        # Patch Stripe network calls
        monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(fake_session_create))
        class _CusList:
            def __init__(self, data):
                self.data = data
        def fake_customer_list(email=None, limit=None):
            # No existing customer
            return _CusList([])
        def fake_customer_create(email=None):
            class C: pass
            c = C()
            c.id = "cus_test_local"
            return c
        monkeypatch.setattr(stripe.Customer, "list", staticmethod(fake_customer_list))
        monkeypatch.setattr(stripe.Customer, "create", staticmethod(fake_customer_create))

        # Create subscription checkout (tier S)
        resp = client.post("/api/v1/billing/subscriptions/checkout", json={"tier": "S"}, headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("session_id")

        # Webhook: checkout.session.completed (mode=subscription) -> creates subscription record
        event1 = {
            "id": "evt_test_sub_completed",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "subscription",
                    "subscription": "sub_test_1",
                    "metadata": {"user_id": user_id, "type": "subscription", "tier": "S", "minutes_per_period": "240"},
                    "customer": "cus_test_123",
                }
            },
        }
        def fake_construct_event(payload, sig_header, secret):
            return json.loads(payload.decode("utf-8"))
        monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(fake_construct_event))
        r1 = client.post(
            "/api/v1/payments/webhook",
            data=json.dumps(event1),
            headers={"stripe-signature": "t=1,v1=test"},
        )
        assert r1.status_code == 200, r1.text

        # Webhook: invoice.payment_succeeded -> create monthly minutes bucket
        now = int(datetime.now(timezone.utc).timestamp())
        end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        event2 = {
            "id": "evt_test_invoice",
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "subscription": "sub_test_1",
                    "customer": "cus_test_123",
                    "lines": {"data": [{"period": {"start": now, "end": end}}]},
                }
            },
        }
        r2 = client.post(
            "/api/v1/payments/webhook",
            data=json.dumps(event2),
            headers={"stripe-signature": "t=2,v1=test"},
        )
        assert r2.status_code == 200, r2.text

        # Check /billing/me shows subscription status and monthly minutes
        me = client.get("/api/v1/billing/me", headers=headers)
        assert me.status_code == 200
        m = me.json()
        assert m["subscription"]["tier"] == "S"
        assert m["minutes"]["by_source"]["subscription"] >= 240

    def test_billing_history_contains_events(self, monkeypatch):
        self._ensure_env()
        self._ensure_localstack_resources()
        client = TestClient(app)
        # Create user + verify email
        email = f"hist-user-{int(time.time())}@example.com"
        token, user_id = self._register_and_login(client, email, "Password123!")
        self._verify_email(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        # Patch stripe checkout session creation
        class _Session:
            def __init__(self, sid, url, subscription=None):
                self.id = sid
                self.url = url
                self.subscription = subscription
        def fake_session_create(mode=None, customer=None, line_items=None, success_url=None, cancel_url=None, metadata=None, payment_intent_data=None, allow_promotion_codes=None, payment_method_types=None):
            # Return a session id; include subscription id in subscription mode
            sub = "sub_hist_1" if mode == "subscription" else None
            return _Session("cs_hist_123", "https://checkout.stripe.com/test", sub)
        import stripe
        # Patch Stripe network calls
        monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(fake_session_create))
        class _CusList:
            def __init__(self, data):
                self.data = data
        def fake_customer_list(email=None, limit=None):
            return _CusList([])
        def fake_customer_create(email=None):
            class C: pass
            c = C()
            c.id = "cus_hist_local"
            return c
        monkeypatch.setattr(stripe.Customer, "list", staticmethod(fake_customer_list))
        monkeypatch.setattr(stripe.Customer, "create", staticmethod(fake_customer_create))

        def fake_construct_event(payload, sig_header, secret):
            return json.loads(payload.decode("utf-8"))
        monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(fake_construct_event))

        # 1) Pack purchase -> pack bucket event
        resp_pack = client.post("/api/v1/billing/packs/checkout", json={"minutes": 100}, headers=headers)
        assert resp_pack.status_code == 200
        evt_pack = {
            "id": "evt_hist_pack",
            "type": "checkout.session.completed",
            "data": {"object": {"mode": "payment", "metadata": {"user_id": user_id, "type": "pack", "minutes": "100"}}},
        }
        rwh_pack = client.post("/api/v1/payments/webhook", data=json.dumps(evt_pack), headers={"stripe-signature": "t=1,v1=test"})
        assert rwh_pack.status_code == 200

        # 2) Subscription period -> subscription bucket event
        resp_sub = client.post("/api/v1/billing/subscriptions/checkout", json={"tier": "S"}, headers=headers)
        assert resp_sub.status_code == 200
        # create subscription record
        evt_sub_completed = {
            "id": "evt_hist_sub_completed",
            "type": "checkout.session.completed",
            "data": {"object": {"mode": "subscription", "subscription": "sub_hist_1", "metadata": {"user_id": user_id, "type": "subscription", "tier": "S", "minutes_per_period": "240"}, "customer": "cus_hist_123"}},
        }
        rwh_sub1 = client.post("/api/v1/payments/webhook", data=json.dumps(evt_sub_completed), headers={"stripe-signature": "t=2,v1=test"})
        assert rwh_sub1.status_code == 200
        # credit monthly bucket
        now = int(datetime.now(timezone.utc).timestamp())
        end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        evt_invoice = {
            "id": "evt_hist_invoice",
            "type": "invoice.payment_succeeded",
            "data": {"object": {"subscription": "sub_hist_1", "customer": "cus_hist_123", "lines": {"data": [{"period": {"start": now, "end": end}}]}}},
        }
        rwh_sub2 = client.post("/api/v1/payments/webhook", data=json.dumps(evt_invoice), headers={"stripe-signature": "t=3,v1=test"})
        assert rwh_sub2.status_code == 200

        # 3) Fetch billing history and assert presence of events
        hist = client.get("/api/v1/billing/history", headers=headers)
        assert hist.status_code == 200, hist.text
        h = hist.json()
        assert h["counts"]["pack_purchases"] >= 1
        assert h["counts"]["subscription_periods"] >= 1
        # Ensure events list contains both types
        types = {e.get("type") for e in h.get("events", [])}
        assert "pack_purchase" in types
        assert "subscription_bucket" in types
