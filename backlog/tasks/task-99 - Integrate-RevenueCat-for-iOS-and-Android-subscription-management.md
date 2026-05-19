---
id: task-99
title: Integrate RevenueCat for iOS and Android subscription management
status: To Do
assignee: []
created_date: '2026-05-19 16:27'
labels:
  - feature
  - mobile
dependencies:
  - task-98
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement in-app purchase and subscription management using RevenueCat as the cross-platform abstraction layer over Apple StoreKit and Google Play Billing. RevenueCat handles receipt validation, entitlement management, and provides webhooks to sync subscription state to our backend.

## Context
- The app uses a 3-tier persona pricing model (validated in docs/research/task-65-pricing-v1-benchmark/README.md): Text-Only 3€, Mix 5€, Audio-Heavy 9€
- Minutes are tracked in DynamoDB tables (`subscriptions`, `minute_buckets`, `minute_usage`) — this logic already exists
- After task-98 (Stripe removal), a stub endpoint `GET /api/entitlements/status` exists that returns the user's tier and remaining minutes
- The mobile app is React Native + Expo

## What to implement

### 1. RevenueCat SDK integration (mobile side)
- Install `react-native-purchases` (RevenueCat's React Native SDK)
- Initialize RevenueCat with platform-specific API keys in `mobile/app/_layout.tsx` (or a dedicated provider)
- Identify the user with our backend user ID (`Purchases.logIn(userId)`) after authentication
- Create a `mobile/src/services/purchaseService.ts` that exposes:
  - `getOfferings()` — fetch available subscription packages
  - `purchasePackage(pkg)` — trigger native purchase flow
  - `restorePurchases()` — restore previous purchases (required by Apple)
  - `getCustomerInfo()` — check current entitlements
- Create a paywall screen `mobile/app/paywall.tsx` showing the 3 tiers with native purchase buttons
- Handle purchase states: success, cancelled, pending (Ask to Buy), error
- After successful purchase, call `GET /api/entitlements/status` to refresh local state

### 2. RevenueCat webhook handler (backend side)
- Create `media_summarizer/api/endpoints/revenucat_webhook.py`
- Endpoint: `POST /api/webhooks/revenucat`
- Verify webhook authenticity via the `Authorization` header (shared secret)
- Handle RevenueCat event types:
  - `INITIAL_PURCHASE` → create/update subscription in DynamoDB, credit minute bucket
  - `RENEWAL` → credit new minute bucket for the period
  - `CANCELLATION` → mark subscription as cancelled (still active until period end)
  - `EXPIRATION` → mark subscription as expired, stop crediting minutes
  - `BILLING_ISSUE_DETECTED` → flag subscription as grace period
  - `PRODUCT_CHANGE` → handle upgrade/downgrade (prorate minutes)
- Map RevenueCat product IDs to our 3 tiers (Text-Only/Mix/Audio-Heavy) and their minute allocations
- Idempotency: use RevenueCat event ID to prevent double-processing (store in a `revenucat_events` DynamoDB table)

### 3. Entitlements endpoint enhancement
- Enhance the stub `GET /api/entitlements/status` (created by task-98) to:
  - Return current tier, period end date, renewal status, remaining minutes
  - Include a `is_active` boolean for the mobile app's paywall gate
  - Return `offerings_config` with tier details for the paywall if user has no active subscription

### 4. DynamoDB additions
- Create `infrastructure/terraform/dynamodb_revenucat_events.tf` — idempotency table for webhook events (PK: event_id, TTL: 30 days)
- Update the `subscriptions` table model: add fields `revenucat_app_user_id`, `revenucat_product_id`, `platform` (ios/android), `period_end`, `auto_renew_status`

### 5. Configuration
- Add to `.env.example`: `REVENUCAT_API_KEY`, `REVENUCAT_WEBHOOK_SECRET`, `REVENUCAT_PROJECT_ID`
- Add to `media_summarizer/core/config.py`: RevenueCat config section
- Add to `mobile/app.config.ts` or env: `EXPO_PUBLIC_REVENUCAT_APPLE_KEY`, `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY`

## What NOT to do
- Do NOT implement free trial logic in V1 (keep it simple: pay → get minutes)
- Do NOT implement coupon/promo codes in V1
- Do NOT add a web paywall — subscriptions are mobile-only for now

## Testing strategy
- Use RevenueCat sandbox mode (auto-detected when using sandbox Apple/Google accounts)
- Create StoreKit Configuration file for local iOS testing
- Add yourself as Google Play License Tester for Android testing
- Verify webhook handling with RevenueCat's "Test Webhook" button in dashboard

## References
- RevenueCat React Native SDK: https://docs.revenuecat.com/docs/reactnative
- RevenueCat webhooks: https://docs.revenuecat.com/docs/webhooks
- Pricing benchmark: `docs/research/task-65-pricing-v1-benchmark/README.md` (Decision section)
- Existing minute accounting: `media_summarizer/utils/minute_db.py`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 RevenueCat SDK initialized in mobile app with platform-specific keys
- [ ] #2 Paywall screen shows 3 subscription tiers with native purchase flow
- [ ] #3 Restore purchases button works and syncs entitlements
- [ ] #4 POST /api/webhooks/revenucat handles INITIAL_PURCHASE, RENEWAL, CANCELLATION, EXPIRATION events
- [ ] #5 Webhook events are idempotent (duplicate event IDs ignored)
- [ ] #6 GET /api/entitlements/status returns active tier, remaining minutes, and period end date
- [ ] #7 Successful purchase credits the correct minute allocation to the user's bucket
- [ ] #8 DynamoDB revenucat_events table created in Terraform
<!-- AC:END -->
