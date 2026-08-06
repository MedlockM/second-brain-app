---
id: task-62
title: Ingestion de newsletters par email
status: To Do
assignee: []
created_date: '2026-03-24 19:43'
updated_date: '2026-08-06 01:26'
labels:
  - ingestion
  - second-brain
  - newsletter
  - email
dependencies: []
priority: low
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Permettre à l'utilisateur d'ingérer des newsletters reçues par email dans le pipeline de traitement existant (transcription/summarization).

Cas d'usage typique : newsletters comme TLDR, Morning Brew, The Batch, etc. qui n'exposent pas de flux RSS officiel et sont uniquement disponibles par email.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 L'utilisateur peut ingérer le contenu d'une newsletter email dans son second brain
- [ ] #2 Fonctionne indépendamment de la plateforme d'envoi (Mailchimp, Substack, envoi direct, etc.)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-06 : réouverte comme fonctionnalité future et laissée volontairement hors exécution automatique via `dispatchable: false`. L'ancien prototype SES/SNS a été retiré de la V1 dans `task-236`; l'implémentation future devra repartir d'un périmètre et d'une architecture validés.
<!-- SECTION:NOTES:END -->
