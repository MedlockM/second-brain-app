---
id: task-72
title: Benchmark LLM pour la génération d'artefacts
status: Done
assignee: []
created_date: '2026-03-29 21:01'
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
- [ ] #1 Benchmark documenté couvrant au moins 5 fournisseurs LLM
- [ ] #2 Comparaison par type d'artefact (summary_short, summary_detailed, flashcards, notes)
- [ ] #3 Critères : qualité, coût, latence, contexte, fiabilité JSON
- [ ] #4 Recommandation par type d'artefact avec justification
- [ ] #5 Estimation du coût mensuel par persona
<!-- AC:END -->
