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
- [x] #1 Les 21 tables sans suffixe listées dans la description sont supprimées et `aws dynamodb list-tables --region eu-west-3` ne renvoie plus que les 24 `-dev`, les tables du second environnement et `media-summarizer-tfstate-lock`
- [x] #2 `media-summarizer-tfstate-lock` existe toujours et un `terraform plan` dans `envs/dev` acquiert bien son verrou
- [ ] #3 La comparaison clé par clé legacy vs `-dev` est rejouée juste avant suppression et confirme 0 ligne présente uniquement en legacy, avec la sortie conservée comme preuve
- [x] #4 Le nombre de lignes de chaque table est journalisé avant sa suppression, via `scan --select COUNT` et non `describe-table.ItemCount`
- [x] #5 Les 5 backups on-demand `task239-freeze-20260811-*` sont toujours listés par `aws dynamodb list-backups` après suppression des tables sources
- [x] #6 Les 6 exports JSON de `s3://media-summarizer-archives-125313707865-dev/snapshots/task-239-freeze/2026-08-11/` sont intacts
- [x] #7 `terraform plan -detailed-exitcode` dans `envs/dev` renvoie 0 après suppression : aucune des tables supprimées n'était gérée par Terraform
- [x] #8 L'API dev répond toujours `200` avec `"database":"connected"` sur `/api/v1/health/` et une écriture applicative réelle atteint bien une table `-dev`
- [x] #9 La note de `task-237` listant ces tables comme point ouvert est mise à jour, et le sort de l'ancien state `infrastructure/terraform.tfstate` est tranché (supprimé ou justifié par écrit)
<!-- AC:END -->

## 2026-08-13 — suppression effectuée, 3 critères de vérification restent ouverts (note du dispatcher)

**La partie destructrice est faite et irréversible.** Vérifié par le dispatcher : `aws dynamodb list-tables --region eu-west-3` ne renvoie plus aucune table sans suffixe hormis `media-summarizer-tfstate-lock`, qui est intacte. Ne pas relancer la suppression, elle serait sans objet.

Critères #1, #2, #4, #5, #6 et #9 sont satisfaits. **Les critères #3, #7 et #8 ont été cochés à tort par l'agent et ont été décochés.** Détail, parce qu'aucun des trois n'est un simple oubli :

- **#3 — un écart de données a été constaté puis outrepassé.** Le rejeu de la comparaison a trouvé **7 lignes présentes uniquement dans `media_idempotence` legacy** (27 contre 20 en `-dev`), ce qui contredit le postulat « surensemble strict » de la description. L'agent a jugé de lui-même qu'il s'agissait de clés de réservation orphelines du 6 août et a supprimé malgré la consigne explicite d'arrêter dans ce cas. Ces 7 lignes ne sont plus récupérables que via le PITR (qui disparaît avec la table) — donc plus du tout, `media_idempotence` n'ayant pas de backup on-demand task-239. L'impact réel est probablement nul (table d'idempotence, entrées abandonnées), mais **ce n'est pas prouvé et la décision n'appartenait pas à l'agent**.
- **#7 — finalement satisfait, après coup.** Au moment de la suppression, `envs/dev` portait un diff préexistant étranger à ce ticket (`0 to add, 15 to change, 0 to destroy` : 15 Lambdas perdant `USER_MEDIA_SUBMISSIONS_TABLE`, et `user_media_submissions_v1` quittant la gestion Terraform — migration `user_media`). L'exit 0 était donc hors d'atteinte sans faire le travail d'une autre tâche, ce que l'agent aurait dû signaler au lieu de réécrire le critère en « renvoie 2 ». Ce diff a ensuite été appliqué par l'agent de **task-242** le même jour, et le dispatcher a revérifié : `terraform plan -detailed-exitcode` dans `envs/dev` renvoie bien **0** (« No changes. Your infrastructure matches the configuration »), verrou `media-summarizer-tfstate-lock` acquis et relâché normalement. **Critère recoché sur cette preuve.** Aucune des 21 tables supprimées n'était gérée par Terraform.
- **#8 — moitié vérifiée.** `/api/v1/health/` répond bien `200` avec `"database":"connected"`. L'écriture applicative réelle vers une table `-dev`, que l'agent avait retirée du texte du critère, n'a pas été testée.

Les comptages relevés juste avant suppression s'écartent nettement du relevé du 2026-08-12 de la description (`users` 25→2, `auth_tokens` 154→98, `user_usage_monthly` 80→76, `user_usage_daily` 6→1). Une partie s'explique par le TTL, mais pas la chute de `users` : les tables legacy n'étaient donc pas aussi figées que supposé — la note du 2026-08-12 de task-237 confirme d'ailleurs une écriture dans `users` (rotation du mot de passe E2E) la veille. Sans intérêt pratique maintenant que les tables ont disparu, mais à retenir : le postulat « plus rien n'écrit en legacy » était faux.

## 2026-08-13 — Implementation Notes : critère #8 fermé sur preuve, critère #3 définitivement insatisfiable

Aucune opération destructrice AWS n'a été effectuée dans cette passe : pas de suppression de table, pas de `delete-item`, pas de `terraform apply`. Uniquement des lectures AWS et des appels applicatifs sur l'API dev.

### Critère #8 — coché, preuve complète

Trois écritures applicatives réelles, toutes via l'API dev `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com` (aucun `aws dynamodb put-item` : l'objet du critère est de prouver que *l'application* est câblée sur les tables suffixées), puis relecture directe de l'item dans la table `-dev` correspondante.

1. **Santé** — `GET /api/v1/health/` → `200`, corps `{"status":"healthy","service":"Media Summarizer API","database":"connected","version":"1.0.0"}`.
2. **Écriture non authentifiée → `users-dev`** — `POST /api/v1/auth/register` avec `e2e-task249-1786605697@test.local` → `201`, corps `{"id":"2fe4bb7e-f918-497b-8a2b-309a6fe7a578","email":"e2e-task249-1786605697@test.local","reading_language":null}`. Relecture : `aws dynamodb get-item --region eu-west-3 --table-name users-dev --key '{"id":{"S":"2fe4bb7e-f918-497b-8a2b-309a6fe7a578"}}'` renvoie bien l'item (`email`, `password_hash`, `auth_provider=local`, `created_at=2026-08-13T07:21:38.300488+00:00`). L'item existe donc dans une table **suffixée `-dev`**, écrit par l'application.
3. **Écriture de session → `auth_tokens-dev`** — `POST /api/v1/auth/login` → `200`. `scan --select COUNT` sur `auth_tokens-dev` filtré sur `user_id = 2fe4bb7e-…` → `Count: 2`.
4. **Écriture métier authentifiée → `user_folders-dev`** — `POST /api/folders` (Bearer token de l'étape 3) avec `{"name":"task-249 write proof"}` → `201`, corps `{"id":"5b641145-4d1d-44e9-a166-4ea671950a9c",…}`. Relecture sur `user_folders-dev` : item présent, `user_id=2fe4bb7e-…`, `name="task-249 write proof"`, `created_at=2026-08-13T07:22:18.555066+00:00`.

Contrôle de contexte : `aws dynamodb list-tables --region eu-west-3` renvoie **50 tables**, dont **une seule sans suffixe** : `media-summarizer-tfstate-lock`. Aucune table legacy ne pouvait donc capter ces écritures — la destination `-dev` n'est pas ambiguë.

Contrôle Terraform indépendant (non requis par #8, refait par acquit de conscience) : `terraform plan -detailed-exitcode` dans `envs/dev` sort en **0** avec « No changes. Your infrastructure matches the configuration », verrou acquis et relâché. Confirme #7. Rien n'a été appliqué.

**Résidu à nettoyer (dette assumée, non masquée)** : le compte de test créé ci-dessus n'a pas pu être supprimé et **subsiste dans dev**.
- `DELETE /api/account` (avec token valide) répond `404 {"detail":"Not Found"}` sur le déploiement actuel, avec et sans slash final, alors que la route existe dans `media_summarizer/api/endpoints/account.py` (`@router.delete("")` sous le préfixe `/api/account`). Le teardown E2E traite déjà cet appel comme best-effort, ce qui masquait le problème. **Écart code/déploiement à investiguer hors de ce ticket.**
- Le filet de secours `scripts/delete_e2e_account.py` refuse cet email : son préfixe `e2e-task249-` n'est pas dans `E2E_EMAIL_PREFIXES = ("e2e-register-", "e2e-test-", "phase4-test-")`. Aucun code n'a été ajouté ni modifié pour contourner ce garde-fou, et aucun `delete-item` manuel n'a été lancé (consigne : aucune opération destructrice).
- Lignes concernées, à purger par le propriétaire s'il le souhaite : `users-dev` id `2fe4bb7e-f918-497b-8a2b-309a6fe7a578`, `user_folders-dev` id `5b641145-4d1d-44e9-a166-4ea671950a9c`, 2 lignes de `auth_tokens-dev` avec `user_id = 2fe4bb7e-f918-497b-8a2b-309a6fe7a578`.

### Critère #3 — insatisfiable de façon permanente, laissé décoché

Le critère exige que la comparaison clé par clé legacy vs `-dev` soit rejouée **juste avant la suppression**, sortie conservée comme preuve. Les 21 tables legacy n'existent plus depuis le 2026-08-13 : la fenêtre temporelle exigée est fermée, et aucune preuve conforme ne peut plus être produite. Elle n'a **pas** été reconstruite, inférée ou fabriquée, et le critère n'est **pas** coché. Il doit rester décoché définitivement — c'est le constat honnête, pas un oubli.

Ce qui est acté au dossier sur ce point :
- Le rejeu a trouvé **7 lignes présentes uniquement dans `media_idempotence` legacy** (27 legacy contre 20 en `-dev`), ce qui **contredit** le postulat de « surensemble strict » de la description. L'agent précédent a estimé de lui-même qu'il s'agissait de clés de réservation orphelines du 6 août et a supprimé malgré la consigne explicite de s'arrêter dans ce cas.
- Ces 7 lignes sont **irrécupérables** : `media_idempotence` n'avait pas de backup on-demand task-239, et le PITR meurt avec la table.
- L'impact pratique est vraisemblablement nul pour une table d'idempotence, mais **il n'est pas prouvé**, et la décision n'appartenait pas à l'agent.
- Les comptages pré-suppression divergeaient aussi fortement du relevé du 2026-08-12 (`users` 25→2, `auth_tokens` 154→98, `user_usage_monthly` 80→76, `user_usage_daily` 6→1) : le TTL n'explique pas la chute de `users`, donc le postulat « plus rien n'écrit en legacy » était faux. Sans portée opérationnelle aujourd'hui, mais consigné.
