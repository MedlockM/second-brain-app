---
id: task-72
title: Benchmark LLM pour la génération d'artefacts
status: Done
assignee:
  - Codex
created_date: '2026-03-29 21:01'
updated_date: '2026-04-28 10:24'
labels:
  - benchmark
  - llm
  - v1
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le backend utilise actuellement GPT-4 (OpenAI) pour la génération de résumés et notes. Le choix du LLM optimal doit être déterminé par un benchmark exhaustif, pas par défaut.

## Benchmark exhaustif requis (recherche internet requise)

Comparer les modèles disponibles pour chaque type d'artefact :

### Modèles à évaluer
- **OpenAI** : GPT-4, GPT-4o, GPT-4o-mini, GPT-3.5-turbo
- **Anthropic** : Claude Sonnet, Claude Haiku, Claude Opus
- **Google** : Gemini Pro, Gemini Flash
- **Mistral** : Mistral Large, Mistral Medium, Mistral Small, Codestral
- **Open source** : Llama 3, Mixtral, Qwen, DeepSeek
- Tout autre modèle pertinent découvert par la recherche

### Critères de comparaison par artefact
Pour chaque type d'artefact (summary_short, summary_detailed, flashcards, notes) :
- **Qualité de sortie** : pertinence, fidélité au contenu source, structure
- **Coût par requête** (input + output tokens × prix)
- **Latence** (temps de réponse moyen)
- **Taille de contexte** (supporte-t-il des transcripts longs ?)
- **Fiabilité du format JSON** (pour les flashcards notamment)

### Livrable
- Tableau comparatif avec recommandation par type d'artefact
- Le modèle optimal peut être différent par artefact (ex: modèle léger pour summary_short, modèle puissant pour summary_detailed)
- Estimation du coût mensuel par persona avec le modèle recommandé
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Benchmark documenté couvrant au moins 5 fournisseurs LLM
- [x] #2 Comparaison par type d'artefact (summary_short, summary_detailed, flashcards, notes)
- [x] #3 Critères : qualité, coût, latence, contexte, fiabilité JSON
- [x] #4 Recommandation par type d'artefact avec justification
- [x] #5 Estimation du coût mensuel par persona
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Refresh docs/research/task-72-llm-artifact-benchmark.md after user request: verify current OpenAI pricing/model docs from official OpenAI sources, update OpenAI inventory and blended/request costs, rerun the artifact recommendation matrix as a desk-research quality pass, remove stale caveats about not rerunning quality comparison, update persona/monthly totals and source dates, then review the markdown for consistency. No automated tests are needed because this is a research-document update.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Refreshed docs/research/task-72-llm-artifact-benchmark.md on 2026-04-28 after user request. Updated OpenAI pricing/model inventory from official OpenAI pricing and model docs, added GPT-5.5/GPT-5.4/GPT-5.4 mini/GPT-5.4 nano, recalculated blended and per-artifact costs, replaced stale 'quality pass not rerun' caveats with a documented desk-research comparative pass, and updated recommendations/persona costs/implementation rollout. Verification: git diff --check passed; no automated tests run because this is a research document update.
<!-- SECTION:NOTES:END -->
