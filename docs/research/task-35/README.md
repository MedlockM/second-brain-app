---
benchmark_validated: false
---

## Owner Validation

**Status**: ⏳ Pending owner review
**Decision**: _(à remplir par l'owner après relecture — accept / reject / accept with modifications)_
**Validated at**: _(date ISO à remplir par l'owner)_

---

# Task 35: Media Processing Quotas Research & Implementation Plan

**Date**: 2026-04-22  
**Status**: Research Complete  
**Context**: Transition from artifact-generation quotas to media-processing quotas aligned with V1 pricing model

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Context & Problem Statement](#context--problem-statement)
3. [Pricing Model Analysis (from task-65)](#pricing-model-analysis-from-task-65)
4. [Quota System Benchmarks](#quota-system-benchmarks)
5. [Proposed Quota Architecture](#proposed-quota-architecture)
6. [Implementation Plan](#implementation-plan)
7. [Testing Strategy](#testing-strategy)
8. [Monitoring & Observability](#monitoring--observability)

---

## Executive Summary

This document defines a quota system for media-summarizer that enforces **media processing limits** (number of media items processed per time window) rather than artifact generation limits. The system aligns with the V1 pricing model established in task-65 and ensures that artifacts are generated once per media item and reused across users.

**Key Decisions**:
- Quota surface: **media submissions per user per time window** (monthly)
- Enforcement point: **POST /api/media/ingest-url** (before job creation)
- Storage: **DynamoDB `user_quotas` table** with sliding window counters
- Error handling: **HTTP 429 with stable error code `QUOTA_EXCEEDED`**
- Artifact access: **Never blocked by quota** (artifacts are reused, not regenerated)

**Recommended Quota Tiers (aligned with task-65 pricing)**:
- **Free**: 5 media/month
- **Standard (9€/month)**: 50 media/month
- **Pro (15€/month)**: 150 media/month

---

## Context & Problem Statement

### Current State

The legacy system has:
1. **Per-artifact generation quotas** that don't align with the product model
2. **Artifact idempotence** (task-34) via `media_artifacts` and `artifact_idempotence` tables in DynamoDB
3. **Minute-based billing** (`minute_buckets`, `minute_usage`) that predates the V1 pricing model

### Target State

The V1 product model requires:
1. **Media-centric quotas**: Limit how many media items a user can submit/process per month
2. **Artifact reuse**: Once an artifact (summary_short, summary_detailed, flashcards, notes) is generated for a media item, it's stored in S3 and reused for any user who has that media in their documentary base
3. **No per-artifact quotas**: Requesting an already-generated artifact should never consume quota
4. **Pricing alignment**: Quotas must match the tier limits from task-65 (Free: 5/month, Standard: 50/month, Pro: 150/month)

### Key Constraint

**Artifacts are single-generation-per-media-item**. The system uses `generation_fingerprint` (from task-34) to ensure idempotence:
- If artifact already exists → return existing S3 key (no LLM call, no cost, no quota consumed)
- If artifact doesn't exist → generate once, store in S3, share across users

**Therefore**: Quota enforcement must happen at **media ingestion** (not artifact generation).

---

## Pricing Model Analysis (from task-65)

### V1 Pricing Tiers

From `docs/research/task-65-benchmark-pricing-v1.md`:

| Tier | Price/Month | Media Limit | Cost per Media (avg) | Margin |
|------|-------------|-------------|----------------------|--------|
| **Free** | €0 | **5 media/month** | $0.072 (mix) | -$0.36/month (acquisition cost) |
| **Standard** | **€9** | **50 media/month** | $0.072 (mix) | +€4.66 (107% margin) |
| **Pro** | **€15** | **150 media/month** | $0.072 (mix) | +€6.76 (82% margin) |

**Key Insights**:
- Standard tier (9€/50 media) is the target for MVP
- Free tier (5 media) is for acquisition (to be added post-MVP)
- Pro tier (150 media) is for power users (to be added post-MVP)
- OpenAI pricing refresh in task-65 does **not** change the quota tiers here, because the retained artifact cost baseline is still Gemini 2.5 Flash-Lite
- Cost per media: ~$0.072 (mix of 40% podcasts/video, 50% articles, 10% OCR)
- Media processing cost breakdown:
  - Transcription (audio/video): $0.175 per 35min media
  - Artifacts (all 3): $0.00167 per media (Gemini 2.5 Flash-Lite)
  - OCR (10% of media): $0.0045 per image

### Competitor Benchmarks

| Competitor | Price | Limit | Type |
|-----------|-------|-------|------|
| **Snipd Premium** | $6.99/month | **900 min/month** | Podcasts only (~20-25 episodes) |
| **Otter.ai Pro** | $8.49/month | **1,200 min/month** | Transcription (~25-30 episodes) |
| **Readwise Full** | $9.99/month | No strict limit | Highlights + Reader |
| **mymind Student** | $7.99/month | No strict limit | Visual bookmarks + AI |

**Observation**: Most competitors use **time-based limits** (minutes of audio) for transcription services, or **no explicit limits** for text-based services. Our **media count limit** (50/month) is comparable to Snipd's 900 min (~30 episodes of 30min each).

---

## Quota System Benchmarks

### Industry Standards

#### 1. Anthropic Claude API (Usage Tiers)

Source: https://platform.claude.com/docs/en/api/rate-limits

**Tier Structure**:
- Tier 1: $5 deposit, $100/month spend limit
- Tier 2: $40 deposit, $500/month spend limit
- Tier 3: $200 deposit, $1,000/month spend limit
- Tier 4: $400 deposit, $200,000/month spend limit

**Rate Limits** (Tier 4 example):
- RPM: 4,000 requests/min
- Input tokens: 2M tokens/min (Sonnet 4.x)
- Output tokens: 400K tokens/min

**Key Mechanisms**:
- **Token bucket algorithm** for rate limiting (continuous replenishment)
- **Spend limits** enforced at organization level (monthly reset)
- **HTTP 429 errors** with `retry-after` header
- **Response headers** expose remaining quota and reset time
- **Tiered access** with automatic promotion based on spend

**Takeaway**: Combine **monthly spend limits** (quota ceiling) with **rate limits** (burst protection).

#### 2. Stripe Usage-Based Billing

Source: https://docs.stripe.com/billing/subscriptions/usage-based

**Patterns**:
- **Metered usage recording**: Track consumption events in real-time
- **Threshold alerts**: Notify admins when customers exceed limits
- **Billing credits**: Prepaid/promotional credits alongside metered usage

**Takeaway**: Track usage events (media submissions) and expose them to users for transparency.

#### 3. Rate Limiting Algorithms

Sources:
- Kong HQ: https://konghq.com/blog/engineering/how-to-design-a-scalable-rate-limiting-algorithm
- Figma: https://www.figma.com/blog/an-alternative-approach-to-rate-limiting/

**Algorithms Evaluated**:

1. **Token Bucket**: Refills tokens at fixed rate, requests consume tokens
   - Pros: Smooths bursts, memory efficient
   - Cons: Race conditions (read-then-write), requires locks/Lua scripts

2. **Fixed Window**: Count requests in fixed time intervals
   - Pros: Simple, no starvation
   - Cons: Boundary burst problem (2x limit at window edges)

3. **Sliding Window Log**: Store timestamped requests, calculate rate over sliding window
   - Pros: Precise, no boundary issues
   - Cons: High memory cost (20MB for 10K users × 500 requests/day)

4. **Sliding Window Counters** (Recommended by Figma)
   - Pros: Balance precision and memory efficiency
   - Implementation: Divide window into smaller buckets (e.g., 60 one-minute counters for hourly limit)
   - Storage: Redis hashes (<100 keys) → ~2.4MB vs 20MB for sliding log
   - Accuracy: To-the-second precision

**Takeaway**: Use **Fixed Window** for monthly quotas (simple, low memory) + **Sliding Window Counters** for rate limits (if needed for burst protection).

---

## Proposed Quota Architecture

### Quota Model

#### DynamoDB Table: `user_quotas`

**Purpose**: Track media submissions per user per time window.

**Schema**:
```python
{
  "pk": "user_id",                    # Partition key
  "sk": "quota#YYYY-MM",              # Sort key (year-month for monthly quotas)
  "tier": "standard",                 # free, standard, pro
  "limit": 50,                        # Max media allowed for this tier/window
  "count": 23,                        # Current count of media submitted
  "window_start": "2026-04-01T00:00:00Z",  # ISO timestamp
  "window_end": "2026-05-01T00:00:00Z",    # ISO timestamp
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-22T14:30:00Z",
  "ttl": 1748736000                   # Auto-delete after window_end + 90 days
}
```

**Access Patterns**:
- Get current quota for user: `pk = user_id, sk begins_with "quota#2026-04"`
- Update quota count (atomic increment): `UpdateItem` with `count = count + 1`

**Indexing**:
- Primary key: `pk` (user_id) + `sk` (quota#YYYY-MM)
- No GSI needed (single-user queries only)

**TTL**: Expire old quota records after `window_end + 90 days` (for auditing/analytics).

---

### Quota Service

#### File: `media_summarizer/core/services/quota_service.py`

**Responsibilities**:
1. **Check quota**: Verify if user can submit a new media item
2. **Increment quota**: Atomically increment count after successful ingestion
3. **Get quota status**: Return current usage and limit for user
4. **Reset quota**: (Admin only) Reset quota for a user

**Core Functions**:

```python
async def check_media_quota(user_id: str, tier: str) -> QuotaCheckResult:
    """
    Check if user has quota available for a new media submission.
    
    Returns:
        QuotaCheckResult with allowed (bool), current count, limit, reset time
    
    Raises:
        QuotaExceededError if quota exhausted
    """
    pass

async def increment_media_quota(user_id: str, tier: str) -> None:
    """
    Atomically increment quota count after successful media ingestion.
    Uses DynamoDB UpdateItem with conditional expression.
    """
    pass

async def get_quota_status(user_id: str, tier: str) -> QuotaStatus:
    """
    Get current quota usage for user.
    Returns: current count, limit, window_start, window_end, remaining.
    """
    pass

async def reset_quota(user_id: str, admin_user_id: str) -> None:
    """
    (Admin only) Reset quota count to 0 for current window.
    """
    pass
```

**Error Handling**:
- `QuotaExceededError` (custom exception) → maps to HTTP 429
- Atomic operations to prevent race conditions
- Idempotent: incrementing already-maxed quota is a no-op (returns error)

---

### Quota Constants

#### File: `media_summarizer/core/constants.py`

Add quota tier definitions:

```python
# ---------------------------------------------------------------------------
# Quota limits (media processing)
# ---------------------------------------------------------------------------

# Maximum media items a user can submit per month, by tier.
# Aligned with V1 pricing model (task-65).
QUOTA_LIMITS = {
    "free": 5,
    "standard": 50,
    "pro": 150,
}

# Default tier for new users (before subscription).
DEFAULT_QUOTA_TIER = "free"

# Quota window duration (for monthly quotas).
QUOTA_WINDOW_DURATION_DAYS = 30
```

#### File: `media_summarizer/core/config.py`

Add environment-configurable overrides:

```python
# Quota Configuration
self.QUOTA_FREE_LIMIT = int(os.getenv("QUOTA_FREE_LIMIT", "5"))
self.QUOTA_STANDARD_LIMIT = int(os.getenv("QUOTA_STANDARD_LIMIT", "50"))
self.QUOTA_PRO_LIMIT = int(os.getenv("QUOTA_PRO_LIMIT", "150"))
self.QUOTA_WINDOW_DAYS = int(os.getenv("QUOTA_WINDOW_DAYS", "30"))
```

---

### Enforcement Point

#### File: `media_summarizer/api/endpoints/media.py`

**Endpoint**: `POST /api/media/ingest-url`

**Current Flow** (lines 100-208):
1. Validate URL
2. Get user from DB
3. Create ProcessingJob
4. Allocate minute hold (legacy billing)
5. Send to SQS queue
6. Return 202 Accepted

**New Flow** (with quota enforcement):
1. Validate URL
2. Get user from DB
3. **→ CHECK QUOTA** (new step)
   - Call `quota_service.check_media_quota(user_id, user.tier)`
   - If quota exceeded → raise HTTPException(429, "QUOTA_EXCEEDED")
4. Create ProcessingJob
5. Allocate minute hold (legacy billing, to be deprecated)
6. Send to SQS queue
7. **→ INCREMENT QUOTA** (new step, after successful queue send)
   - Call `quota_service.increment_media_quota(user_id, user.tier)`
8. Return 202 Accepted

**Error Response** (quota exceeded):
```json
{
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "Monthly media processing quota exceeded. You have processed 50/50 media this month. Quota resets on 2026-05-01.",
    "details": {
      "current_count": 50,
      "limit": 50,
      "reset_at": "2026-05-01T00:00:00Z",
      "tier": "standard"
    }
  }
}
```

**HTTP Status**: 429 Too Many Requests

**Headers**:
```
Retry-After: 691200  # Seconds until window reset (8 days)
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1746316800  # Unix timestamp of window_end
```

---

### Artifact Request Path (No Quota)

#### File: `media_summarizer/api/endpoints/artifacts.py`

**Endpoint**: `POST /api/artifacts/media/{media_item_id}/artifacts`

**Current Flow** (lines 64-144):
1. Validate artifact_type
2. Get ProcessingJob for media_item_id
3. Send artifact generation request to SQS
4. Return 202 Accepted

**No Change Required**:
- Artifact requests **do not check quota**
- Artifact generation is idempotent (via `generation_fingerprint` from task-34)
- If artifact exists → return existing S3 key (no cost, no quota)
- If artifact doesn't exist → generate once (cost already paid during media ingestion)

**Rationale**: The quota surface is **media ingestion**, not artifact generation. Once a media item is in the user's documentary base, they can request any artifact type on demand without consuming additional quota.

---

## Implementation Plan

### Phase 1: Core Quota Service (Priority: High)

**Files to Create**:
1. `media_summarizer/core/services/quota_service.py`
2. `media_summarizer/core/exceptions/quota.py` (custom exceptions)
3. `media_summarizer/utils/quota_db.py` (DynamoDB operations)

**Files to Modify**:
1. `media_summarizer/core/constants.py` (add QUOTA_LIMITS)
2. `media_summarizer/core/config.py` (add quota settings)

**DynamoDB Table**:
- Create `user_quotas` table (PK: user_id, SK: quota#YYYY-MM)
- Enable TTL on `ttl` attribute
- On-demand billing (no provisioned capacity)

**Testing**:
- Unit tests: `tests/unit/core/services/test_quota_service.py`
- Integration tests: `tests/integration/test_quota_db.py`

**Estimated Effort**: 2-3 days

---

### Phase 2: Quota Enforcement in Ingestion Endpoint (Priority: High)

**Files to Modify**:
1. `media_summarizer/api/endpoints/media.py`
   - Add quota check before job creation (line ~130)
   - Add quota increment after SQS send (line ~180)
   - Add error handling for QuotaExceededError → HTTP 429

**Error Response Format**:
- Standard error structure with `QUOTA_EXCEEDED` code
- Include current count, limit, reset time in details
- Add `Retry-After` and rate limit headers

**Testing**:
- Unit tests: `tests/unit/api/endpoints/test_media.py` (add quota scenarios)
- E2E tests: `tests/e2e/test_quota_enforcement.py`
  - Submit 5 media (free tier) → 6th should fail with 429
  - Verify error response structure
  - Verify quota counter increments correctly

**Estimated Effort**: 2 days

---

### Phase 3: User Model Integration (Priority: Medium)

**Files to Modify**:
1. `media_summarizer/core/models/user.py`
   - Add `tier: Optional[str]` field (default: "free")
   - Add to serialization methods (`to_dynamodb_item`, `from_dynamodb_item`)

2. `media_summarizer/api/endpoints/users.py`
   - Expose quota status in GET /api/users/me response:
     ```json
     {
       "id": "user-123",
       "email": "user@example.com",
       "tier": "standard",
       "quota": {
         "limit": 50,
         "used": 23,
         "remaining": 27,
         "reset_at": "2026-05-01T00:00:00Z"
       }
     }
     ```

**Migration**:
- Backfill existing users with `tier = "free"` (or "standard" if they have a subscription)
- No schema migration needed (optional field)

**Testing**:
- Unit tests: `tests/unit/core/models/test_user.py`
- Integration tests: verify quota status in user endpoint

**Estimated Effort**: 1-2 days

---

### Phase 4: Admin Endpoints (Priority: Low)

**Files to Create**:
1. `media_summarizer/api/endpoints/admin.py` (if not exists)
   - `POST /api/admin/users/{user_id}/quota/reset` (reset quota to 0)
   - `GET /api/admin/users/{user_id}/quota` (view quota across all windows)
   - `PATCH /api/admin/users/{user_id}/tier` (change user tier)

**Authorization**:
- Require `admin` role in JWT claims
- Add admin role to `AuthUser` model

**Testing**:
- Unit tests: verify admin-only access
- E2E tests: reset quota, change tier, verify effects

**Estimated Effort**: 1-2 days

---

### Phase 5: Monitoring & Observability (Priority: Medium)

**Metrics to Track** (CloudWatch or similar):
1. `quota.check.count` (tagged by tier, result: allowed/denied)
2. `quota.exceeded.count` (tagged by tier)
3. `quota.increment.count` (tagged by tier)
4. `quota.reset.count` (admin resets)

**Logs to Emit**:
- `quota.check.allowed` (INFO)
- `quota.check.denied` (WARNING, include user_id, tier, current count)
- `quota.increment.succeeded` (INFO)
- `quota.increment.failed` (ERROR, include error details)

**Dashboard**:
- Quota usage by tier (time series)
- Quota exceeded events (count, by tier)
- Top users by quota consumption

**Alerts**:
- High quota exceeded rate (>10% of requests) → investigate abuse or tier mismatch
- Quota service errors (DynamoDB failures) → investigate infra issues

**Estimated Effort**: 1 day

---

### Phase 6: Documentation (Priority: High)

**Documents to Create/Update**:
1. `docs/api/quota-system.md` (quota model, enforcement, error handling)
2. `docs/api/error-codes.md` (add `QUOTA_EXCEEDED` error)
3. `docs/architecture/quota-architecture.md` (system design, DynamoDB schema)
4. API reference (OpenAPI spec) for quota-related endpoints

**User-Facing Docs**:
- Quota limits by tier (Free: 5, Standard: 50, Pro: 150)
- How to check quota status (GET /api/users/me)
- What happens when quota is exceeded (429 error, retry after window reset)
- How quota resets (monthly, on subscription renewal date)

**Estimated Effort**: 1 day

---

## Testing Strategy

### Unit Tests

**Coverage Targets**:
- `quota_service.py`: 100% (core business logic)
- `quota_db.py`: 100% (DynamoDB operations)
- `media.py` (quota enforcement): 90%+

**Key Scenarios**:
1. Check quota: allowed (count < limit)
2. Check quota: denied (count >= limit)
3. Increment quota: success (atomic increment)
4. Increment quota: race condition (concurrent increments)
5. Get quota status: return correct values
6. Reset quota: admin only, resets to 0

---

### Integration Tests

**Test Cases**:
1. **Quota enforcement end-to-end**:
   - Create user with "free" tier (limit: 5)
   - Submit 5 media → all succeed (200)
   - Submit 6th media → fails with 429
   - Verify error response structure

2. **Quota reset (monthly)**:
   - Submit 5 media (free tier, limit exhausted)
   - Wait for window reset (or mock time)
   - Submit new media → succeeds (new window)

3. **Tier upgrade**:
   - User starts with "free" (5/month)
   - Exhausts quota (5/5)
   - Upgrade to "standard" (50/month)
   - Submit new media → succeeds (new limit applies)

4. **Artifact requests (no quota check)**:
   - Exhaust media quota (50/50)
   - Request artifact → succeeds (no quota check)
   - Verify artifact is returned (or queued)

---

### E2E Tests

**Test Cases**:
1. **Quota lifecycle**:
   - Register new user (free tier)
   - Submit media until quota exhausted
   - Verify 429 error
   - Wait for window reset
   - Verify quota resets to 0

2. **Multi-user isolation**:
   - Create 2 users (same tier)
   - User A exhausts quota
   - User B can still submit media

3. **Performance under load**:
   - Simulate 100 concurrent requests from same user
   - Verify only 50 succeed (quota limit)
   - Verify atomic increments (no race conditions)

---

## Monitoring & Observability

### Key Metrics

| Metric | Type | Tags | Alert Threshold |
|--------|------|------|-----------------|
| `quota.check.count` | Counter | tier, result (allowed/denied) | N/A |
| `quota.exceeded.rate` | Gauge | tier | >10% of requests |
| `quota.increment.count` | Counter | tier | N/A |
| `quota.db.latency` | Histogram | operation (check/increment/get) | p99 >500ms |
| `quota.db.errors` | Counter | error_type | >1% error rate |

### Logs

**Log Levels**:
- INFO: Quota checks (allowed), increments (success)
- WARNING: Quota exceeded (include user_id, tier, count, limit)
- ERROR: Quota service failures (DynamoDB errors, race conditions)

**Structured Logging** (JSON):
```json
{
  "event": "quota.check.denied",
  "level": "WARNING",
  "user_id": "user-123",
  "tier": "standard",
  "current_count": 50,
  "limit": 50,
  "reset_at": "2026-05-01T00:00:00Z",
  "error_code": "QUOTA_EXCEEDED"
}
```

### Dashboard

**Panels**:
1. **Quota Usage by Tier** (time series)
   - Free: X/5 media/month
   - Standard: Y/50 media/month
   - Pro: Z/150 media/month

2. **Quota Exceeded Events** (count, by tier)
   - Track users hitting limits
   - Identify need for tier upgrades

3. **Quota Service Health**
   - DynamoDB latency (p50, p99)
   - Error rate
   - Throughput (checks/sec, increments/sec)

4. **Top Users by Quota Consumption**
   - Identify power users
   - Detect abuse patterns

### Alerts

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High quota exceeded rate | >10% of requests denied | Medium | Investigate tier mismatch or user behavior |
| Quota service errors | >1% DynamoDB errors | High | Check DynamoDB health, scaling |
| Quota service latency | p99 >500ms | Medium | Investigate DynamoDB performance |
| Suspicious quota usage | Single user >80% of tier limit in first week | Low | Review for abuse |

---

## Migration Strategy

### Existing Users

**Current State**:
- Users have `minute_buckets` (legacy billing)
- No tier field in user table
- No quota enforcement

**Migration Steps**:
1. **Backfill user tiers**:
   - Query `subscriptions` table
   - If user has active subscription → `tier = subscription.tier` (S/M/L)
   - Else → `tier = "free"`
   - Update `users` table with tier field

2. **Map legacy tiers to V1 tiers**:
   - S (Small) → "free" (5 media/month)
   - M (Medium) → "standard" (50 media/month)
   - L (Large) → "pro" (150 media/month)

3. **Initialize quota counters**:
   - For each user, create `user_quotas` record for current month
   - Set `count = 0` (fresh start)
   - Set `limit` based on tier

4. **Deprecate minute-based billing**:
   - Keep `minute_pool.py` for existing subscriptions (grace period)
   - New users use quota-based system
   - Phase out minute billing over 3-6 months

**Estimated Effort**: 2 days (scripting + validation)

---

## Open Questions & Decisions

### 1. Quota Window Reset Behavior

**Question**: Should quota reset on calendar month (1st of month) or subscription renewal date?

**Options**:
- **Calendar month** (1st of month): Simpler, predictable for users
- **Subscription renewal date**: More aligned with billing cycle

**Recommendation**: **Calendar month** for MVP (simpler), migrate to renewal date in Phase 2 (post-MVP).

---

### 2. Quota Exhaustion Behavior

**Question**: What happens when a user exhausts quota mid-month?

**Options**:
- **Hard block**: No new media until reset (current design)
- **Overage allowance**: Allow X extra media with warning (+ charge overage fee)
- **Upgrade prompt**: Suggest tier upgrade in error response

**Recommendation**: **Hard block + upgrade prompt** in error response. Add overage allowance in Phase 2 (requires billing integration).

---

### 3. Artifact Request Quotas

**Question**: Should artifact requests have separate rate limits (e.g., 100 requests/hour)?

**Options**:
- **No rate limits**: Trust idempotence (existing S3 artifacts are cheap to serve)
- **Soft rate limits**: Log excessive requests, no hard block
- **Hard rate limits**: 429 after X requests/hour (protect against abuse)

**Recommendation**: **No rate limits** for MVP (artifacts are idempotent and cheap). Add soft rate limits in Phase 2 if abuse detected.

---

### 4. Admin Quota Overrides

**Question**: Should admins be able to grant temporary quota boosts (e.g., +10 media for user feedback)?

**Options**:
- **Yes**: Add `quota_override` field to user table (one-time boost)
- **No**: Use tier upgrades only

**Recommendation**: **Yes**, add `quota_override` (simple int field, added to limit). Useful for customer support, promotions, user feedback incentives.

---

### 5. Free Tier Launch Strategy

**Question**: Should Free tier (5 media/month) launch with MVP or Phase 2?

**Options**:
- **MVP**: Launch Free tier immediately (acquisition-focused)
- **Phase 2**: Launch Standard only (9€/month) with trial, add Free later

**Recommendation** (from task-65): **Phase 2**. Launch Standard (9€) with 1-month trial (20 media limit). Add Free tier post-launch to enable viral acquisition once paid user base is established.

---

## Appendix A: DynamoDB Schema

### Table: `user_quotas`

**Partition Key**: `pk` (String) = user_id  
**Sort Key**: `sk` (String) = "quota#YYYY-MM"  
**Billing Mode**: On-Demand (auto-scaling)  
**TTL Attribute**: `ttl` (Number, Unix timestamp)

**Attributes**:
```json
{
  "pk": "user-abc123",
  "sk": "quota#2026-04",
  "tier": "standard",
  "limit": 50,
  "count": 23,
  "window_start": "2026-04-01T00:00:00Z",
  "window_end": "2026-05-01T00:00:00Z",
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-22T14:30:00Z",
  "ttl": 1748736000
}
```

**Access Patterns**:
- **GetItem**: `pk = user_id, sk = "quota#2026-04"` → O(1)
- **UpdateItem**: Atomic increment `count = count + 1` with condition `count < limit`
- **Query**: `pk = user_id, sk begins_with "quota#"` → Get all quota windows for user

**Capacity Planning**:
- Items per user: ~12/year (one per month, TTL after 90 days)
- Item size: ~300 bytes
- For 10,000 users: ~120,000 items × 300B = 36 MB storage
- Read capacity: ~10-20 RCU (1 read per media ingestion)
- Write capacity: ~10-20 WCU (1 write per media ingestion)
- Cost (on-demand): ~$0.01/month for 10K users (negligible)

---

## Appendix B: Error Codes

### QUOTA_EXCEEDED

**HTTP Status**: 429 Too Many Requests

**Code**: `QUOTA_EXCEEDED`

**Message**: "Monthly media processing quota exceeded. You have processed {count}/{limit} media this month. Quota resets on {reset_at}."

**Details**:
```json
{
  "current_count": 50,
  "limit": 50,
  "remaining": 0,
  "reset_at": "2026-05-01T00:00:00Z",
  "tier": "standard",
  "upgrade_url": "/api/billing/upgrade"
}
```

**Headers**:
- `Retry-After`: Seconds until quota resets (e.g., 691200 = 8 days)
- `X-RateLimit-Limit`: Quota limit for current tier
- `X-RateLimit-Remaining`: Remaining quota (0 when exceeded)
- `X-RateLimit-Reset`: Unix timestamp of quota reset

**User-Facing Message**:
> "You've reached your monthly limit of 50 media items. Your quota will reset on May 1st. Upgrade to Pro for 150 media/month."

---

## Appendix C: API Examples

### Check Quota Status

**Request**:
```http
GET /api/users/me
Authorization: Bearer {jwt_token}
```

**Response** (200 OK):
```json
{
  "id": "user-abc123",
  "email": "user@example.com",
  "tier": "standard",
  "quota": {
    "limit": 50,
    "used": 23,
    "remaining": 27,
    "reset_at": "2026-05-01T00:00:00Z",
    "window_start": "2026-04-01T00:00:00Z"
  }
}
```

---

### Ingest Media (Quota OK)

**Request**:
```http
POST /api/media/ingest-url
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response** (202 Accepted):
```json
{
  "media_item_id": "job-xyz789",
  "status": "pending",
  "source_platform": "youtube"
}
```

**Headers**:
```
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 26
X-RateLimit-Reset: 1746316800
```

---

### Ingest Media (Quota Exceeded)

**Request**: Same as above

**Response** (429 Too Many Requests):
```json
{
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "Monthly media processing quota exceeded. You have processed 50/50 media this month. Quota resets on 2026-05-01.",
    "details": {
      "current_count": 50,
      "limit": 50,
      "remaining": 0,
      "reset_at": "2026-05-01T00:00:00Z",
      "tier": "standard",
      "upgrade_url": "/api/billing/upgrade"
    }
  }
}
```

**Headers**:
```
Retry-After: 691200
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1746316800
```

---

## Sources

1. **Task-65 Pricing Research**: `docs/research/task-65-benchmark-pricing-v1.md`
2. **Anthropic Rate Limits**: https://platform.claude.com/docs/en/api/rate-limits
3. **Stripe Usage-Based Billing**: https://docs.stripe.com/billing/subscriptions/usage-based
4. **Kong Rate Limiting Algorithms**: https://konghq.com/blog/engineering/how-to-design-a-scalable-rate-limiting-algorithm
5. **Figma Rate Limiting**: https://www.figma.com/blog/an-alternative-approach-to-rate-limiting/
6. **Existing Codebase**:
   - `media_summarizer/api/endpoints/media.py` (ingestion endpoint)
   - `media_summarizer/core/services/minute_pool.py` (legacy billing)
   - `media_summarizer/core/models/billing.py` (minute-based models)
   - `media_summarizer/core/config.py` (configuration)

---

## Next Steps

1. **Review & Approval**: Share this document with stakeholders for feedback
2. **Implementation**: Follow Phase 1-6 plan above
3. **Testing**: Execute unit, integration, E2E tests
4. **Documentation**: Create user-facing docs + API reference
5. **Deployment**: Roll out quota system to production (behind feature flag)
6. **Monitoring**: Set up dashboard + alerts
7. **Iteration**: Collect feedback, tune limits, add features (overage, etc.)

---

**Document Generated By**: Agent de recherche backlog media-summarizer  
**Date**: 2026-04-22  
**Research Duration**: ~3 hours (web research + codebase analysis + document creation)

Decision validated by owner : no decision fixed for now. Decision about this topic will be taken when everything else will be implemented.
