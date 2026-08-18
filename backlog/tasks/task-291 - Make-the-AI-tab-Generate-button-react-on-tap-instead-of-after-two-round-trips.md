---
id: task-291
title: Make the AI tab Generate button react on tap instead of after two round-trips
status: To Do
assignee: []
created_date: '2026-08-18 16:35'
updated_date: '2026-08-18 18:12'
labels:
  - mobile
  - ui
  - bug
  - performance
dependencies:
  - task-292
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Tapping `Generate` on the AI tab leaves the button visually unchanged for as long as the request takes, so the tap reads as ignored and invites a second tap. Owner-reported on both the media AI tab and the collection AI tab.

## Why the delay exists

`ArtifactTile` is entirely server-driven: `isInProgress` derives only from `state.status`, which comes from the artifact history (`mobile/src/components/ArtifactTile.tsx:80-83`). It holds no local state. Both hosts then gate the visual change behind **two sequential network round-trips**:

```
onPress -> handleGenerate
  await ArtifactService.generateArtifact(...)   // RTT 1 (POST /api/artifacts)
  await refreshArtifacts() / refresh()          // RTT 2 (GET  /api/artifacts?scope=...)
  setArtifactHistory(...)                       // the ONLY moment the tile changes
```

`mobile/app/media/[id].tsx:513-541` and `mobile/app/media/collections/[id].tsx:379-397`.

RTT 1 is not a ping. `create_artifact` (`media_summarizer/api/endpoints/artifacts.py:178-271`) does, before answering: an ownership read, then `resolve_scope_sources`, which lists the scope's media (a collection covers every descendant) and **reads each source's transcript from S3** — the code itself puts 25 sources at ~400 kB of S3 reads (`media_summarizer/core/services/artifact_service.py:495-497`) — then token estimation, a consistent dedup read, a quota check, a conditional write, an SQS send and a quota write. The API Lambda runs at `memory_size = 1024` with no provisioned concurrency (`infrastructure/terraform/modules/platform/lambda_api.tf:91-94`), so a cold start stacks on top.

Two aggravating factors:

- **No press feedback at all.** The button passes a static style array (`ArtifactTile.tsx:108`) instead of the `({ pressed }) => [...]` form used by 20+ other Pressables in the app (`app/(tabs)/inbox.tsx:295` with `digestButtonPressed`, `SubscriptionStatusCard.tsx:106`, `ArtifactHistoryRow.tsx:64`). The button does not even dim under the finger.
- **The button stays tappable during the request.** `canGenerate` knows nothing about an in-flight POST, so the retap the delay invites fires a second full POST — a second S3 fan-out holding a second reserved-concurrency slot. Quota is safe (deterministic `artifact_id`, conditional write, 120 s dedup window, and `record_generation` is skipped on the deduplicated path — `artifact_service.py:86,662-693,764-782`), so this wastes backend work, not user minutes.

## The second round-trip is also a correctness bug

`refreshArtifacts()` reads the history through `list_artifacts_by_scope`, which queries the **`scope-index` GSI** (`media_summarizer/utils/media_artifacts.py:154-200`, `infrastructure/terraform/modules/platform/dynamodb_core_tables.tf:239-243`). A DynamoDB GSI is always eventually consistent — `ConsistentRead` is not available on one. A GET fired milliseconds after the write can come back **without the new entry**. Polling is armed by `hasArtifactInFlight`, derived from that same list (`app/media/[id].tsx:460-467,502-511`), so it never starts: the tile falls back to `Generate`, nothing shows the generation is running, and nothing recovers until the screen is remounted (the load effect depends only on `token`/`scope_id`; no `useFocusEffect` refreshes artifacts). A generation is then running, metered, and invisible.

The POST already answers an `ArtifactDetail`, which `extends ArtifactSummary` (`mobile/src/types/artifacts.ts:36-53`). The response being thrown away carries everything the history needs — the second round-trip is both slower and less reliable than the value already in hand.

## Scope

1. **Immediate local feedback.** Each host screen keeps a local set of artifact types whose POST is in flight, and that set overrides the tile state so the spinner appears on the tap frame with no network wait. Prefer overriding inside the existing `artifactStates` / `tileStates` memo rather than adding a prop to `ArtifactTile` — it keeps the component's API untouched and minimises overlap with task-290. The entry is added before the POST and removed as soon as it answers, success or failure: the merged response carries a real status from then on, so there is no optimistic state left to reconcile.
2. **Drop the post-POST GET.** Merge the POST response into the history (prepend, dedupe by `artifact_id`) instead of calling `refreshArtifacts()` / `refresh()`. This removes RTT 2 and the GSI consistency hole, and arms the poll immediately from the returned entry. Do not assume the response is `queued`: a deduplicated POST answers `200` with the existing entry, which may already be `ready` — merging by id must handle that shape too.
3. **Press feedback** on the generate button, following the repo's `({ pressed }) => [...]` convention.

A refusal must still leave the button tappable and surface the existing refusal banner — the local set is cleared on the error path too, otherwise a refused generation locks the tile.

**This task now depends on task-292**, which extracts the whole AI tab into a single shared component and deletes the duplicated JSX from both screens. Run after it: the line references above point at the pre-task-292 layout, and the rendering the tile state feeds into will live in the shared component. The data side this task changes (`handleGenerate`, the history state, the poll, the local in-flight set) stays in each screen, which is where task-292 leaves it — so the scope holds, only the file boundaries move.

**Overlap with task-290 (landed on `main`, commit `e307932`):** it edited the same three files to remove the `View` button and the `Regenerate` wording, and to space the `Generated` heading. The line references above already reflect that state — there is no merge conflict left to resolve. Stay out of that perimeter: do not touch the headings or the layout, and do not reintroduce a `View` button or the `Regenerate` wording. The tile now shows a single action, `Generate` (or `Retry` when the last entry failed), so the local in-flight override this task adds is the only thing that changes what the action block renders.

**Owner note (not an AC):** only the owner can confirm the felt result on a simulator/device. Worth checking the worst case — a collection with several sources, where the POST does the largest S3 fan-out — on both the media AI tab and the collection AI tab.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 In `mobile/app/media/[id].tsx` and `mobile/app/media/collections/[id].tsx`, the tile's in-progress rendering no longer depends solely on the fetched artifact history: each screen holds local state naming the artifact types whose generation request is in flight, and that state feeds the tile state used for rendering.
- [ ] #2 The local in-flight state is set before the POST is issued, on both screens, so no `await` sits between the press handler and the state update that flips the tile.
- [ ] #3 The local in-flight state is cleared on both the success path and the refusal path; on refusal the tile offers a tappable Generate button again and the existing refusal banner is what reports the reason.
- [ ] #4 While a generation request is in flight for a given artifact type, that tile offers no tappable Generate button, so a second tap cannot issue a second POST for the same type.
- [ ] #5 `handleGenerate` on both screens no longer calls the artifact-list endpoint after the POST: the `ArtifactDetail` returned by `ArtifactService.generateArtifact` is merged into the history state, deduped by `artifact_id`, and grep shows no list call left inside either `handleGenerate`.
- [ ] #6 The merge handles a response whose status is not `queued` (a deduplicated POST answers with an existing entry that may already be `ready` or `failed`) by replacing the entry of the same `artifact_id` rather than appending a duplicate row.
- [ ] #7 The generate button in `mobile/src/components/ArtifactTile.tsx` uses the repo's `style={({ pressed }) => [...]}` form with a distinct pressed style, matching the convention already used in `app/(tabs)/inbox.tsx` and `src/components/ArtifactHistoryRow.tsx`.
- [ ] #8 The `queued`, `generating`, `failed` (Retry) and `!sourceReady` (`Processing...`) renderings of `ArtifactTile` are behaviourally unchanged, and the poll still starts and stops from the history's own content.
- [ ] #9 `npx tsc --noEmit` and the lint command declared in `mobile/package.json` both pass from `mobile/`.
- [ ] #10 No section heading, spacing or layout style is changed on the AI tab: that perimeter belongs to task-290 (landed) and task-292 (the shared component this task builds on).
<!-- AC:END -->
