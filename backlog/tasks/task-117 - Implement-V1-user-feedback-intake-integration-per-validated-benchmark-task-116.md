---
id: task-117
title: >-
  Implement V1 user feedback intake integration per validated benchmark
  (task-116)
status: To Do
assignee: []
created_date: '2026-06-08 10:52'
labels:
  - feature
  - mobile
  - community
dependencies:
  - task-116
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Tâche d'implémentation appariée au benchmark `task-116`. Le choix de l'outil de feedback intake (Canny, Featurebase, Frill, Sleekplan, etc.) est fait par l'owner via le `Decision` du README de `task-116`. **Ne décide rien dans cette tâche** : lis `docs/research/task-116-feedback-intake/README.md` et applique strictement la décision.

## Goal

Intégrer l'outil retenu dans l'app V1 de manière à ce que les users puissent :
1. Accéder au feedback board en ≤ 3 taps depuis l'app mobile
2. Voter / soumettre des idées sans friction (idéalement avec SSO depuis le compte Second Brain Labs déjà connecté)
3. Voir la roadmap publique

L'implémenteur produira en suivant ce que le README dit :
- Configuration du compte sur l'outil retenu (sous-domaine `feedback.<domaine>`, branding Second Brain Labs, statuts customs)
- Implémentation d'un éventuel SSO depuis le backend (endpoint `GET /api/feedback/sso-token` qui retourne un JWT signé acceptable par l'outil retenu) — uniquement si l'outil le supporte et que c'est dans la décision
- Ajout d'un point d'entrée mobile : icône "Feedback" dans le menu Profil ou Settings, qui ouvre le board (deep link, web view, ou navigateur externe selon ce que dit la décision)
- Documentation interne dans `docs/community/feedback-channels.md` : où va le feedback, qui répond, fréquence de review

## Constraints

- Lire **strictement** `docs/research/task-116-feedback-intake/README.md` et appliquer la décision sans la remettre en question
- Si la décision est `Discord` (option communautaire), prévoir l'intégration avec le serveur Discord créé par `task-118` (= cette autre tâche du backlog)
- Respecter le design system mobile "Amber Clarity" pour le bouton/écran "Feedback"
- Pas de hard-codage de l'URL du board — la mettre en `EXPO_PUBLIC_FEEDBACK_URL` dans `.env.example` + `mobile/.env`
- Si SSO : signer avec une nouvelle env var `FEEDBACK_SSO_SECRET`, à ajouter dans `.env.example` + Terraform `secret_payload`

## Acceptance Criteria
<!-- AC:BEGIN -->
Voir AC ci-dessous.

## References

- `docs/research/task-116-feedback-intake/README.md` (à créer par task-116, à lire en priorité)
- `docs/V1_LAUNCH_PLAN.md`
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` — design system mobile
- `task-118` (Discord server) — éventuelle complémentarité
<!-- SECTION:DESCRIPTION:END -->

- [ ] #1 #1 L'outil retenu dans la décision de task-116 est configuré (compte créé, sous-domaine `feedback.<domaine>` ou domaine dédié, branding Second Brain Labs)
- [ ] #2 #2 Un point d'entrée "Feedback" est ajouté dans l'app mobile (Profile ou Settings), conforme au design system Amber Clarity
- [ ] #3 #3 Le tap sur "Feedback" ouvre le board (deep link, web view, ou navigateur externe selon la décision) sans demander à l'user de re-saisir des credentials s'il est déjà connecté (SSO si supporté)
- [ ] #4 #4 Si SSO implémenté : endpoint `GET /api/feedback/sso-token` créé, documenté, testé, et utilisé côté mobile
- [ ] #5 #5 `EXPO_PUBLIC_FEEDBACK_URL` ajouté dans `.env.example` + `mobile/app.config.ts` extra config
- [ ] #6 #6 Si SSO : `FEEDBACK_SSO_SECRET` ajouté dans `.env.example` + Terraform `secret_payload`
- [ ] #7 #7 Roadmap publique configurée avec au moins 3 statuts visibles (Under review / Planned / Shipped) et 3 idees seedees pour montrer l'UX (peuvent être supprimées plus tard)
- [ ] #8 #8 `docs/community/feedback-channels.md` créé avec : URL du board, qui répond, fréquence de review, lien vers `task-116` README pour le rationale
<!-- AC:END -->
