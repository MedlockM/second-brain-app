# Media Key Migration Notes

This document describes the canonical runtime identity model for ingestion and
completion: URL-derived `media_key`.

## Canonical Tables

- `media_idempotence` (PK: `media_key`)
- `media_watchers` (PK: `media_key`, SK: `user_id`)
- `user_media` (PK: `user_id`, SK: `media_item_id`) — durable per-user library row,
  the source of truth for ownership since task-220. Replaces the removed
  `user_media_submissions` pointer table.

## Runtime Behavior

- New submissions compute `media_key` from canonicalized URL and write to
  `media_idempotence` / `media_watchers`.
- Queue and event payloads carry `media_key` as identity.
- Success finalization is driven by processing events (`episode_completion_status`)
  and updates watcher jobs directly to terminal states; it is no longer coupled
  to completion-content emails.
- Email worker has been removed. Completion is fully decoupled from notifications.

## Environment Variables

- `MEDIA_IDEMPOTENCE_TABLE`
- `MEDIA_WATCHERS_TABLE`
- `USER_MEDIA_TABLE`

No default is provided for any of them: since task-237 the runtime fails fast
when a table name is missing from the environment.

## Deployment Sequence

1. Apply Terraform to create canonical `media_*` tables.
2. Deploy application version that reads/writes only canonical media-key tables.
3. Remove legacy episode-guid table references from runtime configuration.
