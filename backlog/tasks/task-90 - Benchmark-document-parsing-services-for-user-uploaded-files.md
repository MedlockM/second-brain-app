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

## Implementation Notes

**2026-04-29** (research agent, initial mode):

Research completed and delivered at `/home/marc-medlock/Documents/Perso/dev/media-summarizer-project/docs/research/task-90-document-parser-benchmark/README.md`.

**Summary of findings:**

Evaluated 8 document parsing solutions (5 SaaS APIs + 3 self-hosted/open source):
- **SaaS**: LlamaParse, Unstructured.io, AWS Textract, Google Document AI, Azure Document Intelligence
- **Self-hosted**: Marker, Docling, PyMuPDF

**Recommendation**: LlamaParse (SaaS) as primary parser + PyMuPDF (self-hosted) as fallback for simple PDFs.

**Rationale**:
- Cost-effective: Free tier (10k credits/month) sufficient for MVP; Starter tier ($50/month) covers growth phase
- Best accuracy: 95.67% on complex documents (per Marker benchmark comparing LlamaParse vs competitors)
- Format coverage: 130+ formats including all user upload scenarios (PDF, DOCX, XLSX, PPTX, images)
- Zero infrastructure: Fully managed SaaS removes deployment overhead for solo dev
- Markdown output: Native markdown generation ideal for LLM pipeline downstream
- Risk mitigation: PyMuPDF fallback prevents vendor lock-in and handles simple PDFs at zero cost

**Cost projection (1,000 docs/month, avg 2 pages/doc)**:
- Phase 1 (MVP): $0 (free tier)
- Phase 2 (growth): $50/month (Starter tier)
- Phase 3 (scale, >10k docs/month): Consider migrating to Unstructured.io flat $0.03/page rate

**Comparison matrix includes**:
- Detailed cost analysis per solution with projections
- Format support by solution (PDF, Office, images, specialized formats)
- Feature comparison (OCR, table extraction, layout detection, metadata, chunking, markdown output)
- Quality benchmarks (Marker's public benchmark: LlamaParse vs Marker vs Docling vs Mathpix)
- Latency data where publicly available

**Trade-offs accepted**:
- Vendor lock-in risk (mitigated by PyMuPDF fallback and abstracted parser interface)
- Credit limits at scale (clear upgrade path to Unstructured.io if volume exceeds LlamaParse economics)
- Table extraction on very complex tables may require manual verification

**Alternative paths documented**:
- Zero budget: PyMuPDF + Unstructured.io open source (self-host)
- High volume (>10k docs/month): Unstructured.io SaaS
- Offline/air-gapped: Marker or Docling (self-host)
- Cloud-native: AWS/GCP/Azure Document AI + PyMuPDF fallback

All sources cited with URLs to official documentation and verified repositories. Benchmark data from Marker's public GitHub benchmark (https://github.com/VikParuchuri/marker).

**Recommendation awaits owner validation**. Front-matter set to `owner_decision: pending`.
