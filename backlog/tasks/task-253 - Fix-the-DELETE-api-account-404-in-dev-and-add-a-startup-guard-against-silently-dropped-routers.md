---
id: task-253
title: >-
  Fix the DELETE /api/account 404 in dev and add a startup guard against
  silently dropped routers
status: Done
assignee: []
created_date: '2026-08-13 13:10'
updated_date: '2026-08-13 15:57'
labels:
  - bug
  - api
  - compliance
  - implementation
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`DELETE /api/account`, shipped by task-224, returns `404` against the dev API. The route itself is correct — `media_summarizer/api/endpoints/account.py:27` declares `@router.delete("", status_code=204)` and `media_summarizer/api/main.py:148` mounts it under `/api/account`. The 404 has two candidate causes and the first must be ruled out before touching any code.

**Cause 1 — the code was very likely never deployed.** `deploy-lambda.yml` only fires on `push` to `main`, and task-224 (`24e9e3f`, 2026-08-12) is one of 53 commits sitting unpushed on local `main`; `origin/main` is still at `1d337e4`. A dev Lambda running a pre-task-224 image legitimately 404s, because the route did not exist in that image. Verify this first: compare the deployed dev Lambda image digest against the commit that introduced the route. If the image predates it, the fix is a push/deploy, not a code change — confirm the endpoint answers `204`/`401` (not `404`) on the redeployed image and close this task there.

**Cause 2 — an import-time crash on a missing environment variable.** Importing `media_summarizer.api.endpoints.account` transitively reaches `media_summarizer/utils/artifact_idempotence.py:18`, which calls `required_env("ARTIFACT_IDEMPOTENCE_TABLE")` at module scope and raises `RuntimeError` when it is unset. The chain is `account.py` → `account_deletion_service.py:65` → `media_purge_service.py:40` → `artifact_idempotence.py`. That import is reproducible locally today. In `main.py` the endpoint imports are a single unguarded `from ... import (...)` block, so a raise there kills the whole app rather than dropping one router — meaning under a plain ASGI server this would produce a total outage, not a per-route 404. If the Lambda handler or an adapter above it swallows import errors, or if a partially-initialised app is served, a single missing router is the shape you would see. Determine which of the two it is from the dev Lambda's cold-start logs before changing anything.

**Why this went unnoticed.** `tests/e2e/conftest.py:199-207` calls `DELETE /api/account` in teardown as best-effort and only prints the status code, so a `404` never fails a run. That masking is part of the bug: the teardown is the one place that exercises the shipped deletion path.

This matters beyond a broken route: in-app account deletion is required by App Store guideline 5.1.1(v), and `mobile/src/services/accountService.ts:22` is wired to this exact endpoint. If it 404s in prod, the mobile deletion flow is broken and the store commitment is not met.

**Note to the owner — the deploy check is yours, not an AC.** The implementer works in an isolated worktree: its code is neither merged nor pushed, so it cannot verify its own fix against a deployed Lambda. That check is therefore deliberately absent from the acceptance criteria. Once this merges and `main` is pushed, and once `deploy-lambda.yml` has run, confirm `DELETE /api/account` answers `401`/`204` rather than `404` against the dev image — and check the deployed digest matches the merge commit, since the workflow is `paths`-filtered.

Do not widen this into a refactor of every endpoint import. The guard asked for is a narrow startup assertion that the expected routers are actually mounted, so a dropped router fails loudly at boot instead of surfacing as a 404 months later.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The root cause is established from evidence and written into the task's Implementation Notes: either the deployed dev image predates the commit that added the route, or an import-time failure is shown in the dev Lambda cold-start logs — not both, and not a guess
- [x] #2 The DELETE /api/account route is declared on the account router and that router is mounted in media_summarizer/api/main.py under the /api/account prefix, with the authentication dependency in place — the wiring is readable end to end in the code
- [ ] #3 If the cause is the import-time RuntimeError, no module reached through the account.py import chain resolves a required environment variable at module scope — ARTIFACT_IDEMPOTENCE_TABLE in particular is resolved lazily at call time
- [x] #4 A startup check asserts that the routers main.py intends to mount are present in app.routes and fails loudly at boot when one is missing, covering at minimum the account router
- [x] #5 The e2e teardown in tests/e2e/conftest.py no longer silently accepts a 404 from DELETE /api/account: an unexpected status is surfaced rather than only printed
- [x] #6 ruff and mypy stay clean on the touched files
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Traité le 2026-08-13. **La cause 1 est confirmée par les preuves, la cause 2 est écartée.**

### AC #1 — la cause racine, établie

Le déploiement était bien la cause. Deux constats indépendants qui concordent :

**L'image déployée précédait la route.** `24e9e3f` (task-224, qui crée `media_summarizer/api/endpoints/account.py`, 2026-08-12) n'est **pas** un ancêtre de `5447053`, le commit du dernier déploiement réussi de `deploy-lambda.yml` (run `31353088904`, 2026-08-10). La Lambda dev servait donc une image dans laquelle la route n'existait pas — un 404 parfaitement légitime.

**Et depuis, elle a été déployée.** `24e9e3f` **est** un ancêtre de `9cb9da5`, dont le run `31712425601` (2026-08-13 14:53) a un job `deploy-api` en `success`. `media-summarizer-api-dev` porte `LastModified 2026-08-13T14:55:11` et tourne le digest `sha256:1878168e…`.

**Vérifié en direct contre l'API dev** (`https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`) :

| Requête | Réponse |
|---|---|
| `DELETE /api/account` | `401 {"detail":"Authentication token required"}` |
| `GET /api/account` | `405 Method Not Allowed` |
| `DELETE /api/nonexistent` | `404 Not Found` |

Le `401` prouve que la route est montée et que la dépendance d'authentification s'applique — un router absent aurait rendu `404`, comme le montre le contrôle négatif. Le `405` sur `GET` confirme que le chemin existe mais n'accepte que `DELETE`. **AC #2 est donc satisfaite en production dev, sans changement de code.**

**Pourquoi la cause 2 est écartée**, alors qu'elle est réellement reproductible en local : importer `media_summarizer.api.endpoints.account` sans `ARTIFACT_IDEMPOTENCE_TABLE` lève bien `RuntimeError` via la chaîne `account.py` → `account_deletion_service.py:65` → `media_purge_service.py:40` → `artifact_idempotence.py:18`. Mais en Lambda la variable **est** injectée par Terraform (`modules/platform/runtime_env.tf`), donc l'import aboutit. Et surtout, comme le ticket l'avait anticipé, l'import de `main.py` est un bloc unique non gardé : cette exception tuerait l'app entière, pas une route — le symptôme observé était un 404 isolé sur une API par ailleurs saine. Les deux hypothèses étaient mutuellement exclusives, et c'est la première qui est vraie.

### AC #3 — sans objet, et volontairement non traitée

L'AC est conditionnelle (« If the cause is the import-time RuntimeError »). La cause n'étant pas celle-là, `artifact_idempotence.py:18` reste inchangé.

Ce n'est pas un oubli mais un choix de périmètre. La dette existe : **21 modules** résolvent un `required_env` au niveau module (`grep -rln "^[A-Z_]* = required_env" media_summarizer/`), dont `database_async.py`, `media_idempotence.py`, `digest_db.py`, `minute_db.py`. Rendre le seul `artifact_idempotence.py` paresseux introduirait un pattern isolé dans un code base qui n'en a aucun (`grep` sur `def _table_name` ne retourne rien), sans corriger le problème de fond. Le ticket disait « Do not widen this into a refactor of every endpoint import » — c'est la même logique appliquée à la couche `utils`. Si l'owner veut traiter ça, c'est une tâche dédiée, à l'échelle des 21 modules.

### AC #4 — le guard de démarrage

Ajouté dans `media_summarizer/api/main.py`, juste après les `include_router` : `CRITICAL_ROUTES` puis `_assert_critical_routes_mounted()`, appelé à l'import du module. Un router manquant fait échouer le boot avec un message qui nomme la route et renvoie à cette tâche.

Trois routes seulement : `DELETE /api/account`, `POST /api/v1/auth/login`, `GET /api/media`. Le choix est celui d'une liste courte et maintenue plutôt que d'un inventaire exhaustif que personne ne mettrait à jour — le critère retenu est « une absence est un incident de conformité ou de produit », ce qui est le cas de la suppression de compte (App Store 5.1.1(v)), du login et de la liste de médias.

Détail d'implémentation : `app.routes` est typé `list[BaseRoute]`, et seul `APIRoute` porte `.path`/`.methods`. Le `getattr` est donc là pour mypy autant que pour la robustesse face aux routes non-HTTP (`Mount`, WebSocket).

Vérifié dans les deux sens, pas seulement au cas nominal :
- import complet de l'app avec les variables de `.env.example` → 73 routes, les 3 routes critiques présentes.
- même import en neutralisant l'`include_router` du router `account` → `RuntimeError: API refusing to start: expected route(s) not mounted: DELETE /api/account`. Le guard est donc réellement porteur, et pas une assertion qui ne peut pas échouer.

### AC #5 — le teardown e2e ne masque plus le 404

`tests/e2e/conftest.py` : le `DELETE /api/account` du teardown émet désormais un `warnings.warn` si le statut n'est pas `204`, avec un message qui explique ce qu'un 404 signifie et pointe le code mobile concerné. Une exception est également warned en plus d'être imprimée.

Le choix du `warnings.warn` plutôt que d'un `raise` ou d'un `pytest.fail` est délibéré. Le docstring de la fonction porte un contrat explicite : « teardown must not turn a passing test into a failure », et le sweep par script reste la garantie de nettoyage. Lever ferait échouer des tests verts pour un défaut de nettoyage. Un warning, lui, remonte dans le résumé pytest et dans les logs CI : l'information cesse d'être noyée dans un `print`, ce que l'AC demande (« surfaced rather than only printed »), sans inverser le contrat de la fonction.

### AC #6 — ruff et mypy

`ruff check` et `mypy` sont clean sur les deux fichiers touchés.

À signaler : `ruff format --check` signale `main.py` et `conftest.py` comme « would reformat », mais c'était **déjà le cas avant ces modifications** — vérifié en stashant le diff. Ces fichiers ne sont pas formatés par `ruff format` dans l'état actuel du repo, et les reformater ici produirait un diff massif sans rapport avec la tâche. `tests/unit` passe (14 tests), et la collecte de `tests/e2e` est propre.

### Ce qui reste à l'owner

Rien pour le bug lui-même : il est corrigé en dev et vérifié. Le seul point d'attention est que ce commit n'est pas encore poussé, et que **le guard n'a pas d'effet tant que l'image n'est pas redéployée**.

Attention par ailleurs : `deploy-workers` est rouge depuis le 2026-08-10 sur un `AccessDeniedException` (`tag:GetResources` manquant sur le rôle IAM dev). Ça n'affecte pas la route `DELETE /api/account`, qui vit dans l'API — mais ça veut dire qu'un run rouge de `deploy-lambda.yml` ne signifie plus « l'API n'est pas déployée ». C'est suivi par **task-256**.
<!-- SECTION:NOTES:END -->
