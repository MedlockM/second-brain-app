# ADR: Algolia Multi-Tenant Model -- Single Shared Index with Secured API Keys

**Status**: Accepted (task-215, 2026-06-16)

## Context

Task-205 introduced per-user Algolia indices (`{prefix}_user_{id}`). This hits the 50-index limit on Grow plans at 51 users and fragments analytics/ranking tuning.

## Decision

Single shared index per environment (`media_items_{env}`) with `user_id` attribute on every record. Tenant isolation via Algolia secured API keys.

## Key elements

1. **Index**: one per environment; every record carries `user_id`
2. **Settings**: `attributesForFaceting: ["filterOnly(user_id)"]`, `unretrievableAttributes: ["user_id"]`
3. **Client search**: backend generates a secured API key (derived from parent search-only key) with `filters: "user_id:<id>"` and short TTL (1h)
4. **Backend search**: explicit `user_id` filter in query params (for proxied `/api/search/transcripts`)
5. **Deletion**: `deleteBy(filters: "user_id:<id>")` for account removal

## Security

- Admin/write key: backend-only (indexing)
- Search-only parent key: backend-only (secured key derivation)
- Secured key: client-side, tamper-proof, short-lived, user-scoped

## References

- https://www.algolia.com/doc/guides/security/api-keys/how-to/user-restricted-access-to-data/
- https://www.algolia.com/doc/guides/security/api-keys/how-to/generating-api-keys/
- https://www.algolia.com/doc/guides/security/api-keys/in-depth/api-key-restrictions/
