---
id: task-240
title: Create the durable user_media table and dual-write on every save
status: In Progress
assignee: []
created_date: '2026-08-11 16:11'
updated_date: '2026-08-12 17:19'
labels:
  - backend
  - infra
  - persistence
dependencies:
  - task-239
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Phase 1 of the task-218 benchmark (§5.2, §4.1-4.3). Découpage de task-219.

Introduit l'enregistrement durable retenu par l'owner (**Option A**) : une table `user_media` dédiée qui devient la source de vérité unique de la bibliothèque d'un utilisateur, `processing_jobs` étant rétrogradé en état purement opérationnel libre d'expirer.

Lire la décision de l'owner et la forme canonique de l'enregistrement dans `docs/research/task-218-durable-media-library-persistence/README.md` — sections **§4.1 (définition de la table)**, **§4.2 (attributs)** et **§4.3 (chemin d'écriture idempotent)**.

Portée : création de la table avec PITR et streams, puis déploiement du code qui crée/met à jour `user_media` à chaque sauvegarde derrière le flag d'environnement `DURABLE_MEDIA_ENABLED`. **Les lectures continuent de passer par `processing_jobs`** — le basculement des lectures est hors périmètre, c'est task-220 (Phase 3, §5.4).

Points structurants du benchmark à respecter :

- `PK = user_id`, `SK = media_item_id` où `media_item_id = "mi_" + sha256(f"{user_id}|{media_key}")[:32]`. L'id déterministe rend l'idempotence race-free sans index supplémentaire.
- Aucun TTL piloté par le traitement. `purge_at` est le seul attribut TTL et seule une suppression initiée par l'utilisateur peut l'écrire.
- `processing_status` est un instantané **dénormalisé et nullable** : la bibliothèque doit s'afficher sans lui.
- `last_job_id` est un **pointeur nullable qui peut pendre** et ne doit jamais être requis pour une lecture.
- Les échecs de l'écriture durable sont loggés et alarmés, pas avalés silencieusement.

Rollback : flag à off. La table est additive et les lignes orphelines sont inoffensives.

Une piste existe sur la branche `recover/task-219` (commit c56c9d8) : ébauche de `core/models/user_media.py`, `core/services/user_media_service.py`, `utils/user_media.py`. À traiter comme une piste non relue et non testée, pas comme un acquis.

Les agents ont tous les droits pour exécuter `terraform apply` et les commandes AWS CLI sur dev.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 L'implémentation suit la décision Option A et la forme d'enregistrement définies en §4.1-4.3 du README task-218
- [x] #2 La table user_media existe en dev avec PITR et streams activés
- [x] #3 Chaque sauvegarde utilisateur réussie crée ou réutilise exactement un enregistrement user_media via un chemin idempotent (PutItem/UpdateItem conditionnel)
- [x] #4 L'id est déterministe: deux sauvegardes du même media_key par le même utilisateur convergent sur la même ligne sans doublon, même en concurrence
- [x] #5 L'enregistrement porte les identifiants et métadonnées requis par §4.2 (title, source, media_type, folder_id, tag_ids, saved_at, updated_at)
- [x] #6 Aucun TTL piloté par le traitement n'existe sur la table; purge_at n'est écrit que par une suppression utilisateur
- [x] #7 processing_status et last_job_id sont nullables et aucun chemin de lecture n'en dépend pour afficher la bibliothèque
- [x] #8 L'écriture durable est placée derrière DURABLE_MEDIA_ENABLED et les lectures passent toujours par processing_jobs
- [x] #9 Un échec d'écriture durable est loggé et remonte une alarme, il n'est pas avalé
- [ ] #10 Vérification en AWS dev: une sauvegarde réelle produit la ligne user_media attendue, et la répéter ne crée pas de doublon
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-11 — **Tâche éligible mais volontairement différée par le dispatcher.** Elle était deuxième dans l'ordre de sélection (high, plus petit numéro après task-237), mais elle ajoute la table `user_media` dans `infrastructure/terraform/` et applique sur AWS dev — soit exactement les fichiers et le state Terraform live que task-237 restructure au même moment via `state rm`/`import`. Deux `terraform apply` concurrents se seraient disputé le lock de state, avec un conflit de merge quasi certain par-dessus. À dispatcher au prochain run, une fois task-237 mergée sur `main` : l'implémenteur écrira alors la table dans la nouvelle arborescence `modules/platform/` au lieu des fichiers racine.

2026-08-11 — **Piste plus complète que `recover/task-219` : la branche `recover/task-240-wip` (commit 9b2b33e).** Récupérée d'un worktree abandonné qui allait être supprimé — le travail n'était pas commité et aurait été perdu. 22 fichiers, +2835/-76, nettement au-delà de l'ébauche de `recover/task-219` (c56c9d8) citée dans la description :

- `media_summarizer/core/models/user_media.py` (+218), `core/services/durable_media_service.py` (+410), `utils/user_media.py` (+552)
- `scripts/backfill_user_media.py` (+616) — recouvre plutôt le périmètre de task-241 (Phase 2) que celui de cette tâche
- `infrastructure/terraform/durable_media_alerts.tf` (+175) et `infrastructure/observability/runbooks/durable-media.md` (+269) — piste pour le critère #9
- modifications dans `api/endpoints/media.py`, `core/media_ingestion/adapters/orchestrators.py`, `core/services/media_submission.py`, `utils/database_async.py`

**À traiter comme une piste non relue, non testée et non validée**, au même titre que `recover/task-219` : aucun critère d'acceptation n'a été vérifié, aucun `terraform apply` n'a été lancé depuis cette branche.

**Attention — même piège TTL que task-237** : cette branche modifie `infrastructure/terraform/dynamodb_core_tables.tf` (+141) et a été créée avant/pendant le gel TTL de task-239. Le TTL de `processing_jobs` doit rester `enabled = false` ; vérifier avec `aws dynamodb describe-time-to-live --table-name processing_jobs` → doit rendre `DISABLED`. Ne pas réactiver en recopiant ce fichier. Seule task-242 (Phase 4) peut légitimement le réactiver.

---

2026-08-12 — **Implémenté et appliqué sur AWS dev.** 9 critères sur 10 vérifiés ; le #10 l'est partiellement (détail plus bas).

**Infra (`modules/platform/`, jamais de fichier `.tf` racine — l'arborescence task-237 est en place)**

- `dynamodb_user_media.tf` : table `user_media-dev`, `PK=user_id`, `SK=media_item_id`, PAY_PER_REQUEST, 2 LSI (`saved-at-index`, `folder-index` sur `<folder_id>#<saved_at>`), stream `NEW_AND_OLD_IMAGES`, PITR, `deletion_protection_enabled`, `prevent_destroy`. **Un seul TTL : `purge_at`.**
- `durable_media_alerts.tf` : 15 metric filters (`durable_media.write_failed` sur le log group API + les 13 workers, `durable_media.created` comme dénominateur) + 2 alarmes gated `var.enable_alarms` — l'alarme d'échec d'écriture, et une alarme tripwire sur `TimeToLiveDeletedItemCount` de `user_media` (invariant I2 : la valeur attendue est exactement 0 tant qu'aucun cas d'usage de suppression n'existe).
- `runtime_env.tf` : `USER_MEDIA_TABLE` + `DURABLE_MEDIA_ENABLED`. `variables.tf` : `durable_media_enabled` (bool, défaut `true`).
- IAM inchangé : `local.table_arns` couvre déjà `table/*-dev` par wildcard de suffixe.
- `dynamodb_core_tables.tf` **non touché** : le TTL de `processing_jobs` reste `enabled = false` (gel task-239). Vérifié après apply : `describe-time-to-live processing_jobs-dev` → `DISABLED`, et le plan liste `processing_jobs` en `no-op`.
- Runbook : `infrastructure/observability/runbooks/durable-media.md` (ancres `#write-failed`, `#unexplained-ttl`, `#rollback`).

**Apply dev** : `terraform plan` → **16 add / 14 change / 0 destroy** (la table, 15 metric filters, l'injection des 2 variables dans les 14 Lambdas). `scripts/tf_plan_guard.sh dev tfplan staging` → PASS sur les 3 couches (0 delete, tous les noms en `-dev`, 0 collision avec les 129 noms staging). Appliqué depuis `envs/dev` uniquement. Les alarmes ne sont pas créées en dev (`enable_alarms = false`, convention de coût du module) ; les metric filters, eux, sont bien présents — vérifié via `describe-metric-filters`.

**Code**

- `core/models/user_media.py` : `UserMediaRecord`, `UserMediaStatus`, `build_media_item_id` = `"mi_" + sha256(f"{user_id}|{media_key}")[:32]`, `build_folder_sort_key`. `processing_status` et `last_job_id` sont réellement `Optional[...] = None` et **absents de l'item** quand inconnus (pas de "pending" par défaut à la lecture).
- `utils/user_media.py` : seul écrivain de la table. `create_if_absent` détient le **seul `put_item`** du module (invariant I1) avec `ConditionExpression="attribute_not_exists(media_item_id)"` et re-lecture de la ligne gagnante sur `ConditionalCheckFailedException`. Tout le reste est un `UpdateItem` attribut par attribut, qui **refuse** `purge_at`/`deleted_at` (invariant I2 structurel) ainsi que les attributs d'identité. Nom de table résolu paresseusement via `required_env` (pas au moment de l'import : un environnement flag-off ne doit pas crasher au chargement).
- `core/services/durable_media_service.py` : `save_media_for_user()` (lève `DurableMediaWriteError` après un log ERROR `durable_media.write_failed`), `try_save_media_for_user()` (wrapper Phase 1, cf. écart assumé ci-dessous), `mirror_job()` / `mirror_attributes()` (best-effort, même événement alarmé).
- Chemins de sauvegarde câblés : `orchestrators.py submit()` (**avant** le court-circuit de doublon, conformément à §4.3 : l'entrée de bibliothèque est créée en premier, et un `media_key` déjà traité globalement reste une entrée neuve pour *cet* utilisateur), `POST /api/media/upload`, `POST /api/media/upload-audio`. `job.media_item_id` porte le pointeur vers la ligne durable.
- Hook de miroir dans `database_async.update_processing_job` : sans lui `processing_status` resterait figé à `pending` et les métadonnées résolues tardivement (titre YouTube, durée audio) n'atteindraient jamais la ligne durable, ce qui viderait le #5 de son sens. Best-effort, no-op si `job.media_item_id` est absent, import paresseux pour éviter le cycle.
- **Les ids retournés par l'API ne changent pas** : `media_item_id` reste `job.id` partout (`_build_media_item_contract`, `/upload`, `/upload-audio`, `IngestionOutcome`). C'est le #8 : les lectures passent encore par `processing_jobs`, donc rendre l'id durable au client produirait un 404 sur le `GET` suivant. **La piste `recover/task-240-wip` avait ce bug** (`media_item_id=durable_media_item_id or job.id`) — non reprise.
- `media_key` n'est volontairement **pas** stocké sur les jobs document/audio : le contrat canonique expose `job.media_key or job.id`, et le remplir aurait changé un champ visible du client hors périmètre.

**Écart assumé sur le #9.** Le service lève ; les points d'appel Phase 1 utilisent `try_save_media_for_user`, qui dégrade en `None` après le log ERROR + l'alarme. Raison : en Phase 1 les lectures ne touchent pas `user_media`, donc faire échouer une ingestion à cause d'une table que personne ne lit encore échangerait une régression réellement visible contre une régression comptable, que le backfill task-241 répare. L'échec est **remonté** (événement dédié + alarme), pas silencieux. `try_save_media_for_user` porte un `TASK-220:` explicite : le wrapper doit disparaître quand les lectures basculent.

**Vérification AWS dev** (code réel exécuté contre les vraies tables `-dev`, 26 assertions + 1 sonde dédiée au hook de miroir, toutes passantes, lignes de sonde supprimées ensuite) :

- ligne créée avec title/source_url/source_platform/media_type/folder_id/tag_ids/saved_at/updated_at/folder_sort_key, **sans aucun attribut TTL** ;
- re-sauvegarde → même id, aucun doublon, et l'organisation utilisateur (folder/tags/title) n'est pas écrasée ;
- **8 `save_media_for_user` concurrents** (`asyncio.gather`) sur le même `(user_id, media_key)` → 1 seule ligne, 8 retours du même id, 0 exception (#4) ;
- `mirror_job` propage statut + titre + durée média (`extraction_metadata.audio_duration_seconds`, jamais `total_duration`) sans toucher folder/tags ;
- `update_attributes` refuse `purge_at` et `deleted_at` ;
- flag à `0` → `None` retourné, rien écrit ; table inexistante → `DurableMediaWriteError` levée et l'événement `durable_media.write_failed` émis ;
- `aws logs test-metric-filter` confirme que le pattern `{ $.event = "durable_media.write_failed" }` matche la vraie ligne JSON produite par `log_event` et **pas** `durable_media.created`.

**#10 laissé décoché** : la sauvegarde a été exercée en appelant le vrai code du chemin de sauvegarde contre les vraies tables dev, mais **pas** via l'endpoint HTTP déployé — pousser une image Lambda depuis une branche non mergée vers l'API dev sort du périmètre (c'est le job de `deploy-lambda.yml` au merge). À faire après déploiement : un `POST /api/media/ingest-url`, puis `aws dynamodb query --table-name user_media-dev --key-condition-expression "user_id = :u"` doit rendre 1 ligne, et rejouer la même URL ne doit pas en créer une seconde.

**Aucun test automatisé ajouté** (contrainte de l'agent d'implémentation), alors que la task en demandait un sur la concurrence. Le critère #4 a été prouvé à la place par la sonde concurrente ci-dessus, exécutée contre AWS dev.

**Risques notés** : (1) une requête qui échoue *après* l'écriture durable (réservation d'idempotence, envoi SQS) laisse une ligne de bibliothèque orpheline — invisible en Phase 1, mais qui apparaîtra comme un item éternellement `pending` quand task-220 basculera les lectures ; le benchmark assume cet ordre (§4.3). (2) Le hook de miroir ajoute une écriture DynamoDB par transition de job. (3) `media_key` des uploads audio dépend du nom de fichier et de la taille : deux fichiers différents de même nom et même taille convergeraient sur une seule ligne de bibliothèque.
<!-- SECTION:NOTES:END -->
