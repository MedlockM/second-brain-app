---
id: task-57
title: >-
  Produce iterative Stitch prompt pack for Media Summarizer mobile UI
  exploration
status: Done
assignee:
  - codex
created_date: '2026-03-17 15:38'
updated_date: '2026-03-17 16:32'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Prepare a production-ready Stitch prompt pack for the mobile share-first product so the team can generate original UI concepts that stay aligned with the canonical mobile roadmap, API contracts, states, constraints, and exclusions already defined in the repository.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A Stitch prompt pack exists for Media Summarizer mobile in App Mode with one seed prompt and targeted refinement prompts.
- [x] #2 The prompt pack reflects the canonical mobile product context from the repository, including supported media sources, tabs, share-first flow, transcript-first behavior, and on-demand artifacts.
- [x] #3 The prompt pack reflects locked public interfaces, status models, and stable error handling without inventing incompatible product behavior.
- [x] #4 The prompt pack explicitly preserves key exclusions: no billing screens, no Spotify linking, no content-email flows, English UI copy only.
- [x] #5 The documentation includes a practical validation checklist for reviewing Stitch outputs against mobile constraints, screen coverage, and state coverage.

- [x] #6 The prompt pack makes search a first-class product surface, including lexical keyword search and semantically related query behavior across the user's media knowledge base.
- [x] #7 The prompt pack makes the weekly in-app newsletter a first-class product surface, including weekly notification entry, digest reading inside the app, concise but exhaustive summaries, and a CTA that opens an interactive quiz for the related media.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Replace the current mega-prompt format with an iterative Stitch prompt pack built for App Mode and aligned with Stitch prompting guidance.
2. Ground the pack in repository truth only: mobile roadmap, canonical media API contract, media client types, mobile stack ADR, and backlog-defined mobile UX scope.
3. Organize the pack into one seed prompt plus targeted refinement prompts for visual system, share intake and inbox, media detail states, transcript reader mode, artifact surfaces, and history/account.
4. Include locked interfaces, statuses, stable error codes, and explicit exclusions so generated designs stay compatible with the mobile share-first product.
5. Add a concise validation checklist for reviewing Stitch outputs against screen coverage, state coverage, mobile constraints, and excluded product surfaces.

6. Revise the seed prompt and prompt breakdown so search and weekly digest become first-class product surfaces rather than secondary history details.

7. Add explicit prompt guidance for lexical and semantic search UX, search results, search empty states, weekly notification entry, weekly digest reading surfaces, and quiz deep-link behavior from each digest item.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Task created after backlog search found no existing Stitch/mobile prompt-pack task. User explicitly approved the implementation plan and requested direct execution.

Created docs/STITCH_MOBILE_PROMPT_PACK.md with one seed prompt, six targeted refinement prompts, a scoped edit template, and a validation checklist aligned with Stitch guidance and the mobile repository contract.

Replaced docs/STITCH_MOBILE_MEGA_PROMPT.md with a compatibility redirect to the iterative prompt-pack document to avoid maintaining two divergent prompt formats.

Verification was documentation-focused only; no automated tests were run because this task only adds and updates docs.

Scope revision requested by user after delivery: search and weekly in-app digest with quiz CTA must be treated as major app components in the Stitch prompt pack.

Refactored docs/STITCH_MOBILE_PROMPT_PACK.md so Search and Weekly Digest are first-class product surfaces in the seed prompt, navigation assumptions, required screens, dedicated refinement prompts, and validation checklist.

Added explicit design guidance for lexical and semantically related search behavior across the user's private media knowledge base, plus weekly notification entry, in-app digest reading, exact digest CTA copy, and quiz deep-link behavior.

Updated docs/STITCH_MOBILE_MEGA_PROMPT.md compatibility note so it points to the iterative pack as the source of truth for the expanded product scope.

User requested a visual-direction revision: generated designs should skew more modern, minimalist, reading-friendly, and also colorful and shimmering without sacrificing legibility.

Adjusted the visual-direction language in the prompt pack so Stitch is steered toward a modern, minimalist, reading-friendly aesthetic with colorful, shimmering, and chatoyant shell surfaces kept separate from calm reading zones.

User requested that the standalone mega-prompt file be updated as well, not only the iterative prompt pack.

Replaced docs/STITCH_MOBILE_MEGA_PROMPT.md placeholder with a full one-shot mega prompt aligned with the revised product scope and visual direction: Search and Weekly Digest as first-class surfaces, exact digest CTA copy, and modern minimalist colorful chatoyant styling that keeps reading zones calm.
<!-- SECTION:NOTES:END -->
