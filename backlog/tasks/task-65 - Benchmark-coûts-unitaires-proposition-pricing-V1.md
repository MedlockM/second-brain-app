---
id: task-65
title: Benchmark coûts unitaires + proposition pricing V1
status: In Progress
assignee:
  - Codex
created_date: '2026-03-27 15:50'
updated_date: '2026-04-29 14:30'
labels:
  - product
  - pricing
  - benchmark
  - v1
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le pricing actuel (tiers S/M/L basés sur des minutes de podcast) n'est plus adapté au produit "second brain" multi-média. Il faut repartir de zéro avec une analyse exhaustive.

## Contraintes validées (2026-03-29)
- Prix maximum envisagé : **9€/mois**
- Si tiers multiples : un free tier limité est envisageable
- Si abonnement unique : privilégier un mois d'essai gratuit
- La décision tiers vs abonnement unique est ouverte

## Étapes

### 1. Benchmark des coûts unitaires (recherche internet requise)
- Coût Deepgram par minute de transcription (selon le plan)
- Coût LLM par artefact généré (summary short, summary detailed, flashcards) — tester plusieurs modèles
- Coût OCR par page/image (selon le service choisi)
- Coût S3/DynamoDB/SQS par utilisateur type
- Coût infra (compute, workers) par requête type

### 2. Modélisation des profils utilisateurs
- Persona "étudiant" : X médias/semaine, types de médias, artefacts demandés
- Persona "professionnel veille" : idem
- Persona "power user" : idem
- Coût mensuel par persona

### 3. Proposition pricing
- Option A : Tiers multiples (Free limité / Standard / Premium)
- Option B : Abonnement unique avec essai gratuit
- Option C : Freemium avec limites (X médias/mois gratuits)
- Analyse comparative avec concurrents (Readwise, Snipd, Podcastle, etc.)
- Recommandation argumentée

## Analyse exhaustive requise
Le benchmark doit être exhaustif et basé sur des données réelles (documentation des fournisseurs, pricing pages, etc.). Ne pas se limiter à 2-3 options.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Coûts unitaires documentés pour chaque service (transcription, LLM, OCR, stockage, compute)
- [x] #2 Profils d'utilisation modélisés pour chaque persona avec coût mensuel estimé
- [x] #3 Au moins 3 options de pricing analysées avec avantages/inconvénients

- [x] #4 Comparaison avec les concurrents (Readwise, Snipd, Podcastle, etc.)
- [x] #5 Recommandation argumentée respectant la contrainte de 9€/mois max
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Reprise REDO du benchmark pricing V1 sur `docs/research/task-65-pricing-v1-benchmark/README.md`.

Plan:
1. Relire le contexte projet (`README.md`, contrat API canonique) et les benchmarks ouverts indiquant les choix de modèles par type de média.
2. Identifier précisément les nouveaux modèles LLM retenus pour podcasts/vidéos, articles/liens, PDF/OCR et artefacts.
3. Vérifier les tarifs fournisseurs actuels sur sources officielles lorsque le coût LLM/pricing dépend d'informations externes.
4. Mettre à jour le benchmark task-65 avec les hypothèses de modèles, les coûts unitaires recalculés, les impacts sur quotas/marges et la recommandation, en conservant `owner_decision: pending`.
5. Relire le README modifié pour cohérence et consigner les changements dans la tâche.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Research Output (2026-04-29, REDO refresh with task-72 LLM routing)

**Mode:** REDO refresh - Owner requested recalculation with the newly selected LLM models.

**Deliverable:** `/home/marc-medlock/Documents/Perso/dev/media-summarizer-project/docs/research/task-65-pricing-v1-benchmark/README.md` (updated)

**Owner/task-72 decisions integrated:**
1. Transcription cost base remains **0.0030 EUR/min** of processed audio/video.
2. LLM routing from task-72 owner validation:
   - `summary_short`: `gpt-5-nano-2025-08-07`
   - `summary_detailed`, `flashcards`, `notes`: `gpt-5.4-nano-2026-03-17`
3. V1 artifact cost now includes `notes` in addition to `summary_short`, `summary_detailed`, and `flashcards`.

**Updated calculations:**
- LLM V1 complete cost: **0.0052 EUR/media**.
- Free trial month average cost: **2.99 EUR/user**.
- Recommended 5 EUR Standard quota: **15 audio/video + 50 articles/texts + 10 OCR**, expected cost **3.20 EUR**, margin **36.1%**.
- 10 EUR Premium is **not recommended as true unlimited** without fair-use protections.
- Premium drops below 20% margin around:
  - Audio-heavy: **73 medias/month** (51 audio + 18 articles + 4 OCR)
  - Balanced: **122 medias/month** (49 audio + 61 articles + 12 OCR)
  - Text-heavy: **185 medias/month** (47 audio + 120 articles + 18 OCR)
- Defendable Premium fair-use guard: **45 audio/video + 100 articles + 20 OCR**, cost **7.76 EUR**, margin **22.4%**.

**Recommendation:** Launch with free trial + 5 EUR Standard first; add 10 EUR Premium only with fair-use wording and cost monitoring.

**Status:** Awaiting owner validation. Recommendation is marked `owner_decision: pending` in the README front-matter.

**Next steps:** Owner reviews the README and updates `owner_decision` with one of: `ok`, `abandoned`, `redo`, or `more`.
<!-- SECTION:NOTES:END -->
