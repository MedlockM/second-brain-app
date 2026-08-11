---
id: task-237
title: >-
  Implement Terraform multi-environment isolation per validated benchmark
  (task-221)
status: To Do
assignee: []
created_date: '2026-08-09 16:57'
updated_date: '2026-08-11 13:21'
labels:
  - infra
  - terraform
  - release
  - implementation
dependencies:
  - task-221
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apply the Terraform multi-environment isolation strategy validated in task-221 so dev, staging and prod can coexist safely. Read the owner's Decision from `docs/research/task-221-terraform-multi-env-isolation/README.md` (Owner Validation section) before planning the implementation — it specifies the chosen isolation architecture, the physical resource naming convention, the ECR handling, and the migration approach for the existing unsuffixed dev resources.

Scope covers: restructuring `infrastructure/terraform/` per the validated architecture, migrating the existing dev resources without data loss (per the strategy described in the benchmark), suffixing physical resource names, removing hardcoded resource-name fallbacks in application code where the benchmark identifies them as a cross-environment risk, and updating the GitHub Actions deployment workflow and ECR image tagging to be environment-aware. Exact scope depends on the benchmark's Decision field.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Terraform is restructured to match the isolation architecture validated in docs/research/task-221-terraform-multi-env-isolation/README.md (Decision field)
- [ ] #2 All physical AWS resource names are environment-suffixed with no collisions possible between dev, staging and prod
- [ ] #3 The existing dev resources and their data are migrated per the benchmark's migration strategy with no data loss
- [ ] #4 A staging plan/apply is proven not to modify or destroy any dev resource, per the benchmark's proof approach
- [ ] #5 The GitHub Actions deploy-lambda workflow and ECR image tagging are environment-aware per the benchmark's specification
- [ ] #6 Hardcoded resource-name fallbacks identified in the benchmark as a cross-environment risk are removed from application code

- [ ] #7 A staging environment is created and its runtime secret is provisioned, with enable_alarms set per the approved decision
- [ ] #8 The staging API health endpoint returns a healthy response over its own endpoint, independent of dev
- [ ] #9 infrastructure/terraform/README.md documents the per-environment plan and apply procedure, replacing the unsafe historical guidance of copying terraform.tfvars with a different environment value
- [ ] #10 No apply is run without a reviewed plan proving the absence of unintended destruction on dev
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-10 — task-225 (duplicate of this task, same task-221 dependency and same scope) was archived in favour of this task. Its four unique acceptance criteria were merged here: effective staging environment creation + runtime secret, staging health endpoint independent of dev, infrastructure/terraform/README.md procedure rewrite, and the no-apply-without-reviewed-plan safety gate. Scope note carried over from task-225: this task delivers the staging environment and unblocks Phase 9 of docs/V1_LAUNCH_PLAN.md; creating the production environment stays out of scope (Phase 10, after staging is validated).

2026-08-10 — Dispatch interrompu : le run `dispatch_backlog.sh --max-dispatch 3` a été tué par un 403 Bedrock (`BedrockOfficeHoursDenyPolicy`, deny explicite sur `us.anthropic.claude-opus-5`), pas par une fin normale. Travail partiel sauvegardé sur la branche `recover/task-237`, deux commits au-dessus de bcf0cfa :

- `9691224 refactor(terraform): split into per-environment roots over a shared module` — 33 fichiers, +1791/-741 : `infrastructure/terraform/` éclaté en `modules/platform/` (dynamodb, sqs, s3, lambda_api, lambda_workers, iam, secrets, alarms, dashboard, runtime_env, locals, variables) + `shared/` (ecr) ; ajout de `scripts/dynamo_copy_env.py` et `scripts/tf_plan_guard.sh`.
- `1e4342e wip(task-237)` — 41 fichiers, +201/-282 : suppression des fallbacks de noms de ressources hardcodés dans les endpoints, services, utils et workers (critère #6).

Aucun `terraform plan` n'a été lancé, rien n'est relu ni testé, aucun critère d'acceptation vérifié, l'environnement staging n'existe pas. À la reprise : repartir de cette branche plutôt que de zéro, mais tout revalider — en particulier les critères #3 (migration des données dev sans perte), #4 (preuve qu'un plan staging ne détruit rien en dev) et #10 (aucun apply sans plan relu).
<!-- SECTION:NOTES:END -->
