---
id: task-266
title: Implement media title derivation per validated benchmark (task-265)
status: To Do
assignee: []
created_date: '2026-08-14 02:02'
labels:
  - ingestion
dependencies:
  - task-265
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the media title derivation retained by the owner at the end of task-265.

**Read `docs/research/task-265-media-title-derivation/README.md` first.** The `Decision` field under `Owner Validation` in the front-matter is authoritative — it may differ from the research agent's initial recommendation, and it may reference `complement-response-*.md` files that refine it. Follow what the `Decision` says, not what the comparison matrix concludes. Do not start if `owner_decision` is not `ok`.

## Scope

Replace the current per-source title derivation across the ingestion pipeline with the retained approach. The paths that carry title today, all of which the implementation will touch or delete:

- `media_summarizer/core/media_ingestion/adapters/orchestrators.py:163` — the `f"{platform}:{media_type}"` sentinel.
- `media_summarizer/core/media_ingestion/use_cases.py:140,172` — the `platform:shared_text` / `platform:audio_file` sentinels.
- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py` — title currently taken from the account/owner fields.
- `media_summarizer/workers/youtube_ingestion_worker.py`, `tiktok_ingestion_worker.py`, `x_ingestion_worker.py`, `article_extraction_worker.py` — workers that resolve provider metadata but publish no title.
- `media_summarizer/core/services/durable_media_service.py:341-350` — the late-metadata mirror, if the retained approach resolves the title after the initial save.
- `media_summarizer/core/services/search_indexing.py` — the title is an indexed and highlighted Algolia field; if the retained approach lets the title change after indexing, the re-index path must be wired.

The **media detail screen** is not in this task's scope: it derived its header from the URL because `MediaItemContract` carried no title at all, which **task-267** fixes independently. Once both have landed, the detail screen shows whatever this task stores — no extra wiring needed here. If task-267 has not landed yet, do not duplicate its fix.

Nothing is deployed and there are no users (see `AGENTS.md` § "Nothing is deployed yet"): the old per-source logic is **deleted** in the same run, not kept behind a flag or a fallback, and no backfill is scoped for existing dev rows carrying a bad title.

## Owner notes (not acceptance criteria — the implementer cannot do these)

- The fix is only observable end to end after a deploy to `-dev`, which happens on push to `main`. The owner submits one media per source afterwards and checks the title shown in the Inbox, in Search and on the detail screen.
- The Instagram and YouTube cases from the original report are the two to check first: an Instagram reel must no longer be titled with the account name, and no media must ever show a `platform:media_type` string.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The approach recorded in the Decision field of docs/research/task-265-media-title-derivation/README.md is implemented; if the Decision references complement files, their refinements are applied too
- [ ] #2 No code path can write a `platform:media_type`-style sentinel as a title any more: the sentinel expressions in orchestrators.py and use_cases.py are gone, replaced by the fallback the Decision specifies
- [ ] #3 The per-source title logic the Decision supersedes is deleted, not left behind a flag, a fallback branch or a dead helper — a grep for the removed expressions returns nothing
- [ ] #4 Every source listed in the benchmark's coverage table is wired to the retained derivation, and any source the Decision explicitly leaves out is named in the task's Implementation Notes with the reason
- [ ] #5 If the retained approach changes a title after the media is indexed, the Algolia re-index path is wired so the indexed title matches the stored one
- [ ] #6 ruff and mypy are clean on the backend
- [ ] #7 If the retained approach needs infrastructure the pipeline does not have yet (a new queue, an IAM permission, an env var, a Terraform variable), it is provisioned and `terraform validate` is clean; if it needs none, that is stated in the Implementation Notes
<!-- AC:END -->
