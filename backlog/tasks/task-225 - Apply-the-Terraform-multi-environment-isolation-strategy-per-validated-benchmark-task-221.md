---
id: task-225
title: >-
  Apply the Terraform multi-environment isolation strategy per validated
  benchmark (task-221)
status: To Do
assignee: []
created_date: '2026-08-05 17:55'
labels:
  - infra
  - terraform
  - release
dependencies:
  - task-221
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Tâche d'implémentation découlant du benchmark task-221 (isolation Terraform dev/staging/prod).

## Source de vérité

L'implémentation **doit suivre la décision finale de l'owner** documentée dans le front-matter et la section *Owner Validation* de :

`docs/research/task-221-terraform-multi-env-isolation/README.md`

L'implémenteur lit le champ `Decision` du README pour connaître :

- La stratégie d'isolation du state retenue (workspaces, répertoires par environnement, backend keys séparées, ou autre).
- La convention de nommage des ressources par environnement.
- La stratégie de migration des ressources dev existantes, dont le traitement du risque de perte de données.
- Le pattern d'environment-awareness attendu du workflow de déploiement et du tagging ECR.
- L'ordre de réalisation et la procédure de vérification avant tout `apply`.

**Ne pas pré-supposer une stratégie dans cette tâche** : la recommandation initiale du benchmark peut différer de la décision finale de l'owner.

## Portée

Cette tâche livre la refonte du provisioning et la **création effective de l'environnement staging**, isolé de dev. Elle débloque la Phase 9 de `docs/V1_LAUNCH_PLAN.md`. La création de l'environnement production reste hors périmètre : elle intervient en Phase 10 une fois staging validé.

Cette tâche touche du provisioning contenant des données réelles en dev. Aucun `apply` ne doit être lancé sans qu'un `plan` ait été relu et prouve l'absence de destruction non intentionnelle.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The implementation reads and follows the owner's final Decision in the task-221 research document
- [ ] #2 Terraform state is isolated per environment according to the approved strategy
- [ ] #3 Every resource that must coexist across environments carries an environment discriminator, with no remaining globally-named collision
- [ ] #4 A staging plan is shown to create only new resources and to modify or destroy nothing in dev, with the plan output recorded as evidence
- [ ] #5 The existing dev environment survives the migration with its data intact, or is recreated per the approved decision with the data loss explicitly accepted in the task notes
- [ ] #6 The GitHub Actions deployment workflow targets an explicit environment and cannot deploy to the wrong one by default
- [ ] #7 ECR image tagging distinguishes environments or is explicitly justified as shared
- [ ] #8 A staging environment is created and its runtime secret is provisioned, with enable_alarms set per the approved decision
- [ ] #9 The staging API health endpoint returns a healthy response over its own endpoint, independent of dev
- [ ] #10 infrastructure/terraform/README.md documents the per-environment plan and apply procedure, replacing the unsafe historical guidance of copying terraform.tfvars with a different environment value
<!-- AC:END -->
