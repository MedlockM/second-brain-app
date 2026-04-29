---
id: task-70
title: Benchmark + implémentation OCR pour images et PDF scannés
status: To Do
assignee: []
created_date: '2026-03-29 21:01'
updated_date: '2026-04-28 16:04'
labels:
  - ingestion
  - ocr
  - benchmark
  - v1
dependencies:
  - task-20
  - task-21
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Nouveau connecteur d'ingestion pour les images et PDF scannés partagés par l'utilisateur. Le texte extrait par OCR devient le "contenu brut" du média, disponible pour la génération d'artefacts (summary, flashcards).

## Étape 1 : Benchmark exhaustif du service OCR (recherche internet requise)

Comparer de manière exhaustive les solutions OCR disponibles :
- **Cloud APIs** : AWS Textract, Google Cloud Vision, Azure Computer Vision, etc.
- **APIs spécialisées** : Mathpix, ABBYY Cloud OCR, OCR.space, etc.
- **Open source / self-hosted** : Tesseract OCR, PaddleOCR, EasyOCR, Surya, docTR, etc.
- **Solutions multimodales** : GPT-4V, Claude Vision, Gemini Pro Vision (LLM pour OCR)

Pour chaque solution : qualité de reconnaissance (langues, handwriting, tableaux, formules), coût, latence, maintenance, dépendances infra, adéquation aux personas (étudiants = notes manuscrites, pros = documents PDF).

## Étape 2 : Implémentation

- Nouveau worker : `media_summarizer/workers/ocr_worker.py`
- Classification URL : détecter les fichiers image (jpg, png, etc.) et PDF partagés
- Pipeline : image/PDF → OCR → texte extrait stocké comme transcript → disponible pour artefacts
- Intégration dans le pipeline existant via l'architecture hexagonale (nouveau resolver/adapter)

## Contraintes
- Doit supporter les langues principales des personas (français, anglais minimum)
- Doit gérer PDF multi-pages
- Coût par page à intégrer dans l'analyse pricing (task-65)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Benchmark exhaustif documenté avec recommandation argumentée
- [ ] #2 Worker OCR fonctionnel avec le service choisi
- [ ] #3 Images (jpg, png) et PDF scannés supportés
- [ ] #4 Texte extrait stocké comme transcript et disponible pour la génération d'artefacts
- [ ] #5 PDF multi-pages supportés
- [ ] #6 Intégré dans l'architecture hexagonale d'ingestion
- [ ] #7 Coût par page/image documenté pour l'analyse pricing
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dispatch 2026-04-28: Phase benchmark (AC#1) complétée par agent-task-70. Document créé: docs/research/task-70-ocr-benchmark.md (42KB, 15+ solutions évaluées). Recommandation: AWS Textract ($0.0015/page, intégration native AWS, handwriting excellent). Alternative: Google Cloud Vision. Scale: PaddleOCR (self-hosted). L'implémentation worker (AC#2-7) reste à faire. Commit direct sur second-brain-project.
<!-- SECTION:NOTES:END -->
