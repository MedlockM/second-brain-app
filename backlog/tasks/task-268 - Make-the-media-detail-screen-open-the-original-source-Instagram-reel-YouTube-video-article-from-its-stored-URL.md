---
id: task-268
title: >-
  Make the media detail screen open the original source (Instagram reel, YouTube
  video, article) from its stored URL
status: Done
assignee: []
created_date: '2026-08-17 18:55'
updated_date: '2026-08-17 19:10'
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
- [x] #1 The media detail screen (mobile/app/media/[id].tsx) exposes a tap affordance in the hero section that calls Linking.openURL on media_item.original_url, wired and reachable in the rendered tree
- [x] #2 The affordance carries a visible external-link indication (icon) and an accessibility label naming the destination, and is placed either on the existing domain metaChip or as a minimal hero icon button
- [x] #3 When original_url is empty or not openable, no press behaviour and no link icon are rendered — no disabled control and no no-op tap
- [x] #4 A rejected Linking.openURL is caught and surfaced through the screen's existing toast mechanism instead of throwing
- [x] #5 displayTitle and its fallback chain are unchanged (verified by diff), and no change is made to the inbox or search surfaces
- [x] #6 No backend, contract or model change: media_summarizer/ and mobile/src/types/media.ts are untouched by the diff, since source_url is already persisted and exposed as original_url
- [x] #7 The task notes record a check against the real user_media-dev table showing that a row for an Instagram-sourced item holds a non-empty source_url, so the affordance has something to open
- [x] #8 npx tsc --noEmit and the project's lint command pass in mobile/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The whole change lives in `mobile/app/media/[id].tsx`. No backend, no contract, no
`mobile/src/types/media.ts` — `source_url` was already persisted and already exposed
as `original_url`, exactly as the description stated (AC #6).

### The chip is the tap target

The preferred design held up: the hero `metaChip` became a `SourceChip`
sub-component. With an openable link it renders as a `Pressable` carrying the
media-type glyph, the uppercased domain, and a trailing `open-outline` glyph, with
`accessibilityRole="link"` and `accessibilityLabel={`Open on ${host}`}`. With
nothing to open it renders as a plain `View` with no glyph and no press handler —
not a disabled control (AC #1, #2, #3).

Touch target: the pill is ~25px tall by design (13px label + `paddingVertical: 4`),
and inflating it to 48px would have wrecked its alignment with the date and duration
in the same meta row. Instead the press area is extended with
`hitSlop={{ top: 14, bottom: 14, left: 8, right: 8 }}`, which is the same trick the
44px header buttons in this file already use to clear the 48px floor.

Pressed feedback is a tonal shift to `Colors.surfaceContainerHigh` (no new token, no
border), per the No-Line rule.

### What counts as "openable"

`resolveSourceLink()` trims the value, parses it with the WHATWG `URL` (Expo SDK 52
installs `whatwg-url-minimum` as a global via its winter runtime, so `protocol` and
`hostname` are reliable — the bare React Native polyfill is not), and accepts
**only** `http:`/`https:`. Anything else, including a parse failure, yields `null`
and therefore no affordance.

**Finding that diverges from the description.** The description assumed uploads and
shared text reach the client with `original_url === ""`. Against the real
`user_media-dev` table that is only half true:

| `source_platform` / `media_type` | stored `source_url` |
| --- | --- |
| `instagram` / `short_video` (5 rows) | `https://instagram.com/reel/<shortcode>/` (38 chars, all non-empty) |
| `youtube` / `youtube_video` (4 rows) | https URL |
| `document` / `document` (3 rows) | **attribute absent** — `original_url` becomes `""` via `record.source_url or ""` in `media_summarizer/api/endpoints/media.py:582` |
| `whatsapp` / `audio_file`, `shared_text` (5 rows) | **`share://whatsapp/...`** — a synthetic marker, non-empty and not openable |

So an emptiness test alone would have shipped a chip that opens `share://whatsapp/…`
on WhatsApp-shared audio, i.e. exactly the silent no-op tap AC #3 forbids. The
scheme allowlist is what makes AC #3 hold for all four row shapes. No schema change
was made, per the description's instruction to report such a finding rather than
smuggle in a fix.

### AC #7 — check against the real table

`aws dynamodb scan --region eu-west-3 --table-name user_media-dev` (projection
`source_platform,media_type,source_url`, filtered on `source_platform = instagram`)
returned 5 rows, every one of them holding a non-empty `source_url` of the form
`https://instagram.com/reel/<shortcode>/`. The affordance has something to open.
Shortcodes are deliberately not transcribed here — the repo is public.

### Failure path

`handleOpenSource` awaits `Linking.openURL` inside a `try/catch` and, on rejection,
calls the screen's existing `showToast`. The toast state gained a `tone`
(`"success" | "error"`) so the failure reuses that one surface with an `alert-circle`
glyph in `Colors.error` instead of introducing a second banner; the three existing
call sites are unchanged and still default to the success tone (AC #4).

`canOpenURL` is deliberately not called: http/https are always handled on both
platforms, so it would only add an async gate before every render decision without
changing the outcome.

### Out of scope, verified

`displayTitle` and `displayDomain` are byte-identical in the diff, and no inbox or
search file is touched (AC #5).

### Checks

`npx tsc --noEmit` clean. `npm run lint` → 0 errors, 10 warnings, all pre-existing
(the only one in this file is the unused `type` prop of `ArtifactRow`, untouched
here) (AC #8).

Per project policy, no automated test was added.
<!-- SECTION:NOTES:END -->
