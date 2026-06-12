---
id: task-189
title: >-
  Benchmark LLM/translation services for transcript translation to user's
  preferred language
status: To Do
assignee: []
created_date: '2026-06-11 10:00'
labels:
  - benchmark
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Recherche exhaustive des solutions de traduction de transcripts (typiquement plusieurs milliers de tokens, parfois 10k+) vers la langue de lecture préférée de l'user, à utiliser en fallback quand le transcript récupéré à l'ingestion (YouTube subs, Podcasting 2.0, TikTok subs, Deepgram, etc.) est dans une autre langue.

Contexte : l'app va prochainement demander à l'user sa langue de lecture préférée à l'onboarding. Le pipeline d'ingestion essaiera d'abord de récupérer un transcript déjà dans cette langue (sous-titres natifs, transcripts Podcasting 2.0 multilingues, etc.), mais quand ce n'est pas possible, on traduit le transcript récupéré avant de l'envoyer aux workers d'artefacts (summary, flashcards, quiz).

L'analyse doit couvrir les dimensions suivantes :

1. **Coût** — pricing par 1M tokens input/output (pour LLM) ou par caractère (pour services dédiés type DeepL, Google Translate, AWS Translate, Azure Translator). Projection pour 1000 transcripts/mois (taille moyenne 5k tokens).
2. **Couverture linguistique** — au minimum FR/EN/ES/DE/IT/PT/NL/JA/ZH/AR/HI. Indiquer toute paire de langues non supportée.
3. **Qualité** — uniquement si benchmarks publics, papers, ou comparatifs sourcés existent (ne pas inventer de scores). Comparer notamment les LLM généralistes (Claude, GPT, Gemini) vs services spécialisés traduction (DeepL, Google Translate v3, AWS Translate, Azure Translator).
4. **Préservation de la structure** — capacité à conserver la ponctuation, les paragraphes, les timestamps si présents, le style oral/parlé d'un transcript (vs traduction de texte formel).
5. **Latence** — uniquement si données sourcées existent. Important : un transcript de 5k tokens doit pouvoir être traduit en < 30s pour ne pas bloquer le pipeline d'ingestion.
6. **Limites de contexte** — taille max d'input par appel ; stratégie de chunking si transcript dépasse la fenêtre.
7. **Réutilisation du stack existant** — comparer le coût/qualité d'utiliser le LLM provider déjà retenu pour les summaries/flashcards (cf. task-72) vs un service dédié traduction. Trade-off entre simplicité opérationnelle (un seul provider) et coût/qualité.

Livrable : `docs/research/task-189-transcript-translation-benchmark/README.md` avec tableau comparatif et recommandation finale (provider + modèle + stratégie de chunking + langues supportées V1).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tableau comparatif d'au moins 5 solutions (mix LLM généralistes et services dédiés traduction)
- [ ] #2 Analyse coût détaillée par solution avec projection pour 1000 transcripts/mois (5k tokens en moyenne)
- [ ] #3 Couverture linguistique exhaustive par solution avec au minimum FR/EN/ES/DE/IT/PT/NL/JA/ZH/AR/HI
- [ ] #4 Analyse de la qualité de traduction sur du contenu de type transcript (oral, conversationnel) avec sources vérifiables
- [ ] #5 Latence et limites de contexte documentées par solution avec stratégie de chunking recommandée
- [ ] #6 Comparaison explicite réutilisation du LLM stack existant (task-72) vs service dédié traduction
- [ ] #7 Recommandation finale argumentée avec trade-offs explicites + langues supportées V1
<!-- AC:END -->
