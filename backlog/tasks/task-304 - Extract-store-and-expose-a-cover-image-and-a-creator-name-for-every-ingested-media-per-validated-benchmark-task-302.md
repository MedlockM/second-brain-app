---
id: task-304
title: >-
  Extract, store and expose a cover image and a creator name for every ingested
  media per validated benchmark (task-302)
status: To Do
assignee: []
created_date: '2026-08-19 21:09'
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
- [ ] #1 The implementation follows the owner's Decision field in docs/research/task-302-*/README.md, and the Implementation Notes state which option was implemented and quote the decision that mandated it
- [ ] #2 Every ingestion path listed in the README's per-source table assigns the cover image and the creator name, or applies the fallback the README documents for that source — no path is left writing nothing silently
- [ ] #3 The values are persisted onto the durable user_media row through the carrier the README specifies, with no second image attribute introduced alongside thumbnail_url
- [ ] #4 Both fields are returned by GET /api/media and present in the media detail contract, and the corresponding mobile types in mobile/src/types/media.ts declare them
- [ ] #5 A single shared derivation helper holds the normalisation and fallback rules, and no per-source copy of that logic remains
- [ ] #6 A metadata or download failure in the new path degrades to the documented fallback and cannot fail or block an ingestion, with the failure logged
- [ ] #7 The Instagram resolver no longer uses the account name as the title: the account name feeds the creator field and the title comes from the task-266 derivation
- [ ] #8 The Implementation Notes carry a per-source table stating, for each ingestion path, where the image and the creator name actually come from in the merged code and what the fallback is
- [ ] #9 ruff and mypy are clean on the touched Python, and terraform validate exits 0 if any Terraform file was changed
- [ ] #10 If the README mandates a mobile image dependency, it is added to mobile/package.json and cd mobile && npm run typecheck && npm run lint are clean
<!-- AC:END -->
