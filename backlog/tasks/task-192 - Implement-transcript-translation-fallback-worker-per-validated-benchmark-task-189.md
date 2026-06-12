---
id: task-192
title: >-
  Implement transcript translation fallback worker per validated benchmark
  (task-189)
status: To Do
assignee: []
created_date: '2026-06-11 10:01'
labels:
  - feature
  - ingestion
  - mobile
dependencies:
  - task-189
  - task-191
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implémenter le worker de traduction de transcript en suivant la solution retenue par l'owner dans `docs/research/task-189-transcript-translation-benchmark/README.md` (section Owner Validation → Decision).

Contexte : quand le pipeline d'ingestion (cf. task-191) ne trouve pas de transcript déjà dans la langue de lecture de l'user (`language_match = false`), un nouveau worker doit traduire le transcript récupéré vers cette langue avant que les artefacts downstream (summary, flashcards, quiz) soient générés.

L'implémenteur doit :

1. Lire la décision finale de l'owner dans le README du benchmark task-189 (provider, modèle, stratégie de chunking, langues V1).
2. Créer un worker `media_summarizer/workers/translation_worker.py` (ou équivalent selon l'architecture retenue — Lambda si task-105/106 mergées) qui :
   - Reçoit `transcript_id`, `source_language`, `target_language` en input
   - Applique la stratégie de chunking validée si la taille dépasse la fenêtre du provider
   - Appelle le provider de traduction
   - Persiste le transcript traduit dans la même structure que les transcripts originaux (avec un flag `is_translated = true` et `translated_from = <source_language>`)
3. Brancher le worker dans le pipeline : après ingestion, si `language_match = false`, déclencher la traduction avant les workers d'artefacts (summary, flashcards, quiz).
4. Les workers downstream (summary/flashcards/quiz) consomment alors le transcript traduit comme s'il était natif. Leur logique `language` existante (cf. `_build_*_prompt`) doit recevoir la `target_language` et non la `source_language`.
5. **Idempotence** : si un transcript est déjà traduit dans la langue cible, ne pas re-traduire (clé de cache : `(transcript_id, target_language)`).
6. **Observabilité** : log structuré incluant provider, modèle, source/target lang, nb tokens, durée, coût estimé.
7. **Gestion d'erreur** : en cas d'échec de la traduction (rate limit, API down, content policy), fallback documenté — soit retry avec backoff, soit passer le transcript original aux workers d'artefacts en marquant clairement à l'user dans l'UI mobile que le contenu n'a pas pu être traduit.

UI mobile : afficher un badge "Translated from XX" sur les artefacts générés depuis un transcript traduit, pour transparence.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Worker de traduction fonctionnel utilisant le provider validé dans le README task-189
- [ ] #2 Stratégie de chunking implémentée si transcript dépasse la fenêtre de contexte
- [ ] #3 Pipeline branché : ingestion → (si language_match=false) traduction → artefacts
- [ ] #4 Workers summary/flashcards/quiz reçoivent la target_language correcte (pas la source)
- [ ] #5 Idempotence : pas de re-traduction si déjà traduit dans la langue cible
- [ ] #6 Logs structurés avec provider, modèle, langues, tokens, durée, coût estimé
- [ ] #7 Gestion d'erreur documentée (retry + fallback transcript original avec badge UI)
- [ ] #8 Badge UI mobile 'Translated from XX' sur artefacts issus d'un transcript traduit
- [ ] #9 Tests d'intégration : transcript anglais → user FR → summary FR généré correctement
<!-- AC:END -->
