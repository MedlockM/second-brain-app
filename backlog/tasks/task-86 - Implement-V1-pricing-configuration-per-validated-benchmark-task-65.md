---
id: task-86
title: Implement V1 pricing configuration per validated benchmark (task-65)
status: Done
assignee: []
created_date: '2026-04-28 16:05'
updated_date: '2026-05-13 16:46'
labels:
  - pricing
  - v1
  - implementation
dependencies:
  - task-65
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apply the V1 pricing decisions validated in task-65 to the codebase and configuration. Read the owner's Decision from `docs/research/task-65-pricing-v1-benchmark/README.md` (Owner Validation section) before planning the implementation.

Scope typically covers: tier definitions, price/quota constants, provider selection flags, and any prompt or worker config changes that embody the validated pricing decisions.

**IMPORTANT — Configuration must be fully dynamic (no redeploy):**
All pricing-related values must be stored in a **DynamoDB configuration table** (e.g. `pricing_config`) so the owner can modify them at runtime without code changes or redeployment. The backend reads this table at startup and caches values in memory with a short TTL (e.g. 5 minutes). An admin endpoint allows updating values live.

This includes but is not limited to:
- Tier prices (monthly subscription amount per tier)
- Audio minute limits per tier
- Hard caps (daily/monthly media limits, cost ceilings)
- Rate limiting thresholds (per-user, per-tier)
- Free trial duration and quotas
- Any other numerical or boolean value that shapes the pricing/quota behavior

The mobile app fetches pricing/tier info from a backend endpoint (`GET /api/pricing`) at launch — never hardcodes prices client-side.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tier definitions and price/quota constants match the decisions validated in docs/research/task-65-pricing-v1-benchmark/README.md
- [ ] #2 ALL pricing/quota values stored in a DynamoDB config table — no hardcoded constants in application code
- [ ] #3 Backend reads config from DynamoDB with in-memory cache (TTL ~5 min) — changes take effect without redeploy

- [ ] #4 Admin endpoint (protected) allows owner to update any pricing parameter at runtime
- [ ] #5 Mobile app fetches pricing from backend endpoint (GET /api/pricing) — never hardcodes prices

- [ ] #6 Any downstream worker/provider/prompt configuration implied by the pricing decisions is updated accordingly
<!-- AC:END -->
