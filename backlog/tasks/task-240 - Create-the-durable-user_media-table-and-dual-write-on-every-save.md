---
id: task-240
title: Create the durable user_media table and dual-write on every save
status: To Do
assignee: []
created_date: '2026-08-11 16:11'
updated_date: '2026-08-11 16:52'
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
- [ ] #1 L'implémentation suit la décision Option A et la forme d'enregistrement définies en §4.1-4.3 du README task-218
- [ ] #2 La table user_media existe en dev avec PITR et streams activés
- [ ] #3 Chaque sauvegarde utilisateur réussie crée ou réutilise exactement un enregistrement user_media via un chemin idempotent (PutItem/UpdateItem conditionnel)
- [ ] #4 L'id est déterministe: deux sauvegardes du même media_key par le même utilisateur convergent sur la même ligne sans doublon, même en concurrence
- [ ] #5 L'enregistrement porte les identifiants et métadonnées requis par §4.2 (title, source, media_type, folder_id, tag_ids, saved_at, updated_at)
- [ ] #6 Aucun TTL piloté par le traitement n'existe sur la table; purge_at n'est écrit que par une suppression utilisateur
- [ ] #7 processing_status et last_job_id sont nullables et aucun chemin de lecture n'en dépend pour afficher la bibliothèque
- [ ] #8 L'écriture durable est placée derrière DURABLE_MEDIA_ENABLED et les lectures passent toujours par processing_jobs
- [ ] #9 Un échec d'écriture durable est loggé et remonte une alarme, il n'est pas avalé
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
<!-- SECTION:NOTES:END -->
