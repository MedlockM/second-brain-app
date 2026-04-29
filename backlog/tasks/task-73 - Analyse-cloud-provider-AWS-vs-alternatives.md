---
id: task-73
title: Analyse cloud provider (AWS vs alternatives)
status: To Do
assignee: []
created_date: '2026-03-29 21:02'
labels:
  - infrastructure
  - benchmark
  - v1
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le projet utilise AWS (DynamoDB, SQS, S3, ECS/Fargate) avec LocalStack pour le dev local. L'utilisateur est novice en déploiement et se demande si une alternative plus simple et moins chère serait adaptée.

## Analyse exhaustive requise (recherche internet requise)

### Fournisseurs à évaluer
- **AWS** (actuel) : DynamoDB, SQS, S3, ECS/Fargate, Lambda
- **GCP** : Firestore, Cloud Tasks/Pub-Sub, Cloud Storage, Cloud Run
- **Alternatives PaaS** : Railway, Fly.io, Render, Supabase, Vercel (serverless)
- **Hybrides** : Cloudflare Workers + R2 + D1, Hetzner + managed services
- Tout autre provider pertinent

### Critères de comparaison
- **Coût mensuel** pour le profil d'usage estimé (faible trafic au lancement)
- **Simplicité de déploiement** (DX, temps de setup, courbe d'apprentissage)
- **Dev experience** : peut-on développer et tester localement sans équivalent LocalStack ?
- **Services nécessaires** : queue de messages, base NoSQL/SQL, stockage objets, compute async (workers), cron/scheduler
- **Scaling** : peut-on scaler de 0 à modéré sans surcoût ?
- **Vendor lock-in** : facilité de migration si besoin
- **Maturité / fiabilité** du provider

### Livrable
- Tableau comparatif
- Recommandation argumentée
- Plan de migration si changement de provider (ou confirmation de rester sur AWS)
- Impact sur le workflow de développement local
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Au moins 5 providers analysés avec leurs services équivalents
- [ ] #2 Coût mensuel estimé pour chaque provider (profil lancement faible trafic)
- [ ] #3 Analyse de la DX (dev local, déploiement, debugging)
- [ ] #4 Recommandation argumentée avec plan de migration si changement
- [ ] #5 Impact sur le workflow dev local documenté
<!-- AC:END -->

## Implementation Notes

**2026-04-29 (task-research agent):**

Research completed in **initial mode** (first pass). Comprehensive cloud provider analysis produced at:
- `/docs/research/task-73-cloud-provider-analysis/README.md`

**Providers analyzed (8 total):**
1. AWS (current stack: DynamoDB, SQS, S3, ECS/Fargate, Lambda)
2. Google Cloud Platform (Firestore, Cloud Run, Cloud Storage, Cloud Tasks)
3. Railway (usage-based PaaS with Postgres)
4. Fly.io (global container platform)
5. Render (managed PaaS with background workers)
6. Supabase (Postgres-first with Edge Functions)
7. Cloudflare (Workers + R2 + D1)
8. Hetzner Cloud (self-managed VPS with object storage)

**Key findings:**
- **Recommendation: Stay on AWS** — Best local dev experience (LocalStack), generous free tier, already implemented, future-proof for scaling
- **Alternative recommendation: Railway** — If simplicity and predictable pricing are paramount over local dev workflow; requires 6-9 weeks migration effort
- **Not recommended: Cloudflare Workers** — 30-second execution limit incompatible with media processing workers (transcription, summarization)
- **Not recommended: Hetzner self-managed** — Too much operational burden for novice deployer

**Cost comparison (launch phase, <100 users, <1000 jobs/month):**
- AWS: $15-50/month (after free tier)
- Railway: $20-40/month (flat, predictable)
- GCP: $20-60/month
- Fly.io: $30-60/month
- Render: $40-80/month
- Supabase: $50-100/month

**Local development impact:**
- AWS + LocalStack: ⭐⭐⭐⭐⭐ (offline testing, full service emulation)
- Railway/Fly.io/Render: ⭐⭐ (deploy to test, no local equivalent)
- Supabase: ⭐⭐⭐⭐ (CLI + Docker for local stack)
- GCP: ⭐⭐⭐ (partial emulators, Cloud Run requires deployment)

**Vendor lock-in:**
- DynamoDB → Postgres: Moderate migration effort (2-4 weeks schema redesign)
- S3 → S3-compatible storage: Very low (API is standardized)
- SQS → Redis/Postgres queues: Low to moderate (1-2 weeks refactor)
- Docker containers: Portable across all platforms

**Migration plan included** for Railway (6-9 weeks) and GCP (7-9 weeks) if owner chooses to switch.

**The recommendation awaits owner validation.** Set `owner_decision` in the benchmark README to `ok`, `abandoned`, `redo`, or `more` based on review.
