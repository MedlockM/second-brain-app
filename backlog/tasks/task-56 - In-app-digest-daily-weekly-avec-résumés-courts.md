---
id: task-56
title: In-app digest (daily + weekly) avec résumés courts
status: Done
assignee: []
created_date: '2026-03-16 22:28'
updated_date: '2026-03-29 21:18'
labels:
  - feature
  - digest
  - v1
dependencies:
  - task-64
  - task-68
  - task-69
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Remplace l'ancien concept de "weekly newsletter par email". Le digest est une fonctionnalité **in-app** (pas d'email) consultable à tout moment dans un écran/onglet dédié.

## Spécification V1

### Daily Digest
- Résumé court (Summary Short) de chaque média ajouté dans la journée
- Consultable à tout moment dans l'app

### Weekly Digest
- Résumé court (Summary Short) de chaque média ajouté dans la semaine
- Notification push à la publication
- Consultable à tout moment dans l'app

### Vue par défaut
- Summary Short pré-sélectionné pour chaque média
- L'utilisateur peut switcher vers Brut ou Flashcards (onglets classiques de la vue média)

### Activation
- Active par défaut pour tous les utilisateurs
- Désactivable dans les settings

### Génération intelligente des Summary Short
- Les résumés courts doivent être pré-générés de manière étalée (pas de burst de requêtes LLM au moment de la publication du digest)
- Utiliser le système d'idempotence des artefacts : si un Summary Short existe déjà (généré on-demand ou par le spaced rep), ne pas re-générer
- Planifier la génération via cron/scheduler en amont de la publication

## Aspects techniques

- Modèle DynamoDB pour le digest (user_id, digest_type [daily|weekly], period_key, media_items, status)
- Cron/scheduler pour la génération (pré-génération Summary Short + assemblage digest)
- Endpoint API : GET /api/digest/daily, GET /api/digest/weekly
- Endpoint API : PATCH /api/user/settings (toggle digest on/off)
- Push notification pour le weekly digest
- Pas d'envoi d'email — tout est in-app
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Daily digest consultable in-app avec Summary Short par média ajouté dans la journée
- [ ] #2 Weekly digest consultable in-app avec Summary Short par média ajouté dans la semaine
- [ ] #3 Notification push envoyée à la publication du weekly digest
- [ ] #4 Vue par défaut : Summary Short pré-sélectionné, switchable vers Brut ou Flashcards
- [ ] #5 Digest actif par défaut, désactivable par l'utilisateur dans les settings
- [ ] #6 Génération des Summary Short étalée dans le temps (pas de burst), avec réutilisation des artefacts existants via idempotence
- [ ] #7 Aucun email envoyé — fonctionnalité 100% in-app
<!-- AC:END -->
