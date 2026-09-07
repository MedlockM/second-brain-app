---
id: task-369
title: >-
  Implémenter les notifications de Digest quotidien et hebdomadaire selon le
  benchmark validé (task-368)
status: To Do
assignee: []
created_date: '2026-09-06 16:13'
labels:
  - mobile
  - backend
  - feature
dependencies:
  - task-367
  - task-368
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qu'il faut lire d'abord

`docs/research/task-368-push-delivery/README.md` : **la décision de l'owner y est notée sous Owner Validation, et c'est elle qui fait foi**. Le chemin de livraison — Expo Push Service, AWS SNS ou APNs/FCM en direct — s'y trouve tranché, avec la forme du consommateur et les credentials.

Ne pas rejouer la comparaison ici, ne pas préférer une autre option à celle qui est validée. Si le README ne désigne aucune option, la tâche s'arrête et le dit : elle ne tranche pas à la place de l'owner. Si la décision renvoie à un fichier de complément du même dossier, le suivre.

## Le comportement attendu

Décisions owner du 2026-09-06 :

- **Daily** : une notification chaque jour à **18h30 heure locale de l'utilisateur**, portant sur les 24 heures glissantes qui précèdent.
- **Weekly** : une notification chaque **lundi à 9h30 heure locale**, portant sur la semaine écoulée, lundi à dimanche révolus.
- **Aucune notification quand la période est vide.** Rien d'enregistré, rien d'envoyé — pas de message « rien aujourd'hui ».
- **Aucune notification quand le fuseau est inconnu**, plutôt qu'un repli sur UTC qui sonnerait à une heure arbitraire. Le fuseau vient de task-367.
- La notification ouvre le Digest correspondant.

## L'existant sur lequel s'appuyer

- `media_summarizer/workers/digest/scheduler.py` **produit déjà** un message de notification sur une file SQS, mais **pour le weekly seulement** : le producteur daily est à écrire. Le nom de file est optionnel et non défini, et Terraform ne crée la file dans aucun environnement.
- **Aucune règle de planification ne vise ce worker** : les seules règles cron du dépôt visent `lambda_api`, `backup_library` et `media_lifecycle`.
- Le déclenchement à l'heure locale impose un balayage **toutes les 15 minutes** — et non toutes les 30, à cause des fuseaux à +5:45 et +12:45 — pour notifier ceux dont l'heure locale vient de franchir l'échéance. Le README de task-368 peut désigner un mécanisme moins coûteux : il prime.
- **L'opt-out existe déjà** : `UserDigestSettings` porte `digest_enabled`, `daily_digest_enabled` et `weekly_digest_enabled` (`core/models/digest.py`). Les réutiliser, ne pas créer un second jeu de réglages.
- Côté app, `expo-notifications` n'est pas installé : permission, enregistrement du token et gestion de l'ouverture sont à ajouter.

## Garde-fous

- **Une seule notification par période et par utilisateur.** Un balayage toutes les 15 minutes ne doit pas produire quatre envois par heure : l'envoi est marqué et l'idempotence est vérifiable.
- **Ne jamais écrire l'identité d'un testeur ni un token dans les logs.** Les tokens de push suivent la politique de `docs/DATA_RETENTION.md` et sont supprimés avec le compte — `core/services/account_deletion_service.py` doit les emporter.
- Le refus de la permission système est un état normal : l'app reste pleinement utilisable, sans relance insistante.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Pas de double chemin d'envoi, pas de mode dégradé conservé, pas de file « au cas où ». Le chemin retenu par le README est le seul implémenté.

## Notes pour l'owner (pas des ACs)

- **Ceci n'est pas une OTA.** `expo-notifications` est une dépendance native : le fingerprint bouge et la livraison exige un **build EAS sur les deux plateformes**. Palier gratuit : 15 builds iOS par mois.
- La réception réelle sur un téléphone ne peut pas être un critère d'acceptation : elle demande un build et un déploiement, tous deux postérieurs à l'agent. C'est ta vérification.
- Les credentials à téléverser sont énumérés dans le README de task-368.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le chemin de livraison implémenté est celui désigné sous Owner Validation dans docs/research/task-368-push-delivery/README.md, et les notes d'implémentation citent l'option retenue telle qu'elle y est nommée
- [x] #2 workers/digest/scheduler.py produit un message de notification pour le daily comme il le fait déjà pour le weekly
- [x] #3 Une planification invoque le worker toutes les 15 minutes, ou selon le mécanisme désigné par le README, et terraform validate passe
- [x] #4 La file de notification est créée par Terraform dans chaque environnement et la variable correspondante est renseignée, terraform validate passe
- [x] #5 Un consommateur lit la file et remet la notification au fournisseur retenu, le chemin de code étant complet et câblé de bout en bout
- [ ] #6 Le daily part à 18h30 et le weekly le lundi à 9h30, heure locale de l'utilisateur issue du fuseau stocké par task-367, vérifiable en simulant plusieurs fuseaux contre les enregistrements DynamoDB -dev
- [x] #7 Aucune notification n'est produite pour une période sans média, ni pour un compte dont le fuseau est inconnu, ni pour un compte dont digest_enabled, daily_digest_enabled ou weekly_digest_enabled le désactive
- [x] #8 Une seule notification est émise par période et par utilisateur malgré le balayage répété : l'envoi est marqué et un second passage dans la même période ne réémet rien, vérifiable sur -dev
- [x] #9 L'application demande la permission de notification, enregistre son token et ouvre le Digest correspondant à l'ouverture d'une notification, un refus de permission laissant l'app pleinement utilisable
- [x] #10 Aucun token ni aucune donnée identifiante n'apparaît dans les logs, et la suppression de compte de account_deletion_service.py emporte les tokens de l'utilisateur
- [x] #11 ruff et mypy passent sur media_summarizer/, npx tsc --noEmit et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Chemin de livraison retenu

Celui nommé sous `## Recommendation` de `docs/research/task-368-push-delivery/README.md`, que l'owner accepte via `owner_decision: ok` :

> **Option 1 — Expo Push Service, un token unique par appareil, consommateur SQS unique dans l'image worker existante, relance du contrôle des accusés de réception par `DelaySeconds=900` sur la même file.**

Le champ `**Decision**:` du README ne dit que « la recommandation » et `**Validated at**` est resté vide ; c'est le front-matter qui fait foi, et la section `## Recommendation` nomme l'option sans ambiguïté. À signaler à l'owner.

Les contraintes que le README reporte sur cette tâche sont respectées telles quelles : corps de notification réduit à un compteur (Expo relaie la charge utile et son personnel peut la voir en débogage), aucun credential push nouveau dans le dépôt ni dans le compte AWS, `getExpoPushTokenAsync()` côté client, et le contrôle des accusés de réception rejoué par un message `receipt_check` réenfilé sur la même file avec `delay_seconds=900`.

### Producteur — `workers/digest/scheduler.py`

Réécrit autour d'un seul balayage. Une règle EventBridge le déclenche sur `cron(0,15,30,45 * * * ? *)` ; à chaque passage il projette `id` + `iana_timezone` de `users`, écarte les comptes sans fuseau, et pour chacun des autres résout la fenêtre daily et la fenêtre weekly dans *leur* heure locale.

- `DigestWindow` porte désormais un quatrième champ, `send_at`. Il était nécessaire : la fenêtre weekly se **termine** le lundi à 00:00 mais s'**annonce** le lundi à 09:30, et lire `end` comme instant d'envoi aurait notifié le monde entier à minuit.
- L'échéance est une fenêtre de grâce (`SEND_GRACE = 1 h`) et non une égalité à la minute. Un tick en échec rejoué une minute plus tard, ou un fuseau à un décalage que la grille ne couvre pas, dégradent en notification tardive au lieu d'un silence définitif.
- La grille à 15 minutes est plus large que nécessaire : d'après le §10.1 du README, sur les 498 fuseaux IANA, 18h30 local et lundi 9h30 local ne tombent que sur les minutes UTC :00, :30 et :45. Le quatrième tir couvre un futur décalage au quart d'heure ; l'écriture conditionnelle rend une grille plus dense inoffensive.
- Trois abandons silencieux, dans cet ordre : réglages (`digest_enabled`, puis `daily_digest_enabled` / `weekly_digest_enabled`), période sans média, période déjà revendiquée.

Supprimés : `run(mode)` et son CLI `--mode`, `assemble_daily_digests`, `assemble_and_publish_weekly_digests`, `_send_weekly_digest_push_notification`, `_get_all_user_ids`, `_is_digest_enabled`, `digest_db.list_all_users_with_digest_enabled`, et le nom de file optionnel avec son court-circuit. Aucun double chemin conservé.

### Idempotence — `utils/digest_db.mark_digest_published`

Écriture conditionnelle sur `user_digests`, `attribute_exists(user_id) AND attribute_not_exists(published_at)`, juste avant l'enfilement : un seul appelant peut gagner, donc un seul message part par période et par compte quel que soit le nombre de passages.

Vérifié directement contre la vraie table `user_digests-dev` à l'AWS CLI, sans passer par le code de l'app :

| Appel | Résultat |
|---|---|
| 1ʳᵉ revendication sur une ligne existante (`weekly#2026-W36`) | succès |
| 2ᵉ revendication, même période, même compte | `ConditionalCheckFailedException` |
| Revendication sur une clé absente | `ConditionalCheckFailedException`, table toujours à 3 lignes — aucune ligne créée |

Le troisième cas est la garde qui empêche une période vide de matérialiser une ligne : sans `attribute_exists(user_id)`, un `update_item` sur une clé absente *créerait* la ligne.

### Consommateur — `workers/push_notification_worker.py`

Nouveau module, une file, deux formes de message routées sur `notification_type` :

- `send` : lit les appareils du compte, poste sur `https://exp.host/--/api/v2/push/send` par lots de 100, apparie tickets et destinataires avec `zip` (une réponse tronquée doit perdre des accusés de réception, jamais en attribuer un au mauvais appareil et supprimer un enregistrement vivant), supprime le token sur `DeviceNotRegistered`, puis réenfile un `receipt_check`.
- `receipt_check` : relit les accusés 15 minutes plus tard sur `getReceipts` et supprime les appareils condamnés. Un accusé encore en attente est compté et laissé — le même verdict revient sur le ticket de l'envoi suivant, et le balayage à 90 jours est le plancher. Pas de seconde échelle de relance.

`EXPO_ACCESS_TOKEN` est lu **optionnellement** : le mode « enhanced security » d'Expo est une bascule du dashboard EAS, une action owner et non un déploiement ; l'exiger casserait tous les envois tant que la valeur n'est pas déposée.

### Infrastructure

- `sqs.tf` : `push-notification-queue` et sa DLQ, `sqs_managed_sse_enabled = true` sur les deux (un `receipt_check` transporte des tokens), `maxReceiveCount = 3`, visibilité 180 s pour un worker à 60 s.
- `dynamodb_push_tokens.tf` : `user_push_tokens`, PK `user_id` / SK `push_token`, PITR, protection contre la suppression, **sans TTL ni `purge_at`** — un token mort est supprimé, jamais marqué, ce qu'impose `scripts/check_purge_at_writers.py`.
- `lambda_digest_scheduler.tf` : la Lambda du balayage, plus deux règles EventBridge sur la même fonction (le balayage, et la purge quotidienne des tokens à 90 jours) routées sur le `source` de l'événement.
- `lambda_workers.tf` : le consommateur `push_notification` et son event source mapping.
- `runtime_env.tf` : `PUSH_NOTIFICATION_QUEUE` et `USER_PUSH_TOKENS_TABLE`.
- `iam_lambda.tf` : la file est ajoutée à la policy **worker** uniquement. L'API n'en produit jamais de message — enregistrer un appareil n'écrit que DynamoDB.

Tout est dans `modules/platform`, partagé par les trois racines, donc les trois environnements l'obtiennent d'office. `terraform validate` passe sur `envs/dev`, `envs/prod` et `envs/staging` ; `terraform fmt -check -recursive modules/platform` est propre.

### Application

- `src/services/pushNotificationService.ts` : canal Android `digest` créé avant toute demande de token, permission demandée **au plus une fois par processus** (et jamais quand l'OS dit que la question est close), `getExpoPushTokenAsync({ projectId })` avec le projectId lu du manifeste, `POST` / `DELETE /api/push-token`. Un refus ou une absence de capacité push renvoient un état, ne lèvent rien et ne changent rien à l'interface.
- `src/hooks/usePushNotifications.ts` : enregistrement une fois par compte, réessayé à chaque retour au premier plan — ce qui rattrape le hors-ligne et la permission accordée après coup dans les réglages système, sans jamais reposer la question — et routage de l'ouverture d'une notification vers le Digest concerné.
- `app/_layout.tsx` : `PushNotificationGate` monté à côté de `SplashGate`, donc présent pour tous les points d'entrée.
- `app/(tabs)/digest.tsx` : l'onglet actif vit dans le paramètre de route `tab`, ce qui fait de « la notification ouvre le bon Digest » le même geste qu'un appui sur le segment. Tout le reste de l'écran appartient à une seule période et vit dans `DigestPeriodView`, monté avec `key={activeTab}` — le changement de période est un remontage, plus quatre remises à zéro à ne pas oublier. Aucun `setState` dans un effet (`react-hooks/set-state-in-effect` est une erreur ici).
- `src/contexts/AuthContext.tsx` : désenregistrement au mieux avant la déconnexion, sinon l'appareil resterait enregistré sous le compte sortant.
- `app.config.ts` : `"expo-notifications"` en chaîne nue dans `plugins` — c'est toute la configuration native (le plugin pose `aps-environment` et les entrées de manifeste Android, Expo détient la clé APNs et le compte de service FCM, et l'arbitrage sandbox/production se joue chez eux).

### Confidentialité

Aucun token n'est journalisé : le consommateur ne journalise que des compteurs, des plateformes et les codes d'erreur d'Expo, et `utils/logging_config.py` redacte `push_token` / `expo_push_token` par nom en filet de sécurité. `USER_PUSH_TOKENS_TABLE` figure dans `_USER_PARTITION_TABLES` de `account_deletion_service.py`, donc la suppression de compte emporte les appareils. `docs/DATA_RETENTION.md`, `docs/compliance/privacy-policy.md`, `apple-app-privacy.md` et `google-play-data-safety.md` nomment Expo et déclarent le token.

### Vérifications passées

`ruff check media_summarizer/` propre. `mypy media_summarizer/` : 180 fichiers, aucun problème. `terraform validate` : succès sur dev, prod et staging. `terraform fmt -check -recursive modules/platform` : propre. `scripts/check_purge_at_writers.py` et `scripts/check_env_example_complete.py` : OK. `npx tsc --noEmit` : aucune erreur. ESLint sur les six fichiers mobile touchés : aucune erreur.

### AC #6 non coché, et pourquoi

L'AC demande une vérification « en simulant plusieurs fuseaux contre les enregistrements DynamoDB -dev ». Ce n'est pas atteignable depuis ce worktree : un scan de `users-dev` compte **18 comptes, dont 0 portant un `iana_timezone`**. Le champ de task-367 existe et le client le renseigne, mais aucun build le portant n'a encore tourné contre dev, donc il n'y a aucun fuseau réel à simuler contre quoi que ce soit. Fabriquer des fuseaux et appeler les résolveurs serait un test unitaire déguisé, que ce projet interdit.

Ce qui est en revanche vérifié, c'est le comportement dérivé de cette absence, soit la seconde clause de l'AC #7 : un compte sans fuseau ne produit rien. Aujourd'hui `_list_accounts_with_timezone` écarte les 18 comptes de dev et le balayage n'émettrait aucune notification. Le reste de l'AC #6 (18h30 daily, lundi 9h30 weekly, dans le fuseau stocké) est implémenté dans `digest_service.DAILY_SEND_TIME` / `WEEKLY_SEND_TIME` et les deux résolveurs, et devient observable dès que l'owner dispose d'un build qui reporte un fuseau.

### Reste à la charge de l'owner (hors ACs)

1. `terraform apply` sur dev — la file `push-notification-queue-dev`, la table `user_push_tokens-dev` et les deux règles EventBridge n'existent pas encore (vérifié à l'AWS CLI : absentes de la liste des ressources dev).
2. Déposer les credentials push chez EAS : clé APNs `.p8` et compte de service FCM v1, comme énumérés au README de task-368. Rien n'entre dans ce dépôt.
3. **Build EAS sur les deux plateformes.** Ce n'est pas une OTA : `expo-notifications` est une dépendance native et `runtimeVersion` est en politique `fingerprint`, donc aucune mise à jour ne peut porter les notifications à un binaire déjà installé.
4. Sur appareil : accepter la permission, vérifier la réception d'une notification de Digest, vérifier qu'un appui ouvre le bon onglet, puis refuser la permission sur un second appareil et vérifier que l'app reste pleinement utilisable.
5. Facultatif : activer « enhanced security » chez Expo et déposer `EXPO_ACCESS_TOKEN` dans le secret runtime. Le code le lit s'il est présent et s'en passe sinon.
<!-- SECTION:NOTES:END -->
