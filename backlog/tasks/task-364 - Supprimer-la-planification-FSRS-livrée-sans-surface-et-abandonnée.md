---
id: task-364
title: 'Supprimer la planification FSRS, livrée sans surface et abandonnée'
status: To Do
assignee: []
created_date: '2026-09-06 15:40'
labels:
  - backend
  - cleanup
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le fait qui déclenche la tâche

La répétition espacée FSRS (task-63) est livrée côté backend et **n'a jamais eu de surface**. Aucune ligne de `mobile/` n'appelle `/review/due`, `/review/{card_id}/result` ni `/user/settings` : dans l'app, « flashcards » n'existe que comme type d'artefact affiché dans le détail d'un média. Les cartes sont planifiées, leurs échéances passent, et personne n'est jamais interrogé.

**Décision owner du 2026-09-06 : abandon de la répétition espacée.** On supprime, on ne branche pas.

## Périmètre exact

Quatre modules disparaissent en entier :
- `media_summarizer/api/endpoints/review.py`
- `media_summarizer/core/services/fsrs_service.py`
- `media_summarizer/utils/review_db.py`
- `media_summarizer/core/models/review_schedule.py`

Un seul point d'accroche ailleurs dans le code : `media_summarizer/workers/artifact_generator/worker.py` — l'import ligne 36 (`fsrs_service, quota_enforcer`, dont seul `quota_enforcer` survit) et l'appel à `initialize_cards_for_flashcards` vers la ligne 495, exécuté après la génération des flashcards.

Reste à retirer : le montage du router dans `media_summarizer/api/main.py` (~ligne 153), la dépendance `fsrs>=1.0.0` de `pyproject.toml` (~ligne 28) et son override mypy (~ligne 153), le fichier terraform `infrastructure/terraform/modules/platform/dynamodb_review_tables.tf` et les variables correspondantes de `runtime_env.tf`.

## Ce qui ne bouge pas — à lire avant de supprimer

**L'artefact flashcards reste au produit.** Le générateur `media_summarizer/workers/artifact_generator/generators/flashcards.py`, l'enum `FLASHCARDS` de `media_artifact.py` et `media_contracts.py`, la clé de prompt `flashcards:...:prompt-v4`, l'entrée `flashcards_model` de `pricing_config_service.py`, la tuile de l'onglet IA et les ~25 clés i18n des 11 langues sont **hors périmètre**. Les fiches de store (`docs/store-listing/`) vendent les flashcards et ne doivent pas être touchées.

Seule la *planification* des cartes meurt. Les flashcards continuent d'être générées et consultables.

## Attention au nom de l'endpoint

`GET`/`PATCH /user/settings` vit dans `review.py` et ne porte **que** des réglages FSRS (`spaced_rep_enabled`, `review_hour`, `review_frequency`, `max_items_per_session`). L'endpoint disparaît donc entièrement malgré son nom générique. Aucun client ne l'appelle : mobile n'y touche pas.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Pas de dépréciation, pas de conservation « au cas où », pas de migration de données. La table DynamoDB des cartes est supprimée en terraform, pas vidée ni renommée. Rien n'est en circulation qu'on ne puisse réémettre.

## Note pour l'owner (pas un AC)

Le `terraform apply` qui détruit réellement la table se joue au push sur `main`, longtemps après la fin de l'agent. La tâche ne peut prouver que la validité de la configuration.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Les quatre modules FSRS n'existent plus dans le dépôt : api/endpoints/review.py, core/services/fsrs_service.py, utils/review_db.py, core/models/review_schedule.py
- [ ] #2 workers/artifact_generator/worker.py ne référence plus fsrs_service : l'appel à initialize_cards_for_flashcards est retiré et l'import ne conserve que quota_enforcer
- [ ] #3 api/main.py ne monte plus le router review : plus aucune route /review ni /user/settings n'est exposée par l'application
- [ ] #4 pyproject.toml ne déclare plus la dépendance fsrs ni son override mypy, et 'uv sync' aboutit sans elle
- [ ] #5 Le fichier infrastructure/terraform/modules/platform/dynamodb_review_tables.tf est supprimé, les variables correspondantes de runtime_env.tf sont retirées, et 'terraform validate' passe
- [ ] #6 Un grep insensible à la casse sur 'fsrs', 'spaced_rep' et 'review_schedule' dans media_summarizer/ et infrastructure/ ne retourne plus aucune occurrence
- [ ] #7 La génération de l'artefact flashcards est intacte : generators/flashcards.py, l'enum FLASHCARDS de media_artifact.py et media_contracts.py, la clé de prompt et flashcards_model de pricing_config_service.py sont inchangés
- [ ] #8 Aucun fichier de mobile/ ni de docs/store-listing/ n'est modifié par cette tâche
- [ ] #9 ruff et mypy passent sur media_summarizer/
<!-- AC:END -->
