---
id: task-192
title: >-
  Detect transcript language across all sources and translate to user's reading
  language if needed (GPT-5-nano per task-189)
status: Done
assignee: []
created_date: '2026-06-11 10:01'
updated_date: '2026-06-14 19:31'
labels:
  - feature
  - ingestion
  - mobile
dependencies:
  - task-189
  - task-190
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mettre en place, dans le pipeline d'ingestion, une étape **universelle** (indépendante de la source) de détection de la langue du transcript généré, puis de traduction vers la langue de lecture de l'user (cf. task-190) quand elle ne correspond pas. La traduction utilise le modèle validé par l'owner dans `docs/research/task-189-transcript-translation-benchmark/README.md` (section Owner Validation → Decision : **GPT-5-nano**, via la stack OpenAI existante, pas de chunking pour V1).

## Principe : détection, pas priorisation par source

Contrairement à une approche « récupérer le transcript déjà dans la bonne langue piste par piste » (abandonnée — elle ne couvre ni l'audio/Deepgram, ni l'OCR d'image, ni les articles qui n'ont qu'un seul transcript), cette tâche traite **n'importe quel transcript généré, quelle que soit la source** :

- YouTube, TikTok, Instagram (sous-titres / captions)
- Audio file & Podcast (transcription Deepgram)
- Article / page web (texte extrait)
- Image (texte OCR)
- Document PDF/DOCX/PPTX (texte extrait)
- X (Twitter), texte partagé, et toute source future

Le point d'insertion est **unique et commun** à toutes les sources : juste après que le transcript est disponible et **avant** la génération des artefacts (summary_short, summary_detailed, notes, flashcards, quiz). Aucun worker source-spécifique ne doit dupliquer cette logique.

## Comportement attendu

1. **Détection de langue** du transcript généré :
   - Si la source expose déjà un tag de langue fiable (ex : langue de la piste de sous-titres YouTube, `language` Deepgram, `<podcast:transcript language>`), l'utiliser comme indice.
   - Sinon (ou pour confirmer), détecter la langue à partir du texte. Choisir une méthode et la justifier dans l'implémentation : détection locale légère (`langdetect`/`lingua`) gratuite, OU détection intégrée au prompt GPT-5-nano (« détecte d'abord la langue, traduis seulement si différente de {target} »). La détection locale évite un appel LLM quand aucune traduction n'est nécessaire — c'est le chemin le plus fréquent (user qui consomme du contenu dans sa langue).
   - Persister la langue détectée sur le transcript (`detected_language`, ISO 639-1).

2. **Décision de traduction** : comparer `detected_language` à la `reading_language` de l'user (lue depuis le job context / user lookup, cf. task-190).
   - Si elles correspondent → aucune traduction, le transcript original passe tel quel aux artefacts.
   - Si elles diffèrent **et** la cible fait partie des 11 langues V1 du benchmark task-189 → déclencher la traduction.

3. **Traduction GPT-5-nano** :
   - System prompt préservant le registre oral, les paragraphes, les timestamps et les speaker labels (cf. section « System Prompt » du README task-189).
   - Pas de chunking pour V1 (fenêtre 400k tokens largement suffisante).
   - Persister le transcript traduit dans la même structure que les transcripts originaux, avec `is_translated = true`, `translated_from = <detected_language>`, `target_language = <reading_language>`.

4. **Artefacts downstream** : summary/notes/flashcards/quiz consomment le transcript traduit comme s'il était natif. Leur logique `language` existante (`_build_*_prompt`) doit recevoir la `target_language`, pas la langue source.

5. **Idempotence** : clé de cache `(transcript_id, target_language)` — ne jamais re-traduire un couple déjà produit.

6. **Observabilité** : log structuré incluant source, `detected_language`, `target_language`, méthode de détection, modèle, nb tokens, durée, coût estimé, et `translated` (bool).

7. **Gestion d'erreur** : en cas d'échec de détection ou de traduction (rate limit, API down, content policy), fallback documenté — retry avec backoff, puis à défaut passer le transcript original aux artefacts en signalant clairement dans l'UI mobile que le contenu n'a pas pu être traduit.

## Architecture

Suivre l'architecture worker/Lambda retenue dans le projet (Lambda si task-105/106 mergées, sinon worker). Le composant doit s'intégrer comme une étape pipeline commune déclenchée pour **toutes** les sources, et non comme un worker branché manuellement source par source.

## UI mobile

Afficher un badge « Translated from XX » sur les artefacts issus d'un transcript traduit, pour transparence.

## Docs

Mettre à jour `docs/INGESTION_WORKERS_PROVIDERS.md` pour documenter cette étape commune de détection+traduction placée entre la récupération du transcript et la génération des artefacts, et préciser qu'elle s'applique à toutes les sources.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Étape de détection de langue commune à TOUTES les sources (YouTube, TikTok, Instagram, audio, podcast, article, image OCR, document, X, texte partagé), placée après la récupération du transcript et avant la génération des artefacts
- [ ] #2 Langue détectée persistée sur le transcript (`detected_language`, ISO 639-1) ; méthode de détection choisie et justifiée (locale légère vs prompt LLM)
- [ ] #3 Traduction déclenchée uniquement si `detected_language` != `reading_language` de l'user (task-190) et cible dans les 11 langues V1 du benchmark task-189
- [ ] #4 Traduction réalisée avec le modèle validé dans le README task-189 (GPT-5-nano), system prompt préservant registre oral / paragraphes / timestamps / speaker labels, sans chunking pour V1
- [ ] #5 Transcript traduit persisté avec `is_translated=true`, `translated_from`, `target_language`, dans la même structure que les transcripts originaux
- [ ] #6 Workers summary_short/summary_detailed/notes/flashcards/quiz reçoivent la target_language correcte (pas la langue source)
- [ ] #7 Idempotence : pas de re-traduction si le couple (transcript_id, target_language) existe déjà
- [ ] #8 Logs structurés : source, detected_language, target_language, méthode de détection, modèle, tokens, durée, coût estimé, translated(bool)
- [ ] #9 Gestion d'erreur documentée : retry+backoff puis fallback transcript original avec badge UI signalant l'échec de traduction

- [ ] #10 Badge UI mobile 'Translated from XX' sur les artefacts issus d'un transcript traduit
- [ ] #11 Tests : (a) transcript EN + user FR -> détection EN, traduction FR, summary FR ; (b) transcript FR + user FR -> aucune traduction, aucun appel LLM de traduction ; (c) source audio Deepgram et source image OCR couvertes par la même étape
- [ ] #12 docs/INGESTION_WORKERS_PROVIDERS.md mis à jour avec l'étape commune détection+traduction et son périmètre multi-sources
<!-- AC:END -->
