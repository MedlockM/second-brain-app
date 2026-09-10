---
id: task-395
title: >-
  Traduire les artefacts et l'aperçu sur changement de langue au lieu de les
  régénérer
status: To Do
assignee: []
created_date: '2026-09-10 12:37'
labels:
  - backend
  - artifacts
  - cost
  - i18n
dependencies:
  - task-394
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Un changement de langue de lecture ne traduit rien : il régénère. La langue est portée par `parameters` et entre donc dans `build_artifact_id` (*"parameters carries the reading language, so two reading languages are two different ids"*), si bien qu'une seconde langue produit une nouvelle entrée générée **depuis le transcript entier**. Pour un `review_blurb` de quelques lignes, le coût est dominé par les jetons d'entrée : on relit tout le texte pour réécrire un paragraphe.

Le mécanisme voulu existe déjà pour le texte complet et sert de modèle : `transcript_translation` détecte la langue localement (gratuit), n'appelle le modèle que si la langue diffère, et **persiste la traduction sous une clé déterministe** *"keyed on `(transcript_s3_key, target_language)` so a couple is never re-translated"*.

## Décision du propriétaire

Sur changement de langue de lecture, **on traduit l'existant au lieu de le régénérer** : le texte complet (déjà en place) et les artefacts, aperçu compris.

Deux exigences de coût :

- **Déclenchement à l'ouverture du média concerné**, pas en masse sur toute la bibliothèque au moment où la langue change.
- **Persistance**, de sorte qu'une réouverture du même média ne relance aucune traduction.

## Périmètre

Artefacts de scope média, `review_blurb` inclus. Le comportement attendu à l'ouverture d'un média dont les artefacts existent dans une autre langue : ils sont traduits une fois, conservés, et servis tels quels ensuite. Un artefact qui n'existe dans aucune langue n'est pas concerné — il relève de la génération normale.

## Point d'attention pour l'implémenteur

Les entrées d'artefact sont append-only : *"once it reaches ready it is never modified again — there is no staleness flag, no expiry, no automatic regeneration"*. Une traduction est donc une nouvelle entrée, pas une mutation de l'entrée d'origine, et l'original reste servi aux comptes qui lisent dans sa langue.

À vérifier avant d'écrire du code : `trigger_review_blurb_generation` passe délibérément `reading_language=None` pour éviter d'être envoyé dans le pipeline de traduction, parce qu'il n'a aucun retry derrière lui et qu'une `ArtifactTranscriptNotReadyError` y serait définitive. Ce raisonnement porte sur la génération à l'ingestion et ne doit pas être cassé par la traduction à l'ouverture, qui, elle, a un déclencheur qui peut se répéter.

## Notes au propriétaire (hors critères d'acceptation)

Vérification manuelle après déploiement : changer la langue de lecture, constater qu'aucune traduction ne part immédiatement, ouvrir un média disposant d'un résumé et d'un aperçu, les voir traduits, puis rouvrir le même média et vérifier côté coûts fournisseur qu'aucun nouvel appel n'a lieu.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 À l'ouverture d'un média dont les artefacts existent dans une autre langue que la langue de lecture courante, ces artefacts — review_blurb compris — sont traduits à partir de l'existant et non régénérés depuis le transcript.
- [ ] #2 Aucune traduction d'artefact n'est déclenchée par le changement de langue lui-même : le déclencheur est l'ouverture du média concerné.
- [ ] #3 Une traduction produite est persistée : rouvrir le même média dans la même langue ne déclenche aucun nouvel appel au fournisseur.
- [ ] #4 Une traduction est une nouvelle entrée d'artefact ; l'entrée d'origine n'est pas modifiée et reste servie dans sa langue.
- [ ] #5 ruff et mypy passent sans erreur sur les modules touchés.
- [ ] #6 Une vérification directe contre le DynamoDB -dev réel, documentée dans les notes d'implémentation, montre l'entrée traduite persistée à côté de l'originale.
<!-- AC:END -->
