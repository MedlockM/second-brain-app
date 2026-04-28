---
id: task-69
title: Onglet Brut — transcript/texte extrait/OCR brut accessible via API
status: To Do
assignee: []
created_date: '2026-03-29 21:01'
updated_date: '2026-03-29 21:18'
labels:
  - feature
  - artifact
  - v1
dependencies:
  - task-33
  - task-60
  - task-70
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

L'onglet "Brut" dans l'app affiche le contenu source brut du média, correctement mis en forme. Le contenu dépend du type de média :
- **Podcasts / audio / vidéo** : transcript reçu de Deepgram
- **Articles web** : texte extrait par trafilatura
- **Tweets / posts LinkedIn** : texte brut du post
- **Images / PDF scannés** : résultat de l'OCR

## Spécification V1

Le contenu brut est déjà stocké en S3 (transcription_s3_key pour audio/video, transcript pour articles/posts). L'enjeu est de l'exposer proprement via l'API.

## Aspects techniques

- Endpoint API : le contenu brut doit être récupérable via un endpoint canonique
- Options : soit un artifact_type "raw_content" dans le système d'artefacts existant, soit un champ dédié dans le media status endpoint
- Le contenu doit être correctement formaté (paragraphes, ponctuation, mise en forme markdown si pertinent)
- Pour les transcripts Deepgram : formatter le JSON de transcription en texte lisible (paragraphes, speaker labels si disponibles)

## Pas d'implémentation frontend ici (Stitch)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le contenu brut est accessible via l'API pour chaque type de média
- [ ] #2 Transcripts Deepgram formatés en texte lisible (paragraphes)
- [ ] #3 Texte d'articles web correctement formaté
- [ ] #4 Texte de posts sociaux (tweets, LinkedIn) accessible
- [ ] #5 Résultat OCR accessible (dépend de l'implémentation du connecteur OCR)
- [ ] #6 Format de sortie cohérent quel que soit le type de média source
<!-- AC:END -->
