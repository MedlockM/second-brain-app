---
id: task-73
title: Analyse cloud provider (AWS vs alternatives)
status: Done
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
