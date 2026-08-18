---
id: task-275
title: >-
  Benchmark strategies to stop making a Lambda wait on a slow social-video
  provider (Instagram, then TikTok)
status: Done
assignee:
  - Codex
created_date: '2026-08-17 20:54'
updated_date: '2026-08-18 00:55'
labels:
  - benchmark
  - ingestion
  - backend
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

task-274 moves Instagram resolution off the API request onto the queue-first worker, which stops the user-facing `Save failed`: a worker whose ceiling clears the measured worst case absorbs the fallback's latency instead of dying on it. Saves then work, but every save that falls back costs 60-100 s and one billed Apify run.

This benchmark addresses what task-274 cannot: our exposure to a provider latency we do not control.

Hard data measured on dev on 2026-08-17, all reproducible from the Apify account and the CloudWatch log groups:

- The `apify~instagram-reel-scraper` fallback took **63-100 s** across six runs, all `SUCCEEDED`. The same actor took **6-9 s** on 10 June 2026 — roughly a 10x slowdown in two months, with no change on our side.
- The yt-dlp primary path is refused from the Lambda IP on **6 attempts out of 6** (`Requested content is not available, rate-limit reached or login required`), where it had carried every working save on 12 August at ~2 s end to end.
- Because the API caps at 30 s (API Gateway HTTP API, not configurable), every one of those successful runs was billed and its payload discarded before task-274.

The point is the trend, not today's number: a worker ceiling chosen against 63-100 s has no reason to hold when the same actor was at 6-9 s eight weeks ago. Raising the ceiling again each time is not a strategy. So the question is which architecture stops a Lambda from waiting on the provider at all.

## Scope: the fallback layer only

Two layers can be hardened, and the owner has already decided how to split them:

- **In scope here (V1) — make the Apify fallback non-blocking.** Candidates: Apify run webhooks (`ACTOR.RUN.SUCCEEDED`); self-requeue with `DelaySeconds`; `waitForFinish`; Step Functions or another orchestration if it beats these on the same criteria. The repo already has a precedent for provider callbacks in the Deepgram `push`/`pull` modes, which should be assessed as a template.
- **Out of scope (V2) — keeping the free yt-dlp primary path working**, i.e. the residential-proxy question. The owner has deferred it to V2, consistent with the same decision already taken for TikTok. It is tracked in task-145, whose scope now covers Instagram too. Do not re-benchmark proxy vendors here.

These two layers are complementary, not competing: the proxy would reduce how often the fallback is reached, and would not make the fallback itself able to complete. A recommendation here must therefore hold whether or not a proxy ships later, and must not assume the fallback becomes rare.

## Criteria

Save latency on the happy path and on the provider-blocked path; monthly cost at realistic volumes; new infrastructure and new attack surface, including any publicly reachable endpoint and how it would be authenticated; failure and retry semantics, including what happens to a job whose callback never arrives; and resilience to a further provider slowdown.

Be explicit about one thing in particular: `waitForFinish` is included so its rejection is argued rather than assumed, but establish whether it changes anything at all given that it appears to relocate the same blocking wait rather than remove it.

State also whether the recommended option lets the worker ceiling that task-274 raises come back down, and by how much.

## Cross-cutting question the benchmark must settle

State whether TikTok should adopt the same shape for its own Apify fallback, so the two social-video paths do not diverge into two architectures. TikTok's fallback is the same provider and the same pattern; a decision that fits only Instagram should say why.

## References

- Instagram bug, root cause and measurements: task-274.
- Residential proxy, deferred to V2 for both platforms: task-145 (non-dispatchable placeholder), task-144, and `docs/research/task-140-tiktok-extraction/README.md`. Note the decision of record is Apify; the proxy was deferred, not adopted.
- Instagram extraction benchmark: `docs/research/task-107-instagram-extraction-benchmark/README.md`.
- Current fallback strategy of record: `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`.
- Resolver under discussion: `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`.

## Note to the owner

The Instagram yt-dlp block may lift on its own, since the egress IP is shared and the limit is Instagram's. A spontaneous recovery would make the fallback rare again, not sound: it would still be one provider slowdown away from the same cliff, which is exactly what this benchmark is meant to remove.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 docs/research/task-275-<short-description>/README.md exists with owner_decision: pending in its front-matter and an Owner Validation section
- [x] #2 Each candidate is compared on save latency (happy path and provider-blocked path), monthly cost at realistic volumes, new infrastructure and attack surface including endpoint authentication, retry and failure semantics including a callback that never arrives, and resilience to a further provider slowdown
- [x] #3 The README establishes whether waitForFinish changes anything versus the current polling, or merely relocates the same blocking wait, rather than assuming its rejection
- [x] #4 A single recommendation is stated with the rejection rationale for every discarded option, and the README says whether it lets task-274's raised worker ceiling come back down and by how much
- [x] #5 The measured facts of the incident are carried into the README and sourced: the 63-100 s Apify runs versus 6-9 s in June, the 6/6 yt-dlp blocks, and the 30 s API Gateway integration cap

- [x] #6 The README records that the residential proxy is out of scope and deferred to V2 in task-145, and that the recommendation holds whether or not a proxy ships later — it must not assume the fallback becomes rare
- [x] #7 The README states whether TikTok should adopt the same shape for its own Apify fallback, or argues why a solution fitting only Instagram is acceptable
- [x] #8 No implementation work is performed in this task
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Auditer le fallback Apify Instagram/TikTok actuel, les ADR et benchmarks associés, ainsi que le précédent Deepgram push/pull. — Terminé.
2. Effectuer une recherche internet exhaustive fondée sur les documentations officielles Apify, AWS Lambda/SQS et AWS Step Functions afin d’établir limites, sécurité, retries, latences et coûts à jour. — Terminé.
3. Comparer les webhooks Apify, l’auto-ré-enqueue SQS, waitForFinish, Step Functions Standard/Express et le polling actuel sur la grille complète, avec scénarios de 100, 1 000 et 10 000 fallbacks mensuels. — Terminé.
4. Rédiger docs/research/task-275-apify-async-orchestration/README.md avec owner_decision: pending, Owner Validation, recommandation unique, motifs de rejet, impact sur les timeouts, portée TikTok et exclusion explicite du proxy résidentiel. — Terminé.
5. Relire le livrable contre chaque critère, vérifier les calculs et sources, puis consigner le résultat. — Terminé. La tâche reste To Do et est bloquée par owner_decision: pending jusqu’à la validation owner, conformément au lifecycle benchmark.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Mode initial. Benchmark produit dans docs/research/task-275-apify-async-orchestration/README.md. Recherche fondée sur les documentations officielles Apify et AWS, l’implémentation locale, task-274 et les benchmarks task-107/task-140. Recommandation : run Apify asynchrone avec webhook ad hoc sur tous les états terminaux, continuation SQS idempotente et backstop unique à 15 minutes qui réconcilie le run ; même orchestration pour Instagram et TikTok. waitForFinish, polling SQS continu, Step Functions et relèvement des timeouts sont comparés et rejetés avec coûts eu-west-3. Aucun code ni Terraform modifié. La recommandation attend la validation de l’owner via owner_decision.

Décision owner traitée le 2026-08-18 : `owner_decision: ok`; la recommandation du README est acceptée. L’implémentation transverse a été livrée par task-277, qui supersède explicitement le ticket d’implémentation task-276.
<!-- SECTION:NOTES:END -->
