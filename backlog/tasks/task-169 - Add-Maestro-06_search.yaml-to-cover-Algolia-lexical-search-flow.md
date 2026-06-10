---
id: task-169
title: Add Maestro 06_search.yaml to cover Algolia lexical search flow
status: To Do
assignee: []
created_date: '2026-06-10 05:58'
labels:
  - phase-5
  - mobile
  - release
  - tooling
  - e2e
dependencies:
  - task-161
  - task-162
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Phase 5 TDD coverage. La suite Maestro actuelle (01-05) couvre auth, share intake, inbox, media detail, artifact generation. Il manque la **search lexical** (Algolia) qui est l'un des flows V1 critiques (cf. task-85 qui implémente le search lexical, déjà Done).

Sans test Maestro sur le search, toute régression côté `mobile/app/(tabs)/search.tsx` ou côté indexation Algolia (`media_summarizer/algolia_*`) passe inaperçue jusqu'au device manuel.

## Scope

Crée `mobile/.maestro/06_search.yaml` qui :

1. Lance l'app, authentifie via le sous-flow login email (factorisé par task-168, ou inline si pas encore prêt)
2. Tape sur le tab "Search" (Expo Router : route `/search` ou onglet)
3. Saisit un terme de recherche connu pour exister dans le compte de test (ex: un mot du titre du media partagé en setup, ou un fixture pré-loadé)
4. Attend l'apparition d'au moins un résultat (`extendedWaitUntil` sur un selector de résultat)
5. Tap sur le résultat → vérifie qu'on arrive sur le media detail screen correspondant

## Setup data

Pour qu'il y ait un résultat à trouver, le flow doit pouvoir compter sur :
- Soit un user de test pré-loadé avec un media indexé sur Algolia
- Soit un setup inline qui partage une URL connue (réutilise le pattern de `02_share_intake.yaml`) puis attend l'indexation Algolia (~5-10s typique)

Documente le choix dans le commentaire du flow.

## Convention

- `appId: com.secondbrainlabs.core`, tags `critical, search`
- Réutilise `${SEARCH_TEST_TERM}` ou ajoute-le dans `mobile/.maestro/config.yaml` (par défaut un mot du `SHARE_TEST_URL` existant)
- Timeout généreux pour Algolia indexing (jusqu'à 15s)

## References

- `mobile/.maestro/02_share_intake.yaml` (pattern de share + wait)
- `mobile/.maestro/03_inbox_visibility.yaml` (pattern de scroll + assertion)
- `mobile/.maestro/config.yaml`
- `mobile/app/(tabs)/search.tsx`
- task-85 (implémentation lexical search)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mobile/.maestro/06_search.yaml existe et tourne sans erreur en local
- [ ] #2 Couvre tap tab Search + input + résultat affiché + tap résultat → detail screen
- [ ] #3 Setup data documenté dans le flow (user pré-loadé OU partage inline)
- [ ] #4 Pas de hardcoding du terme de recherche : utilise une env var ou une valeur dérivée du SHARE_TEST_URL
<!-- AC:END -->
