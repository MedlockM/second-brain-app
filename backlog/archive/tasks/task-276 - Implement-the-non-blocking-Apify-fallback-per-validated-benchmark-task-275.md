---
id: task-276
title: Implement the non-blocking Apify fallback per validated benchmark (task-275)
status: To Do
assignee: []
created_date: '2026-08-17 20:55'
updated_date: '2026-08-17 21:03'
labels:
  - ingestion
  - backend
dependencies:
  - task-275
  - task-274
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Goal

Stop any Lambda in the social-video ingestion path from waiting on an Apify run, so a save no longer depends on the provider answering inside an invocation's lifetime.

Read `docs/research/task-275-*/README.md` and follow the owner's `Decision` field under `Owner Validation`. That decision is authoritative, including any reference it makes to complement files in the same directory. Do not infer the architecture from this description, from the benchmark's initial recommendation, or from the options that were merely under discussion — the owner's choice may differ from all of them.

## Background

task-274 already moved Instagram resolution off the HTTP request onto the queue-first worker and raised the worker ceiling above the measured worst case, which stopped the user-facing `Save failed`. That makes saves work; it does not make them safe. The fallback answered in 63-100 s on 2026-08-17 against 6-9 s in June 2026, so the ceiling task-274 chose is sized against a number that moved by 10x in eight weeks. This task removes the wait rather than re-raising the ceiling.

## Scope boundaries

- Instagram first: it is the path with a measured outage.
- The residential proxy is **not** in this task. Keeping the free yt-dlp primary path working is deferred to V2 and tracked in task-145. Consequently, do not build anything that assumes the fallback is rare — it currently carries 100% of Instagram saves.
- The benchmark is required to state whether TikTok adopts the same shape for its own Apify fallback. Honour that conclusion: converge both platforms if the decision covers both, otherwise leave TikTok alone and record why in the notes.
- Whatever is superseded gets deleted in the same run, per the project's no-compatibility-layer rule: no polling loop kept "in case", no dual path behind a flag.
- If the validated design lets task-274's raised worker ceiling come back down, bring it down in this task and keep the queue's visibility timeout consistent with the new value.
- Update `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md` so the strategy of record matches what ships.

## Note to the owner

LAUNCH PREREQUISITE — the end-to-end confirmation needs the deploy. After this merges and `main` is pushed, save one Instagram reel from the app and confirm it reaches a transcript with no Lambda spending its invocation waiting on Apify. The fallback can be exercised on demand with the existing E2E sentinel that routes straight to Apify, which works whether or not the yt-dlp IP block has lifted by then.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The architecture implemented matches the owner's Decision field in docs/research/task-275-*/README.md, and the Implementation Notes name that decision and quote the part of it that drove the design
- [ ] #2 No Lambda in the Instagram ingestion path spends its invocation waiting on an Apify run, and no code path can outlive the invocation that runs it
- [ ] #3 A job whose provider result never arrives reaches a terminal state with a stable user-facing reason, rather than stalling indefinitely or dying on a timeout
- [ ] #4 Nothing in the implementation assumes the Apify fallback is rare: it currently carries every Instagram save, since the residential proxy is deferred to V2 in task-145
- [ ] #5 Any externally reachable callback surface is authenticated, its verification is readable in the code, and no provider callback can mutate a job it does not own
- [ ] #6 The superseded polling path is deleted rather than kept behind a flag, with no orphan queue, env var, IAM permission or secret left pointing at a path nobody reads
- [ ] #7 If the validated design allows it, task-274's raised worker ceiling is brought back down and the queue's visibility timeout stays consistent with the new value
- [ ] #8 task-145 and the TikTok fallback are handled per the benchmark's conclusion: either converged with this work, or explicitly left standalone with the reason recorded in the Implementation Notes

- [ ] #9 docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md describes the shipped strategy and marks the superseded one as such
- [ ] #10 ruff and mypy are clean; if infrastructure/terraform is touched, terraform validate and terraform plan exit 0 for the dev env
- [ ] #11 No provider token or callback secret is written into any tracked file, the task notes included
<!-- AC:END -->
