---
id: task-267
title: >-
  Surface the stored title on the media detail screen instead of deriving it
  from the URL
status: To Do
assignee: []
created_date: '2026-08-14 02:09'
updated_date: '2026-08-17 15:28'
labels:
  - mobile
  - api
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A podcast whose title is correct in the Inbox ("LE MEILLEUR DE BOUVARD - La blague…") shows as **"2mnZkgwaHARGf0uAXGdACm"** on its detail screen — the Spotify episode id. The title is not wrong here: it never reaches the screen at all.

## Root cause

Two surfaces read two different contracts:

- **Inbox** consumes `GET /api/media` → `MediaSearchItem` / `MediaListItem`, which **has** a `title` field ([mobile/src/types/media.ts:185](mobile/src/types/media.ts#L185)). Correct title.
- **Detail screen** consumes `GET /api/media/{id}/status` → `MediaItemContract`, which **has no title field at all** ([media_summarizer/api/models/media_contracts.py:179-192](media_summarizer/api/models/media_contracts.py#L179-L192), mirrored at [mobile/src/types/media.ts:134-147](mobile/src/types/media.ts#L134-L147)). So the screen invents one from the URL at [mobile/app/media/[id].tsx:623-628](mobile/app/media/%5Bid%5D.tsx#L623-L628): last path segment of `original_url`, falling back to the whole URL. For `open.spotify.com/episode/2mnZkgwa…` that segment is the episode id.

The fix is cheap because the data is already in hand: `_build_media_item_contract` ([media_summarizer/api/endpoints/media.py:563-587](media_summarizer/api/endpoints/media.py#L563-L587)) is passed the `UserMediaRecord` — the very durable row the Inbox reads its title from — and simply does not project the field.

## Scope

1. Add `title` to `MediaItemContract` (backend) and to its mobile mirror.
2. Project `record.title` in `_build_media_item_contract`.
3. Render it as the hero title on the detail screen, and **delete** the URL-derived `displayTitle` block. Nothing is deployed and there are no users (`AGENTS.md` § "Nothing is deployed yet"): the URL-parsing fallback is not kept as a safety net. If the stored title is absent, use the same fallback the rest of the app uses for a missing title rather than reintroducing URL parsing.

Out of scope: **what** the stored title contains. That is task-265 / task-266 — this task only makes the detail screen show whatever the library row holds. The two are independent and can land in either order.

## Owner note (not an acceptance criterion)

Visual check after the deploy to `-dev`: open a podcast from the Inbox and confirm the detail header matches the Inbox vignette.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 MediaItemContract carries a title field on the backend and in the mobile type mirror, populated from the durable UserMediaRecord in _build_media_item_contract
- [x] #2 The media detail screen renders the title coming from the contract, and the URL-derived displayTitle block in mobile/app/media/[id].tsx is deleted — a grep for the URL-parsing fallback returns nothing
- [x] #3 The screen degrades to the app's existing missing-title fallback when the contract carries no title, without reintroducing URL parsing
- [x] #4 ruff and mypy are clean on the backend, tsc --noEmit and eslint are clean on the mobile app
- [x] #5 A direct read of a podcast row in the -dev user_media DynamoDB table (AWS CLI) shows the non-empty title attribute the new projection reads, and the field name used in _build_media_item_contract matches that attribute
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**Backend.** `MediaItemContract` (`media_summarizer/api/models/media_contracts.py`) gains `title: Optional[str] = None`, placed with the identity/URL block, and `_build_media_item_contract` (`media_summarizer/api/endpoints/media.py`) now projects `title=record.title` from the durable `UserMediaRecord` it was already handed. No normalization on the way out: the row never stores an empty string (`UserMediaRecord.to_dynamodb_item` drops falsy optionals), and the client trims anyway. The docstring records that this is the same field the list endpoint projects, so the two surfaces cannot disagree.

**Mobile.** `MediaItemContract` in `mobile/src/types/media.ts` mirrors it as `title?: string | null`. The detail screen's URL-derived title is gone — the `new URL(original_url).pathname.split("/").pop()` block is deleted, replaced by `media_item.title?.trim() || media_item.original_url.trim() || "Untitled"`. The chain reuses fallbacks that already exist in the app: the source URL is what the inbox vignette and `MediaListCard` show for a titleless row, and `"Untitled"` is the search screen's fallback, needed here because shared text and uploads have no URL either (their contract carries `original_url: ""`). `grep -rn "pathname.split" mobile/` now returns nothing; the only remaining `new URL(...)` on the screen builds the *domain* chip, which is a legitimate use. The hero keeps its existing `heroTitle` style (display preset, uncapped line count, matching `mobile-design-mockups/media_detail_ai_artifacts_dropdown/code.html`) — no new tokens, no visual change other than the value.

**Field name confirmed on real infrastructure (AC#5).** `aws dynamodb scan --table-name user_media-dev --filter-expression "media_type = :t"` with `:t = podcast_episode`, region `eu-west-3`, projecting `media_item_id, title, media_type, source_platform`: the Spotify podcast row comes back with a **non-empty `title` String** ("LE MEILLEUR DE BOUVARD - La blague de Carlos") and `source_platform = spotify`. The DynamoDB attribute is literally `title`, which is the `UserMediaRecord.title` field the new projection reads (`from_dynamodb_item` passes it through untouched). So the very row that rendered as `2mnZkgwaHARGf0uAXGdACm` already held the right string.

**Checks.** `ruff check` and `mypy` clean on both touched Python files. `npm run typecheck` (tsc --noEmit) clean. `npm run lint` reports 0 errors; the 10 remaining warnings are pre-existing and untouched by this diff (including the one in `[id].tsx:949`, an unused destructured prop unrelated to the title).

**Not verified here (out of the worktree's reach).** The owner's visual check — open a podcast from the Inbox on `-dev` and confirm the detail header matches the vignette — needs the merged code deployed, which happens on push to `main`. It stays an owner note, as the task states.

Docs: `docs/CANONICAL_MEDIA_API_CONTRACT.md` §2 example now carries `title`, with a note that it is the `user_media` row's attribute, nullable, and that clients degrade to the source URL rather than to a URL path segment.
<!-- SECTION:NOTES:END -->
