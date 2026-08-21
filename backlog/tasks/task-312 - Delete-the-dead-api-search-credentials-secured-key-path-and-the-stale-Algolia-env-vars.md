---
id: task-312
title: >-
  Delete the dead /api/search/credentials secured-key path and the stale Algolia
  env vars
status: Done
assignee: []
created_date: '2026-08-21 10:00'
updated_date: '2026-08-21 03:44'
labels:
  - backend
  - mobile
  - cleanup
  - search
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

`GET /api/search/credentials` was built as a "future optimization": let the mobile
client query Algolia directly with a short-lived secured key instead of proxying
through the backend. The optimization was never wired, and the path has been dead
on both sides ever since.

Measured on `main` at `a2dafa5` on 2026-08-21:

- **Backend.** `media_summarizer/api/endpoints/search.py:82` exposes the endpoint,
  which calls `generate_secured_search_key` (`utils/algolia_client.py:152`), which
  reads `ALGOLIA_SEARCH_API_KEY` (`algolia_client.py:46`).
- **That variable exists nowhere.** It is absent from `media-summarizer-runtime-dev`
  (40 keys, checked key by key) and absent from
  `infrastructure/terraform/modules/platform/runtime_env.tf`. So the endpoint has
  *never* been able to answer: it raises `RuntimeError` and returns `503` on every
  call, in every environment that has ever existed.
- **Mobile.** `mobile/src/services/searchService.ts:62` declares
  `getSearchCredentials`, and **nothing calls it**. `mobile/app/(tabs)/search.tsx:188`
  is the only consumer of the service and uses `SearchService.searchTranscripts`,
  the backend-proxied mode, which works.

So this is not "a missing credential to provision". It is a code path with no
caller, guarded by a variable no environment has, returning `503` by construction.
Nothing is deployed and there is no installed base, so it gets deleted rather than
completed — and the deletion is what keeps it out of the prod secret.

Two neighbouring Algolia variables are stale in the same way and go with it:

- `ALGOLIA_INDEX_NAME` — **dead**, no reader. The index name is derived as
  `media_items_{ENVIRONMENT}` by `algolia_client.py:84`, and Terraform injects
  `ENVIRONMENT` (`runtime_env.tf:103`). It survives only as a leftover row in the
  dev secret, where it still holds the pre-`task-205` value.
- `ALGOLIA_INDEX_PREFIX` — declared in `.env.example:397` with a comment
  describing a per-user index scheme (`{prefix}_user_{user_id}`) that
  `task-205` decided against. No reader either.

## Why this blocks task-252

`task-252` populates the prod runtime secret. Its key list is taken from dev, so
whatever is dead in dev gets copied into a brand-new prod secret and stays there
forever. Doing the cleanup first drops the prod list from 40 rows to the **37 live
keys** and removes the question "do we need to create an `ALGOLIA_SEARCH_API_KEY`
for prod?" — the answer is no, because the only thing that read it is gone.
`task-252` therefore depends on this task.

## Scope

**Backend — `media_summarizer/api/endpoints/search.py`**

Remove the `GET /credentials` endpoint, its `SearchCredentialsResponse` model, and
the `generate_secured_search_key` import. Keep `GET /transcripts` and everything it
uses. The module docstring describes the two-mode design ("Backend-proxied search"
/ "Direct client search"); rewrite it to describe the one mode that exists —
including the multi-tenant isolation note, which must now say the `user_id` filter
is applied server-side in the query, and nothing else.

**Backend — `media_summarizer/utils/algolia_client.py`**

Remove `generate_secured_search_key`, the module-level `ALGOLIA_SEARCH_API_KEY`
constant, and the now-unused `SecuredApiKeyRestrictions` import (line 35). Strip the
secured-key lines from the module docstring (lines 5, 12-13) and from the
`Environment variables` block (line 23).

**Mobile — `mobile/src/services/searchService.ts`**

Remove `getSearchCredentials` and the `SearchCredentials` interface. The
`SearchService` class docstring enumerates the two modes and calls the second one a
"future optimization"; reduce it to the proxied mode.

**`.env.example`**

Remove `ALGOLIA_SEARCH_API_KEY` (line 396) and `ALGOLIA_INDEX_PREFIX` (line 397,
comment included). `ALGOLIA_APP_ID` and `ALGOLIA_API_KEY` stay — both are read.

**`docs/DEVBOX_SETUP.md`**

The section around line 195 states the dev secret holds 37 keys and lists the ones
the `.env` injection skips. Both facts have drifted: the secret holds **40**, and
`REVENUCAT_WEBHOOK_SECRET` is no longer empty. Bring the count and the dead-key list
in line with what this task leaves behind.

## What is NOT in scope

`GET /api/search/transcripts`, `search_indexing.py`, the shared-index settings, and
the mobile search screen. They work and carry every search today.

## Owner notes (not acceptance criteria)

1. **Remove `ALGOLIA_INDEX_NAME` from the dev secret.** It is one row of
   `media-summarizer-runtime-dev` and removing it means re-`put-secret-value` with
   the full JSON, which is an owner operation on a live secret — deliberately not
   an AC. Harmless if left, but it will otherwise be copied into prod by hand.
2. **Rotate the Algolia admin key while you are there** — not required by this
   task, but `ALGOLIA_API_KEY` is currently the account-wide admin key on both
   sides, and `task-252` asks for an index-scoped key for prod. Creating the dev
   one at the same time costs nothing (Algolia allows unlimited API keys) and
   closes the path where a dev Lambda can delete the prod index.
3. After the deploy on `main`, confirm the search tab still returns results on dev
   — the proxied endpoint is untouched, so a regression there would mean the
   deletion took something it should not have.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GET /api/search/credentials no longer exists: the search router declares only /transcripts, and grep -n "credentials" on media_summarizer/api/endpoints/search.py returns nothing
- [x] #2 grep -rn "ALGOLIA_SEARCH_API_KEY\|generate_secured_search_key\|SecuredApiKeyRestrictions" on media_summarizer/ returns zero results
- [x] #3 grep -rn "getSearchCredentials\|SearchCredentials" on mobile/src and mobile/app returns zero results
- [x] #4 .env.example contains neither ALGOLIA_SEARCH_API_KEY nor ALGOLIA_INDEX_PREFIX, and still contains ALGOLIA_APP_ID and ALGOLIA_API_KEY
- [x] #5 The module docstrings of search.py and algolia_client.py no longer describe a direct-client / secured-key mode
- [x] #6 make lint is clean on media_summarizer/, and npm run typecheck plus npm run lint are clean in mobile/
- [x] #7 docs/DEVBOX_SETUP.md states the real key count of the dev secret and a dead-key list that matches the code after this task
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Backend `api/endpoints/search.py` : supprimer l'endpoint `GET /credentials`, le modèle `SearchCredentialsResponse`, l'import `generate_secured_search_key` ; réécrire le docstring module sur le seul mode proxied.
2. Backend `utils/algolia_client.py` : supprimer `generate_secured_search_key`, la constante `ALGOLIA_SEARCH_API_KEY`, l'import `SecuredApiKeyRestrictions` (+ `time` devenu inutile) ; nettoyer le docstring.
3. Backend `core/config.py` : supprimer `self.ALGOLIA_SEARCH_API_KEY` (lecteur non listé dans le scope de la tâche mais exigé par l'AC #2).
4. Mobile `src/services/searchService.ts` : supprimer `getSearchCredentials` et l'interface `SearchCredentials` ; docstring réduit au mode proxied.
5. `.env.example` : supprimer `ALGOLIA_SEARCH_API_KEY` et `ALGOLIA_INDEX_PREFIX`.
6. `docs/DEVBOX_SETUP.md` : corriger le compte de clés du secret dev et la liste des clés mortes, vérifiés contre `media-summarizer-runtime-dev`.
7. Vérifier `make lint`, `npm run typecheck`, `npm run lint`.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Ce qui a été supprimé

- **`media_summarizer/api/endpoints/search.py`** — endpoint `GET /credentials`, modèle `SearchCredentialsResponse`, import `generate_secured_search_key`. Le router ne déclare plus que `/transcripts` (vérifié à l'import : `['/transcripts']`). Docstring module réécrit : un seul mode, isolation multi-tenant par filtre `user_id` appliqué côté serveur dans la requête.
- **`media_summarizer/utils/algolia_client.py`** — `generate_secured_search_key`, la constante `ALGOLIA_SEARCH_API_KEY`, l'import `SecuredApiKeyRestrictions`, et `import time` devenu orphelin (ruff F401 sinon). Docstring nettoyé du modèle secured-key.
- **`mobile/src/services/searchService.ts`** — `getSearchCredentials` et l'interface `SearchCredentials`. Docstring de `SearchService` réduit au mode proxied.
- **`.env.example`** — `ALGOLIA_SEARCH_API_KEY` et `ALGOLIA_INDEX_PREFIX` (commentaire per-user index inclus). `ALGOLIA_APP_ID` et `ALGOLIA_API_KEY` restent, tous deux lus.

## Hors du périmètre écrit, mais nécessaire

- **`media_summarizer/core/config.py:74`** portait un troisième lecteur de `ALGOLIA_SEARCH_API_KEY` (`self.ALGOLIA_SEARCH_API_KEY = os.getenv(...)`), non mentionné dans la description. L'AC #2 exige zéro occurrence dans `media_summarizer/` : la ligne est supprimée. Personne ne lisait cet attribut de `Settings`.
- **`docs/V1_LAUNCH_PLAN.md` §3.4** listait `ALGOLIA_SEARCH_API_KEY=... # search-only key` dans les credentials à provisionner au lancement. Supprimé, sinon la checklist de lancement demande une clé que plus rien ne lit — exactement le problème que cette tâche ferme pour task-252.
- **`.env.example` §auth** annonçait « Four keys of the runtime secret (COOKIE_NAME_REFRESH, COOKIE_SECURE, COOKIE_SAMESITE, COOKIE_DOMAIN) are dead ». Le secret dev n'en contient plus qu'une (`COOKIE_DOMAIN`) ; corrigé pour rester cohérent avec `DEVBOX_SETUP.md` réécrit juste à côté.

## État réel du secret dev (relevé le 2026-08-21)

`media-summarizer-runtime-dev` contient **40 clés**, dont **37 vivantes**. Les trois mortes :

| Clé | Statut vis-à-vis de l'injection `.env` |
|---|---|
| `ALGOLIA_INDEX_NAME` | sautée (absente de `.env.example`) |
| `COOKIE_DOMAIN` | sautée (absente de `.env.example`), et seule valeur vide du secret |
| `APIFY_INSTAGRAM_COMMENT_ACTOR_ID` | **injectée** — encore déclarée dans `.env.example:257`, morte depuis task-173 |

La section §6 de `docs/DEVBOX_SETUP.md` disait « 37 clés » et « l'injection en saute cinq » : les deux chiffres étaient faux. Elle annonce désormais 40 clés / 37 vivantes, les deux noms réellement sautés, et signale la troisième morte qui, elle, passe dans le `.env`. `ALGOLIA_SEARCH_API_KEY` n'étant dans aucun environnement, sa suppression ne change pas la liste `skipped:`.

## Vérifications

- `make lint` : `ruff` clean, `mypy` — 173 fichiers, aucun problème.
- `mobile/` : `npm run typecheck` clean ; `npm run lint` 0 erreur, 2 warnings préexistants sans rapport (`digest.tsx` `CARD_WIDTH` inutilisé, `purchaseService.ts` `any`).
- Import du module : `media_summarizer.api.endpoints.search.router` ne déclare que `/transcripts`.
- `grep` repo-wide sur `search/credentials`, `SearchCredentialsResponse`, `getSearchCredentials` : plus que des mentions historiques dans `backlog/`.

## Restes assumés

`scripts/migrate_algolia_to_shared_index.py` lit encore `ALGOLIA_INDEX_PREFIX` (défaut `"transcripts"` en dur, donc il fonctionne sans la variable). C'est le script one-shot de migration task-205 → task-215, explicitement hors périmètre ; il n'est pas dans `media_summarizer/` et aucune AC ne le couvre.
<!-- SECTION:NOTES:END -->
