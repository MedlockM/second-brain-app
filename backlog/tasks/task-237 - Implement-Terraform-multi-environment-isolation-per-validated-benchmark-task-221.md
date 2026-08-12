---
id: task-237
title: >-
  Implement Terraform multi-environment isolation per validated benchmark
  (task-221)
status: In Progress
assignee: []
created_date: '2026-08-09 16:57'
updated_date: '2026-08-12 00:15'
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

- [ ] #10 Les 21 erreurs prevent_destroy qui font avorter le plan sur la nouvelle structure sont traitées, et un terraform plan complet aboutit en listant bien les Lambdas API et workers
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-10 — task-225 (duplicate of this task, same task-221 dependency and same scope) was archived in favour of this task. Its four unique acceptance criteria were merged here: effective staging environment creation + runtime secret, staging health endpoint independent of dev, infrastructure/terraform/README.md procedure rewrite, and the no-apply-without-reviewed-plan safety gate. Scope note carried over from task-225: this task delivers the staging environment and unblocks Phase 9 of docs/V1_LAUNCH_PLAN.md; creating the production environment stays out of scope (Phase 10, after staging is validated).

2026-08-10 — Dispatch interrompu : le run `dispatch_backlog.sh --max-dispatch 3` a été tué par un 403 Bedrock (`BedrockOfficeHoursDenyPolicy`, deny explicite sur `us.anthropic.claude-opus-5`), pas par une fin normale. Travail partiel sauvegardé sur la branche `recover/task-237`, deux commits au-dessus de bcf0cfa :

- `9691224 refactor(terraform): split into per-environment roots over a shared module` — 33 fichiers, +1791/-741 : `infrastructure/terraform/` éclaté en `modules/platform/` (dynamodb, sqs, s3, lambda_api, lambda_workers, iam, secrets, alarms, dashboard, runtime_env, locals, variables) + `shared/` (ecr) ; ajout de `scripts/dynamo_copy_env.py` et `scripts/tf_plan_guard.sh`.
- `1e4342e wip(task-237)` — 41 fichiers, +201/-282 : suppression des fallbacks de noms de ressources hardcodés dans les endpoints, services, utils et workers (critère #6).

Aucun `terraform plan` n'a été lancé, rien n'est relu ni testé, aucun critère d'acceptation vérifié, l'environnement staging n'existe pas. À la reprise : repartir de cette branche plutôt que de zéro, mais tout revalider — en particulier les critères #3 (migration des données dev sans perte), #4 (preuve qu'un plan staging ne détruit rien en dev) et #10 (aucun apply sans plan relu).

2026-08-11 — Deuxième tentative, également interrompue (run arrêté avant merge, pas de fin normale). Travail sauvegardé sur `recover/task-237-v2` (commit a9cf70e, 78 fichiers, +2153/-1158). Va plus loin que `recover/task-237` :

- `infrastructure/terraform/envs/{dev,staging,prod}/` : racines par environnement au-dessus de `modules/platform/`
- `envs/dev/moved.tf` généré par `scripts/gen_moved_blocks.py` (migration du state sans destruction)
- `.github/workflows/deploy-lambda-env.yml` : déploiement environment-aware
- `media_summarizer/utils/env.py` + suppression des fallbacks hardcodés dans ~50 fichiers (critère #6)
- `scripts/tf_plan_guard.sh`, `scripts/dynamo_copy_env.py`

Découverte utile consignée par l'agent : un `terraform plan` naïf sur la nouvelle structure avorte sur **21 erreurs `prevent_destroy`** et ne produit donc pas un inventaire complet — les Lambdas API et workers n'apparaissent pas dans le plan. L'agent a simulé le plan post-`state rm` sur une **copie scratch du state dans /tmp**, sans jamais toucher l'état réel. Vérifié : aucun `terraform apply`/`destroy`/`state rm`/`import` n'a été exécuté sur l'infra réelle, et `infrastructure/terraform/` du repo principal est intact (17 fichiers .tf à la racine, inchangés).

Toujours : rien de relu ni testé, aucun critère d'acceptation validé, staging n'existe pas. Les 21 `prevent_destroy` sont le prochain obstacle concret à traiter, et la reprise doit partir de `recover/task-237-v2` (pas de `recover/task-237`, qui est un sous-ensemble).

2026-08-11 — **Autorisation owner : les agents ont tous les droits sur Terraform.** L'owner a explicitement levé les précautions. Le critère #10 (« no apply without a reviewed plan »), que j'avais importé de task-225, est **supprimé** : c'était lui, et non une config de permissions, qui bloquait les agents (le dispatcher lance déjà `claude --dangerously-skip-permissions`).

Consigne pour l'implémenteur : tu es autorisé à exécuter `terraform init/plan/apply`, `terraform state mv/rm/import` et les commandes AWS CLI nécessaires sur les environnements **dev et staging**, sans validation humaine intermédiaire. Va jusqu'à la création effective de staging (critères #7 et #8) et jusqu'à la migration du state dev (#3, #4). Ne demande pas de runbook à la place du travail. Production reste hors périmètre (Phase 10).

Point factuel à connaître, pas une précaution : d'après le benchmark task-218 §1.5, il n'existe aujourd'hui **aucun filet de récupération** sur ce compte — le PITR est désactivé sur `processing_jobs` et `user_folders`, et la Lambda `job-archiver` est un placeholder no-op de 462 octets (144 invocations, 0 objet écrit). Une perte de données dev serait donc définitive. L'activation du PITR fait partie de la Phase 0 de task-239 : la lancer d'abord crée le filet, sans rien ralentir ici.

2026-08-11 — **Le filet de récupération existe désormais** : task-239 est Done et vérifiée côté AWS. Le PITR est `ENABLED` avec 35 jours de fenêtre sur `processing_jobs`, `user_folders`, `user_tags`, `media_artifacts`, `user_media_submissions`, et des backups on-demand + exports S3 datent du 2026-08-11 (`s3://media-summarizer-archives-125313707865-dev/snapshots/task-239-freeze/2026-08-11/`). La mise en garde de la note précédente sur l'absence de filet est donc **périmée** : `state rm`/`import` et les apply sur dev sont désormais couverts par un point de restauration.

**Attention — piège d'interaction avec task-239** : le TTL de `processing_jobs` est maintenant `enabled = false` dans `dynamodb_core_tables.tf`, volontairement. La restructuration ne doit **pas** le réactiver en recopiant une version antérieure du fichier vers `modules/platform/`. Les branches `recover/task-237` et `recover/task-237-v2` ont été créées **avant** ce gel : leur copie de `dynamodb_core_tables.tf` contient encore le TTL actif. Reprendre depuis ces branches en écrasant le fichier ferait repartir la suppression des 16 lignes `completed` sauvées. Vérifier `aws dynamodb describe-time-to-live --table-name processing_jobs` → doit rester `DISABLED` après la migration. Seule la Phase 4 (task-242) peut légitimement le réactiver.

Nouveau critère #10 ajouté pour les 21 `prevent_destroy` : trois runs consécutifs ont buté dessus sans qu'aucun critère ne le couvre, ce qui condamnait chaque agent à le redécouvrir.

## 2026-08-11 — Quatrième tentative, interrompue elle aussi (erreur API « connection lost »)

**Cette tentative est allée beaucoup plus loin que les trois précédentes : elle a réellement appliqué sur AWS.** Travail préservé sur `recover/task-237-v3` (4 commits, 77 fichiers, +2202/-1198) — les trois premiers commits étaient déjà faits par l'agent, le quatrième (`3ae9e48`) est le WIP non commité que le dispatcher a sauvé du worktree avant suppression :

- `8081892` restructuration en racines par environnement au-dessus d'un module partagé
- `743ba6b` `scripts/tf_plan_guard.sh` + `scripts/dynamo_copy_env.py`
- `6589260` « fix three defects found by actually applying the dev migration »
- `3ae9e48` (WIP récupéré) suppression des fallbacks de noms de ressources dans ~42 fichiers — critère #6, **non relu**

**`recover/task-237-v3` remplace `recover/task-237-v2` comme point de reprise.**

### État réel constaté côté AWS (vérifié par le dispatcher, région **eu-west-3**)

- **Rien n'a été détruit.** Les tables historiques non suffixées (`processing_jobs`, `user_folders`, `media_artifacts`, …) existent toujours, intactes.
- Les jeux suffixés `-dev` **et** `-staging` ont été créés (23 tables chacun).
- **La copie des données dev a réussi** : `processing_jobs-dev` = 22 items, `media_artifacts-dev` = 166, `users-dev` = 25 — identiques aux sources. Critère #3 vraisemblablement tenu, à reconfirmer.
- **Piège de vérification à connaître** : `describe-table --query Table.ItemCount` renvoie `0` sur ces tables fraîchement créées ; DynamoDB ne rafraîchit cette métadonnée que toutes les ~6 h. Seul `scan --select COUNT` donne le vrai compte. Ne pas conclure à une perte de données sur `ItemCount`.
- **Piège de région** : le compte a `AWS_REGION=us-east-1` exporté dans l'environnement du shell alors que le projet vit en `eu-west-3`. Un `list-tables` sans `--region` renvoie une liste vide et donne l'illusion que tout a disparu. Toujours passer `--region eu-west-3`.
- Le TTL de `processing_jobs` est resté `DISABLED`, et `processing_jobs-dev` est aussi `DISABLED` : **le piège task-239 a été correctement évité** par cette tentative.
- Les deux Lambdas `media-summarizer-api-dev` et `media-summarizer-api-staging` sont déployées, chacune avec son `ENVIRONMENT`, son `RUNTIME_SECRET_NAME` et ses noms de tables suffixés.
- Les deux API répondent `200 {"status":"healthy","database":"connected"}` sur **leurs endpoints respectifs et indépendants** — critère #8 vraisemblablement tenu. Chemin exact : `/api/v1/health/` **avec le slash final** (sans slash → `307`, et `/health` → `404`).

### Point de blocage exact — critère #7 non terminé

L'agent s'est arrêté sur la phrase « Now criterion #7: the staging runtime secret ». Constat : `media-summarizer-runtime-staging` **existe mais est vide (0 clé)**, là où `media-summarizer-runtime-dev` en contient 37 (dont 2 vides). **Staging est donc vert au health check mais fonctionnellement creux** : la connexion DynamoDB passe par le rôle IAM, mais toutes les intégrations tierces (Deepgram, OpenAI, Apify, RevenueCat, …) échoueraient. C'est le premier travail à reprendre.

### Observation technique laissée par l'agent

`terraform plan -refresh-only -detailed-exitcode` renvoie **toujours** `2` avec le provider aws 5.x, y compris sur un staging fraîchement appliqué : c'est de la normalisation d'attributs calculés, pas de la vraie dérive. L'assertion qui porte réellement pour le critère #4 est `plan -detailed-exitcode` = `0` sur dev, et elle passait.

### Divergence à traiter en priorité à la reprise

**AWS a été modifié mais `main` ne contient aucun de ces changements** — la restructuration Terraform, les scripts et la suppression des fallbacks vivent uniquement sur `recover/task-237-v3`. Le dispatcher n'a délibérément **pas** mergé : l'agent a échoué avant la fin, les 77 fichiers ne sont ni relus ni testés, et aucun critère n'a été validé par lui. Cette dérive entre l'infra réelle et le dépôt est le risque principal du moment : la prochaine tentative doit la résorber en premier, soit en finissant et en mergeant `recover/task-237-v3`, soit en décidant explicitement de revenir en arrière côté AWS.

## Divergence résorbée — `recover/task-237-v3` mergé le 2026-08-12 (`9bfbb7b`)

La branche a été **relue et vérifiée avant merge**, pas acceptée sur parole. Ce qui a été contrôlé :

- **`main` décrit désormais l'infra réelle** : `terraform plan -detailed-exitcode` depuis `envs/dev` **et** `envs/staging` renvoie `0` / `No changes`. La dérive dépôt↔AWS est fermée.
- **Les 47 noms `required_env()` sont injectés sur les 30 Lambdas** (15 × dev + 15 × staging), aucune manquante. `job-archiver` est le seul à n'en avoir aucune : il ne lit que `ARCHIVE_BUCKET`, présent.
- **Les 91 appels `required_env()` au niveau module se résolvent réellement** : les deux API renvoient `200 {"status":"healthy","database":"connected"}` sur `/api/v1/health/`. C'était le risque majeur du commit WIP `3ae9e48` — un import suffisait à faire crasher une Lambda si une variable manquait.
- **Aucun croisement d'environnement** : 24 tables par env, toutes suffixées correctement, aucune ne pointe vers l'autre env.
- **Pas de régression E2E** : `pytest -m e2e` donne **11 failed / 2 passed / 6 errors** à l'identique sur `main` et sur la branche, avec le même `404` sur la même URL. Ces échecs **préexistent** au chantier task-237.
- **Le fix de rédaction des identifiants (`1d337e4`) survit au merge** : `merge-tree` confirme `redact_hierarchy` présent dans l'arbre résultant. Le fichier n'apparaissait « supprimé » que parce que la branche est basée sur `3a907b5`, antérieur à sa création.
- **Le gel task-239 a tenu** : TTL `DISABLED` + PITR `ENABLED` sur les 5 tables `-dev` critiques.

### Reste à faire — critère #7 toujours ouvert

Le secret `media-summarizer-runtime-staging` contient **0 clé** contre 37 pour dev. Staging reste vert au health check et fonctionnellement creux. C'est le point de reprise.

### Deux défauts constatés, hors périmètre du merge

1. **Le teardown E2E ne nettoie plus en local.** `tests/e2e/conftest.py:173-177` avale l'échec d'import de `database_async` et sort. Ce garde est **identique sur `main`** (donc pas une régression de code), mais son effet a changé : maintenant que `required_env()` lève sans env, l'import échoue toujours en local et le teardown est systématiquement sauté. Conséquence mesurée : **7 utilisateurs `e2e-test-*` orphelins dans `users-dev`**, 3 dans `users`. À traiter, sinon la table se remplit à chaque run local.
2. **La rédaction des dumps ne couvre que les nœuds dont le `resource-id` matche** `password|email|token|secret|otp|code`. Un identifiant affiché dans un nœud sans `resource-id` parlant passerait encore.

### Non traité, à décider par le propriétaire

- Les **22 tables historiques non suffixées** coexistent avec les `-dev`. Filet de sécurité utile, mais données dupliquées : ne rien y toucher avant d'avoir confirmé que les Lambdas lisent bien les `-dev`.
- L'ancien state `s3://…/infrastructure/terraform.tfstate` (serial 20, 104 ressources) existe toujours à côté des trois nouveaux (`env/dev`, `env/staging`, `env/shared`). Plus référencé par aucun code depuis le merge.
- Le secret `E2E_TEST_USER_PASSWORD` **n'a pas été rotaté** après la fuite du 2026-08-11 16:52 (dernière mise à jour : 2026-08-10).
<!-- SECTION:NOTES:END -->
