---
id: task-65
title: Benchmark coûts unitaires + proposition pricing V1
status: Done
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

### Research Output (2026-04-30, REDO 3rd pass - YouTube + document parsing + rate limiting)

**Mode:** REDO 3rd pass - Owner requested:
1. Replace OCR section with document parsing (LlamaParse + Unstructured fallback strategy from task-90)
2. Integrate YouTube 95% free captions + 5% transcription fallback
3. Include concrete rate limiting numbers for implementation
4. Recalculate all totals

**Deliverable:** `/home/marc-medlock/Documents/Perso/dev/media-summarizer-project/docs/research/task-65-pricing-v1-benchmark/README.md` (updated)

**Integrated decisions:**
1. **Document parsing strategy (task-90):**
   - LlamaParse free tier: 10k credits/month (basic mode 1 credit/page = $0.00125/page)
   - Fallback Unstructured API: 15k pages free, then $0.03/page pay-as-you-go
   - Recommendation: Use LlamaParse Starter ($50/month for 40k credits) after free tiers exhausted
   - Cost per document (3 pages, post free-tier): **0.00324 EUR** (LlamaParse basic) vs **0.0774 EUR** (Unstructured PAYG)
   - Free tier impact: **0 EUR** for first months (10k + 15k pages combined)

2. **YouTube video cost model:**
   - **95% videos**: free captions/ASR retrieval → **0 EUR transcription**
   - **5% videos**: fallback transcription at 0.003€/min
   - YouTube 25 min video cost: **0.00895 EUR** (vs 0.0802 EUR in previous benchmark, -89% reduction)

3. **Rate limiting chiffré:**
   - **Fournisseurs:** Deepgram 10 concurrent, OpenAI Tier 1 (500 RPM / 200k TPM), LlamaParse ~100 RPM
   - **Applicatif Standard 5€:** 5 audio/day, 20 articles/day, 5 documents/day, API 10 req/min
   - **Applicatif Premium 10€:** 10 audio/day, 30 articles/day, 10 documents/day, API 20 req/min
   - **Global plateforme:** 8 concurrent transcriptions, 400 concurrent LLM, 80 concurrent parsing
   - **Anti-abus free trial:** alert à 5 EUR/user, blocage à 8 EUR/user

**Updated calculations:**
- Free trial month average cost: **2.99 EUR → 2.12 EUR/user** (-29% thanks to YouTube free + doc parsing free tier)
- Recommended 5 EUR Standard quota: **15 audio/video + 15 YouTube + 20 articles + 10 documents** (60 total), cost **3.25 EUR**, margin **35.0%**
- 10 EUR Premium seuils (>=20% margin):
  - Audio-heavy: **75 medias** (45 audio + 15 YouTube + 11 articles + 4 docs)
  - Balanced: **110 medias** (33 audio + 33 YouTube + 33 articles + 11 docs)
  - Text-heavy: **145 medias** (22 audio + 29 YouTube + 72 articles + 22 docs)
- Premium fair-use guard: **40 audio + 30 YouTube + 50 articles + 20 docs** (140 total), cost **7.73 EUR**, margin **22.7%**

**Key improvements vs REDO 2:**
1. YouTube captions gratuites reduce free trial cost by 29% and make Premium much more attractive for YouTube-heavy users
2. Document parsing free tier (25k pages combined) eliminates parsing cost for first months
3. LlamaParse basic mode 23% cheaper than OCR hypothesis after free tiers exhausted
4. Rate limiting concrete numbers provided for backend implementation
5. All calculations redone with new cost assumptions

**Recommendation:** Launch with free trial + 5 EUR Standard; add 10 EUR Premium with fair-use wording and cost monitoring. Premium is now very attractive for YouTube/text-heavy users.

**Status:** Awaiting owner validation. Recommendation is marked `owner_decision: pending` in the README front-matter.

**Next steps:** Owner reviews the README and updates `owner_decision` with one of: `ok`, `abandoned`, `redo`, or `more`.

### Research Output (2026-05-13, REDO 5th pass - Algolia free + 3-tier persona structure)

**Mode:** REDO 5th pass - Owner requested (2026-05-13):
1. Remove search cost entirely (Typesense Cloud 43 €/mo replaced by Algolia Build free tier, task-53.1 validated 2026-05-12).
2. Add 3-tier structure based on 3 personas: Text-Only (0 transcription), Mix (300 min), Audio-Heavy (900 min).

**Deliverable:** `/home/marc-medlock/Documents/Perso/dev/media-summarizer-project/docs/research/task-65-pricing-v1-benchmark/README.md` (updated) + `compute.py` (updated)

**Integrated decisions:**
1. **Recherche lexicale: Algolia Build free tier** (task-53.1 validated 2026-05-12):
   - 1 GB index max, 1M records, 10k searches/month — free permanently.
   - 100u × 200 docs × 4 chunks = 80k records × 9 KB = 720 MB < 1 GB ✓
   - Headroom: ~130 users before 1 GB cap → migration to Algolia Grow (~116 €/mo Y2) or self-hosted Typesense/Meilisearch (~20-50 €/mo).
   - Cost Y1 @100u: **0 €** (vs 43 €/mo Typesense Cloud in 4th pass).

2. **Infra cost revised**:
   - Total fixed @100u phase launch: **19,0 €/mois** (EC2 10,55 + EBS 2,06 + Route53 0,43 + Algolia 0 + misc 1 + variable 5).
   - Cost per user @100u: **0,190 €/user** (vs 0,575 €/user in 4th pass with Typesense).
   - **−43 €/mo fixed cost** = **−75% infra fixed**.

3. **3-tier persona structure**:

| Tier | Prix TTC | Persona | Quota audio | Revenu net | Coût @100u | Marge |
|------|----------|---------|-------------|------------|------------|-------|
| **Text-Only** | **3 €/mois** | Lecteur (articles/newsletters/documents/YouTube), **0 min transcription** | **0 min** (blocked backend) | 2,125 € | 1,33 € (150 articles + 30 docs + 20 YouTube) | **+37,2 %** |
| **Mix** | **5 €/mois** | Étudiant/pro équilibré (mix articles + podcasts modérés) | **300 min** (5h) | 3,542 € | 1,86 € (300 min + 100 articles + 15 docs + 10 YouTube) | **+47,4 %** |
| **Audio-Heavy** | **9 €/mois** | Passionné podcast (écoute quotidienne) | **900 min** (15h) | 6,375 € | 3,63 € (900 min + 50 articles + 10 docs + 20 YouTube) | **+43,1 %** |

**Key improvements vs 4th pass:**
1. **Suppression Typesense Cloud** → Algolia Build free: **−43 €/mois** = **+20 pts de marge** sur Mix 5€ @100u (47,4% vs 27,0%).
2. **Tier Text-Only 3€** = différenciation majeure: seul acteur à proposer un tier pure-text à 3€ avec marge excellente (+37,2%). Persona sous-servi (lecteurs compulsifs qui ne consomment pas de podcasts).
3. **Parcours d'upgrade naturel**: Text-Only 3€ → Mix 5€ (+2€) → Audio-Heavy 9€ (+4€).
4. **Pricing transparent mensuel**: pas d'engagement annuel obligatoire, contrairement aux concurrents (Readwise, Recall, Otter annuels pour prix attractifs).
5. **Tous les prix ≤ 9€/mois** (contrainte owner respectée).

**Positionnement vs concurrents:**
- **Text-Only 3€**: 70% moins cher que Readwise Full (9,99 $/mois annuel) pour persona similaire (lecteur).
- **Mix 5€**: comparable à Readwise Lite (5,59 $/mois annuel) mais ajoute 300 min audio que Readwise n'a pas. Positionnement unique.
- **Audio-Heavy 9€**: aligné sur Snipd Premium (6,99 $) à quota identique (900 min) mais ajoute articles/docs illimités. 47% moins cher qu'Otter Pro mensuel (16,99 $).

**Migration Algolia Build → Grow (@130+ users Y2):**
- Headroom Build free: ~130 users heavy-podcast (200 docs/user × 36 KB × 4 chunks = 720 MB < 1 GB).
- Au-delà 130u: passage Algolia Grow (~116 €/mo @1000u Y2, overages) ou migration vers self-hosted Typesense/Meilisearch (~20-50 €/mo).
- À Y2 @1000u avec Algolia Grow, marge Mix 5€ reste >40% (infra 0,127 €/user).

**Recommendation:** Launch avec 3 tiers (Text-Only 3€, Mix 5€, Audio-Heavy 9€) + mois gratuit tier Mix (300 min audio + text illimité, hard cap 300 articles + 50 docs). Algolia Build free couvre 100% de la phase launch Y1 @100u sans frais. Monitorer index size quotidiennement pour préparer migration Y2.

**Status:** Awaiting owner validation. Recommendation is marked `owner_decision: pending` in the README front-matter.

**Next steps:** Owner reviews the README and updates `owner_decision` with one of: `ok`, `abandoned`, `redo`, or `more`.
