---
id: task-169
title: Add Maestro 06_search.yaml to cover Algolia lexical search flow
status: In Progress
assignee:
  - Codex
created_date: '2026-06-10 05:58'
updated_date: '2026-08-09 20:13'
labels:
  - phase-5
  - mobile
  - release
  - tooling
  - e2e
dependencies:
  - task-161
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
- [ ] #1 mobile/.maestro/06_search.yaml existe et s'exécute sur les jobs iOS et Android CI
- [x] #2 Le flow couvre l'ouverture de Search, la saisie, l'affichage d'au moins un résultat et l'ouverture du détail média
- [x] #3 Le jeu de données préchargé et la variable SEARCH_TEST_TERM sont documentés dans le flow et le workflow CI
- [x] #4 Le terme de recherche n'est pas hardcodé dans le flow
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Ajouter un identifiant d'accessibilité stable au premier résultat de recherche. 2. Créer 06_search.yaml en réutilisant le login factorisé et SEARCH_TEST_TERM. 3. Injecter la donnée de test dans les jobs CI. 4. Valider sur iOS et Android CI.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Ajout de mobile/.maestro/06_search.yaml et des testID search-input/search-result-card. Le flow réutilise le login, injecte SEARCH_TEST_TERM, attend un résultat puis ouvre le détail média.

2026-08-09 — Fixture persistante provisionnée sur AWS dev : article Commonplace book arrivé ready_for_artifacts et recherche Algolia 'commonplace' vérifiée avec 1 résultat. Identifiants et terme stockés dans les secrets GitHub Actions. L'AC #1 attend les runs CI de la version commitée.
<!-- SECTION:NOTES:END -->
