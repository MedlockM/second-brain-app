---
id: task-249
title: >-
  Drop the 21 obsolete unsuffixed DynamoDB tables left behind by the environment
  migration
status: To Do
assignee: []
created_date: '2026-08-12 16:41'
labels:
  - infra
  - cleanup
  - terraform
dependencies:
  - task-237
  - task-241
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Supprimer les **21 tables DynamoDB sans suffixe** devenues obsolètes après la migration vers les noms par environnement (task-237). Elles ne sont plus gérées par Terraform, plus lues par le code, et l'application écrit désormais exclusivement dans les tables `-dev`.

## Pourquoi c'est sûr : état des lieux du 2026-08-12

Le compte `125313707865` (`eu-west-3`) porte **70 tables** : 24 `-dev`, 24 `-staging`, 21 legacy sans suffixe, plus `media-summarizer-tfstate-lock`.

**Comparaison clé par clé entre chaque table legacy et son homologue `-dev`** (scan complet des clés primaires, pas `describe-table.ItemCount`) :

| Table legacy | lignes legacy | lignes `-dev` | lignes présentes UNIQUEMENT en legacy |
|---|---|---|---|
| artifact_idempotence | 35 | 35 | **0** |
| auth_tokens | 154 | 195 | **0** |
| bug_reports | 1 | 1 | **0** |
| feed_forecasts | 0 | 0 | **0** |
| follows | 0 | 0 | **0** |
| media_artifacts | 166 | 166 | **0** |
| media_idempotence | 27 | 27 | **0** |
| media_watchers | 0 | 0 | **0** |
| pricing_config | 8 | 8 | **0** |
| processing_jobs | 22 | 28 | **0** |
| revenucat_events | 0 | 0 | **0** |
| subscriptions | 1 | 1 | **0** |
| translation_idempotence | 14 | 14 | **0** |
| user_digest_settings | 0 | 0 | **0** |
| user_digests | 8 | 8 | **0** |
| user_folders | 14 | 14 | **0** |
| user_media_submissions | 27 | 27 | **0** |
| user_tags | 1 | 1 | **0** |
| user_usage_daily | 6 | 13 | **0** |
| user_usage_monthly | 80 | 87 | **0** |
| users | 25 | 33 | **0** |

**Résultat décisif : 0 ligne n'existe uniquement en legacy sur les 21 tables.** Les `-dev` sont un **surensemble strict** — les 5 écarts (`auth_tokens` +41, `users` +8, `user_usage_daily` +7, `user_usage_monthly` +7, `processing_jobs` +6) sont des lignes écrites *après* la migration, donc uniquement côté `-dev`. Supprimer les legacy ne perd aucune donnée. La méthode de vérification est à rejouer avant suppression, elle est reproductible.

## Ne pas confondre : `media-summarizer-tfstate-lock`

Cette table n'a pas de suffixe **mais n'est pas legacy** : c'est la table de verrouillage Terraform, partagée par les quatre backends (`envs/{dev,staging,prod}` et `shared/`). La supprimer casse tout `terraform plan`. Elle est explicitement **hors périmètre**.

## Autres faits vérifiés

- **Aucune des 21 tables n'est dans un state Terraform.** `terraform state list` dans `envs/dev` retourne 24 `aws_dynamodb_table`, tous suffixés (contrôlé : `users_v2` → `name = "users-dev"`). Aucun `terraform state rm` n'est donc nécessaire : la suppression est purement côté AWS CLI.
- **Le code ne référence plus aucun nom legacy.** Le seul reste est une docstring d'exemple dans `media_summarizer/utils/env.py` — `required_env()` a supprimé les fallbacks codés en dur (critère #6 de task-237).
- **Les sauvegardes de task-239 portent sur les tables legacy**, pas sur les `-dev` : 5 backups on-demand `task239-freeze-20260811-*` (`processing_jobs`, `user_folders`, `user_tags`, `media_artifacts`, `user_media_submissions`) et 6 exports JSON dans `s3://media-summarizer-archives-125313707865-dev/snapshots/task-239-freeze/2026-08-11/`. Ces artefacts **survivent à la suppression des tables** : un backup on-demand DynamoDB est indépendant de sa table source. C'est le filet à conserver.
- **PITR : `ENABLED` sur 5 tables legacy** (`media_artifacts`, `processing_jobs`, `user_folders`, `user_media_submissions`, `user_tags`), `DISABLED` sur les 16 autres. Le PITR, lui, **disparaît avec la table** — d'où l'intérêt des backups on-demand ci-dessus.
- 3 tables `-dev` n'ont aucun homologue legacy (`review_schedule`, `user_review_settings`, `user_rss_feeds`) : créées après la migration, sans objet ici.
- Volume total des 21 tables : ~254 Ko. **Le gain n'est pas financier** (quelques centimes en PAY_PER_REQUEST) mais cognitif : 70 tables dont un tiers de doublons figés rend tout diagnostic ambigu, et un doublon figé peut être pris pour un backup utilisable alors qu'il ne l'est plus.

## Dépendance à respecter avant suppression

`task-241` (backfill de `user_media`) consomme `processing_jobs`, `user_media_submissions` et `media_artifacts` comme sources de reconstruction. Sur ces trois tables les legacy et les `-dev` sont **identiques ou sous-ensembles** (22/28, 27/27, 166/166), donc task-241 peut travailler sur les `-dev` sans rien perdre. Vérifier néanmoins que task-241 lit bien les noms suffixés avant de supprimer, et attendre son achèvement si un doute subsiste : les backups on-demand ne sont pas requêtables directement, il faudrait restaurer une table pour y accéder.

## Travail attendu

Supprimer les 21 tables via AWS CLI, en journalisant pour chacune le nombre de lignes constaté juste avant suppression. Ne pas écrire de script « intelligent » qui devine la liste par pattern : une table sans suffixe n'est pas nécessairement legacy (cf. `tfstate-lock`). La liste explicite des 21 noms figure dans le tableau ci-dessus.

Mettre ensuite à jour la note « Non traité, à décider par le propriétaire » de `task-237` qui mentionne ces tables comme point ouvert, et supprimer l'ancien state Terraform devenu orphelin `s3://media-summarizer-tfstate-125313707865/infrastructure/terraform.tfstate` (450 Ko, serial 20, 104 ressources, plus référencé par aucun code depuis le merge `9bfbb7b`) — ou dire explicitement pourquoi le conserver.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Les 21 tables sans suffixe listées dans la description sont supprimées et `aws dynamodb list-tables --region eu-west-3` ne renvoie plus que les 24 `-dev`, les tables du second environnement et `media-summarizer-tfstate-lock`
- [ ] #2 `media-summarizer-tfstate-lock` existe toujours et un `terraform plan` dans `envs/dev` acquiert bien son verrou
- [ ] #3 La comparaison clé par clé legacy vs `-dev` est rejouée juste avant suppression et confirme 0 ligne présente uniquement en legacy, avec la sortie conservée comme preuve
- [ ] #4 Le nombre de lignes de chaque table est journalisé avant sa suppression, via `scan --select COUNT` et non `describe-table.ItemCount`
- [ ] #5 Les 5 backups on-demand `task239-freeze-20260811-*` sont toujours listés par `aws dynamodb list-backups` après suppression des tables sources
- [ ] #6 Les 6 exports JSON de `s3://media-summarizer-archives-125313707865-dev/snapshots/task-239-freeze/2026-08-11/` sont intacts
- [ ] #7 `terraform plan -detailed-exitcode` dans `envs/dev` renvoie 0 après suppression : aucune des tables supprimées n'était gérée par Terraform
- [ ] #8 L'API dev répond toujours `200` avec `"database":"connected"` sur `/api/v1/health/` et une écriture applicative réelle atteint bien une table `-dev`
- [ ] #9 La note de `task-237` listant ces tables comme point ouvert est mise à jour, et le sort de l'ancien state `infrastructure/terraform.tfstate` est tranché (supprimé ou justifié par écrit)
<!-- AC:END -->
