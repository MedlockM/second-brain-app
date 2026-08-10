---
id: task-237
title: >-
  Implement Terraform multi-environment isolation per validated benchmark
  (task-221)
status: To Do
assignee: []
created_date: '2026-08-09 16:57'
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
<!-- AC:END -->
