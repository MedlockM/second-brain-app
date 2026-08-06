---
id: task-221
title: >-
  Benchmark Terraform multi-environment isolation strategies for dev, staging
  and production
status: In Progress
assignee:
  - Codex
created_date: '2026-08-05 17:53'
updated_date: '2026-08-06 00:51'
labels:
  - benchmark
  - infra
  - terraform
  - release
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le provisioning Terraform actuel (`infrastructure/terraform/`) ne permet pas de faire coexister trois environnements. Deux causes cumulées :

1. **State unique** : le backend S3 utilise une seule clé (`infrastructure/terraform.tfstate`). Il n'existe aucune séparation par environnement.
2. **Noms de ressources globaux non suffixés** : la majorité des ~140 ressources créées portent des noms sans discriminant d'environnement (tables `users`, `processing_jobs`, Lambda `media-summarizer-api`, queues SQS sans suffixe, repository ECR partagé). Seul le secret runtime suit le pattern `media-summarizer-runtime-<env>`.

La consigne historique documentée dans `docs/V1_LAUNCH_PLAN.md` (« recopier `terraform.tfvars` avec un autre `environment` ») est **dangereuse en l'état** : un `terraform apply` avec `environment = "staging"` viserait les mêmes noms de ressources physiques que dev et provoquerait des collisions ou des destructions.

Cette tâche bloque la Phase 9 (staging end-to-end) et donc toute la chaîne de release production.

## Objectif du benchmark

Trancher la stratégie d'isolation avant toute modification destructive. Comparer au minimum :

- **Terraform workspaces** (`terraform workspace new staging`) avec interpolation de `terraform.workspace` dans les noms.
- **Répertoires par environnement** (`envs/dev/`, `envs/staging/`, `envs/prod/`) avec un module partagé et des backends distincts.
- **State keys séparées** via `-backend-config` au `init`, sur une base de code unique paramétrée par `var.environment`.
- **Terragrunt** ou équivalent, si le gain justifie la dépendance supplémentaire.

Le benchmark doit également traiter le **problème de migration de l'existant** : les ressources dev actuelles portent des noms non suffixés et contiennent des données réelles. Renommer une table DynamoDB ou une queue SQS dans le HCL provoque un `destroy`/`create` par défaut. Les options (`terraform state mv`, import, conservation d'un alias legacy pour dev uniquement, recréation à froid de dev) doivent être évaluées avec leur risque de perte de données.

## Livrable

`docs/research/task-XX-terraform-multi-env-isolation/README.md` avec `owner_decision: pending`, incluant une recommandation claire et une section Owner Validation. Aucune modification de `infrastructure/terraform/` dans cette tâche — recherche et comparaison uniquement.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The current blocker is documented with evidence: single S3 state key and an inventory of the resource names that would collide across environments
- [ ] #2 At least Terraform workspaces, per-environment directories with a shared module, and separate backend state keys are compared
- [ ] #3 Each option is evaluated for state isolation guarantees, resource naming ergonomics, blast radius, CI/CD integration with the existing deploy-lambda workflow, secret and ECR image handling per environment, cost, and operational complexity
- [ ] #4 A migration strategy for the existing unsuffixed dev resources is specified, including the data-loss risk of each approach and whether dev is renamed in place, state-moved, or recreated
- [ ] #5 The recommendation defines how a staging plan is proven not to modify or destroy any dev resource before any apply is run
- [ ] #6 The environment-awareness requirements for the GitHub Actions deployment workflow and for ECR image tagging are specified
- [ ] #7 The research document contains a clear recommendation and an Owner Validation section with owner_decision: pending
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Établir l’état des lieux depuis le dépôt et l’état Terraform en lecture seule : backend S3, usages de `var.environment`, inventaire des noms physiques non discriminés et surfaces de collision.
2. Rechercher exhaustivement dans les sources officielles Terraform/OpenTofu/Terragrunt/AWS les garanties et limites des workspaces, répertoires avec module partagé, clés de state séparées et Terragrunt.
3. Comparer les options dans une matrice couvrant isolation du state, nommage, blast radius, CI/CD existante, secrets, ECR, coûts et complexité opérationnelle.
4. Concevoir une migration sûre des ressources dev non suffixées, avec risques de perte de données, commandes/state moves/imports envisageables, stratégie de rollback et traitement spécial éventuel de dev legacy.
5. Définir une preuve bloquante qu’un plan staging ne touche aucune ressource dev, ainsi que les exigences d’environnement pour GitHub Actions et le versionnement ECR.
6. Rédiger `docs/research/task-221-terraform-multi-env-isolation/README.md` avec recommandation claire, sources, `owner_decision: pending` et section Owner Validation, sans modifier `infrastructure/terraform/`.
7. Vérifier chaque critère d’acceptation, consigner les validations dans Backlog et laisser le benchmark en attente de la décision owner conformément au lifecycle.
<!-- SECTION:PLAN:END -->
