---
id: task-252
title: Provision the 37 runtime credentials of the prod secret (owner only)
status: To Do
assignee: []
created_date: '2026-08-13 07:30'
updated_date: '2026-09-03 11:40'
labels:
  - infra
  - security
  - release
  - phase-10
  - blocker-launch
  - owner-only
dependencies:
  - task-248
  - task-312
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUEL — OWNER UNIQUEMENT. NE JAMAIS DISPATCHER VERS UN SUBAGENT.**
>
> Cette tâche manipule des credentials tiers que **seul l'owner détient** :
> comptes RevenueCat/Deepgram/OpenAI/Apify, clés Apple, secrets Google. Aucun
> agent ne doit tenter de les obtenir, de les fabriquer ni de les deviner. Le
> verrou `dispatchable: false` du front-matter est là pour ça — il est lu par
> `scripts/dispatch_backlog.sh` (denylist impérative injectée dans le prompt du
> dispatcher), indépendamment du statut, de la priorité, des labels et des
> dépendances.

## Pourquoi cette tâche existe

Elle recueille le seul reste-à-faire du critère #7 de task-237 (« a staging
environment is created and **its runtime secret is provisioned** »), volontairement
suspendu à la clôture de cette dernière le 2026-08-13.

Sans ces credentials, **prod est une coquille vide** : le health check répond `200`
parce que la connexion DynamoDB passe par le rôle IAM, mais toute intégration
tierce échoue — pas de transcription (Deepgram), pas de résumé (OpenAI), pas de
résolution TikTok/Instagram/YouTube (Apify), pas de recherche (Algolia), pas
d'achat (RevenueCat), et surtout aucune session utilisateur valide
(`JWT_SECRET_KEY`).

C'est un **bloquant de lancement dur**, à traiter en Phase 10.

## Correction du 2026-08-21 : « ne rien recopier de dev » était faux

La version précédente de cette tâche interdisait de reprendre la moindre valeur de
dev, en s'appuyant sur le benchmark task-221 §7.3. Vérification faite clé par clé
contre le code et les dashboards, **cette consigne aurait produit une prod
cassée**. §7.3 a été écrit avant que RevenueCat, Sign in with Apple et Sign in with
Google soient câblés, à une époque où « une clé par environnement » était encore
une abstraction sans app.

Ce qui a été constaté, et qui change la tâche :

- **Il n'y a qu'une seule app.** Un bundle ID (`com.secondbrainlabs.core`,
  `mobile/app.config.ts:98` et `:125`), un compte Apple Developer, un projet Google
  Cloud, un projet RevenueCat. Les identités OAuth et IAP ne sont pas
  « par environnement » : elles sont **par app**.
- **Le profil `production` de `mobile/eas.json` embarque exactement les mêmes
  `EXPO_PUBLIC_GOOGLE_CLIENT_ID_*` que `development`** — vérifié par comparaison
  avec le secret dev le 2026-08-21, les trois valeurs sont égales. Le binaire qui
  part sur les stores porte ces client IDs. Un backend prod qui n'accepterait pas
  ces audiences-là refuserait tous les Sign in with Google.
- **`APPLE_NATIVE_AUDIENCE` vaut littéralement le bundle ID.** Même raisonnement.
- **RevenueCat n'a pas de couple sandbox/live.** Le projet `proj879a771a` porte
  l'app App Store `app0d4b00c12f` et l'app Play `appb253c0f75a` (voir
  `docs/REVENUECAT_ENTITLEMENTS.md`). Un bundle ID ne se rattache qu'à une app
  RevenueCat, donc un second projet « prod » ne pourrait pas porter les mêmes
  produits. Le sandbox est un **attribut de l'achat** (`environment: SANDBOX` dans
  l'event webhook), pas une clé.
- **L'isolation Algolia est déjà structurelle.** `utils/algolia_client.py:84`
  dérive l'index en `media_items_{ENVIRONMENT}` et
  `modules/platform/runtime_env.tf:103` injecte `ENVIRONMENT = "prod"`. Prod aura
  `media_items_prod` sans qu'aucune clé ne le décide.

Le vrai périmètre n'est donc pas « 37 credentials neufs ». C'est **5 valeurs à
créer, 30 à recopier de dev, et 2 valeurs de configuration bloquées sur le
domaine** (regroupement du 2026-09-03, voir plus bas).

## État constaté le 2026-08-21 (AWS eu-west-3)

- `media-summarizer-runtime-dev` (compte `125313707865`) contient **40 clés**, pas
  37 : `APIFY_WEBHOOK_SECRET` et `GOOGLE_NATIVE_AUDIENCE_IOS` /
  `GOOGLE_NATIVE_AUDIENCE_ANDROID` sont arrivées depuis la rédaction initiale.
  `REVENUCAT_WEBHOOK_SECRET` **est renseignée** (elle était vide au 2026-08-13).
- **3 de ces 40 clés sont mortes** et ne doivent pas naître dans le secret prod :
  `ALGOLIA_INDEX_NAME`, `COOKIE_DOMAIN` (morte depuis task-293),
  `APIFY_INSTAGRAM_COMMENT_ACTOR_ID` (morte depuis task-173). Aucun code ne les
  lit. → **37 clés vivantes**, d'où le titre inchangé.
- `media-summarizer-runtime-prod` (compte `866874944541`) contient `{}`.
- `ALGOLIA_SEARCH_API_KEY` est lue par le code mais absente de dev *et* de
  Terraform : c'est task-312 qui la supprime, avec le seul chemin qui la lisait.
  D'où la dépendance : sans elle, cette tâche hériterait d'une 38ᵉ clé à créer
  pour rien.

## Les 37 clés, en deux groupes (regroupement du 2026-09-03)

Décision de l'owner le 2026-09-03 : ramener les cinq groupes de la version
précédente à **deux**, avec un critère unique et exécutable — *une clé n'est
recréée que si la partager avec dev fait courir un risque réel*. Tout le reste se
recopie. Le raisonnement clé par clé de la section précédente ne change pas ;
seul le classement est simplifié, pour que la tâche se déroule en deux gestes au
lieu de cinq.

Un seul reclassement de fond en découle : **`ALGOLIA_API_KEY` monte dans le
groupe 2.** Elle était rangée avec quatre clés fournisseur dont le seul bénéfice
est l'attribution de coût, alors qu'elle est d'une autre nature — c'est
aujourd'hui la clé **Admin**, portée sur toute l'application Algolia, donc une
Lambda dev peut effacer l'index prod. Capacité destructive croisée, pas hygiène.

Deux arbitrages tranchés par l'owner le 2026-09-03, contre la recommandation
dans le premier cas — ils sont notés ici pour que personne ne les rejoue :

- **`OPENAI_API_KEY` et `DEEPGRAM_API_KEY` restent en groupe 1.** Un project
  dédié était gratuit et donnait la seule mesure fiable du coût par utilisateur
  réel, ce qui touche directement `task-65`. L'owner a préféré s'en tenir au
  critère : partager ces clés ne crée aucune escalade de privilège, donc pas
  d'obligation. **Conséquence assumée** : usage et facturation OpenAI/Deepgram
  restent mélangés entre dev et prod, donc aucun chiffre de coût par user n'est
  attribuable tant que ça dure, et un emballement de retries en dev consomme le
  budget prod. À rouvrir quand le pricing devra s'appuyer sur du réel.
- **Les 3 tokens Apify se recopient**, sans compte payant ni nouveaux comptes
  free tier. **Conséquence assumée** : dev et prod se partagent les crédits, donc
  un épuisement en dev **arrête l'ingestion prod**. Acceptable au lancement
  (zéro user, volume nul) ; le passage payant se décidera sur du volume réel.

### Groupe 2 — créer une valeur neuve pour prod, obligatoire (5)

| Clé | Le risque si on recopie dev |
|---|---|
| `JWT_SECRET_KEY` | Un token émis par dev est **valide en prod**. Escalade de privilège inter-environnement, la plus directe de la liste. |
| `PRICING_ADMIN_SECRET` | Idem sur l'endpoint admin pricing : un secret connu côté dev pilote la tarification de prod. |
| `APIFY_WEBHOOK_SECRET` | Bearer de `/api/webhooks/apify`. Auto-contenu : `infrastructure/apify_adapter.py:146-147` l'envoie lui-même à la création du run, donc rien à coller dans un dashboard — création gratuite, zéro friction. |
| `REVENUCAT_WEBHOOK_SECRET` | Secret choisi par l'owner et collé dans RevenueCat. **Sous réserve de la question ouverte plus bas** : si le projet n'accepte qu'une seule URL de webhook, la valeur dev devient morte plutôt que distincte. |
| `ALGOLIA_API_KEY` | **Le seul geste d'isolation Algolia qui compte.** La clé actuelle est Admin sur toute l'application : une Lambda dev peut effacer l'index prod. Algolia autorise un nombre illimité de clés **scopées par index** — une restreinte à `media_items_prod`, une à `media_items_dev`. Ce n'est donc pas « une clé neuve » mais « une clé neuve **et scopée** » : une seconde clé Admin ne résoudrait rien. |

Les quatre premières sont des secrets **maison**, pas des credentials tiers :
aucun compte à ouvrir, `openssl rand -hex 32` suffit.

### Groupe 1 — recopier la valeur de dev (30)

Trois raisons distinctes de recopier, qui n'ont pas le même statut : les deux
premières sont *la seule option correcte*, la troisième est *un arbitrage de
coût assumé*. Ne pas les confondre en relisant.

**(a) Identités par app, pas par environnement — 14 clés.** Il n'y a **qu'une
seule app** : un bundle ID (`com.secondbrainlabs.core`), un compte Apple
Developer, un projet Google Cloud, un projet RevenueCat. Les identités OAuth et
IAP se rattachent à l'app, pas à l'environnement, donc un backend prod qui
n'accepterait pas ces audiences refuserait tous les sign-in du binaire publié.

`APPLE_CLIENT_ID` · `APPLE_TEAM_ID` · `APPLE_KEY_ID` · `APPLE_PRIVATE_KEY` ·
`APPLE_NATIVE_AUDIENCE` · `GOOGLE_CLIENT_ID` · `GOOGLE_CLIENT_SECRET` ·
`GOOGLE_NATIVE_AUDIENCE_IOS` · `GOOGLE_NATIVE_AUDIENCE_ANDROID` ·
`REVENUCAT_API_KEY` · `REVENUCAT_PROJECT_ID` · `CANNY_BOARD_TOKEN` ·
`CANNY_SSO_PRIVATE_KEY` · `X_API_BEARER_TOKEN`

- `APPLE_NATIVE_AUDIENCE` vaut littéralement le bundle ID.
- Canny : le board est **public et unique**, c'est celui où les users postent. Un
  board « dev » séparé est un contresens.
- X : le free tier est un projet par compte développeur ; deux apps partageraient
  le quota de toute façon. Le sujet est le quota, pas l'isolation.
- Exception possible mais sans intérêt réel : `APPLE_KEY_ID` /
  `APPLE_PRIVATE_KEY` pourraient être une seconde clé Sign in with Apple du même
  team (Apple en autorise plusieurs). Gain : révocation indépendante. À faire
  seulement si c'est gratuit en temps.

**(b) Identifiants publics et configuration, pas des secrets — 7 clés.**

`ALGOLIA_APP_ID` · `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` ·
`APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` · `APIFY_INSTAGRAM_POST_ACTOR_ID` ·
`APIFY_INSTAGRAM_REEL_ACTOR_ID` · `DEEPGRAM_MODEL` · `OPENAI_MODEL`

- Les 4 actor IDs Apify sont des identifiants **publics** de la marketplace.
- `ALGOLIA_APP_ID` : le plan Build gratuit, c'est une application. L'isolation ne
  dépend pas de l'App ID, elle dépend de l'index — et l'index est déjà dérivé
  d'`ENVIRONMENT`, cf. plus haut.
- `DEEPGRAM_MODEL` / `OPENAI_MODEL` ne sont pas des clés du tout, c'est de la
  configuration. Les faire diverger (figer prod sur un modèle pinné, laisser dev
  flotter) est une décision produit, pas de sécurité — à trancher ailleurs.

**(c) Une clé neuve était possible ; l'owner a tranché de recopier — 9 clés.**

`OPENAI_API_KEY` · `DEEPGRAM_API_KEY` · `LLAMAPARSE_API_KEY` ·
`UNSTRUCTURED_API_KEY` · `APIFY_YOUTUBE_API_TOKEN` · `APIFY_TIKTOK_API_TOKEN` ·
`APIFY_INSTAGRAM_API_TOKEN` · `PODCASTINDEXORG_API_KEY` ·
`PODCASTINDEXORG_API_SECRET`

Contrairement à (a) et (b), recopier ici n'est pas *correct par nature* : c'est un
choix. Deux cas à ne pas confondre.

- **Recréer n'apportait rien** — les 2 clés PodcastIndex : service gratuit, aucune
  donnée, aucune facturation à attribuer. Recopier est sans conséquence.
- **Recréer apportait quelque chose de réel** — les 7 autres : une clé de plus
  depuis le même compte était gratuite et donnait révocation indépendante et
  attribution de coût. C'est ici que sont les **deux seuls endroits de la liste où
  dev peut casser prod sans franchir aucune permission** : budget
  OpenAI/Deepgram commun (et quota LlamaParse/Unstructured), crédits Apify
  communs. Les deux conséquences sont écrites en tête de section ; ce ne sont pas
  des détails de forme.

Les 3 tokens Apify sont **3 comptes distincts**, créés par task-127 pour cumuler
les crédits gratuits.

### Ni l'un ni l'autre : 2 valeurs de configuration bloquées sur le domaine

`APPLE_REDIRECT_URI` · `GOOGLE_REDIRECT_URI`

Elles ne rentrent dans aucun des deux groupes, et les y forcer serait un piège.
Leur valeur **doit** différer de dev — mais pas pour une raison de risque : c'est
une URL d'environnement. Les ranger dans « recopier de dev » produirait exactement
la panne silencieuse de task-136, une valeur acceptée par Secrets Manager et
fausse à l'exécution.

Elles pointent aujourd'hui sur l'URL brute API Gateway de dev. Un Service ID
Apple et un client web Google acceptent **plusieurs** Return URLs, donc partager
`APPLE_CLIENT_ID` / `GOOGLE_CLIENT_ID` ne pose aucun problème : seule l'URI
diffère.

Bloquant réel : `api.secondbrainlabs.com` et `api.mediasummarizer.com` sont tous
deux en NXDOMAIN, et le profil `production` de `mobile/eas.json` pointe encore sur
le second alors que le plan de lancement vise le premier. Il faut d'abord décider
quel domaine porte l'API (`docs/V1_LAUNCH_PLAN.md`, Phase 10 étape 0bis). Peupler
cette tâche en deux passes — les 35 autres clés d'abord, ces 2 ensuite — est
parfaitement acceptable, à condition de le noter.

## Question ouverte à trancher : le webhook RevenueCat

RevenueCat n'expose qu'**une URL de webhook par projet**, et il n'y a qu'un projet.
Donc la question n'est pas « quelle valeur pour `REVENUCAT_WEBHOOK_SECRET` en
prod » mais **qui reçoit les events**. Trois issues possibles, à vérifier dans le
dashboard avant de peupler :

1. RevenueCat accepte plusieurs intégrations webhook sur le même projet → dev et
   prod ont chacun leur URL et leur secret, **groupe 2 tel quel**.
2. Une seule URL possible → au lancement, on la bascule sur l'API prod et le
   webhook dev cesse de recevoir. `REVENUCAT_WEBHOOK_SECRET` de dev devient une
   valeur morte, à retirer plutôt qu'à garder « au cas où ».
3. On accepte de partager la même valeur des deux côtés en attendant → à écrire
   explicitement dans les notes, **parce que c'est la seule exception au groupe 2
   et qu'une exception tacite est une régression silencieuse**.

Owner au 2026-09-03 : **pas encore regardé**, la question reste ouverte. Le chemin
pour trancher est la liste des webhooks du projet (sélecteur de projet en haut de
la barre latérale → `Integrations` → `Webhooks`) : ce qui répond, c'est la
présence ou l'absence d'un bouton d'ajout au-dessus de la liste des webhooks
existants. S'il est là, c'est l'issue 1.

Écrire la réponse constatée dans les notes d'implémentation : c'est l'AC #8.

## Comment procéder

Le secret est un **shell vide créé par Terraform** (`modules/platform/secrets.tf`) :
`secret_payload` n'est plus passé pour prod (task-221 §7.3, seule partie de §7.3
qui tient toujours — ne jamais écrire un credential dans le state Terraform). La
valeur se pousse à la main :

```bash
AWS_PROFILE=prod aws secretsmanager put-secret-value \
  --secret-id media-summarizer-runtime-prod \
  --secret-string file://runtime-secrets.json   # puis supprimer le fichier local
```

Piège mesuré sur task-136 : une valeur collée avec un commentaire en fin de ligne
ou un espace final est acceptée par Secrets Manager et casse l'intégration
**silencieusement**. Vérifier chaque valeur sensible après écriture
(`get-secret-value | jq -r .CLE | wc -c`). Ne jamais committer de valeur :
`terraform.tfvars` est gitignoré, seul `terraform.tfvars.example` est suivi et ne
contient que des placeholders.

## Owner notes (pas des critères d'acceptation)

- Le déploiement des Lambdas prod se fait sur push vers `main` ; le secret n'est
  relu qu'au **cold start**. Après le `put-secret-value`, forcer un cold start
  avant de conclure que quelque chose ne marche pas.
- `enable_alarms`, `enable_dashboard` et `enable_worker_polling` sont à `false` sur
  prod (mise en veille, `envs/prod/main.tf`). Un worker ne consommera aucune file
  tant que ce n'est pas rebasculé : ne pas conclure d'un silence que les
  credentials sont faux.
- Le quota Lambda « Concurrent executions » du compte prod est passé de 10 à
  **1000 le 2026-08-13** (`L-B99A9384`, accordé ; relevé le 2026-09-03). Ce n'est
  donc plus une explication possible d'un throttling constaté ici. En revanche
  aucune réservation n'existe encore côté AWS : la ligne de contournement
  `api_reserved_concurrency = -1` a été retirée d'`envs/prod/main.tf` le
  2026-09-03, mais l'`apply` prod manuel qui la matérialise reste à faire (cf.
  `docs/V1_LAUNCH_PLAN.md`, Phase 9 point 3 — cet apply bute sur la protection de
  suppression d'`artifact_idempotence-prod`).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le secret runtime de prod contient exactement les 37 clés vivantes de dev — aucune absente, et aucune des 3 mortes (ALGOLIA_INDEX_NAME, COOKIE_DOMAIN, APIFY_INSTAGRAM_COMMENT_ACTOR_ID) — vérifié par diff des deux listes de noms de clés
- [ ] #2 Les 5 clés du groupe 2 (JWT_SECRET_KEY, PRICING_ADMIN_SECRET, APIFY_WEBHOOK_SECRET, REVENUCAT_WEBHOOK_SECRET, ALGOLIA_API_KEY) ont une valeur différente de celle de dev, vérifié par comparaison des empreintes des deux secrets et non des valeurs en clair
- [ ] #3 ALGOLIA_API_KEY de prod n'est pas seulement neuve mais restreinte à l'index media_items_prod — prouvé par un appel réel sur media_items_dev avec la clé prod, qui doit échouer ; et la clé Algolia de dev est restreinte symétriquement à media_items_dev, prouvé par un appel réel sur media_items_prod qui doit échouer aussi
- [ ] #4 Les 30 clés du groupe 1 sont identiques à celles de dev ; en particulier GOOGLE_CLIENT_ID, GOOGLE_NATIVE_AUDIENCE_IOS et GOOGLE_NATIVE_AUDIENCE_ANDROID sont égales aux valeurs du profil production de mobile/eas.json
- [ ] #5 Aucune valeur ne porte d'espace final ni de commentaire résiduel, vérifié clé par clé sur les valeurs sensibles
- [ ] #6 Aucune valeur n'est committée dans le dépôt ; seul terraform.tfvars.example est mis à jour, avec des placeholders
- [ ] #7 APPLE_REDIRECT_URI et GOOGLE_REDIRECT_URI sont soit renseignées avec le domaine prod retenu, soit listées dans les notes comme restant à faire, avec leur bloquant nommé
- [ ] #8 La question du webhook RevenueCat est tranchée et l'issue retenue parmi les trois est écrite dans les notes d'implémentation
- [ ] #9 Une invocation réelle prouve qu'au moins une intégration tierce fonctionne en prod avec ces credentials, et non la seule lecture du secret
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-13 — Tâche créée à la clôture de task-237 pour ne pas perdre la trace du
seul reste-à-faire de son critère #7. Le critère #7 de task-237 est marqué
**suspendu**, pas satisfait : staging existe bien et `enable_alarms` est conforme
à la décision de mise en veille du 2026-08-12, mais le secret runtime n'a jamais
été peuplé — et il ne devait pas l'être sur staging, que task-248 a détruit.

2026-08-21 — Tâche réécrite après audit clé par clé du secret dev contre le code,
`mobile/eas.json`, `docs/REVENUECAT_ENTITLEMENTS.md` et les dashboards tiers.
Trois erreurs de la version initiale sont corrigées :

- **L'ancienne AC #3 était insatisfaisable.** « Les clés RevenueCat sont les clés
  live du projet, pas les clés sandbox » : RevenueCat n'a pas de couple
  sandbox/live. Supprimée.
- **L'ancienne AC #2 exigeait un `ALGOLIA_INDEX_NAME` distinct.** Cette clé est
  morte, aucun code ne la lit, et l'index est dérivé de `ENVIRONMENT`. Vérifier une
  clé morte, c'est vérifier du vide. Remplacée par l'AC #3 actuelle, qui porte sur
  le scope de la clé API — le seul endroit où l'isolation Algolia se joue.
- **Le décompte a dérivé** : 40 clés sur dev, dont 3 mortes. Le total de 37 tient
  toujours, mais pas avec la même composition.

Ajout de la dépendance sur task-312, conformément à la règle « les cleanups
d'abord » : elle supprime le chemin mort qui lisait `ALGOLIA_SEARCH_API_KEY` et
évite de créer cette clé pour prod.

2026-09-03 — **Cinq groupes ramenés à deux**, à la demande de l'owner, pour que la
tâche s'exécute en deux gestes au lieu de cinq. Critère unique : *une clé n'est
recréée que si la partager avec dev fait courir un risque réel*. L'audit clé par
clé du 2026-08-21 n'est pas remis en cause — c'est un reclassement, pas une
révision. Ce qui change :

- **`ALGOLIA_API_KEY` monte en groupe 2** (elle était dans l'ancien groupe C, avec
  des clés dont le seul bénéfice était l'attribution de coût). Elle est d'une autre
  nature : clé Admin sur toute l'application, donc dev peut effacer l'index prod.
  C'est le seul changement de fond du regroupement.
- **AC #3 réécrite en conséquence** : elle ne porte plus sur « 5 clés neuves du
  groupe C » mais uniquement sur Algolia, et elle exige désormais la **symétrie**
  — la clé dev doit être restreinte à `media_items_dev`, pas seulement la clé prod
  à `media_items_prod`. Sans ça le risque reste ouvert dans le sens qui compte :
  dev garderait une clé Admin capable d'effacer l'index prod. Cette symétrie était
  déjà écrite dans la description du 2026-08-21 mais n'était vérifiée par aucun
  critère.
- **AC #2 passe de 4 à 5 clés**, **AC #4 de 18 à 30**.
- **Les 2 redirect URI sortent des groupes.** Les forcer dans « recopier de dev »
  aurait reproduit la panne silencieuse de task-136 : leur valeur doit différer,
  mais pour une raison de configuration d'environnement, pas de risque. Elles
  restent couvertes par l'AC #7, inchangée.

Deux arbitrages tranchés par l'owner le même jour, dont le premier contre la
recommandation — écrits dans la description pour ne pas être rejoués :
`OPENAI_API_KEY` / `DEEPGRAM_API_KEY` restent en groupe 1 (donc pas d'attribution
de coût par environnement, ce qui devra rouvrir quand le pricing s'appuiera sur du
réel), et les 3 tokens Apify se recopient (donc crédits communs, un épuisement en
dev arrête l'ingestion prod). La question du webhook RevenueCat n'est pas encore
regardée dans le dashboard et reste ouverte.
<!-- SECTION:NOTES:END -->
