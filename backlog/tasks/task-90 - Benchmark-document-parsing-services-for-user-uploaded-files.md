---
id: task-90
title: Benchmark document parsing services for user-uploaded files
status: To Do
assignee: []
created_date: '2026-04-29 17:14'
updated_date: '2026-04-29 17:17'
labels:
  - benchmark
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Recherche exhaustive des solutions de parsing de fichiers disponibles sur le marché (API SaaS et self-hosted). L'analyse doit couvrir les dimensions suivantes :

1. **Coût** — pricing API (par page, par requête, par Go) OU coût infra si self-hosted (RAM, CPU, stockage)
2. **Palette de formats supportés** — PDF, XLSX, DOCX, PPTX, CSV, HTML, images (OCR intégré ?), ePub, etc. Indiquer clairement quels formats sont supportés nativement vs via conversion
3. **Fonctionnalités** — OCR intégré, extraction de tableaux, détection de layout/colonnes, extraction de métadonnées, support des images embarquées, chunking natif, markdown output, etc.
4. **Qualité de parsing** — uniquement si des benchmarks publics, papers, ou comparatifs sourcés existent (ne pas inventer de scores)
5. **Latence** — uniquement si des données sourcées existent (benchmarks publics, documentation officielle)

Contexte : l'application permet aux users d'uploader des fichiers (documents, présentations, spreadsheets) qui seront ensuite résumés et transformés en artefacts (flashcards, notes, quiz). Le parser doit extraire le texte structuré de manière fiable pour alimenter le pipeline LLM en aval.

Livrable : `docs/research/task-90-document-parser-benchmark/README.md` avec tableau comparatif et recommandation finale.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tableau comparatif d'au moins 5 solutions (mix API et self-hosted)
- [ ] #2 Analyse coût détaillée par solution avec projection pour 1000 docs/mois
- [ ] #3 Liste exhaustive des formats supportés par solution
- [ ] #4 Analyse des fonctionnalités par solution (OCR, extraction tableaux, layout detection, metadata, chunking, etc.)
- [ ] #5 Qualité et latence documentées uniquement avec sources vérifiables

- [ ] #6 Recommandation finale argumentée avec trade-offs explicites
<!-- AC:END -->
