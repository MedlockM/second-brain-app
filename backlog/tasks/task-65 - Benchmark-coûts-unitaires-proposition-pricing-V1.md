---
id: task-65
title: Benchmark coûts unitaires + proposition pricing V1
status: To Do
assignee: []
created_date: '2026-03-27 15:50'
updated_date: '2026-04-21 21:52'
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
- [ ] #1 Coûts unitaires documentés pour chaque service (transcription, LLM, OCR, stockage, compute)
- [ ] #2 Profils d'utilisation modélisés pour chaque persona avec coût mensuel estimé
- [ ] #3 Au moins 3 options de pricing analysées avec avantages/inconvénients

- [ ] #4 Comparaison avec les concurrents (Readwise, Snipd, Podcastle, etc.)
- [ ] #5 Recommandation argumentée respectant la contrainte de 9€/mois max
<!-- AC:END -->

## Implementation Notes

### Research Output (2026-04-29, REDO)

**Mode:** REDO - Owner rejected previous benchmark with specific feedback on pricing strategy.

**Deliverable:** `/home/marc-medlock/Documents/Perso/dev/media-summarizer-project/docs/research/task-65-pricing-v1-benchmark/README.md` (updated)

**Owner's requirements integrated:**
1. Free month with no quotas → Calculated average cost per user: **2.82€/month** (based on realistic usage distribution: 50% casual, 35% moderate, 15% intensive)
2. Tier 5€ with 30% margin → Quota recommendation: **15 podcasts/videos + 40 articles + 8 OCR items** (63 total medias/month) → Actual margin: **41.6%** ✓
3. Tier 10€ theoretically unlimited → Profitability analysis shows **>20% margin maintained** up to:
   - **Audio-heavy users** (70% podcasts): 70 total medias = 49 podcasts + 18 articles + 3 OCR
   - **Balanced users** (40% podcasts): 125 total medias = 50 podcasts + 62 articles + 13 OCR
   - **Text-heavy users** (25% podcasts): 200 total medias = 50 podcasts + 130 articles + 20 OCR
4. Transcription cost base: **0.0030€/min** as specified by owner

**Key differences from previous analysis:**
- Used owner's transcription cost (0.0030€/min) instead of previous 0.0045€/min → 33% cost reduction on audio/video processing
- Focused on precise quota calculations for 30% margin target (5€ tier) rather than general profitability ranges
- Detailed breakeven analysis for 10€ tier by user profile (audio-heavy, balanced, text-heavy) to identify unprofitability thresholds
- Provided specific media count limits (not just general recommendations) for each tier
- Calculated exact free trial month cost (2.82€ average) with user distribution assumptions

**Recommendation:** 
- **5€ Standard tier:** 15 podcasts + 40 articles + 8 OCR (41.6% margin)
- **10€ Premium tier:** Soft limit at 150 medias/month to maintain >20% margin for realistic intensive usage
- **Free trial:** 1 month, recommend limiting to 30 medias OR requiring credit card to reduce cost risk (avg 2.82€/user)

**Status:** Awaiting owner validation. Recommendation is marked `owner_decision: pending` in the README front-matter.

**Next steps:** Owner will review the README and update `owner_decision` field with one of: `ok`, `abandoned`, `redo`, or `more`.
