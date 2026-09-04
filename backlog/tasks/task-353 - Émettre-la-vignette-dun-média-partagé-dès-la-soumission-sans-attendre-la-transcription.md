---
id: task-353
title: >-
  Émettre la vignette d'un média partagé dès la soumission, sans attendre la
  transcription
status: To Do
assignee: []
created_date: '2026-09-04 13:37'
labels:
  - backend
  - ingestion
  - feature
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qui est remonté

Un beta testeur TestFlight (Feedback-Id `AMJ0KSQjGg3YQ0EeAOegfk8`, build `1.0.0 (6)`) constate qu'après avoir partagé puis enregistré un média, la tuile reste sur l'icône générique (trombone) dans « Ajouts récents » et n'affiche l'image qu'une fois la transcription terminée. Sa demande : que l'image apparaisse dès que possible.

## Pourquoi c'est une tâche backend

La tuile mobile ne peut rien afficher plus tôt par elle-même : elle lit `image_url` / `media_image` renvoyés par le serveur, et `InboxItem` (`mobile/src/contexts/InboxContext.tsx:12-37`) ne porte aucun URI de fichier local — seulement `url`, `sourcePlatform`, `state`. Les deux voies possibles étaient (a) plomber l'URI local du fichier mis en scène pour l'upload jusqu'à l'item pending côté mobile, ou (b) faire émettre l'image plus tôt par le backend.

**L'owner a tranché la voie (b) : c'est le backend qui émet l'image plus tôt.** Motif : cela bénéficie à tous les clients au lieu de dupliquer un cache d'URI temporaires dans le mobile, et cela évite d'avoir à gérer la durée de vie d'un fichier que iOS peut purger. Ne pas re-poser cette question ni implémenter la voie mobile.

## Le travail

`media_image` existe déjà sur le job (`media_summarizer/core/models/processing_job.py:75`) et transite par `media_submission.py` (`thumbnail_url` / `media_image` / `episode_image`) ; l'orchestrateur d'ingestion le renseigne à `orchestrators.py:398` (`media_image=cover_url`). Le point à établir est **quand** cette valeur devient lisible par le client par rapport au reste du pipeline : aujourd'hui l'image n'est visible qu'en fin de traitement, alors que pour un média partagé depuis le téléphone la source de l'image est disponible dès la soumission.

Établir d'abord le fait, en lisant le code et les items réels sur les tables `-dev`, puis rendre l'image lisible dès que la source en dispose, sans attendre la transcription. La forme exacte (écriture anticipée du champ au moment de la soumission, ou exposition plus tôt dans la réponse de lecture) est à l'appréciation de l'implémenteur une fois le pipeline établi — mais le résultat doit valoir pour un item encore en cours de traitement, pas seulement pour un item terminé.

Rappel de cadrage (`AGENTS.md`, « Nothing is deployed yet ») : rien n'est en production, aucun contrat à préserver. Pas de champ de compatibilité, pas de double écriture, pas de fenêtre de dépréciation — l'ancien chemin est remplacé, pas doublé.

## Note pour l'owner (pas un AC)

La vérification qui compte est visuelle et vous revient : après merge et push de `main`, partager une photo vers l'app, enregistrer, et regarder si la tuile « Ajouts récents » porte l'image avant la fin de la transcription. L'implémenteur ne peut pas la faire depuis son worktree — son code n'est pas déployé pendant qu'il travaille.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le champ portant la vignette est renseigné et lisible pour un média encore en cours de traitement : un item soumis sur les ressources `-dev` porte sa valeur d'image avant que la transcription soit terminée, vérifié par une lecture directe DynamoDB/AWS CLI
- [ ] #2 Aucun chemin de lecture ne dépend plus de la fin du traitement pour exposer la vignette ; les points d'appel touchés sont tous mis à jour, aucun ancien chemin conservé en parallèle
- [ ] #3 `ruff` et `mypy` passent proprement sur `media_summarizer/`
<!-- AC:END -->
