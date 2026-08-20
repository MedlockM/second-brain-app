---
id: task-304
title: >-
  Extract, store and expose a cover image and a creator name for every ingested
  media per validated benchmark (task-302)
status: Done
assignee: []
created_date: '2026-08-19 21:09'
updated_date: '2026-08-20 00:00'
labels:
  - ingestion
  - backend
  - api
  - phase-6
dependencies:
  - task-302
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Give every media row in the library a **cover image** and a **creator name**, so the reworked Inbox tiles can render an image, a title and an author the way the owner's reference screenshot does.

**Read `docs/research/task-302-*/README.md` first.** The owner's `Decision` field under `Owner Validation` is authoritative — it may differ from the recommendation, and it may reference complement files (`complement-response-*.md`), which you must follow too. Everything below is scope, not design: where the image comes from per source, whether it is hotlinked or re-hosted, the creator field's name and shape, and whether it joins the Algolia index are all decided in that README. Do not re-decide them, and do not implement the recommendation if the `Decision` says something else.

## Scope

- **Extraction**, in every ingestion path the README's per-source table covers: article, YouTube, podcast episode, TikTok, Instagram, X post, shared text, uploaded document, camera photo, gallery photo, audio file. A source the README declares imageless or creatorless gets the documented fallback, not a silent empty string.
- **Persistence** onto the durable library row (`user_media`), through the carrier the README specifies — today `thumbnail_url` is mirrored from `job.media_image` by `durable_media_service.mirror_job` (`:450`), and that hook is the natural one for a second field.
- **Exposure**: the list contract (`MediaSearchItem`, `api/endpoints/media.py:336`, which already carries `media_image`), the detail contract (`api/models/media_contracts.py`, `MediaItemContract`, which carries neither), and the mobile types (`mobile/src/types/media.ts` — `MediaListItem.media_image` is declared and read by nothing today).
- **Whatever the README's decision implies infrastructurally**: an S3 prefix and its lifecycle if images are re-hosted, an Algolia settings change if the creator becomes searchable, a Terraform change if either applies.
- If the README recommends a mobile image library (`expo-image` or equivalent), add the dependency here so the screen task does not have to. The screens themselves are out of scope.

## Out of scope

- The Inbox/Home redesign and the Search-tab library list — separate tasks in this batch, both consumers of what you deliver here.
- Surfacing the creator on the media detail screen. The field must be *in* the detail contract; rendering it there is not this task.
- Any backfill of existing `-dev` rows. Nothing is deployed (`AGENTS.md`); rows saved before this change stay imageless until re-ingested, and that is an accepted outcome, not a migration to script.

## Constraints

- **One carrier per fact.** No second image field alongside `thumbnail_url`, no per-source special-case attribute. One derivation helper shared by the sources, in the spirit of `core/media_ingestion/title_derivation.py` from task-266.
- **A missing image must never fail an ingestion.** Same rule the title derivation follows: a failure or a timeout in the metadata path degrades to the documented fallback and never to a failed job. Log it, do not raise.
- `instagram_apify_resolver.py:447` and `:555` currently use the account name **as the title**. Once a creator field exists, that misuse is a bug you own: the account name belongs in the creator field, and the title stays whatever task-266's derivation produces. Do not leave both reading the same value.
- No automated tests unless the owner asks (`AGENTS.md`, Delivery rules). `ruff` and `mypy` clean; `terraform validate` clean if you touch Terraform.

## Owner notes (not acceptance criteria)

- LAUNCH PREREQUISITE, owner-side after merge and deploy: re-ingest one item per source on `-dev` (article, YouTube, podcast, Instagram reel, TikTok, X post, a PDF, a camera photo) and check with the AWS CLI that its `user_media` row carries a usable image URL and a creator name. That is the only check that exercises the workers end to end, and no implementer can run it.
- Worth confirming at the same time: an Instagram or TikTok image URL still resolves a few days after ingestion. If it does not, the README's hotlink decision needs revisiting rather than patching here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The implementation follows the owner's Decision field in docs/research/task-302-*/README.md, and the Implementation Notes state which option was implemented and quote the decision that mandated it
- [x] #2 Every ingestion path listed in the README's per-source table assigns the cover image and the creator name, or applies the fallback the README documents for that source — no path is left writing nothing silently
- [x] #3 The values are persisted onto the durable user_media row through the carrier the README specifies, with no second image attribute introduced alongside thumbnail_url
- [x] #4 Both fields are returned by GET /api/media and present in the media detail contract, and the corresponding mobile types in mobile/src/types/media.ts declare them
- [x] #5 A single shared derivation helper holds the normalisation and fallback rules, and no per-source copy of that logic remains
- [x] #6 A metadata or download failure in the new path degrades to the documented fallback and cannot fail or block an ingestion, with the failure logged
- [x] #7 The Instagram resolver no longer uses the account name as the title: the account name feeds the creator field and the title comes from the task-266 derivation
- [x] #8 The Implementation Notes carry a per-source table stating, for each ingestion path, where the image and the creator name actually come from in the merged code and what the fallback is
- [x] #9 ruff and mypy are clean on the touched Python, and terraform validate exits 0 if any Terraform file was changed
- [x] #10 If the README mandates a mobile image dependency, it is added to mobile/package.json and cd mobile && npm run typecheck && npm run lint are clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented **Approach C**, per the owner's `Decision` in `docs/research/task-302-media-cover-and-creator/README.md`:

> **Decision**: Approach C — *"read what the pipeline already holds, hotlink the URLs that are public and stable, re-host only the three sources whose URL is signed or private"* (validated 2026-08-20).

### Per-source outcome, as merged (AC #8)

| # | Source | Cover, in the merged code | Hotlink / re-host | Creator, in the merged code | Fallback |
|---|---|---|---|---|---|
| 1 | Web article | `Document.image` (`og:image`/`twitter:image`) — `article_extraction_worker.py:_extract_article_metadata` | hotlink | `Document.sitename`, then `Document.author` | no cover → type icon; no creator → line omitted |
| 2 | YouTube (yt-dlp) | `info["thumbnail"]` → `largest_thumbnail(info["thumbnails"])` → deterministic `i.ytimg.com/vi/<id>/hqdefault.jpg` | hotlink | `info["channel"]` → `uploader` → `uploader_id` | `hqdefault` always exists, so a cover is effectively guaranteed |
| 2b | YouTube (Apify, IP-blocked) | `_apify_item_string(item, _APIFY_THUMBNAIL_FIELDS)` → deterministic `hqdefault` | hotlink | `_apify_item_string(item, _APIFY_CREATOR_FIELDS)` | deterministic cover; creator may be empty |
| 3 | Podcast episode | `episode_image`, already stored (`podcastindex_resolution_worker.py:313`) + `submit_media_for_user(media_image=…)` | hotlink | `podcast_title` — the show — at `:318`, and `source_title` on the submit path | `"Podcast"` placeholder is rejected → no creator |
| 4 | TikTok (yt-dlp) | `info["thumbnail"]` → `cover_capture.capture_from_url` | **re-host** (`x-expires`) | `info["uploader"]` → `creator` → `uploader_id` | capture returns `None` → type icon |
| 4b | TikTok (Apify native transcript) | none — the actor returns text only, and it runs precisely when yt-dlp was blocked | — | none | documented in place; type icon |
| 5 | Instagram reel / post | `displayUrl` → `cover_capture.capture_from_url`. The **reel branch used to ignore this field** although the actor returns it | **re-host** (`oh`/`oe`) | `ownerFullName` → `ownerUsername` | capture returns `None` → type icon |
| 6 | X post | `includes.media[].url` / `preview_image_url`, via `expansions=attachments.media_keys` added to the lookup already being made | hotlink | `author_name` → `@author_username` | text-only post → no cover, type icon. The avatar is **not** used as a fallback |
| 7 | Shared text | none, by construction — no provider, no URL | — | none — the sharer is the user | documented at the `ResolvedMedia` site |
| 8 | Uploaded document | none — `ParseResult` carries no image and there is no page rasteriser | — | none | documented in the worker and at the endpoint |
| 9 | Camera photo | the media itself: `cover_capture.capture_from_s3(DOCUMENT_BUCKET, document_s3_key)` | **re-host** (private, up to 50 MB) | none | decode failure → type icon |
| 10 | Gallery photo | same path as #9 | **re-host** | none | same |
| 11 | Audio file (upload / shared) | none — reading an ID3 `APIC` would need `mutagen` for a payoff limited to ripped podcasts | — | none | documented at both sites |

RSS-polled items are absent on purpose: they still have no `user_media` row at all (`rss_feed_poll_worker.py`, pre-existing defect surfaced by task-265 §13.2), so there is no tile to give a cover to.

### Carrier and shape (AC #3)

`user_media.thumbnail_url` stays the **only** image attribute. Its value now has two shapes: an absolute `https://…` URL when hotlinked, and an `s3://bucket/key` locator when re-hosted, resolved into a presigned URL at read time. `creator_name` is one new attribute on `UserMediaRecord` / `ProcessingJob` / `ResolvedMedia`, mirrored by **one added line** in the `mirror_job` tuple (`durable_media_service.py:445-452`) — the same hook the title uses. No second image field, no per-source attribute.

### Shared helper (AC #5)

`core/media_ingestion/media_metadata.py` — pure, no I/O, sibling of `title_derivation.py`: `normalize_creator_name`, `select_creator` (publisher-first, drops a creator equal to the title using task-266's own comparison helper), `normalize_cover_url`, `largest_thumbnail`, `youtube_thumbnail_url`, `build_cover_locator` / `parse_cover_locator`. Every producer calls it; no source re-implements a rule.

`core/services/cover_capture.py` is the only part that touches the network: fetch (bounded in time and size) → downscale to a 640-px longest edge JPEG q80 → PUT. Verified locally: a 1920×1080 source lands at 640×360 / 2.6 KB, a 1080×1920 at 360×640, a non-image returns `None`.

### Failure behaviour (AC #6)

Every new path is best-effort by contract and returns `None` rather than raising: `_fetch`, `_downscale_to_jpeg`, `_store`, `resolve_cover_url`, `delete_cover`, and `_extract_article_metadata`. A timeout, a 403, an undecodable payload, a missing `COVERS_BUCKET` or an unsignable key logs and leaves the row without a cover. No ingestion can fail because of a thumbnail.

### Exposure (AC #4)

`GET /api/media` returns `creator_name` and a resolved `media_image`; `MediaItemContract` gains both (it carried neither); the digest contract gains `thumbnail_url` and `creator_name` — the mobile digest card has rendered an always-`null` image since it was written (task-302 §2.5), and both halves now exist. Mobile types updated in `mobile/src/types/media.ts` and `digest.ts`.

Signing goes through a new `s3.generate_presigned_urls(items)` that opens **one** client per page instead of one per cover — the waste task-302 §3.4 flagged as a prerequisite.

### Instagram title misuse (AC #7)

The account name now feeds `creator_name` only. The title stays what task-266's `derive_media_title` produces from the caption, and `ownerFullName`/`ownerUsername` remain in its `authors=` rejection list — so the two can never converge on the same value again.

### Algolia

`searchableAttributes` becomes `["title", "creator_name", "transcript"]` — ordered, creator above transcript and below title (task-302 §7.4) — plus `attributesToRetrieve`, and the field is carried through `media_completed_worker` → the indexing queue → `index_transcript`, on both the primary-user and watcher fan-out paths. Written on the job **before** the completion event, so no re-index pass is needed.

### Infrastructure

New private `covers` bucket in `s3.tf` (`prevent_destroy`, explicit public-access block), `COVERS_BUCKET` in `runtime_env.tf`, both IAM statements extended, and the purge cascade deletes a re-hosted cover with its row (`media_lifecycle.py`, unconditional — a cover belongs to one save, unlike the transcript). `pillow>=11.0.0` added to the `worker` and `dev` extras; `uv.lock` regenerated (pillow 12.3.0). Only the worker image needs it — the API just signs a URL, and `_downscale_to_jpeg` imports Pillow lazily so the API image can still import the module.

### Checks (AC #9, #10)

- `ruff check .` — clean
- `mypy media_summarizer` — clean, 172 source files
- `terraform validate` (envs/dev) — Success; `terraform fmt` clean
- `cd mobile && npm run typecheck` — clean; `npm run lint` — 0 errors (4 pre-existing warnings, none in touched files)
- `expo-image ~55.0.11` installed and declared in `app.config.ts` plugins. The screens themselves are out of scope, so nothing renders it yet — that is the consumer task's job.

### Not done, and why

- **No backfill.** Rows saved before this change stay imageless and creatorless until re-ingested (`AGENTS.md`, "Nothing is deployed yet"), as the task instructs.
- **The owner's LAUNCH PREREQUISITE is unticked by construction**: re-ingesting one item per source on `-dev` and checking the row with the AWS CLI requires this code to be deployed, which happens on push to `main` long after this run. Worth pairing with the second owner note — checking a few days later that a re-hosted Instagram/TikTok cover still resolves, which it now should, since those two are the sources this task stopped hotlinking.
<!-- SECTION:NOTES:END -->
