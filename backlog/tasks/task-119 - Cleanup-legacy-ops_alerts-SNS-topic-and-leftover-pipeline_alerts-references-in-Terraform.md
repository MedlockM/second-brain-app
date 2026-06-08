---
id: task-119
title: Cleanup legacy ops_alerts SNS topic and leftover pipeline_alerts references in Terraform
status: Done
assignee: []
created_date: '2026-06-08 18:00'
labels:
  - cleanup
  - infrastructure
dependencies: []
priority: low
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Le 2026-06-08, en préparant le `terraform apply` initial du V1 launch plan (Phase 3), on a identifié du code legacy dans `infrastructure/terraform/` qu'il faut nettoyer.

### Identifié lors du plan initial

1. **`monitoring.tf` contenait un doublon** de `aws_cloudwatch_log_group.lambda_api` qui faisait planter `terraform init` (déjà déclaré dans `lambda_api.tf:23`). Suppression appliquée directement (fix bloquant).

2. **`dynamodb_quota_tables.tf` contenait un second bloc `terraform { required_providers }`** qui dupliquait `main.tf:6`. Suppression appliquée directement (fix bloquant).

3. **37 blocs `attribute { name = "X" type = "Y" }`** sur une seule ligne dans les fichiers `dynamodb_*.tf`, syntaxe HCL invalide. Reformatés automatiquement.

### Reste à nettoyer (pas bloquant pour le `apply` mais code mort)

#### A. SNS topic `ops_alerts` (legacy ECS) dans `monitoring.tf`

Le topic SNS `aws_sns_topic.ops_alerts` est annoté `# legacy -- retained for backward compatibility` mais **aucune alarme ne publie dessus** depuis la migration Lambda (task-106). Le seul abonné est `aws_sns_topic_subscription.ops_email`. Le topic moderne `pipeline_alerts` (dans `pipeline_alerts.tf`) reçoit toutes les alarmes actives.

**Action** : supprimer `aws_sns_topic.ops_alerts` + `aws_sns_topic_subscription.ops_email` de `monitoring.tf`. Vérifier avec `grep -rn "aws_sns_topic.ops_alerts\|ops_alerts" infrastructure/` qu'aucun autre fichier n'y réfère.

#### B. Commentaire trompeur dans `monitoring.tf`

> "The primary alerting is now in pipeline_alerts.tf (pipeline_alerts topic)."

Le fichier `monitoring.tf` ne contient plus que le `aws_cloudwatch_log_group.lambda_workers` après la suppression du log_group dupliqué et du topic legacy. À ce stade, le fichier devient trivial. Soit on **renomme** `monitoring.tf` en quelque chose comme `cloudwatch_log_groups.tf`, soit on **fusionne** son contenu dans `lambda_workers.tf` ou `lambda_api.tf` qui sont les emplacements naturels des log groups.

#### C. `s3_bucket_lifecycle_configuration.archives` warning provider

`terraform validate` remonte un warning :

> "No attribute specified when one (and only one) of [rule[0].filter, rule[0].prefix] is required. This will be an error in a future version of the provider."

Source : `archiving.tf:15`. Il faut ajouter explicitement `filter {}` (vide pour matcher tout le bucket) ou un `prefix = ""` dans la rule. Pas bloquant aujourd'hui mais le sera à la prochaine majeure du provider AWS.

#### D. Variable `enable_alarms` documentation

On a introduit `var.enable_alarms` (default `false`) dans `main.tf` pour conditionner les 42 alarmes + 2 SNS topics. À documenter dans `infrastructure/terraform/README.md` :
- Quand l'activer (staging/prod uniquement)
- Comment changer (`enable_alarms = true` dans le `terraform.tfvars` correspondant)
- Coût impact (~$4.20/mois × env quand activé)

## Goal

Code Terraform propre sans legacy ECS, sans warnings provider, structure de fichiers cohérente, doc à jour.

## Out of scope

- Migration vers un nouveau provider AWS major
- Réorganisation complète de l'arborescence Terraform
- Ajout de nouvelles alarmes
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `aws_sns_topic.ops_alerts` et `aws_sns_topic_subscription.ops_email` supprimés de `monitoring.tf`
- [ ] #2 Vérifié par grep qu'aucun autre fichier ne référence `ops_alerts` (à part le commentaire de migration)
- [ ] #3 Contenu de `monitoring.tf` simplifié ou fusionné dans un fichier plus pertinent (proposition documentation)
- [ ] #4 Warning `s3_bucket_lifecycle_configuration.archives` résolu (ajout explicite de `filter {}` ou `prefix`)
- [ ] #5 `infrastructure/terraform/README.md` documente la variable `enable_alarms` (when/how/cost)
- [ ] #6 `terraform validate` passe sans warning
- [ ] #7 `terraform plan` ne montre **aucun changement de ressource** par rapport à l'état actuel après premier apply (refactor zero-diff)
<!-- AC:END -->
