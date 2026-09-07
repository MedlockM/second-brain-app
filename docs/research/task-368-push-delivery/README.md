---
owner_decision: pending   # pending | ok | abandoned | redo | more
---

# Benchmark : chemin de livraison des notifications push mobiles du Digest

## Owner Validation

**Decision**: _(à remplir par l'owner après relecture — texte libre décrivant la décision finale : accept recommandation X, reject parce que Y, accept with modifications Z, OU, si redo, les consignes précises de correction à intégrer au prochain passage)_
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

**Option 1 — Expo Push Service, un token unique par appareil, consommateur SQS unique dans l'image worker existante, relance du contrôle des accusés de réception par `DelaySeconds=900` sur la même file.**

Cinq arguments, dans l'ordre de force.

1. **C'est la seule option où aucun credential push n'entre dans ce dépôt ni dans son compte AWS.** Les trois options exigent *le même jeu* de credentials (une clé APNs `.p8`, un compte de service Firebase FCM v1, un projet Firebase, `google-services.json`). Elles ne diffèrent que par l'endroit où ces valeurs sont déposées. Avec Expo, les deux vont sur les serveurs EAS, qui détiennent **déjà** le certificat de distribution iOS, les profils de provisioning et le keystore Android. Zéro clé nouvelle dans le secret runtime, zéro nouvelle procédure `put-secret-value`, zéro nouveau secret GitHub. SNS et le direct ajoutent chacun deux valeurs à faire vivre côté dépôt — voir §5.2 et §9.4, qui montrent que dans le cas SNS cela oblige à un `terraform apply` alimenté en clair, donc à un domicile de credential supplémentaire.
2. **Le côté mobile ne peut pas discriminer, donc l'arbitrage se joue entièrement côté backend.** `expo-notifications` doit être installé dans les trois cas : c'est le seul chemin de *réception* dans un projet Expo SDK 55 en CNG, et c'est son config plugin qui pose l'entitlement `aps-environment`. Le fingerprint bouge donc identiquement dans les trois options (§13). La seule différence côté client est une ligne : `getExpoPushTokenAsync()` au lieu de `getDevicePushTokenAsync()`.
3. **Un token, un magasin, une taxonomie d'erreur.** Expo rend un jeton `ExponentPushToken[…]` valable pour les deux plateformes, qui « never expires », reste stable à travers les mises à jour et — sur iOS — survit à une désinstallation/réinstallation. L'invalidation arrive sous une seule forme, `DeviceNotRegistered`. En face : deux taxonomies natives à écrire et à tenir (APNs `410 Unregistered` + FCM `404 UNREGISTERED` / `400 INVALID_ARGUMENT`), ou, pour SNS, un **objet d'état supplémentaire par appareil** (l'`EndpointArn`) à réconcilier à chaque lancement d'app selon le pseudo-code d'AWS lui-même (§5.3).
4. **Le coût ne discrimine pas.** Aux quatre volumes chiffrés en §11 — 20, 1 000, 10 000, 100 000 comptes — les trois options coûtent la même chose à 4 $/mois près, et cette différence n'apparaît qu'à 100 000 comptes, où SNS devient la seule des trois à facturer le message. Le vrai poste de coût est ailleurs et il est commun aux trois : les lectures DynamoDB du balayage des fuseaux (§10).
5. **La réversibilité est bornée et connue.** Le producteur SQS existant ne nomme ni token, ni endpoint, ni plateforme (§8.1) : il survit **intact** dans les trois options. Changer de chemin de livraison, plus tard, c'est réécrire une fonction d'envoi dans un seul module de consommateur, retourner une ligne côté client et attendre que les appareils se réenregistrent au prochain lancement. Rien n'est en circulation qu'on ne puisse réémettre (`CLAUDE.md`, « Nothing is deployed yet ») : ce n'est pas une migration, c'est une réémission.

**Compromis explicitement acceptés :**

- **Un relais tiers sans SLA sur le chemin.** La documentation Expo l'écrit noir sur blanc : « The Expo push notification service does not have an SLA ». Ce qu'on perd si le relais tombe est **la notification de cette fenêtre-là**, pas le digest : `get_or_assemble_daily_digest` / `get_or_assemble_weekly_digest` écrivent dans `user_digests` indépendamment, et l'app le lit au lancement. Le rayon de souffle est une notification manquée, pas une donnée perdue. Ni SNS ni le direct ne suppriment ce risque, ils le déplacent : APNs et FCM ont aussi des pannes, et SNS ajoute son propre étage.
- **Expo voit passer le contenu de la notification.** La FAQ Expo est explicite : le contenu n'est pas stocké en base (« only in memory and in message queues ») mais « may be seen by Expo staff » pendant un débogage actif. **Contrainte à reporter sur task-369** : le corps de la notification doit rester un compteur, comme le producteur existant le fait déjà (« You have N items in your weekly digest. ») — aucun titre de média, aucun extrait. Sous cette contrainte, Expo ne voit jamais de contenu utilisateur, seulement « quelqu'un a N éléments ».
- **Le contrôle des accusés de réception demande une passe différée.** C'est le point où Expo est objectivement le moins bon des trois : APNs et FCM répondent l'invalidation de façon **synchrone** (410 / 404), SNS la pousse en événement et désactive l'endpoint tout seul ; Expo veut qu'on relise les *receipts* environ 15 minutes plus tard. Coût réel, mesuré sur le dépôt : **zéro nouvelle infrastructure**, parce que `utils/sqs.send_message` accepte déjà `delay_seconds` et que le maximum SQS (900 s) est exactement la fenêtre recommandée par Expo. Le consommateur se réenfile un message `receipt_check` portant les identifiants de tickets (§8.3).
- **Le token Expo n'est pas portable.** Un `ExponentPushToken` ne se convertit pas en token natif. Si l'option est abandonnée un jour, il faut un build EAS de plus et attendre le réenregistrement des appareils. Acceptable ici, et seulement ici, parce qu'il n'existe aucun parc installé qu'on ne puisse réémettre.
- **Le plafond de 600 notifications/s par projet est fixe et non négociable.** C'est le premier plafond dur qu'atteindrait l'une des trois options côté fournisseur, et il ne mord qu'autour de 10⁶ comptes (§11.5). À ce moment-là seulement, l'argument coût/plafond basculerait vers SNS ou le direct.
- **Une option 0 existe et est écartée, pas ignorée** : les notifications **locales** programmées d'`expo-notifications` (triggers `DAILY` / `WEEKLY`) coûtent zéro, ne demandent aucun credential, aucun token, aucun backend et **suivent nativement le fuseau de l'appareil** — donc elles annulent toute la question secondaire du §10. Elles sont écartées pour une raison unique et dirimante : l'appareil ne sait pas si le digest de la période est vide, et task-369 exige de ne pas notifier une période vide. Détail en §7.

---

## 0. Périmètre, mode, et ce que ce document ne fait pas

Mode **initial** : le dossier `docs/research/task-368-push-delivery/` n'existait pas avant ce passage.

Ce document tranche **un seul choix** : par quel chemin le backend fait apparaître une notification système sur l'appareil. À l'écran, les trois options produisent le même pixel ; l'utilisateur ne peut pas les distinguer. Tout le reste est invisible, et c'est exactement ce qui est comparé ici.

Hors périmètre, par la description de la tâche :

- **Le fuseau de l'utilisateur** — nom IANA stocké sur `User`, c'est task-367. Ce document suppose seulement que le champ existera et qu'un fuseau inconnu signifie « pas de notification ».
- **L'implémentation** — c'est task-369, qui doit lire la décision de l'owner ci-dessus, pas cette recommandation.
- **Aucun code applicatif, aucune dépendance, aucun fichier Terraform n'est modifié par cette tâche.** Les seuls fichiers écrits sont ce document et le fichier de tâche.

Date de collecte de toutes les sources et de tous les tarifs : **2026-09-07**. Région de référence : **eu-west-3 (Europe, Paris)**, celle du dépôt.

---

## 1. L'existant, mesuré

Sept faits relevés dans le dépôt et sur le compte dev, parce que la recommandation s'y appuie.

| Fait | Où | Valeur |
|---|---|---|
| Le producteur push existe déjà, pour le weekly seulement | `media_summarizer/workers/digest/scheduler.py:215-257` | `_send_weekly_digest_push_notification()` publie sur SQS |
| Le nom de file est **optionnel**, unique cas du dépôt | `scheduler.py:38-47` | `PUSH_NOTIFICATION_QUEUE` lu avec un défaut vide |
| Le producteur *daily* n'envoie rien | `scheduler.py:127-161` | `assemble_daily_digests()` assemble et sort |
| Le scheduler n'est **pas** une Lambda | `media_summarizer/workers/lambda_handlers.py` | aucun handler digest ; entrée CLI `__main__` uniquement |
| Aucune file push en Terraform | `infrastructure/terraform/modules/platform/sqs.tf` | aucune ressource `push_notification` |
| `expo-notifications` absent | `mobile/package.json` | aucune dépendance de notification |
| Volume actuel | `aws dynamodb describe-table --table-name users-dev` | **18 items, 5 246 octets** → ~291 o/utilisateur |

Deux précédents du dépôt sont réutilisables tels quels et cités plus loin :

- **Une Lambda planifiée, hors du map `local.workers`** : `infrastructure/terraform/modules/platform/lambda_media_lifecycle.tf`. Le commentaire y explique pourquoi (« Declared here rather than in local.workers because that map is SQS-shaped ») et comment la CI la déploie quand même (découverte par tag `Environment` plus préfixe de nom `media-summarizer-worker-`). Elle porte un `aws_cloudwatch_event_rule` avec `schedule_expression`, un `aws_cloudwatch_event_target` avec un `input` JSON, et un `aws_lambda_permission`. C'est le gabarit exact du scheduler digest.
- **`aws_scheduler_schedule` est déjà utilisé, avec `schedule_expression_timezone`** : `backup_library.tf:268-297` (valeur `"UTC"`). L'alternative « une planification par fuseau » du §10.4 est donc à une ligne d'un type de ressource déjà présent dans l'état.

Enfin, la contrainte qui gouverne §9 : `infrastructure/terraform/modules/platform/secrets.tf:8-11` — « Terraform creates the secret SHELL ONLY and never writes its value (task-221 §7.3) ». Et `.github/workflows/terraform-dev.yml` **ne passe aucune variable** à Terraform ; prod reste « a manual `terraform apply` from the owner's machine ».

---

## 2. Le tronc commun : ce qui ne dépend pas du choix

Avant de comparer, il faut isoler ce qui est identique dans les trois options — sinon on attribue à une option un coût que les trois portent.

| Élément | Identique dans les 3 options ? | Détail |
|---|---|---|
| `expo-notifications` installé et déclaré dans `plugins` | **Oui** | seul chemin de réception ; son plugin pose `aps-environment` |
| Build EAS sur les deux plateformes (pas d'OTA) | **Oui** | dépendance native → le fingerprint bouge |
| Permission `POST_NOTIFICATIONS` (Android 13+) et prompt iOS | **Oui** | `requestPermissionsAsync()` |
| Canal de notification Android (`setNotificationChannelAsync`) | **Oui** | et obligatoirement **avant** la demande de token |
| Projet Firebase, `google-services.json`, `android.googleServicesFile` | **Oui** | requis pour qu'un appareil Android obtienne un token FCM, y compris via Expo |
| Clé APNs `.p8` (authentification par jeton) | **Oui** | seul l'endroit du dépôt change |
| Une table de tokens côté backend | **Oui** | §12 |
| Une file SQS `push-notification` en Terraform, dans **tous** les environnements | **Oui** | plus une DLQ, sur le patron de `sqs.tf` |
| Le producteur `scheduler.py` | **Oui, intact** | §8.1 |
| Une Lambda planifiée pour le balayage des fuseaux | **Oui** | §10 |
| Une Lambda consommatrice branchée sur la file | **Oui** | seul son module d'envoi diffère |

**Conséquence directe** : ni le mobile, ni le fingerprint, ni Firebase, ni la clé APNs, ni la file, ni le producteur, ni le balayage ne peuvent servir d'argument pour ou contre une option. Le choix se réduit à quatre questions : *où vivent les credentials*, *combien d'objets d'état par appareil*, *comment l'invalidation revient*, et *qui est sur le chemin*.

---

## 3. Tableau comparatif

### 3.1 Vue synthétique

| Critère | **Expo Push Service** | **AWS SNS mobile push** | **APNs + FCM en direct** |
|---|---|---|---|
| **Credentials à obtenir** | clé APNs `.p8` + compte de service FCM v1 | idem | idem |
| **Où ils sont déposés** | serveurs **EAS** (2 téléversements) | **application de plateforme SNS**, 3 fois (APNS, APNS_SANDBOX, GCM) | **secret runtime `media-summarizer-runtime-<env>`**, 3 environnements |
| **Nouvelle valeur secrète côté dépôt / AWS** | **aucune** | oui, et fournie en clair au moment du `terraform apply` (§9.4) | oui, 4 valeurs, rotation à écrire |
| **Nombre d'intégrations d'envoi à maintenir** | **1** | 1 (via `boto3`) | **2** (HTTP/2 + JWT ES256 ; OAuth2 + JWT RS256) |
| **Token côté client** | `getExpoPushTokenAsync()` — 1 token, 2 plateformes | `getDevicePushTokenAsync()` — natif, par plateforme | idem SNS |
| **Objets d'état par appareil** | **1** (le token) | **2** (token + `EndpointArn`) | **1** (le token) |
| **Sandbox APNs contre production** | **géré par Expo** | 2 applications de plateforme, et le consommateur doit savoir d'où vient le token | le consommateur choisit l'hôte |
| **Invalidation d'un appareil désinstallé** | `DeviceNotRegistered` dans le **receipt**, passe différée d'environ 15 min | événement `EventDeliveryFailure` sur un topic, endpoint désactivé automatiquement | **synchrone** : APNs `410`, FCM `404 UNREGISTERED` |
| **Accusés de réception** | tickets puis receipts (`getReceipts`), receipts purgés à 24 h | delivery status logging vers CloudWatch Logs, succès échantillonnés | code HTTP de la réponse, immédiat |
| **Observabilité des échecs** | corps de réponse HTTP et receipts → logs Lambda, métriques à écrire | CloudWatch Logs + rôle IAM dédié + topic d'événements | logs Lambda, métriques à écrire |
| **Nouvelles dépendances Python** | **0** (`httpx` présent) | **0** (`aioboto3` présent) | `h2` via `httpx[http2]`, plus `hpack` et `hyperframe` |
| **Coût du message** | **0 $, sans limite de volume documentée** | 0 $ jusqu'à 1 M/mois, puis **0,67 $/M**, plus 0,50 $/M de requêtes API | **0 $** (ni APNs ni FCM ne facturent) |
| **Plafond de débit** | **600 notif/s par projet**, fixe | quota régional Service Quotas, ajustable — valeur non vérifiée (§16) | FCM **600 000 msg/min par projet** ; APNs non documenté |
| **Dépendance tierce** | Expo, plus Apple/Google | AWS, plus Apple/Google | Apple/Google seulement |
| **SLA** | **aucun**, écrit dans la doc | SLA de service SNS (pas un SLA de délivrance) | aucun |
| **Réversibilité** | 1 ligne client + 1 module serveur, **mais token non portable** | 1 module serveur ; token natif **portable** vers le direct | 1 module serveur ; token portable vers SNS |
| **Producteur SQS existant** | **intact** | **intact** | **intact** |
| **Forme du consommateur** | 1 Lambda SQS, 2 sortes de messages (`send`, `receipt_check`) | 1 Lambda SQS, plus la réconciliation d'endpoints dans l'API `/push-token`, plus un abonné au topic d'événements | 1 Lambda SQS, 2 clients HTTP |
| **Impact sur le fingerprint mobile** | **identique aux trois** | identique | identique |
| **Effort d'implémentation** | **le plus faible** | moyen (endpoints, création hors Terraform) | le plus élevé (2 protocoles, 2 caches de jeton) |

### 3.2 Ce que chaque option coûte *en plus* du tronc commun

| | Expo | SNS | Direct |
|---|---|---|---|
| Modules serveur nouveaux | 1 (envoi + receipts) | 2 (envoi + réconciliation d'endpoints) | 2 (APNs, FCM) + 2 caches de jeton d'authentification |
| Ressources Terraform nouvelles, hors tronc commun | **0** | 3 applications de plateforme (créées **hors** Terraform, §9.4), 1 topic d'événements, 1 abonnement, 1 rôle IAM pour CloudWatch Logs | 0 |
| Clés à faire tourner | 0 côté dépôt | 2 | 4 |
| Endroits où une clé push existe | 1 (EAS) | 2 (SNS, plus le domicile CI de la valeur) | 2 (Secrets Manager, plus la machine de l'owner pour prod) |
| Appels réseau par notification | 1 POST par lot de 100 | 1 `Publish` **par appareil** | 1 POST par appareil et par plateforme |

---

## 4. Option 1 — Expo Push Service

### 4.1 Mécanique

Le client appelle `Notifications.getExpoPushTokenAsync({ projectId })` et obtient un jeton `ExponentPushToken[…]`. Le backend fait un `POST` sur `https://exp.host/--/api/v2/push/send` avec un tableau d'au plus 100 messages ; Expo répond un **push ticket** par message, portant un identifiant. Environ 15 minutes plus tard, un `POST` sur `https://exp.host/--/api/v2/push/getReceipts` avec au plus 1 000 identifiants rend les **push receipts**, dont le champ d'erreur peut valoir `DeviceNotRegistered`.

Limites documentées : 600 notifications par seconde et par projet (`TOO_MANY_REQUESTS`), 100 notifications par requête (`PUSH_TOO_MANY_NOTIFICATIONS`), 1 000 receipts par requête (`PUSH_TOO_MANY_RECEIPTS`), receipts purgés après 24 h. Sécurité renforcée facultative : un jeton d'accès EAS passé en en-tête `Authorization`, activable depuis le tableau de bord ; sans lui, un token de push qui fuite permet à un tiers d'envoyer des notifications au nom du projet (l'erreur correspondante est `UNAUTHORIZED`).

### 4.2 Ce qui plaide pour

- Un seul token pour les deux plateformes, donc un seul schéma de stockage, un seul chemin d'envoi, un seul code d'erreur d'invalidation.
- Le token « never expires », reste stable à travers les mises à jour, et survit sur iOS à une désinstallation puis réinstallation. Sur Android, « reinstalling the app may result in the token changing » — sans conséquence, l'app renvoie son token à chaque lancement.
- **Aucune clé dans le compte AWS.** C'est le point qui pèse le plus dans un dépôt public dont `secrets.tf` interdit à Terraform d'écrire une valeur de secret.
- Expo gère l'aiguillage sandbox/production d'APNs. Avec cinq profils de build (`development`, `development-simulator`, `preview`, `internal`, `production` dans `mobile/eas.json`), dont deux en Debug et trois en Release, c'est une source d'erreur réelle qui disparaît.
- Zéro dépendance Python nouvelle : `httpx` est déjà une dépendance du projet.
- Payload : un champ `data` d'environ 4 KiB, quatre priorités, et un destinataire qui accepte un tableau — le lot naturel est déjà celui de l'API.

### 4.3 Ce qui plaide contre

- Un tiers de plus sur le chemin, sans SLA, avec un accès possible au contenu pendant un débogage. Mitigé par la contrainte « corps réduit à un compteur ».
- La passe de receipts est une mécanique en deux temps. Réponse concrète en §8.3 : elle ne coûte aucune infrastructure nouvelle.
- Le token n'est pas portable : sortir d'Expo demande un build de plus.
- Le plafond de 600 notifications par seconde est fixe, non ajustable par demande de quota.

---

## 5. Option 2 — AWS SNS mobile push

### 5.1 Mécanique

Une **application de plateforme** par couple (plateforme, environnement APNs) : `APNS`, `APNS_SANDBOX`, `GCM`. Chaque appareil devient un **endpoint** via `CreatePlatformEndpoint(PlatformApplicationArn, Token)`, et on publie sur son `EndpointArn`. FCM v1 est supporté : la référence d'API précise que « for GCM (Firebase Cloud Messaging) using token credentials, there is no `PlatformPrincipal` » et que « the `PlatformCredential` is a JSON formatted private key file ». Pour APNs par jeton : le principal est l'identifiant de la clé de signature, le credential est la clé de signature elle-même, complétés par l'identifiant d'équipe et le bundle identifier.

SNS mobile push est disponible en **Europe (Paris)** ; la région n'est pas un obstacle.

### 5.2 L'objection décisive : le credential doit exister en clair au moment du `terraform apply`

L'argument `platform_credential` de `aws_sns_platform_application` est **requis**. La documentation du provider précise que la valeur n'est conservée dans l'état que sous forme de *hash* — l'état n'est donc pas le problème. Le problème est l'**alimentation** :

- Via `data "aws_secretsmanager_secret_version"` : refusé. Les attributs d'une source de données sont écrits **en clair** dans l'état, donc le `.p8` et la clé privée du compte de service Google atterriraient dans le bucket d'état, exactement ce que `secrets.tf` et task-221 §7.3 interdisent.
- Via une `variable` : il faut la fournir à chaque run. Or `.github/workflows/terraform-dev.yml` ne passe **aucune** variable ; il faudrait y ajouter deux secrets GitHub `TF_VAR_*`. Et prod « stays a manual `terraform apply` from the owner's machine » : l'owner devrait détenir les deux fichiers sur sa machine à chaque apply.
- Via une création **hors Terraform** (`aws sns create-platform-application`), puis un `import` ou une simple variable d'ARN : c'est la seule voie propre. Elle fonctionne, mais elle annule l'argument principal de SNS (« tout est décrit en Terraform »), puisque la ressource pivot de l'option devient une ressource manuelle, non décrite, à recréer à la main dans chaque environnement.

Autrement dit : soit deux clés entrent dans l'état ou dans un troisième coffre, soit la ressource pivot sort de l'IaC. Aucune des deux issues n'est meilleure que « les clés restent chez EAS ».

### 5.3 L'objection d'exploitation : un objet d'état de plus par appareil

Le guide SNS impose de stocker « all device tokens, corresponding Amazon SNS endpoint ARNs, and timestamps on your application server », et son pseudo-code recommandé, à exécuter **à chaque démarrage de l'app**, est :

```
retrieve the latest device token from the mobile operating system
if (the platform endpoint ARN is not stored)
  # this is a first-time registration
  call CreatePlatformEndpoint and store the returned ARN
else
  call GetEndpointAttributes on the stored endpoint ARN
  if (the endpoint is not found)
    call CreatePlatformEndpoint and store the returned ARN
  else if (the stored token differs, or the endpoint is disabled)
    call SetEndpointAttributes to update the token and re-enable it
```

Traduction pour ce dépôt : l'endpoint `POST /api/push-token` ne fait plus un simple `put_item`, il fait un aller-retour SNS de 1 à 3 appels, avec la gestion des cas « endpoint introuvable » et « endpoint désactivé ». Ces appels sont facturés comme requêtes API SNS. C'est du code, des erreurs à traiter, et une seconde vérité (l'endpoint) à garder synchrone avec la première (le token) — pour un pixel identique à l'écran.

### 5.4 Ce qui plaide pour

- Cohérence avec le backend : `aioboto3` est déjà là, l'IAM est déjà le mécanisme d'autorisation, les métriques arrivent dans CloudWatch sans écrire de code.
- **Invalidation poussée** : l'événement `EventDeliveryFailure` sur un topic, avec un type d'échec `InvalidPlatformToken`, et SNS **désactive lui-même** l'endpoint sur un `UNREGISTERED` (HTTP 404) renvoyé par FCM. Aucune passe différée à écrire. C'est le meilleur des trois sur ce critère précis.
- Delivery status logging vers CloudWatch Logs, avec la réponse brute du fournisseur, le temps d'attente et le code de statut — utile pour diagnostiquer une panne côté Apple ou Google.
- Token natif, donc portable vers l'option 3 sans nouveau build.

### 5.5 Ce qui plaide contre

- Les objections de §5.2 et §5.3.
- Trois applications de plateforme, et donc trois credentials à faire tourner dans une console AWS.
- L'échantillonnage : tous les échecs de livraison génèrent un log, mais les succès sont échantillonnés par un pourcentage configurable — l'observabilité complète a donc un coût de logs.
- Un `Publish` **par appareil** : pas de lot. À 100 000 comptes, cela fait environ 4,1 M d'appels sortants par mois depuis la Lambda, contre environ 41 000 POST en lots de 100 avec Expo.
- La seule des trois options qui facture le message.

---

## 6. Option 3 — APNs + FCM en direct

### 6.1 Mécanique

**APNs** : connexion HTTP/2 vers `api.push.apple.com` (production) ou `api.sandbox.push.apple.com` (développement), requête `POST` sur `/3/device/<token>`, en-têtes `apns-topic` valant le bundle identifier, `apns-push-type`, et `authorization` portant un JWT. Le JWT est signé **ES256** avec le `.p8`, son `kid` est l'identifiant de la clé et son `iss` l'identifiant d'équipe ; sa durée de vie est au plus une heure et Apple demande de ne pas le régénérer plus souvent que toutes les 20 minutes. Réponses à traiter : `410 Unregistered`, `400 BadDeviceToken`, `403 ExpiredProviderToken`, `429 TooManyRequests`.

**FCM v1** : requête `POST` sur `https://fcm.googleapis.com/v1/projects/{project_id}/messages:send`, en-tête `Authorization` portant un jeton OAuth2 obtenu par échange d'un JWT RS256 signé avec la clé du compte de service (scope de messagerie Firebase). Quota de 600 000 messages par minute et par projet ; supprimer le token sur `404 UNREGISTERED`, vérifier le payload sur `400 INVALID_ARGUMENT`.

### 6.2 Ce qui plaide pour

- Aucun intermédiaire : le rayon de souffle d'une panne se réduit à Apple et Google, que nulle option ne peut éviter.
- Invalidation **synchrone**, dans la réponse même de l'envoi. Pas de passe différée, pas de topic, pas d'endpoint.
- Coût nul, et aucun plafond imposé par Expo ni par AWS.
- Accès à toutes les options fines des deux protocoles.

### 6.3 Ce qui plaide contre

- **Deux protocoles, deux formats de payload, deux taxonomies d'erreur, deux mécanismes d'authentification à cache** — dans une Lambda qui, sinon, ferait un seul POST.
- Une dépendance nouvelle : HTTP/2 est **obligatoire** pour APNs, donc `httpx[http2]` et son `h2`. Ce sont des paquets Python purs, donc aucun risque de wheel binaire incompatible sur l'image arm64 — mais c'est une dépendance de plus dans une image partagée par toutes les fonctions.
- **Quatre valeurs nouvelles dans `media-summarizer-runtime-<env>`**, dont la clé privée d'un compte de service Google Cloud, dont le rayon de souffle dépasse le push. Chacune avec sa procédure de dépôt et sa rotation.
- Le compte Apple **plafonne à 2 clés APNs**. Ce n'est pas bloquant, mais c'est une ressource rare à ne pas gaspiller entre EAS, SNS et un secret backend.
- Le choix sandbox/production d'APNs remonte dans le code du consommateur, qui doit donc savoir de quel type de build provient chaque token — cinq profils de build à ne pas confondre.
- Le gain (« full access to all FCM and APNs features », dit la documentation Expo) n'achète rien pour un titre, un corps et un lien profond.

---

## 7. Option 0, documentée et écartée — les notifications locales programmées

À mentionner parce qu'elle rend la question secondaire du §10 sans objet et qu'elle coûte zéro.

`expo-notifications` sait programmer une notification **sur l'appareil**, sans réseau, sans token, sans credential, avec un déclencheur `DAILY` (heure et minute) ou `WEEKLY` (jour, heure, minute). Sur iOS, ces deux formes se ramènent à un `UNCalendarNotificationTrigger`. **L'appareil applique son propre fuseau** : 18h30 locale est exact par construction, sans balayage, sans champ de fuseau, sans lecture DynamoDB, sans Lambda, sans file.

**Pourquoi c'est écarté** : l'appareil ne sait pas ce que contient le digest. task-369 exige de ne pas notifier une période vide, et « vide » est une propriété serveur (`digest.media_items`). Une notification locale notifierait tous les jours, y compris les jours sans rien — ce qui est précisément la mécanique qui fait désactiver les notifications d'une app.

Une variante hybride existe : le serveur pousse une notification silencieuse et l'app reprogramme sa notification locale. Elle additionne les deux complexités, dépend du bon vouloir d'iOS pour réveiller l'app en arrière-plan, et n'économise que le balayage. Écartée.

---

## 8. Le producteur SQS existant, et la forme du consommateur

### 8.1 Le producteur survit intact dans les trois options — et voici pourquoi

Le message publié par `_send_weekly_digest_push_notification` porte cinq champs : l'identifiant d'utilisateur, un type de notification (`weekly_digest_published`), un titre, un corps calculé à partir du nombre d'éléments, et un bloc `data` contenant le type de digest, la clé de période et ce même nombre.

Il ne nomme **ni token, ni `EndpointArn`, ni plateforme, ni fournisseur**. C'est un ordre métier (« notifie cet utilisateur de ceci »), pas un ordre de transport. Le choix du chemin de livraison est donc entièrement encapsulé dans le consommateur : **aucune** des trois options ne demande de toucher à cette forme de message. C'est le meilleur argument objectif en faveur de la réversibilité du choix, quel qu'il soit.

### 8.2 Ce qui change dans `scheduler.py`, identiquement dans les trois options

| # | Changement | Pourquoi | Où |
|---|---|---|---|
| 1 | Rendre `PUSH_NOTIFICATION_QUEUE` **obligatoire** et supprimer le court-circuit qui rend la fonction inerte quand la variable est vide | La file existera dans tous les environnements. Le dépôt interdit les couches de compatibilité : on supprime l'ancien comportement, on ne le garde pas en repli. | `scheduler.py:38-47` et `scheduler.py:223-229` |
| 2 | Ajouter le producteur **daily** | `assemble_daily_digests()` n'envoie rien aujourd'hui. Même forme de message, avec un type `daily_digest_published`. | `scheduler.py:127-161` |
| 3 | Ne pas notifier une période vide | Le weekly le fait déjà (il exige `digest.media_items` non vide) ; le daily doit le faire aussi. | idem |
| 4 | Idempotence par période | Le balayage tire 72 fois par jour ; le weekly est protégé par sa condition `status != PUBLISHED`, le daily ne l'est pas. Il faut un marqueur de notification par couple (utilisateur, période). | table `user_digests` |
| 5 | Ne balayer que les utilisateurs **dus** | `_get_all_user_ids()` fait un `Scan` complet, appelé une fois par mode. Multiplié par 72 tirs par jour, c'est le seul poste de coût réel (§10). | `scheduler.py:50-71` |
| 6 | Devenir une **Lambda** | Aucun handler digest n'existe. Ce n'est pas un consommateur SQS, donc pas `_build_handler` : c'est un tick planifié, exactement comme `media_lifecycle_handler`. | `lambda_handlers.py` |

Le point 6 mérite une précision Terraform : la nouvelle fonction ne va **pas** dans le map `local.workers` de `lambda_workers.tf`, parce que ce map est indexé par ARN de file et crée un event source mapping par entrée. Elle va dans son propre fichier, sur le modèle de `lambda_media_lifecycle.tf`, et la CI la déploiera parce qu'elle portera le préfixe de nom `media-summarizer-worker-` et le tag `Environment`.

### 8.3 La forme du consommateur, option par option

Dans les trois cas : **une** Lambda de plus, déclarée comme entrée du map `local.workers` du module platform, avec `image_config.command` pointant sur un nouveau handler de `lambda_handlers.py` construit par `_build_handler`, un retour `batchItemFailures`, et une DLQ à trois tentatives comme les treize autres. C'est le patron existant, rien de neuf.

**Option 1 — Expo.** Un consommateur, **deux sortes de messages sur la même file** :

```
message "send"          -> lire les tokens de user_id (Query sur user_push_tokens)
                        -> POST /--/api/v2/push/send, par lots de 100
                        -> collecter les identifiants de tickets
                        -> se réenfiler {"notification_type": "receipt_check",
                                         "ticket_ids": [...], "token_map": {...}}
                           avec delay_seconds=900

message "receipt_check" -> POST /--/api/v2/push/getReceipts, par lots de 1000
                        -> pour chaque receipt en erreur DeviceNotRegistered :
                           supprimer le token correspondant
```

Trois faits vérifiés rendent ce dessin gratuit :

1. `media_summarizer/utils/sqs.py:61-66` — la signature de `send_message` expose déjà un paramètre `delay_seconds` qu'elle traduit en `DelaySeconds`.
2. Le maximum SQS pour ce délai est de **15 minutes**, et la recommandation d'Expo est de vérifier les receipts « 15 minutes after sending ». Les deux coïncident exactement.
3. Aucune table, aucune règle EventBridge, aucune seconde Lambda. Le surcoût SQS est d'un message par lot de 100 notifications, soit **1 %**.

**Option 2 — SNS.** Le consommateur lit les `EndpointArn` de l'utilisateur et fait un `Publish` par endpoint, avec une structure de message JSON portant un payload par plateforme. Mais l'option demande **un second chemin** hors du consommateur : la réconciliation d'endpoints du §5.3, qui vit dans l'API `POST /api/push-token` ; et **un troisième** : un abonné (Lambda ou file) au topic d'événements de plateforme, pour traiter `EventDeliveryFailure` et supprimer le token invalidé. Soit trois endroits au lieu d'un.

**Option 3 — Direct.** Le consommateur porte deux clients : un client HTTP/2 persistant vers APNs avec un cache de JWT ES256 régénéré au plus toutes les 20 minutes, et un client HTTP/1.1 vers FCM avec un cache de jeton OAuth2. Il route sur la plateforme du token, mappe les codes de retour des deux fournisseurs vers une décision unique (« supprimer ce token », « réessayer », « échec permanent »), et choisit l'hôte APNs selon la provenance du build. Un seul endroit, mais le plus dense des trois.

---

## 9. Credentials : quoi obtenir, où le déposer

Intitulés relevés le 2026-09-07 dans les interfaces courantes. Un credential se dépose ; **sa valeur ne s'écrit jamais dans ce dépôt**.

### 9.1 Côté Apple — obtenir la clé APNs (nécessaire dans les 3 options)

Console : **Apple Developer** → *Certificates, Identifiers & Profiles*.

1. Cliquer **Keys** dans la barre latérale, puis le bouton **+** en haut à gauche. Rôle requis : *Account Holder* ou *Admin*.
2. Sous **Key Name**, saisir un nom unique.
3. Cocher la case en face de **Apple Push Notifications service (APNs)**, puis **Continue**, puis **Register**.
4. **Télécharger** le fichier `.p8` — Apple ne le propose qu'une seule fois.
5. Relever le **Key ID** (page *Keys*, en ouvrant la clé) et le **Team ID** (page *Membership details*).

Deux contraintes documentées par Expo : « You can have a maximum of **2** APN keys associated with your Apple Developer account », et « Push notification keys do not expire ». Révoquer une clé casse le push de toutes les apps qui s'en servent.

L'entitlement `aps-environment` n'est pas une clé : il est posé automatiquement dès que `"expo-notifications"` figure dans le tableau `plugins` de `mobile/app.config.ts`.

### 9.2 Côté Google — projet Firebase et compte de service (nécessaire dans les 3 options)

Console : **Firebase Console**.

1. Créer, ou réutiliser, le projet Firebase de l'app.
2. **Project settings** → onglet **Service accounts**.
3. **Generate New Private Key**, confirmer par **Generate Key** → un fichier JSON est téléchargé. À ne **jamais** committer.
4. Télécharger `google-services.json` depuis la console, le placer dans `mobile/`, et déclarer `android.googleServicesFile` dans `mobile/app.config.ts`. Ce fichier-là est committable : « You may commit this file to your repository since it contains public-facing identifiers ».
5. Si la clé d'API contenue dans `google-services.json` est restreinte : **Google Cloud Console** → *APIs & Services* → *Credentials* → sous **API restrictions**, autoriser **FCM Registration API** et **Firebase Installations API** ; sous **Application restrictions**, utiliser l'empreinte SHA-1 lue dans la Google Play Console sous **Release** → **Setup** → **App Integrity** → **App signing key certificate** (et non la clé d'upload). Un décalage fait répondre `403 PERMISSION_DENIED` avec le message « Requests from this Android client application are blocked », et l'app n'obtient jamais de token.

Pour réutiliser un compte de service existant : **Google Cloud Console** → *IAM & Admin* → onglet **Permissions** → repérer le **Principal**, cliquer l'icône crayon (**Edit Principal**) → **Add Role** → **Firebase Cloud Messaging API Admin** → **Save**.

### 9.3 Option 1 — dépôt dans EAS

**Android, en CLI** : `eas credentials` → `Android` → `production` → `Google Service Account` → `Manage your Google Service Account Key for Push Notifications (FCM V1)` → `Set up a Google Service Account Key for Push Notifications (FCM V1)` → `Upload a new service account key`.

**Android, dans le tableau de bord** : sous **Project settings**, cliquer **Credentials** dans le menu de navigation → pour **Android**, cliquer **Add Application Identifier** ou sélectionner un **Application identifier** existant → sous **Service Credentials** → **FCM V1 service account key**, cliquer **Add a service account key** → sous **Upload new key**, téléverser le fichier JSON → **Save**.

**iOS, en CLI** : `eas credentials` → `iOS` → `Push Notifications: Manage your Apple Push Notifications Key`. Au premier `eas build`, EAS propose de tout faire lui-même : répondre oui à *Setup Push Notifications for your project*, puis à *Generating a new Apple Push Notifications service key*. Dans ce cas la clé est **créée par EAS** et il n'y a rien à téléverser.

**Backend** : rien. Optionnellement, si la sécurité renforcée est activée depuis le tableau de bord EAS (section **Access tokens**), un jeton d'accès EAS à déposer dans `media-summarizer-runtime-<env>` sous un nom du genre `EXPO_ACCESS_TOKEN` — un jeton d'envoi, pas un credential de plateforme.

Contrôle : `eas credentials` affiche l'état des deux plateformes, et le tableau de bord aussi.

### 9.4 Option 2 — dépôt dans SNS

Console : **Amazon SNS** → dans le volet de navigation, **Mobile** → **Push notifications** → section **Platform applications** → **Create platform application**.

- **Application name** : de 1 à 256 caractères.
- **Push notification platform** : *Apple Push Notification Service (APNs)* ou *Firebase Cloud Messaging (FCM)*.
- Pour APNs : choisir l'authentification **token-based**, téléverser le fichier `.p8`, saisir l'identifiant de la clé de signature, l'identifiant d'équipe et le bundle ID (`com.secondbrainlabs.core`). **Deux applications** sont nécessaires : `APNS` et `APNS_SANDBOX`.
- Pour FCM v1 : le credential est le **JSON du compte de service** aplati en une seule chaîne (la documentation AWS montre `jq @json` pour l'obtenir). Attention : la page console du guide SNS parle encore d'un « Server key from Firebase Console », c'est-à-dire de l'ancienne API FCM ; la référence d'API, elle, documente bien le JSON de compte de service.

Journalisation de la délivrance : **Mobile** → **Push notifications** → choisir l'application dans **Platform applications** → **Application Actions** → **Delivery Status** → **Create IAM Roles** → **Allow** (redirection vers IAM) → renseigner **Percentage of Success to Sample (0-100)** → **Save Configuration**.

Événements de plateforme : **Mobile** → **Push notifications** → choisir l'application → **Edit** → déplier **Event notifications** → **Actions** → **Configure events** → renseigner les ARN de topic pour *Endpoint Created*, *Endpoint Deleted*, *Endpoint Updated* et *Delivery Failure* → **Save changes**. En CLI, c'est `aws sns set-platform-application-attributes` avec les attributs `EventEndpointCreated`, `EventEndpointDeleted`, `EventEndpointUpdated` et `EventDeliveryFailure`.

**Le point de friction, à décider avant de choisir cette option** : `aws_sns_platform_application` exige son credential au moment du plan. Voir §5.2 — soit deux secrets GitHub `TF_VAR_*` ajoutés à `terraform-dev.yml` et les deux fichiers présents sur la machine de l'owner pour prod, soit les trois applications créées en CLI hors Terraform et référencées par ARN.

**EAS** : rien à déposer côté push dans cette option.

### 9.5 Option 3 — dépôt dans le secret runtime

Quatre valeurs, dans `media-summarizer-runtime-<env>`, sous des noms du genre `APNS_KEY_P8`, `APNS_KEY_ID`, `APPLE_TEAM_ID` et `FCM_SERVICE_ACCOUNT_JSON`, écrites hors bande selon la procédure de `secrets.tf` :

```
aws secretsmanager put-secret-value \
  --secret-id media-summarizer-runtime-<env> \
  --secret-string file://runtime-secrets.json
# puis supprimer le fichier local
```

`lambda_handlers.py:26-32` les injectera dans l'environnement au cold start. **EAS** : rien à déposer côté push. À noter : le `.p8` est un PEM multiligne — il faut décider de son encodage (échappement JSON ou base64) et l'écrire dans la procédure de rotation, sinon la rotation suivante casse silencieusement.

### 9.6 Récapitulatif

| Credential | Expo | SNS | Direct |
|---|---|---|---|
| Clé APNs `.p8` | **EAS**, ou générée par EAS | application de plateforme SNS, 2 fois | secret runtime, 3 environnements |
| Identifiant de clé APNs et identifiant d'équipe | implicite (EAS) | champs de l'application de plateforme | secret runtime |
| Compte de service FCM v1 (JSON) | **EAS** | application de plateforme SNS (GCM) | secret runtime, 3 environnements |
| `google-services.json` | `mobile/`, committé | idem | idem |
| Entitlement `aps-environment` | posé par le plugin `expo-notifications` | idem | idem |
| Jeton d'envoi côté serveur | facultatif (jeton d'accès EAS) | IAM, donc aucun secret | aucun (dérivé des clés) |
| **Nombre de valeurs secrètes nouvelles côté dépôt/AWS** | **0, ou 1 facultative** | **2, plus un domicile CI** | **4** |

---

## 10. Question secondaire : le coût du balayage des fuseaux

### 10.1 Le pas de 15 minutes n'est pas nécessaire : 72 tirs par jour suffisent, et c'est prouvable

La description part de 15 minutes à cause du Népal (+5:45) et de Chatham (+12:45). Vérification exhaustive faite ici sur la base tzdata du système, **498 zones IANA**, aux deux dates de sondage 2026-01-15 et 2026-07-15 :

| Mesure | 2026-01-15 | 2026-07-15 |
|---|---|---|
| Décalages UTC distincts | **38** | **38** |
| Marques de minutes de ces décalages | 27 à `:00`, 8 à `:30`, 3 à `:45` | idem |
| **Minutes UTC auxquelles il est 18h30 quelque part** | `{:00, :30, :45}` | `{:00, :30, :45}` |
| **Minutes UTC auxquelles il est 09h30 un lundi quelque part** | `{:00, :30, :45}` | `{:00, :30, :45}` |

Il n'existe **aucun fuseau** pour lequel 18h30 locale tombe sur une minute UTC `:15`. L'arithmétique le confirme : les seuls décalages à `:45` sont positifs (+5:45, +8:45, +12:45, +13:45), et retrancher `:45` à `:30` remonte à `:45`, jamais à `:15`.

Conséquence : `schedule_expression = "cron(0,30,45 * * * ? *)"` couvre **exhaustivement** les deux cibles avec **72 tirs par jour** au lieu de 96 pour `rate(15 minutes)` — 25 % de tirs en moins, et surtout aucun tir qui ne peut structurellement rien trouver.

**Le compromis à assumer** : cette chaîne cron encode une propriété de la base tzdata. Si l'IANA introduisait un jour un décalage à `:15`, le cron deviendrait faux **silencieusement**. Mitigation minimale, à porter dans task-369 : un commentaire au-dessus du cron nommant l'invariant, et l'assertion correspondante dans le worker (« si la minute courante n'est pas dans {0, 30, 45}, ce tir ne peut rien trouver »). Qui préfère la robustesse à l'économie garde `cron(0,15,30,45 * * * ? *)` : le surcoût est de 24 invocations Lambda par jour, soit **moins de cinq centimes par mois** (§10.2). Ce n'est donc pas un choix économique, c'est un choix de style, et les deux sont défendables — le second est plus sûr.

### 10.2 Le déclencheur lui-même est gratuit — dans les trois options

Le balayage est **en amont** de la livraison : il produit des messages SQS. Son coût est donc **identique dans les trois options**. Tarifs eu-west-3 relevés le 2026-09-07 via l'AWS Price List Query API.

| Poste | Tarif eu-west-3 | 72 tirs/jour (2 160/mois) | 96 tirs/jour (2 880/mois) |
|---|---|---|---|
| `aws_cloudwatch_event_rule` avec `schedule_expression` | **aucun poste facturé** : le catalogue eu-west-3 d'`AWSEvents` ne contient aucun type d'usage pour une règle planifiée | **0,00 $** | **0,00 $** |
| `aws_scheduler_schedule` (EventBridge Scheduler), si utilisé à la place | `EUW3-ScheduledInvocation` : 0 $ jusqu'à **14 M** invocations/mois, puis 1,20 $/M | **0,00 $** | **0,00 $** |
| Invocations Lambda | 0,0000002 $ par requête, **1 M/mois offert** | 0,00 $ (0,00043 $ hors palier) | 0,00 $ (0,00058 $ hors palier) |
| Durée Lambda arm64 | 0,0000133334 $ par GB-s, **400 000 GB-s/mois offerts** | 0,00 $ (environ 0,14 $ hors palier à 512 Mo pendant 10 s) | 0,00 $ (environ 0,19 $ hors palier) |

**Le déclencheur ne coûte rien, dans aucune des trois options.** Ce qui coûte, c'est ce que la Lambda **lit** à chaque tir.

### 10.3 Le vrai coût : les lectures DynamoDB, et il est le même dans les trois options

Base de calcul : 512 o par ligne de la table `users` (291 o mesurés sur dev, marge prise pour le champ de fuseau de task-367), lectures **éventuellement cohérentes** (0,5 RRU par 4 Ko), 0,1487 $ par million de RRU en eu-west-3, 2 160 tirs par mois.

**(a) Balayage naïf — le code actuel inchangé.** `_get_all_user_ids()` fait un `Scan` complet, puis une lecture de réglages par utilisateur :

- `Scan` : N × 512 / 4096 × 0,5 = **N × 0,0625 RRU par tir**
- `get_user_digest_settings` : **N × 0,5 RRU par tir**
- Total : **N × 0,5625 RRU par tir**, soit **N × 1 215 RRU par mois**

| Comptes | RRU/mois | Coût DynamoDB | Durée d'un tir (15 ms par aller-retour, séquentiel) |
|---|---|---|---|
| 20 | 24 300 | 0,004 $ | 0,3 s |
| 1 000 | 1,22 M | **0,18 $** | 15 s |
| 10 000 | 12,2 M | **1,81 $** | 150 s |
| 100 000 | 121,5 M | **18,07 $** | environ **1 500 s → dépasse le plafond de 900 s d'une Lambda** |

Le mur à 100 000 comptes n'est donc pas tarifaire, il est **temporel** : le balayage naïf cesse de terminer.

**(b) Balayage filtré par fuseau — le mécanisme moins coûteux.** Un GSI sur `users` dont la clé de partition est le **nom IANA du fuseau** (le champ que task-367 stocke déjà, aucune valeur dérivée). À chaque tir, la Lambda calcule en mémoire, avec `zoneinfo` et pour un coût nul, l'ensemble des noms de zone où il est en ce moment 18h30 — quelques dizaines — puis fait une `Query` par zone. Chaque utilisateur est alors lu **une fois par jour** au lieu de 72.

- Lectures utiles : environ 34,35 × (0,0625 + 0,5) = **environ 19,3 RRU par utilisateur et par mois**
- `Query` vides (une zone due mais sans utilisateur) : minimum 0,5 RRU, soit environ 14 000 RRU par mois au total, négligeable

| Comptes | RRU/mois | Coût | Rapport contre (a) |
|---|---|---|---|
| 1 000 | 19 300 | **0,003 $** | ÷ 63 |
| 10 000 | 193 000 | **0,03 $** | ÷ 63 |
| 100 000 | 1,93 M | **0,29 $** | ÷ 62 |

Et la durée d'un tir devient proportionnelle aux utilisateurs **dus**, pas au parc entier : environ 1 400 utilisateurs par tir à 100 000 comptes, soit environ 21 s. Le mur temporel disparaît.

**Pourquoi le nom de zone plutôt qu'un créneau UTC pré-calculé** : un créneau stocké (par exemple `digest_slot = "16:30"`) serait faux deux fois par an à chaque bascule d'heure d'été, et il faudrait une passe nocturne pour le recalculer sur tout le parc. Le nom IANA, lui, ne périme jamais ; c'est le *lecteur* qui fait l'arithmétique, au moment du tir, gratuitement.

**Faut-il le construire tout de suite ?** Non. À 20 comptes, le balayage naïf coûte 0,004 $ par mois et 0,3 s par tir. Le GSI est la sortie de secours **documentée**, avec un seuil de bascule chiffré : au-delà d'environ **5 000 comptes**, un tir naïf dépasse 75 s et devient une dépense de temps Lambda qui ne rapporte rien. C'est ce seuil, et non le prix, qui doit déclencher le travail.

### 10.4 Les deux mécanismes alternatifs, évalués et écartés

**(i) Une planification par fuseau, côté EventBridge Scheduler.** `aws_scheduler_schedule` accepte `schedule_expression_timezone` avec un nom IANA et gère l'heure d'été. Une planification `cron(30 18 * * ? *)` par fuseau, avec ce fuseau en paramètre, tirerait exactement une fois par jour et par fuseau : **le balayage disparaît**. Le quota par défaut est de 10 000 000 planifications par région, et 2 planifications × environ 100 fuseaux × 30 tirs font 6 000 invocations par mois, très en dessous des 14 M offertes → **0 $**. Le dépôt utilise déjà ce type de ressource (`backup_library.tf:268`).

*Pourquoi écarté* : les fuseaux des utilisateurs sont inconnus à l'heure du `terraform apply`. Deux issues, mauvaises toutes les deux. Soit un `for_each` sur une liste figée de zones — mais laquelle ? les 498, ce qui ferait environ 1 000 ressources dans l'état pour deux notifications ; et si on réduit aux 38 décalages via des zones `Etc/GMT±X`, on perd l'heure d'été et un utilisateur parisien serait notifié à 19h30 en été. Soit une création dynamique par le code applicatif (`CreateSchedule` et `DeleteSchedule` quand un utilisateur choisit un fuseau inédit) — c'est-à-dire du code applicatif qui fabrique de l'infrastructure hors de Terraform, avec l'IAM correspondant et une dérive garantie. Pour un projet solo, un `cron` à trois valeurs de minutes est plus petit que les deux.

**(ii) La planification différée côté fournisseur.** Vérifié : **aucun des trois fournisseurs ne la propose sur son API d'envoi.** APNs a un en-tête `apns-expiration`, qui est une date de *péremption*, pas de livraison. FCM v1 (`projects.messages:send`) n'a aucun champ de date d'envoi — la planification n'existe que pour les campagnes de la console Firebase, pas pour l'API. Expo n'a pas de champ de délai. SNS a un TTL, pas un différé. Le seul différé disponible dans toute la chaîne est celui de SQS, plafonné à 15 minutes — utile pour la passe de receipts (§8.3), inutilisable pour attendre 18h30.

### 10.5 Réponse en une phrase à la question secondaire

Le balayage ne coûte **rien** au déclencheur et **la même chose** dans les trois options ; le pas correct est `cron(0,30,45 * * * ? *)`, soit 72 tirs par jour avec exhaustivité démontrée, et non 15 minutes ; et le mécanisme réellement moins coûteux n'est pas un autre déclencheur mais un **GSI sur le nom de fuseau**, qui fait lire à chaque tir uniquement les utilisateurs dus — 63 fois moins de RRU, et, à partir d'environ 5 000 comptes, la seule façon qu'un tir termine.

---

## 11. Coût total, aux volumes du projet et un ordre de grandeur au-dessus

### 11.1 Hypothèses de volume

| Scénario | Comptes | Appareils par compte | Notifications par mois |
|---|---|---|---|
| **Aujourd'hui** (18 comptes mesurés sur dev, testeurs TestFlight) | 20 | 1,0 | environ 690 |
| **V1 réaliste** | 1 000 | 1,2 | environ 41 200 |
| **Un ordre de grandeur au-dessus** | 10 000 | 1,2 | environ 412 000 |
| **Deux ordres** (pour situer le premier seuil facturable) | 100 000 | 1,2 | environ 4 120 000 |

30 notifications quotidiennes plus 4,35 hebdomadaires font 34,35 par compte et par mois, multipliées par le nombre d'appareils.

### 11.2 Tarifs eu-west-3 utilisés (AWS Price List Query API, 2026-09-07)

| Service | Poste | Tarif | Palier gratuit mensuel |
|---|---|---|---|
| SNS | `Notifications-Mobile` | 0,67 $/M | **1 000 000** |
| SNS | `EUW3-Requests-Tier1` | 0,50 $/M | **1 000 000** |
| SQS | `EUW3-Requests-Tier1` (standard) | 0,40 $/M | **1 000 000** |
| DynamoDB | `EUW3-ReadRequestUnits` | 0,1487 $/M | — |
| DynamoDB | `EUW3-WriteRequestUnits` | 0,7423 $/M | — |
| Lambda | requêtes et durée arm64 | 0,0000002 $ par requête, 0,0000133334 $ par GB-s | 1 M requêtes, 400 000 GB-s |
| EventBridge Scheduler | `EUW3-ScheduledInvocation` | 1,20 $/M | **14 000 000** |
| CloudWatch Events, règle planifiée | — | **aucun poste facturé** | — |
| Expo Push Service | envoi | **0 $** — « There is no cost associated with sending notifications through Expo push notification service » | aucune limite de volume documentée |
| APNs et FCM | envoi | **0 $** | — |

### 11.3 Coût mensuel par option

Les postes communs (SQS, DynamoDB, Lambda) sont calculés avec le balayage **filtré par fuseau** du §10.3(b), qui est le dessin recommandé. Le balayage naïf ajoute 0,18 $, 1,81 $ puis 18,07 $ aux trois colonnes, identiquement.

| Comptes | Postes communs | **Expo** | **SNS** | **Direct** |
|---|---|---|---|---|
| 20 | environ 0,00 $ | **0,00 $** | **0,00 $** | **0,00 $** |
| 1 000 | environ 0,01 $ | **0,01 $** | **0,01 $** | **0,01 $** |
| 10 000 | environ 0,10 $ | **0,10 $** | **0,10 $** | **0,10 $** |
| 100 000 | environ 4,7 $ | **4,7 $** | **8,9 $** | **4,7 $** |

Détail du delta SNS à 100 000 comptes : 4,12 M `Publish`, donc 3,12 M de notifications facturées à 0,67 $/M = **2,09 $** ; côté requêtes API, 4,12 M `Publish` plus environ 1,0 M de `GetEndpointAttributes` (un par lancement d'app, environ dix par compte et par mois), moins le million offert, soit 4,12 M à 0,50 $/M = **2,06 $**. Total **environ 4,2 $ par mois** de plus que les deux autres options.

Détail des postes communs à 100 000 comptes : SQS environ 10,3 M requêtes (envoi, réception et suppression, plus 1 % de messages `receipt_check` dans l'option Expo) moins le million offert = **3,72 $** ; DynamoDB environ 0,29 $ de lectures de balayage, 0,26 $ de lectures de tokens et 0,74 $ d'écritures de tokens = **1,29 $** ; Lambda **0 $**, dans les paliers gratuits. Le seul poste au-dessus de 1 $ est **SQS**, dans les trois options.

### 11.4 Lecture

- **Aux volumes de ce projet, et un ordre de grandeur au-dessus, les trois options sont gratuites.** Le coût ne peut donc pas départager.
- SNS est la seule à facturer le message, et son delta n'apparaît qu'au-delà d'environ 24 000 comptes, le point où le million de notifications mensuelles offert est dépassé. À 100 000 comptes, il vaut **4,2 $ par mois** — moins que le surcoût du balayage naïf.
- Le poste dominant à grande échelle est **SQS**, commun aux trois. S'il fallait un jour le réduire, la voie est d'agréger plusieurs utilisateurs par message, pas de changer de fournisseur de push.

### 11.5 Où sont les plafonds, et lequel arrive en premier

| Plafond | Valeur | Comptes correspondants, sur la fenêtre la plus chargée |
|---|---|---|
| Expo : 600 notifications/s par projet | fixe, non ajustable | environ 10⁶ comptes avant qu'une fenêtre dépasse la durée d'une Lambda |
| Expo : 100 notifications par requête, 1 000 receipts par requête | fixe | aucun impact, c'est la taille de lot naturelle |
| FCM v1 : 600 000 messages/minute par projet | soit 10 000/s | environ 1,7 × 10⁷ |
| APNs | non documenté | — |
| SNS, TPS de `Publish` | quota régional ajustable — **valeur non vérifiée, voir §16** | — |
| Lambda : 900 s par invocation | plafond dur | **environ 5 000 comptes avec le balayage naïf** ← *le premier plafond atteint* |

Le plafond qui mord le plus tôt n'appartient à aucun fournisseur de push : c'est la durée d'une Lambda face à un balayage naïf. Autrement dit, la question secondaire du §10 est plus contraignante que le choix du §3.

---

## 12. Rétention des tokens, au regard de `docs/DATA_RETENTION.md`

Un token push est une donnée **d'appareil**, pas une donnée de bibliothèque. Il ne relève donc pas de la règle centrale (« A user's library has no retention clock. Only the user can end its life ») mais du régime des tables par utilisateur.

**Forme recommandée, identique dans les trois options** : une table `user_push_tokens`, clé de partition `user_id`, clé de tri le token (options 1 et 3) ou un identifiant d'appareil (option 2, qui doit aussi porter l'`EndpointArn`), avec les attributs `platform`, `created_at` et `last_seen_at`.

Cinq points à respecter, tous vérifiables dans le dépôt :

1. **Aucune écriture de `purge_at` ni de `deleted_at`.** `scripts/check_purge_at_writers.py` fait échouer la CI si un second écrivain de ces deux attributs apparaît dans `media_summarizer/` ou `scripts/`. Un token périmé se **supprime**, il ne se marque pas. Donc aucun TTL `purge_at` sur cette table.
2. **Suppression à la suppression de compte.** `core/services/account_deletion_service.py:85-93` énumère `_USER_PARTITION_TABLES` ; la nouvelle table s'y ajoute par un tuple, et `purge_account` la vide avec le reste. C'est le point le plus important de cette section, et il tient en une ligne.
3. **Suppression à l'invalidation.** `DeviceNotRegistered` pour Expo, `EventDeliveryFailure` avec `InvalidPlatformToken` pour SNS, `410` ou `404 UNREGISTERED` pour le direct → `delete_item`. Un token mort qu'on garde est une donnée d'appareil conservée sans finalité.
4. **Un `last_seen_at` rafraîchi à chaque lancement**, et une suppression des lignes non revues depuis N jours (90 est un choix raisonnable, à trancher dans task-369). C'est le filet qui attrape les désinstallations qu'aucun fournisseur ne signale — la documentation Expo prévient que la remontée de `DeviceNotRegistered` « takes an undefined amount of time and is often impossible to test ».
5. **Rien à ajouter au tableau du §2 de `DATA_RETENTION.md` pour Expo** au titre d'un stockage tiers : la FAQ Expo indique que le contenu des notifications n'est conservé qu'en mémoire et dans des files, « not in databases ». En revanche, `docs/DATA_RETENTION.md` **et** `docs/compliance/privacy-policy.md` devront nommer le nouveau sous-traitant choisi — Expo, ou aucun dans l'option 3. C'est un travail de task-369, pas de celui-ci.

Différence entre options sur ce critère : l'option SNS stocke **une donnée de plus** par appareil (l'`EndpointArn`) et crée un objet **côté AWS**, l'endpoint de plateforme, qui survit à la suppression de la ligne DynamoDB si on l'oublie. `purge_account` devrait donc aussi appeler `DeleteEndpoint`, sinon la suppression de compte laisse un résidu chez le fournisseur. Les options 1 et 3 n'ont pas ce piège.

---

## 13. Effort d'implémentation et impact sur le fingerprint mobile

### 13.1 Le fingerprint bouge, identiquement dans les trois options

`mobile/app.config.ts:179-181` fixe `runtimeVersion: { policy: "fingerprint" }`. Le fingerprint est un hachage du projet **natif** : ajouter `expo-notifications` à `package.json` et son entrée au tableau `plugins` change les modules autolinkés, l'entitlement `aps-environment` côté iOS et le manifeste Android (permission `POST_NOTIFICATIONS` pour Android 13+, plus `RECEIVE_BOOT_COMPLETED` et `SCHEDULE_EXACT_ALARM` posées par la bibliothèque).

Conséquences, à retenir telles quelles :

- **Pas d'OTA.** `mobile-ota-or-build.yml` décidera « build », et il faut les **deux** plateformes. Le palier gratuit EAS plafonne à 15 builds iOS par mois : c'est un build de plus à budgéter.
- **Aucune de ces conséquences ne dépend de l'option choisie.** Le seul écart côté client est `getExpoPushTokenAsync()` contre `getDevicePushTokenAsync()`, une ligne.
- Depuis le SDK 53, Expo Go ne fait plus de push : les essais se font sur un development build.
- L'ordre d'appel est contraint sur Android : `setNotificationChannelAsync` **avant** la demande de token, sinon aucun token.

### 13.2 Effort backend, comparé

| Bloc | Expo | SNS | Direct |
|---|---|---|---|
| Table de tokens et endpoint `POST /api/push-token` | 1 écriture | 1 écriture **plus** la réconciliation d'endpoint (1 à 3 appels SNS, cas « introuvable » et « désactivé ») | 1 écriture |
| Module d'envoi | 1 POST, lots de 100 | 1 `Publish` par endpoint, payload JSON par plateforme | 2 clients, 2 payloads, 2 caches d'authentification |
| Traitement de l'invalidation | 1 passe `receipt_check` sur la même file, avec `delay_seconds=900` | 1 abonné de plus au topic d'événements de plateforme | dans la réponse de l'envoi |
| Ressources Terraform hors tronc commun | **0** | 3 applications de plateforme (hors Terraform, §9.4), 1 topic, 1 abonnement, 1 rôle IAM | 0 |
| Dépendances Python nouvelles | **0** | **0** | `h2`, `hpack`, `hyperframe` |
| Secrets à créer et à faire tourner | **0** | 2 | 4 |
| Chemins de code distincts à vérifier manuellement | 2 (`send`, `receipt_check`) | 3 (enregistrement, envoi, événement) | 2 × 2 plateformes |

### 13.3 Un point d'attention commun, à ne pas oublier dans task-369

Le worker de balayage devra faire de l'arithmétique de fuseau (`zoneinfo.ZoneInfo("<nom IANA>")`). Sur une image Lambda basée sur Amazon Linux, la présence de `/usr/share/zoneinfo` **n'a pas été vérifiée ici** (§16). Si elle manque, la parade est d'ajouter le paquet `tzdata` en dépendance — à trancher à l'implémentation, sur l'image réelle. Ce point est indépendant du choix de fournisseur.

---

## 14. Dépendance tierce et réversibilité

| Question | Expo | SNS | Direct |
|---|---|---|---|
| Qui est sur le chemin, en plus d'Apple et Google | Expo | AWS | personne |
| Ce qu'on perd si cet étage tombe | la notification de la fenêtre. Le digest est déjà écrit dans `user_digests` et l'app le lit au lancement. | idem | sans objet |
| Le message est-il perdu ? | non : le message SQS échoue, est réessayé trois fois, puis part en DLQ — rejouable | idem | idem |
| Engagement de service | « does not have an SLA », explicite | SLA de service SNS, pas de délivrance | aucun |
| Le fournisseur voit-il le contenu ? | oui, en mémoire ; « may be seen by Expo staff » en débogage | AWS, dans le compte du projet | non |
| Token portable vers une autre option ? | **non** (`ExponentPushToken`) | oui (token natif) | oui (token natif) |
| Coût de sortie | 1 ligne client, 1 module serveur, **1 build EAS et un réenregistrement** | 1 module serveur, plus la suppression des endpoints | 1 module serveur |
| Verrouillage réel | faible : `expo-notifications` est explicitement agnostique — « You can use any push notification service for Expo projects » | faible | nul |

Le seul verrou d'Expo est le format du token, et il ne se paie qu'une fois, au moment d'une sortie hypothétique, par un build que ce projet fait de toute façon plusieurs fois par mois. À comparer au verrou de SNS, qui est un objet d'état par appareil dans un service dont on doit sortir en supprimant des endpoints un par un.

---

## 15. Ce que ce benchmark impose à task-369, si la recommandation est retenue

Liste destinée à l'implémenteur, à ne suivre que si l'owner valide l'option 1.

1. `expo-notifications` dans `mobile/package.json`, et `"expo-notifications"` dans le tableau `plugins` de `mobile/app.config.ts`. Rien d'autre côté config iOS : le plugin pose `aps-environment`.
2. `setNotificationChannelAsync("default", …)` sur Android **avant** `getExpoPushTokenAsync({ projectId })`.
3. Le corps de la notification reste un **compteur**. Aucun titre de média, aucun extrait, ni dans le titre, ni dans le corps, ni dans `data` (§4.3).
4. Table `user_push_tokens` indexée par `user_id`, ajoutée à `_USER_PARTITION_TABLES` de `account_deletion_service.py`, sans `purge_at` ni `deleted_at`.
5. File `push-notification` et sa DLQ en Terraform, dans **tous** les environnements, sur le patron de `sqs.tf`, avec `PUSH_NOTIFICATION_QUEUE` ajouté à la liste des noms de files de `runtime_env.tf`.
6. Suppression du court-circuit qui rend le producteur inerte quand `PUSH_NOTIFICATION_QUEUE` est vide — pas de repli, pas de double chemin.
7. Producteur daily ajouté, ne notifiant pas une période vide, idempotent par couple (utilisateur, période).
8. Lambda de balayage dans son propre fichier Terraform, sur le modèle de `lambda_media_lifecycle.tf`, avec `schedule_expression = "cron(0,30,45 * * * ? *)"` et le commentaire qui nomme l'invariant tzdata du §10.1.
9. Lambda consommatrice déclarée dans `local.workers`, handler construit par `_build_handler`, deux sortes de messages (`send` et `receipt_check`), la seconde réenfilée avec `delay_seconds=900`.
10. Suppression du token sur `DeviceNotRegistered`, plus un `last_seen_at` et une purge des tokens non revus.
11. Décider si la sécurité renforcée d'Expo est activée ; si oui, un jeton d'accès EAS dans `media-summarizer-runtime-<env>`, déposé hors bande.
12. Vérifier la présence de `/usr/share/zoneinfo` sur l'image worker et ajouter `tzdata` si elle manque.

---

## 16. Limites de ce benchmark — ce qui n'a pas pu être vérifié

Écrit ici plutôt que déguisé en fait ailleurs.

- **Le quota `Publish` par seconde de SNS n'a pas été vérifié.** La page de quotas de service de SNS n'a pas rendu de tableau exploitable depuis cet environnement. Le §11.5 le laisse donc vide. Cela ne change pas la recommandation : le plafond limitant est celui de la Lambda.
- **Aucun essai de terrain.** Aucune notification n'a été envoyée, aucun token n'a été obtenu, aucun appareil n'a rien reçu. Tout ce document repose sur la documentation des fournisseurs, sur les tarifs de l'API Price List, sur le code du dépôt et sur une mesure `describe-table`. La première preuve réelle sera un envoi manuel de l'owner depuis l'outil de test d'Expo après le premier build.
- **Les intitulés de console sont ceux relevés le 2026-09-07** et peuvent bouger. Deux incohérences ont déjà été repérées et sont signalées comme telles : le guide SNS demande encore un « Server key from Firebase Console », c'est-à-dire l'ancienne API FCM, alors que la référence d'API documente le JSON de compte de service (§9.4) ; et la documentation du provider Terraform illustre encore la plateforme `GCM` avec une clé d'API à l'ancienne.
- **La présence de `/usr/share/zoneinfo` sur l'image worker n'a pas été vérifiée** (§13.3).
- **Les durées d'aller-retour DynamoDB, 15 ms, sont une hypothèse**, pas une mesure. Les seuils temporels du §10.3 en dépendent linéairement : à 5 ms, le mur du balayage naïf recule d'environ 5 000 à environ 15 000 comptes ; à 30 ms, il avance à environ 2 500. L'ordre de grandeur de la conclusion tient dans les trois cas.
- **Les hypothèses de volume du §11.1 sont des scénarios**, pas des prévisions. Seul le point « aujourd'hui » est mesuré : 18 comptes sur dev.

---

## 17. Sources

Toutes consultées le **2026-09-07**.

**Expo / EAS**
- Vue d'ensemble du push — https://docs.expo.dev/push-notifications/overview/
- Mise en place, credentials de développement, outil d'essai — https://docs.expo.dev/push-notifications/push-notifications-setup/
- Envoi via Expo Push Service : tickets, receipts, erreurs, absence de SLA, sécurité renforcée, formats — https://docs.expo.dev/push-notifications/sending-notifications/
- Envoi direct via FCM et APNs, `getDevicePushTokenAsync`, entitlement `aps-environment` — https://docs.expo.dev/push-notifications/sending-notifications-custom/
- Credentials FCM v1 : Firebase Console, EAS CLI, tableau de bord, `google-services.json`, restrictions de clé d'API — https://docs.expo.dev/push-notifications/fcm-credentials/
- FAQ : coût nul, plafond de 600 notifications par seconde, non-stockage du contenu, accès du personnel Expo, cycle de vie du token, Expo Go depuis le SDK 53 — https://docs.expo.dev/push-notifications/faq/
- Credentials d'app : maximum de 2 clés APNs, clés qui n'expirent pas, tableau des credentials iOS — https://docs.expo.dev/app-signing/app-credentials/
- Credentials gérés : intitulés exacts de `eas credentials` pour les deux plateformes — https://docs.expo.dev/app-signing/managed-credentials/
- Référence `expo-notifications` : `getDevicePushTokenAsync`, `getExpoPushTokenAsync`, `scheduleNotificationAsync`, déclencheurs `DAILY` / `WEEKLY` / `CALENDAR`, permissions Android — https://docs.expo.dev/versions/latest/sdk/notifications/
- Index Markdown de la documentation, le suffixe `.md` rendant n'importe quelle page en Markdown — https://docs.expo.dev/llms.txt

**Apple**
- Créer une clé privée, chemin exact *Certificates, Identifiers & Profiles* → **Keys** → **+** — https://developer.apple.com/help/account/keys/create-a-private-key/
- Communiquer avec APNs par jetons d'authentification — https://developer.apple.com/help/account/keys/apns-authentication-tokens/
- Enregistrer l'app auprès d'APNs — https://developer.apple.com/documentation/usernotifications/registering-your-app-with-apns
- Référence des clés du payload d'une notification distante — https://developer.apple.com/documentation/usernotifications/generating-a-remote-notification

**Google / Firebase**
- `projects.messages:send` de l'API FCM HTTP v1 — https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages/send
- Codes d'erreur FCM — https://firebase.google.com/docs/reference/fcm/rest/v1/ErrorCode
- Quotas et limitation de débit — https://firebase.google.com/docs/cloud-messaging/throttling-and-quotas
- Gérer les jetons d'enregistrement — https://firebase.google.com/docs/cloud-messaging/manage-tokens

**AWS**
- Envoyer des notifications push mobiles avec SNS — https://docs.aws.amazon.com/sns/latest/dg/sns-mobile-application-as-subscriber.html
- Créer une application de plateforme SNS, chemin console exact — https://docs.aws.amazon.com/sns/latest/dg/mobile-push-send-register.html
- `CreatePlatformApplication` : principal et credential par plateforme, FCM v1 par JSON — https://docs.aws.amazon.com/sns/latest/api/API_CreatePlatformApplication.html
- Attributs d'application mobile SNS : delivery status logging, chemin console, exemples de logs — https://docs.aws.amazon.com/sns/latest/dg/sns-msg-status.html
- Notifications d'événements d'application, chemin console et CLI — https://docs.aws.amazon.com/sns/latest/dg/application-event-notifications.html
- Bonnes pratiques de gestion du push mobile, dont le stockage des ARN d'endpoints — https://docs.aws.amazon.com/sns/latest/dg/mobile-push-notifications-best-practices.html
- Gestion des endpoints FCM par SNS : pseudo-code de réconciliation, `UNREGISTERED`, `INVALID_ARGUMENT` — https://docs.aws.amazon.com/sns/latest/dg/sns-fcm-endpoint-management.html
- Régions où SNS mobile push est disponible — https://docs.aws.amazon.com/sns/latest/dg/sns-mobile-push-supported-regions.html
- Files à délai SQS, maximum de 15 minutes — https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-delay-queues.html
- EventBridge Scheduler : présentation et quotas — https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html et https://docs.aws.amazon.com/scheduler/latest/UserGuide/scheduler-quotas.html
- Tarifs, source unique de tous les chiffres du §11.2, via l'AWS Price List Query API — `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<Service>/current/eu-west-3/index.json` pour `AmazonSNS`, `AWSQueueService`, `AmazonDynamoDB`, `AWSLambda` et `AWSEvents`
- `aws_sns_platform_application` : arguments requis, credential conservé sous forme de hash dans l'état — https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_platform_application

**Dépôt** (chemins relatifs à la racine)
- `media_summarizer/workers/digest/scheduler.py`, `media_summarizer/workers/lambda_handlers.py`, `media_summarizer/utils/sqs.py`, `media_summarizer/core/services/account_deletion_service.py`
- `infrastructure/terraform/modules/platform/` : `secrets.tf`, `sqs.tf`, `lambda_workers.tf`, `lambda_media_lifecycle.tf`, `backup_library.tf`, `runtime_env.tf`
- `mobile/package.json`, `mobile/app.config.ts`, `mobile/eas.json`
- `docs/DATA_RETENTION.md`, `.github/workflows/terraform-dev.yml`, `AGENTS.md`, `CLAUDE.md`
- Mesure de volume : `aws dynamodb describe-table --table-name users-dev --region eu-west-3` → 18 items, 5 246 octets
- Vérification des fuseaux : `zoneinfo.available_timezones()`, 498 zones, sondées aux dates 2026-01-15 et 2026-07-15
