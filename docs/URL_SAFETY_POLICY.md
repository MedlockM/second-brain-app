# URL Safety Policy

This policy defines how shared URLs are accepted or rejected by the canonical ingestion flow.

## Scope

Applies to:
- `POST /api/media/ingest-url`
- core classifier `RuleBasedUrlClassifier`

## Decision model

Safety decisions are evaluated before resolver routing:
1. Validate URL shape and protocol constraints.
2. Validate host safety constraints.
3. Apply domain allow/deny policy.
4. If accepted, continue with media-family routing.

User-facing errors remain stable:
- malformed URL -> `InvalidUrlError` (`INVALID_URL`)
- unsafe/blocked URL -> `UnsupportedUrlError` (`UNSUPPORTED_URL`)

## Validation constraints

Rejected patterns include:
- empty URLs
- malformed URLs (parse/host validation failures)
- unsupported schemes (anything outside `http` / `https`)
- URLs containing credentials (`user:password@host`)
- local/private/loopback/link-local/reserved/multicast hosts

## Domain governance

Environment variables:
- `INGEST_URL_BLOCKED_DOMAINS`: comma-separated blocked domain suffixes
- `INGEST_URL_ALLOWED_DOMAINS`: comma-separated allowlist suffixes

Suffix matching rules:
- exact domain and subdomains match (e.g. `bad.tld` blocks `bad.tld` and `a.bad.tld`)
- allowlist overrides denylist when both match

Operational governance:
1. Add newly identified malicious domains to `INGEST_URL_BLOCKED_DOMAINS`.
2. Use `INGEST_URL_ALLOWED_DOMAINS` only as a temporary override with explicit incident note.
3. Review overrides regularly and remove stale allow entries.

## Audit logging

Every safety decision emits a structured log event:
- message: `ingestion_url_safety_decision`
- fields: `decision`, `reason`, `scheme`, `host`

This log is the operational source for:
- blocked-domain incident analysis
- false-positive allowlist tuning
- ingestion safety trend monitoring
