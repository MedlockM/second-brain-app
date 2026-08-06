---
id: task-217
title: Isolate the interactive API runtime from shared Lambda worker dependencies
status: Done
assignee:
  - Codex
created_date: '2026-07-27 20:59'
updated_date: '2026-08-06 00:50'
labels:
  - infra
  - lambda
  - performance
  - cost-optimization
  - release
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The FastAPI Lambda currently uses the same 406 MB container image as every asynchronous worker. After a long idle period, reactivation produced two API Gateway 500 responses followed by a 25.7-second first invocation, placing the interactive API close to its 30-second integration timeout. Implement the owner-approved production shape: keep the API on Lambda ARM64/on-demand but give it a minimal dedicated runtime; retain a shared image for asynchronous workers; protect interactive capacity without enabling paid provisioned concurrency by default; and add a low-cost warm-up plus release checks that detect an unavailable or unhealthy API. The outcome should reduce cold-start latency and deployment blast radius while preserving the Lambda-only architecture and near-zero idle cost. Provisioned concurrency remains an opt-in operational control to enable later only when production metrics justify it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The FastAPI Lambda is deployed from a dedicated minimal container image that excludes worker-only runtime dependencies.
- [x] #2 All asynchronous SQS workers continue to run from a shared worker image and retain their existing handler mappings.
- [x] #3 The deployment pipeline builds immutable versioned API and worker images and updates each Lambda group with the correct image without forcing unrelated functions onto the other runtime.
- [x] #4 Terraform represents the distinct API and worker deployment artifacts while preserving ARM64 and the existing Lambda-only architecture.
- [x] #5 The API has configurable reserved concurrency that protects interactive traffic from worker concurrency exhaustion without enabling paid provisioned concurrency by default.
- [x] #6 A low-cost scheduled warm invocation prevents multi-week inactivity and verifies the canonical health endpoint without introducing permanent provisioned capacity.
- [x] #7 Release validation waits for the Lambda to be Active and fails unless the public API health endpoint returns a successful healthy response.
- [x] #8 API Gateway access logs capture the integration error message needed to diagnose failures occurring before Lambda invocation.
- [x] #9 Before-and-after measurements document compressed image sizes, cold initialization duration, first-request latency, and warm-request latency in AWS dev.
- [x] #10 The production configuration keeps provisioned concurrency disabled by default and documents the measured threshold and explicit procedure for enabling it later.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Auditer les imports et dépendances réellement nécessaires au démarrage FastAPI, puis créer une image API ARM64 dédiée minimale tout en conservant l’image workers partagée et leurs handlers.
2. Adapter le pipeline GitHub Actions pour construire deux images distinctes, les publier avec des tags immuables dérivés du commit et ne mettre à jour que le groupe Lambda correspondant; attendre l’état Active/Successful de chaque fonction.
3. Faire représenter explicitement par Terraform les artefacts API/worker; ajouter une reserved concurrency API configurable, sans provisioned concurrency par défaut.
4. Ajouter un warm-up planifié à bas coût qui invoque et valide le health check, enrichir les access logs API Gateway avec le message d’erreur d’intégration, et faire échouer la validation de release si le health endpoint public n’est pas sain.
5. Documenter la procédure et le seuil mesuré d’activation optionnelle de provisioned concurrency.
6. Valider les Dockerfiles, le format/validate Terraform et la cohérence du workflow; déployer en AWS dev, puis mesurer image compressée, cold init, première requête et latence chaude avant/après.
7. Mettre à jour les critères et notes Backlog, passer task-217 à Done, puis recalculer la prochaine tâche exécutable la plus prioritaire.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Blocage (2026-08-06) : plan d’implémentation présenté à l’owner mais pas encore explicitement approuvé. Aucune modification de code ou d’infrastructure effectuée. Mesures AWS dev de référence collectées en lecture seule : image actuelle 404 533 119 octets compressés, Init Duration 3 862,65 ms, première requête observée 4,92 s, requêtes chaudes 0,60–0,73 s, aucune reserved concurrency.

Approbation owner reçue le 2026-08-06 après le blocage initial ; implémentation reprise conformément au plan.

Implémentation : image API ARM64 dédiée via `infrastructure/docker/lambda-api.Dockerfile`; image workers partagée enrichie par l’extra Python `worker`; CI séparée API/workers avec détection de chemins, tags SHA et déploiement par digest; Terraform avec artefacts distincts, warm-up EventBridge, logs API Gateway enrichis et reserved concurrency configurable; documentation ajoutée dans `docs/API_LAMBDA_RUNTIME.md`.

Validation statique : Ruff OK sur `media_summarizer/api/lambda_handler.py`; Mypy OK sur 159 fichiers; `py_compile` OK; `terraform validate` OK; plan Terraform post-apply = `No changes`; actionlint OK; `git diff --check` OK. Aucun test automatisé ajouté/exécuté, conformément aux règles du projet.

Validation images/deploiement AWS dev : builds Docker réels linux/arm64 réussis. API ECR `sha256:0fef91b1f25cba20135d7634225b38a486a36f45130340ab45206ead5e9959ec` (297 839 156 octets); workers `sha256:94861d5bff10fa38521ebbcfe200acc010730d4f4de9afd0bb0d9a604ee0c74d` (405 026 760 octets). API et 13 workers vérifiés `Active/Successful`, ARM64, bons digests et handlers.

Validation runtime : health public retourne HTTP 200/`healthy`; invocation directe du payload EventBridge réussie sans FunctionError; règle planifiée `rate(15 minutes)` active avec permission/target corrects. Mesures avant/après documentées : image -26,5 %, cold Init 3 862,65 -> 9 163,50 ms, première requête 4,92 -> 10,49 s, chaud 0,60–0,73 -> 0,64–0,66 s. Le cold start unique n’a pas été présenté comme une amélioration ; le warm-up est la mitigation mesurée.

Concurrence : staging/production utilisent 10 par défaut et provisioned concurrency reste désactivée. AWS dev utilise -1 car son quota régional refuse toute réservation tout en imposant 10 exécutions non réservées; l’override, les seuils mesurés et la procédure d’activation future sont documentés.
<!-- SECTION:NOTES:END -->
