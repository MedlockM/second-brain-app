---
id: task-267
title: >-
  Surface the stored title on the media detail screen instead of deriving it
  from the URL
status: To Do
assignee: []
created_date: '2026-08-14 02:09'
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
- [ ] #1 MediaItemContract carries a title field on the backend and in the mobile type mirror, populated from the durable UserMediaRecord in _build_media_item_contract
- [ ] #2 The media detail screen renders the title coming from the contract, and the URL-derived displayTitle block in mobile/app/media/[id].tsx is deleted — a grep for the URL-parsing fallback returns nothing
- [ ] #3 The screen degrades to the app's existing missing-title fallback when the contract carries no title, without reintroducing URL parsing
- [ ] #4 ruff and mypy are clean on the backend, tsc --noEmit and eslint are clean on the mobile app
- [ ] #5 A direct read of a podcast row in the -dev user_media DynamoDB table (AWS CLI) shows the non-empty title attribute the new projection reads, and the field name used in _build_media_item_contract matches that attribute
<!-- AC:END -->
