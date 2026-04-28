---
id: task-47
title: >-
  Implement URL safety hardening (strict validation and malicious-domain
  blocking)
status: Done
assignee: []
created_date: '2026-02-24 11:04'
updated_date: '2026-02-24 21:00'
labels: []
dependencies:
  - task-21
  - task-10
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Harden URL intake with strict validation and malicious-domain blocking policies to reduce ingestion risk.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 URL validation rejects malformed and unsafe URL patterns consistently.
- [x] #2 Malicious or blocked domains are denied with stable user-safe errors.
- [x] #3 Safety decisions are logged for audit and operations visibility.
- [x] #4 Safety policy and allow/deny governance are documented.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Harden URL validation in the ingestion classifier to reject malformed and unsafe URL patterns deterministically.
2. Add malicious/blocked domain policy (denylist with explicit allow overrides) and return stable user-safe errors.
3. Add structured safety-decision logging for allow/deny outcomes to support audit and operations visibility.
4. Document URL safety policy and allow/deny governance in ingestion architecture docs.
5. Run targeted validation (compile) and update task notes + acceptance criteria.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented URL safety hardening in `RuleBasedUrlClassifier` with deterministic pre-routing safety gates:
- strict URL shape checks (empty, max length, invalid parsed port)
- host hardening (`..`, invalid label pattern, invalid host shape)
- explicit denial for URL user-info credentials (`user:pass@host`)
- existing forbidden host/IP checks retained for localhost/private/link-local/etc.

Added malicious-domain policy with governance knobs:
- built-in blocked suffix defaults
- env-driven denylist via `INGEST_URL_BLOCKED_DOMAINS`
- env-driven allow override via `INGEST_URL_ALLOWED_DOMAINS`
- suffix matching supports exact domain + subdomains

Added structured safety decision logging for audit/ops visibility:
- event message: `ingestion_url_safety_decision`
- fields: `decision`, `reason`, `scheme`, `host`
- deny reasons include `unsupported_scheme`, `missing_host`, `user_info_not_allowed`, `invalid_host_pattern`, `forbidden_host_or_ip`, `blocked_domain_policy`.

Documented safety policy and governance:
- updated `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` with task-47 section
- added `docs/URL_SAFETY_POLICY.md` for policy, governance, and audit logging runbook.

Validation:
- `python3 -m compileall media_summarizer/core/media_ingestion/adapters/classifiers.py media_summarizer/core/media_ingestion` passed.
<!-- SECTION:NOTES:END -->
