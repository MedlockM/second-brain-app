---
id: task-98
title: >-
  Remove all Stripe integration code and replace billing with RevenueCat-ready
  architecture
status: Done
assignee: []
created_date: '2026-05-19 16:26'
labels:
  - cleanup
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The mobile app will be distributed via Apple App Store and Google Play, which prohibit third-party payment processors (Stripe) for digital goods consumed in-app. Stripe must be fully removed and replaced with a RevenueCat-compatible architecture.

## Files to delete entirely:
- `media_summarizer/core/services/stripe_service_v2.py` — Stripe webhook handler, checkout session creation, subscription management
- `media_summarizer/api/endpoints/billing.py` — Stripe-specific billing API routes (checkout, webhook, portal)
- `media_summarizer/api/models/payment.py` — Stripe-specific request/response models
- `media_summarizer/tests/unit/core/services/test_stripe_service.py` — Stripe service tests
- `media_summarizer/tests/unit/api/endpoints/test_payments.py` — Stripe endpoint tests
- `media_summarizer/tests/unit/api/models/test_payment.py` — Stripe model tests
- `infrastructure/terraform/dynamodb_stripe_events.tf` — Stripe idempotency table
- `front/src/components/PaymentMethods.tsx` — Stripe payment UI
- `front/src/components/PricingPage.tsx` — Stripe checkout pricing page

## Files to edit (remove Stripe references, keep the rest):
- `media_summarizer/core/config.py` — remove all STRIPE_* config vars
- `media_summarizer/api/main.py` — remove billing router import/include
- `media_summarizer/core/services/__init__.py` — remove stripe_service export
- `media_summarizer/core/models/billing.py` — remove Stripe-specific fields (stripe_customer_id, stripe_subscription_id, stripe_price_id) but KEEP the subscription/minutes model structure
- `media_summarizer/utils/database_async.py` — remove stripe_events table references
- `media_summarizer/utils/minute_db.py` — remove stripe_events references
- `media_summarizer/tests/utils/base_test_classes.py` — remove Stripe mocks/fixtures
- `media_summarizer/tests/utils/localstack_helpers.py` — remove stripe_events table creation
- `infrastructure/terraform/localstack/main.tf` — remove stripe_events table from LocalStack provisioning
- `infrastructure/terraform/dynamodb_minutes_tables.tf` — remove stripe-index GSI from subscriptions table if it only serves Stripe lookup
- `docker-compose.dev.yml` — remove STRIPE_* env vars
- `pyproject.toml` — remove `stripe>=7.0.0` dependency
- `.env.example` — remove all STRIPE_* variables (lines 135-163)
- `.github/workflows/integration-tests.yml` — remove Stripe-related test matrix entries
- `.github/workflows/e2e-tests.yml` — remove Stripe webhook test steps
- `openapi.json` — remove /billing/* endpoints
- `README.md` — remove Stripe mentions

## What to KEEP intact:
- The `subscriptions` DynamoDB table itself (will be reused for RevenueCat entitlements)
- The `minute_buckets` and `minute_usage` tables (consumption tracking stays)
- The minutes/quota accounting logic in `minute_db.py` (decrement/check logic is payment-agnostic)
- The user's subscription status field in the user model (just remove the stripe_* fields)

## After cleanup, leave a stub:
- Create `media_summarizer/api/endpoints/entitlements.py` with a single `GET /api/entitlements/status` endpoint that returns the user's current subscription tier and remaining minutes (reads from DynamoDB). This is the endpoint the mobile app will call to check access. Mark it with a TODO comment: "Wire to RevenueCat webhook handler in task-XX" (reference the RevenueCat implementation task).

## Verification:
- `grep -r "stripe\|Stripe\|STRIPE" --include="*.py" --include="*.ts" --include="*.tf" --include="*.yml" --include="*.toml"` returns zero results (excluding docs/research/ which are historical)
- Python tests pass (`pytest` — no import errors from removed modules)
- API starts without errors (`uvicorn media_summarizer.api.main:app`)
- `terraform validate` passes on the infra directory
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No Stripe imports, env vars, or API routes remain in Python/TS/Terraform code (docs/research excluded)
- [ ] #2 stripe dependency removed from pyproject.toml
- [ ] #3 dynamodb_stripe_events.tf deleted, stripe_events table removed from LocalStack provisioning
- [ ] #4 Subscriptions table and minute accounting logic preserved intact
- [ ] #5 GET /api/entitlements/status endpoint exists and returns user tier + remaining minutes
- [ ] #6 pytest runs without import errors
- [ ] #7 API server starts without errors
<!-- AC:END -->
