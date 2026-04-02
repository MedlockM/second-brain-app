---
id: task-65
title: Benchmark coûts unitaires + proposition pricing V1
status: To Do
assignee: []
created_date: '2026-03-27 15:50'
updated_date: '2026-03-29 21:00'
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
