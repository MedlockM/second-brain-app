---
id: task-224
title: >-
  Implement in-app account deletion with full data purge and remove the
  non-functional Export Data control
status: Done
assignee: []
created_date: '2026-08-05 17:54'
updated_date: '2026-08-12 19:34'
labels:
  - feature
  - compliance
  - mobile
  - api
  - release
dependencies:
  - task-240
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Deux manques bloquent la soumission stores et la conformité :

1. **Aucune suppression de compte in-app.** L'App Store guideline **5.1.1(v)** impose que toute app permettant la création d'un compte permette sa suppression **depuis l'app**. C'est un motif de rejet automatique. C'est aussi le droit à l'effacement (RGPD art. 17).
2. **Un bouton `Export Data` inactif** dans `mobile/app/(tabs)/account.tsx:107`. Un contrôle mort est en soi un risque de review.

## Décision owner (2026-08-05) — périmètre RGPD volontairement minimal

L'owner arbitre de n'implémenter que le strict nécessaire. **Le bouton `Export Data` est supprimé**, pas implémenté.

Précision juridique retenue : les données de l'app **sont** des données personnelles au sens de l'art. 4(1) — email, mot de passe, bibliothèque de médias sauvegardés, tags, dossiers, `reading_language` sont rattachés à un compte identifiable, même quand le contenu source est public. Les droits d'accès (art. 15) et de portabilité (art. 20) s'appliquent donc.

Mais ces deux droits **n'ont aucune obligation d'être self-service in-app** : un traitement manuel sur demande via l'email de support satisfait le règlement, dans le délai d'un mois. La politique de confidentialité doit alors documenter cette voie de recours. La suppression, elle, doit être in-app pour la raison Apple ci-dessus.

## Attention : `DELETE /api/v1/users/{user_id}` n'est pas la base

L'endpoint actuel est non authentifié (cf. task-222) **et** ne purge pas les données liées. Ne pas le réutiliser tel quel.

La purge doit couvrir l'ensemble des données rattachées au compte, à recenser à l'implémentation — au minimum : `users`, `auth_tokens`, `processing_jobs`, `media_artifacts`, tags, dossiers, `user_media_submissions`, `subscriptions`, `revenucat_events`, `media_watchers`, l'index Algolia, et les objets S3 (audio, documents, archives, flashcards).

## Dépendance task-219

La persistance durable de la media library (task-219) introduit une nouvelle source de vérité pour les médias sauvegardés. La purge doit la couvrir. Coordonner l'ordre de réalisation : si task-219 n'est pas encore mergée, la purge doit être écrite de façon à ce que l'ajout du nouveau store soit une extension évidente, et une note de suivi explicite doit être laissée.

Côté RevenueCat : la suppression du compte applicatif n'annule pas un abonnement store actif. Le comportement attendu (et son message à l'utilisateur) doit être décidé et documenté.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An authenticated account-deletion endpoint exists that derives the target account from the session and cannot delete another user's account
- [x] #2 The Account screen exposes a discoverable account-deletion action with an explicit irreversible-action confirmation, satisfying App Store guideline 5.1.1(v)
- [x] #3 Deletion purges every store holding data attached to the account, and the implementation notes list the full inventory of stores covered
- [x] #4 S3 objects and Algolia records belonging to the account are removed, not just the DynamoDB rows
- [x] #5 Durable media-library records introduced by task-219 are covered by the purge, or an explicit follow-up is recorded if task-219 lands later
- [x] #6 Deletion is idempotent and a partial failure leaves no state where the account is unusable but its data is still discoverable
- [x] #7 The behaviour toward an active RevenueCat subscription is decided, implemented, and surfaced to the user before confirmation
- [x] #8 The non-functional Export Data control is removed from the Account screen along with any dead handler code
- [x] #9 The privacy policy documents the manual support-email procedure for access and portability requests and the one-month response window
- [x] #10 Deletion is verified end to end against AWS dev: the account can no longer authenticate and its media, artifacts, folders, tags and search records are gone
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-11 — task-219 a été découpée (task-239 → 240 → 241 → 220 → 242 → 243). La dépendance passe de task-219 (archivée) à **task-240**, qui crée la table durable `user_media` — c'est le minimum nécessaire pour que la purge de compte ait quelque chose à purger. Pas besoin d'attendre le backfill ni le basculement des lectures.

Coordination avec task-243 (cycle de vie rétention/suppression/backup) : task-243 a un critère dédié à garantir que `user_media` est inclus dans le périmètre de purge de la suppression de compte. Si cette tâche-ci part la première, elle doit inclure `user_media` dans la purge, et task-243 se contentera de le vérifier. Éviter de dupliquer la logique de suppression entre les deux.

## 2026-08-12 — implémentation

### Endpoint

`DELETE /api/account` (`media_summarizer/api/endpoints/account.py`). **Aucun id en path** : le compte est déduit du bearer token via `get_current_user`, donc il n'y a structurellement rien à autoriser et le contrôle d'ownership ne peut pas être oublié. Pas de `/api/v1/` (interdit par AGENTS.md). L'ancien module `endpoints/users.py` et son `DELETE /{user_id}` sont **supprimés**, ainsi que leur montage dans `api/main.py`. Le teardown E2E (`tests/e2e/conftest.py`) et `tests/e2e/README.md` sont mis à jour.

Toute la logique vit dans `media_summarizer/core/services/account_deletion_service.py` (`purge_account`), pas dans l'endpoint : task-243 doit pouvoir la vérifier, pas la réécrire.

### Inventaire complet de la purge (AC#3)

Ordre d'exécution — c'est une propriété de correction, pas un style : `index de recherche -> artifacts + objets -> objets média -> lignes média -> tables par user -> identité`. Une panne laisse donc un compte qui s'authentifie encore et peut relancer la suppression, jamais un compte verrouillé dont les transcripts restent cherchables (AC#6).

| Étape | Store | Accès |
|---|---|---|
| 1 | Index Algolia partagé | `search_indexing.delete_user_records` (filtre `user_id`) |
| 2 | `media_artifacts` (lignes + pointeurs `request#`) | GSI `media-item-index` sur chaque `media_item_id` |
| 2 | Objets S3 d'artifacts + `artifact_idempotence` | via `generation_fingerprint`, **seulement si aucun sibling ne survit** |
| 3 | S3 transcripts (+ `.translated.<lang>.`), audio (`{job_id}` et `shared-audio/{user_id}/`), documents (`{job_id}/`), summary/quiz legacy | préfixes dérivés du job id |
| 3 | `translation_idempotence` | fingerprint reconstruit depuis chaque objet traduit trouvé |
| 4 | `media_watchers` | `(media_key, user_id)` collectés avant suppression des lignes |
| 5 | `processing_jobs` | GSI `user-index`, paginé (le helper de l'inbox s'arrête à 1 page de 1 MB) |
| 6 | `user_media` (task-240) | `user_media.delete_all_for_user` |
| 7 | `user_media_submissions`, `user_usage_monthly`, `user_usage_daily`, `review_schedule`, `user_review_settings`, `user_digests`, `user_digest_settings`, `follows` | PK = `user_id` |
| 8 | `user_folders`, `user_tags`, `user_rss_feeds`, `subscriptions`, `bug_reports` | GSI `user-index` |
| 9 | Objets S3 des pièces jointes de bug reports | `attachment_key` des lignes `bug_reports` |
| 10 | `revenucat_events` | scan filtré (pas de GSI `user_id`, table bornée) |
| 11 | `auth_tokens` puis `users` | **toujours en dernier** |

Les deux tuples `_USER_PARTITION_TABLES` / `_USER_INDEX_TABLES` sont déclaratifs exprès : ajouter une table user-scoped sans l'y ajouter est le bug que cette forme rend visible.

**Hors périmètre, assumé** : `media_idempotence` (PK `media_key`) et `feed_forecasts` (PK `feed_id`) décrivent du contenu, pas des personnes — aucun `user_id`, partagés entre tous les comptes ayant soumis le même média, non requêtables par user. `pricing_config` est de la config globale. Le bucket d'archives n'est pas balayé : ses clés sont partitionnées par date d'archivage, rien à énumérer par user (couvert par le lifecycle de task-243).

### Contenu partagé entre comptes

Les artifacts sont content-addressed : deux users qui importent le même épisode lisent le **même objet S3** (même `generation_fingerprint`). La purge ne supprime l'objet et son lock de génération que si **aucun sibling ne survit**. Sinon la ligne et le pointeur du user partent, les octets restent (`artifact_objects_kept_shared` dans le rapport). Limite connue : un artifact orphelin (plus atteignable par aucun `media_item_id` connu) est sur-conservé plutôt que supprimé à tort.

### Contrat avec l'archiveur (task-242)

Supprimer une ligne `processing_jobs` émet un `REMOVE` sur le stream, et l'archiveur écrirait la charge utile du job dans le bucket d'archives — c'est-à-dire **créerait** une copie des données pendant qu'on les efface. Chaque ligne est donc estampillée `purge_reason = "account_deletion"` (un `update_item`) juste avant son `delete_item`, signal porté par l'`OLD_IMAGE`. `infrastructure/terraform/modules/platform/archiving.tf` documente ce contrat ; le `filter_criteria` reste inchangé (un filtre de stream ne sait pas matcher l'absence d'un attribut). L'archiveur déployé aujourd'hui est un placeholder qui ignore les records, donc rien n'est cassé en attendant task-242.

### RevenueCat (AC#7)

Décision : **la suppression du compte n'annule pas l'abonnement store**, et l'app ne tente pas de le faire — seul l'App Store / Play Store peut annuler, aucune API RevenueCat ne le permet côté serveur. Les lignes `subscriptions` et `revenucat_events` sont purgées (données personnelles), l'abonnement store reste actif jusqu'à annulation par l'utilisateur. Conséquence surfacée **avant** confirmation : l'écran de suppression affiche, uniquement si `isSubscribed`, un encart "Deleting your account does not cancel your subscription" avec un lien direct vers `apps.apple.com/account/subscriptions` ou `play.google.com/store/account/subscriptions` selon la plateforme. Même mention ajoutée en privacy policy §8.2.

### Mobile

- `mobile/app/settings/delete-account.tsx` : écran dédié (route enregistrée dans `app/_layout.tsx`). Double barrière — case à cocher "I understand…" qui déverrouille le CTA, puis `Alert.alert` destructif natif. Un menu + alerte ne suffisait pas : ce qu'il faut lire avant de confirmer (ce qui est effacé, l'abonnement, comment obtenir une copie) ne tient pas dans un corps d'alerte.
- Après succès : `logout()` (purge le secure store) puis `router.replace("/(auth)/login")` — le guard de `(tabs)` ne couvre pas un écran du root stack, il ne peut donc pas rediriger tout seul.
- `mobile/src/services/accountService.ts` : `AccountService.deleteAccount(token)`, aucun `fetch` inline.
- `mobile/app/(tabs)/account.tsx` : `Export Data` supprimé (AC#8), ligne danger `Delete Account` ajoutée sous `Sign Out`. Tokens `theme.ts` uniquement, aucune nouvelle dépendance npm (`expo-linking` déjà présent). `npm run typecheck` OK, `npm run lint` sans nouveau warning sur les fichiers touchés.
- Le bouton mort `Settings` (`onPress={() => {}}`) reste : hors périmètre de cette tâche, à traiter avant review store.

### Docs

`docs/compliance/privacy-policy.md` : §7 (rétention réelle : effacement immédiat + expiration des backups chiffrés sous 35 jours), §8.1 accès et §8.3 portabilité traités manuellement par `privacy@mediasummarizer.com` **sous un mois** (AC#9), §8.2 chemin in-app + réserve abonnement store, §12 RGPD. `docs/compliance/google-play-data-safety.md` et `docs/V1_LAUNCH_PLAN.md` (lignes "Sécurité users legacy", "Suppression/export de compte", Phase 10 légal) alignés.

### Terraform — prérequis de déploiement

`bug_reports.tf` ajoute `s3:DeleteObject` sur le bucket de pièces jointes à la policy API/worker. **Appliquer Terraform avant de déployer l'API** : sinon tout user ayant un jour joint une capture d'écran reçoit un 500 au lieu d'une suppression (la purge est fail-fast par choix, pour rester réessayable).

### Vérification AWS dev (AC#10)

Script one-off hors repo (`/tmp/task224_verify.py`, non versionné) exécuté contre les vraies ressources dev (tables `-dev`, buckets `-dev`, index Algolia partagé, secrets `media-summarizer-runtime-dev`) : compte synthétique semé dans 22 tables + 8 buckets + Algolia, puis `purge_account`. **47 assertions vertes** (7 de contrôle du seed, 39 post-purge, 1 d'idempotence), dont : ligne `users` absente, `auth_tokens` vides (le compte ne peut plus s'authentifier), jobs / `user_media` / artifacts / pointeurs / folders / tags / rss / subscriptions / bug reports / usage / digests / follows / review schedule / watchers / revenucat events à zéro, objets S3 (transcript, traduction, audio job, `shared-audio/`, document, summary et quiz legacy, artifact, pièce jointe) supprimés, records Algolia à 0 hit. Le garde-fou de contenu partagé est vérifié positivement : l'objet et le lock encore référencés par l'artifact d'un autre compte **survivent**, la ligne et le pointeur du compte purgé partent. Second `purge_account` : aucune exception, tous les compteurs à zéro (AC#6). Données de vérification nettoyées, aucun résidu en dev.

Le seul reste non vérifiable ici est l'aller-retour HTTP sur la Lambda dev, qui n'embarque pas encore ce code : à valider après `terraform apply` + déploiement de l'image API.

### Pas de tests automatisés

Aucun test unitaire ni d'intégration n'a été ajouté (règle projet). La vérification s'est faite par le script one-off ci-dessus contre AWS dev.
<!-- SECTION:NOTES:END -->
