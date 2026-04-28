---
id: task-17
title: >-
  Adapt per-user duplicate-submission guard to media-key model (from
  user_episode_submissions pattern)
status: Done
assignee:
  - '@codex'
created_date: '2026-02-23 22:46'
updated_date: '2026-02-23 23:19'
labels: []
dependencies:
  - task-15
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Adapt the existing per-user duplicate-submission protection pattern (`user_episode_submissions`) to the new URL/media-key world, preserving useful behavior while decoupling from podcast GUID semantics.

Context:
- `media_summarizer/utils/user_episode_submissions.py` implements useful safeguards (block duplicates when completed or permanently failed, allow retry when transient failure).
- New roadmap uses canonical URL-based `media_key` as identity.

Scope:
- Introduce media-keyed equivalent storage/helper (e.g. `user_media_submissions`) using the same decision semantics:
  - block completed
  - block permanently failed
  - allow retry when retry budget remains
  - block in-progress duplicates
- Define migration/backward-compat strategy for callers still using episode GUID path during transition.
- Add tests covering all state transitions and retry semantics.
- Document how this helper integrates with universal URL ingestion and idempotence (`task-15`/`task-10`).

Out of scope:
- Full idempotence table migration (covered by task-15).
- Spotify feature removal itself.

Key files:
- `media_summarizer/utils/user_episode_submissions.py`
- new helper module for media submissions
- calling services that perform user-level dedup checks

Acceptance Criteria:
- A media-keyed per-user dedup helper exists with parity decision rules to current behavior.
- Tests cover completed/failed(including retry exhaustion)/in-progress/not-found paths.
- Migration strategy is explicit (compat path for legacy GUID callers during transition).
- Integration contract is documented for universal URL ingestion flow.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A media-keyed per-user dedup helper exists with parity decision rules to current behavior.
- [ ] #2 Tests cover completed/failed (including retry exhaustion)/in-progress/not-found paths.
- [x] #3 Migration strategy is explicit (compat path for legacy GUID callers during transition).
- [x] #4 Integration contract is documented for universal URL ingestion flow.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Plan d’implémentation (sans ajout de tests, selon consigne utilisateur):
1) Créer un nouveau helper `user_media_submissions` basé sur `media_key` avec la même sémantique de décision que `user_episode_submissions` (completed/permanent failed/in-progress/not-found/retry budget).
2) Introduire une stratégie de migration explicite dans le helper: lecture prioritaire table média, fallback optionnel table legacy GUID, et voie de compatibilité pour les appelants encore GUID.
3) Transformer `user_episode_submissions.py` en adaptateur de compatibilité (wrappers vers le helper média) pour éviter de casser les services existants pendant la transition.
4) Ajouter la configuration infra/env minimale pour la nouvelle table `user_media_submissions` (Terraform + localstack + env example).
5) Documenter le contrat d’intégration avec l’ingestion universelle URL (`media_key`) et la coexistence avec le chemin legacy GUID.
6) Validation rapide par vérification syntaxique/compilation des fichiers touchés (pas de tests).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Décision utilisateur: ne pas rédiger de tests pour ce chantier; implémentation directe.

Implémentation livrée sans tests conformément à la consigne utilisateur explicite ('pas de rédaction de tests').

Nouveau helper media-key: `media_summarizer/utils/user_media_submissions.py` avec parité de décision (completed/permanent failed/retry/in-progress/not-found).

Compatibilité migration: `media_summarizer/utils/user_episode_submissions.py` converti en adaptateur GUID -> media_key (`episode_guid:{guid}`), fallback lecture legacy et dual-write best-effort legacy.

Infra/config ajoutées pour la table `user_media_submissions`: `.env.example`, `infrastructure/terraform/dynamodb_core_tables.tf`, `infrastructure/terraform/localstack/main.tf`.

Contrat d'intégration documenté: `docs/MEDIA_KEY_SUBMISSION_GUARD_CONTRACT.md`.

Validation technique légère effectuée: parsing AST des modules Python modifiés OK.

Task clôturée sur instruction explicite utilisateur.

Critère #2 (tests) laissé non implémenté conformément à la directive utilisateur: "pas de rédaction de tests dans ce projet".

Le reste du périmètre est livré: helper media-key, stratégie de migration compat GUID, infra/env, et contrat d’intégration documenté.
<!-- SECTION:NOTES:END -->
