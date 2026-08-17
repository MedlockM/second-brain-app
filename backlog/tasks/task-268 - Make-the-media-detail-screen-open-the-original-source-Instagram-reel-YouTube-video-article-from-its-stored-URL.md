---
id: task-268
title: >-
  Make the media detail screen open the original source (Instagram reel, YouTube
  video, article) from its stored URL
status: To Do
assignee: []
created_date: '2026-08-17 18:55'
labels:
  - mobile
  - ux
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The user shares a media item into the app, reads its transcript and artifacts, and then has no way back to the thing itself. If the saved item is an Instagram reel, there is currently no affordance on `mobile/app/media/[id].tsx` to reopen that reel — not in the Instagram app, not even in a browser. The link is a dead end once ingested.

## Storing the link is already done — do not rebuild it

Verified on 2026-08-17 before writing this task. Nothing needs to be added to the model, the table or the contract:

- `media_summarizer/core/models/user_media.py:111` persists `source_url` on the durable library row, and `to_item()` writes it to DynamoDB (`user_media.py:177`).
- `media_summarizer/api/models/media_contracts.py` exposes it on `MediaItemContract` as `original_url` (and `normalized_url`), populated from `record.source_url` in `media_summarizer/api/endpoints/media.py:582`.
- `mobile/src/types/media.ts` already types `original_url: string` on `MediaItemContract`, and `source_url` on `MediaListItem` for the list rows.
- The detail screen already *reads* `original_url` — but only to derive a fallback title and the domain chip (`mobile/app/media/[id].tsx:625-634`).

So this task is **purely the mobile affordance**. If the implementer finds a source whose `source_url` is genuinely never persisted, that is a finding to report in the task notes, not a schema change to smuggle in.

## Scope: the affordance and its placement

The hero section already renders a `metaChip` showing the media-type icon plus the uppercased domain (`INSTAGRAM.COM`, `YOUTUBE.COM`) at `mobile/app/media/[id].tsx:811-822`. **The strongly preferred design is to make that existing chip the tap target** rather than adding a separate button: it already names the source, it already sits directly under the title, and turning it into a `Pressable` with a small trailing `open-outline` icon costs one element instead of introducing a new one. That keeps the screen minimal while making the affordance visible — a chip that names the platform and carries an external-link glyph reads as openable.

The implementer may deviate if the pressable chip proves wrong in practice (too small a target, unclear affordance), but the alternative must stay minimal — a discreet icon-only button in the hero, not a full-width primary CTA competing with the artifacts section.

Requirements regardless of placement:

- Opens `media_item.original_url` via `expo-linking` (`import * as Linking from "expo-linking"`, the pattern already used in `mobile/app/settings/delete-account.tsx:14`).
- Rely on the **https universal link**, not a custom scheme. On iOS and Android an `instagram.com` / `youtube.com` https URL is claimed by the installed app and opens it natively; falling back to `instagram://` would require declaring `LSApplicationQueriesSchemes` per platform in `mobile/app.config.ts` for every source we support, for no gain.
- **No affordance at all when there is no source to open.** Uploads and shared text carry `source_url=""` (see `media_summarizer/core/services/media_submission.py:92` and `media_summarizer/api/endpoints/media.py:1004`), which reaches the client as an empty `original_url`. An empty or unopenable URL must render no chip press behaviour and no icon — not a disabled button, and never a tap that silently does nothing.
- Handle the open failing (`Linking.openURL` rejects) without crashing the screen. The screen already has a toast mechanism (`toastMessage`); reuse it rather than inventing a new error surface.
- Accessible: `accessibilityRole="link"` (or `"button"`) and a label naming the destination, e.g. `Open on instagram.com`.

## Out of scope

- **The title.** Do not touch `displayTitle` or its fallback chain — title derivation is owned by task-265/task-266. This task only adds the link affordance.
- The inbox list rows and the search results. One surface only: the media detail screen.

## Note to the owner (not an acceptance criterion)

After this merges and `main` deploys to `-dev`: open a saved Instagram reel from the Inbox, tap the source chip, and confirm the Instagram app opens on that reel rather than a browser tab or the Instagram home feed. Then do the same on an uploaded document and confirm the chip shows no link affordance at all.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The media detail screen (mobile/app/media/[id].tsx) exposes a tap affordance in the hero section that calls Linking.openURL on media_item.original_url, wired and reachable in the rendered tree
- [ ] #2 The affordance carries a visible external-link indication (icon) and an accessibility label naming the destination, and is placed either on the existing domain metaChip or as a minimal hero icon button
- [ ] #3 When original_url is empty or not openable, no press behaviour and no link icon are rendered — no disabled control and no no-op tap
- [ ] #4 A rejected Linking.openURL is caught and surfaced through the screen's existing toast mechanism instead of throwing
- [ ] #5 displayTitle and its fallback chain are unchanged (verified by diff), and no change is made to the inbox or search surfaces
- [ ] #6 No backend, contract or model change: media_summarizer/ and mobile/src/types/media.ts are untouched by the diff, since source_url is already persisted and exposed as original_url
- [ ] #7 The task notes record a check against the real user_media-dev table showing that a row for an Instagram-sourced item holds a non-empty source_url, so the affordance has something to open
- [ ] #8 npx tsc --noEmit and the project's lint command pass in mobile/
<!-- AC:END -->
