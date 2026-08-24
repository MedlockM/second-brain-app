---
id: task-252
title: Provision the 37 runtime credentials of the prod secret (owner only)
status: To Do
assignee: []
created_date: '2026-08-13 07:30'
updated_date: '2026-08-21 10:00'
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

Le vrai périmètre n'est donc pas « 37 credentials neufs ». C'est **4 valeurs à
générer, 5 clés à réémettre depuis les mêmes comptes, 18 à recopier parce que
c'est la seule option correcte, 8 à recopier faute de bénéfice, et 2 bloquées sur
le domaine.**

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

## Les 37 clés, par traitement

### Groupe A — valeur neuve obligatoire (4)

Secrets **maison**, pas des credentials tiers : aucun compte à ouvrir, un
`openssl rand -hex 32` suffit. C'est ici qu'est la seule vraie frontière de
sécurité de la liste.

| Clé | Pourquoi |
|---|---|
| `JWT_SECRET_KEY` | Partagée, un token émis par dev est **valide en prod**. |
| `PRICING_ADMIN_SECRET` | Idem pour l'endpoint admin pricing. |
| `APIFY_WEBHOOK_SECRET` | Bearer de `/api/webhooks/apify`. Auto-contenu : `infrastructure/apify_adapter.py:146-147` l'envoie lui-même à la création du run, rien à coller dans un dashboard. |
| `REVENUCAT_WEBHOOK_SECRET` | Secret choisi par l'owner et collé dans RevenueCat → Integrations → Webhooks. **Voir la question ouverte plus bas.** |

### Groupe B — identiques à dev, et c'est la seule option correcte (18)

`ALGOLIA_APP_ID` · `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` ·
`APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` · `APIFY_INSTAGRAM_POST_ACTOR_ID` ·
`APIFY_INSTAGRAM_REEL_ACTOR_ID` · `APPLE_CLIENT_ID` · `APPLE_TEAM_ID` ·
`APPLE_KEY_ID` · `APPLE_PRIVATE_KEY` · `APPLE_NATIVE_AUDIENCE` ·
`GOOGLE_CLIENT_ID` · `GOOGLE_CLIENT_SECRET` · `GOOGLE_NATIVE_AUDIENCE_IOS` ·
`GOOGLE_NATIVE_AUDIENCE_ANDROID` · `REVENUCAT_API_KEY` · `REVENUCAT_PROJECT_ID` ·
`DEEPGRAM_MODEL` · `OPENAI_MODEL`

- Les identités Apple/Google/RevenueCat sont **par app**, cf. ci-dessus.
- Les 4 actor IDs Apify sont des identifiants **publics** de la marketplace.
- `DEEPGRAM_MODEL` et `OPENAI_MODEL` sont de la configuration, pas des secrets. Les
  faire diverger est une décision produit (figer prod sur un modèle pinné et
  laisser dev flotter) et pas une décision de sécurité — à trancher séparément si
  l'envie vient, pas ici.
- `ALGOLIA_APP_ID` : le plan Build gratuit d'Algolia, c'est une application. Et
  l'isolation ne dépend pas de l'App ID, elle dépend de l'index.
- Deux exceptions possibles mais sans intérêt réel : `APPLE_KEY_ID` /
  `APPLE_PRIVATE_KEY` pourraient être une seconde clé Sign in with Apple du même
  team (Apple en autorise plusieurs). Gain : révocation indépendante. À faire
  seulement si c'est gratuit en temps.

### Groupe C — nouvelle clé émise depuis le **même compte** (5)

Pas de nouveau compte fournisseur : une clé de plus, gratuite, qui donne la
révocation indépendante et l'attribution de coût.

| Clé | Comment |
|---|---|
| `OPENAI_API_KEY` | Un *project* dédié dans la même org : usage et facturation attribués séparément. |
| `DEEPGRAM_API_KEY` | Idem via un project Deepgram. |
| `LLAMAPARSE_API_KEY` | Seconde clé du même compte. |
| `UNSTRUCTURED_API_KEY` | Seconde clé du même compte. |
| `ALGOLIA_API_KEY` | **Le vrai geste d'isolation Algolia est ici.** Aujourd'hui c'est la clé Admin, portée sur toute l'application : une Lambda dev peut effacer l'index prod. Algolia autorise un nombre illimité de clés **scopées par index** — une restreinte à `media_items_prod` pour prod, une à `media_items_dev` pour dev. |

### Groupe D — recopier de dev, bénéfice nul ou négatif (8)

`PODCASTINDEXORG_API_KEY` · `PODCASTINDEXORG_API_SECRET` · `X_API_BEARER_TOKEN` ·
`CANNY_BOARD_TOKEN` · `CANNY_SSO_PRIVATE_KEY` · `APIFY_YOUTUBE_API_TOKEN` ·
`APIFY_TIKTOK_API_TOKEN` · `APIFY_INSTAGRAM_API_TOKEN`

- PodcastIndex : gratuit, pas de donnée, pas de facturation à attribuer.
- X : le free tier est un projet par compte développeur ; deux apps partagent le
  quota de toute façon. Le sujet ici est le quota, pas l'isolation.
- Canny : le board est **public et unique**, c'est celui où les users postent. Un
  board « dev » séparé est un contresens.
- Les 3 tokens Apify sont **3 comptes distincts**, créés par task-127 pour cumuler
  les crédits gratuits. En créer trois de plus pour prod veut dire faire tourner
  la prod sur du free-tier. La vraie question est « prod passe-t-elle sur un compte
  Apify payant ? » — décision de coût, à trancher hors de cette tâche. Si on
  recopie, dev et prod se partagent les crédits : acceptable au lancement, à
  surveiller.

### Groupe E — bloquées sur le domaine public (2)

`APPLE_REDIRECT_URI` · `GOOGLE_REDIRECT_URI`

Elles pointent aujourd'hui sur l'URL brute API Gateway de dev. Un Service ID Apple
et un client web Google acceptent **plusieurs** Return URLs, donc partager
`APPLE_CLIENT_ID` / `GOOGLE_CLIENT_ID` entre dev et prod ne pose aucun problème :
seule la valeur de l'URI diffère.

Bloquant réel : `api.secondbrainlabs.com` et `api.mediasummarizer.com` sont tous
deux en NXDOMAIN, et le profil `production` de `mobile/eas.json` pointe encore sur
le second alors que le plan de lancement vise le premier. Il faut d'abord décider
quel domaine porte l'API (`docs/V1_LAUNCH_PLAN.md`, Phase 10 étape 0bis). Peupler
cette tâche en deux passes — les 35 clés indépendantes d'abord, ces 2 ensuite — est
parfaitement acceptable, à condition de le noter.

## Question ouverte à trancher : le webhook RevenueCat

RevenueCat n'expose qu'**une URL de webhook par projet**, et il n'y a qu'un projet.
Donc la question n'est pas « quelle valeur pour `REVENUCAT_WEBHOOK_SECRET` en
prod » mais **qui reçoit les events**. Trois issues possibles, à vérifier dans le
dashboard avant de peupler :

1. RevenueCat accepte plusieurs intégrations webhook sur le même projet → dev et
   prod ont chacun leur URL et leur secret, groupe A tel quel.
2. Une seule URL possible → au lancement, on la bascule sur l'API prod et le
   webhook dev cesse de recevoir. `REVENUCAT_WEBHOOK_SECRET` de dev devient une
   valeur morte, à retirer plutôt qu'à garder « au cas où ».
3. On accepte de partager la même valeur des deux côtés en attendant → à écrire
   explicitement dans les notes, parce que ça contredit le groupe A.

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
- Le quota Lambda « Concurrent executions » du compte prod est à 10 et une demande
  d'augmentation est PENDING (`envs/prod/main.tf`). Même remarque.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le secret runtime de prod contient exactement les 37 clés vivantes de dev — aucune absente, et aucune des 3 mortes (ALGOLIA_INDEX_NAME, COOKIE_DOMAIN, APIFY_INSTAGRAM_COMMENT_ACTOR_ID) — vérifié par diff des deux listes de noms de clés
- [ ] #2 Les 4 clés du groupe A (JWT_SECRET_KEY, PRICING_ADMIN_SECRET, APIFY_WEBHOOK_SECRET, REVENUCAT_WEBHOOK_SECRET) ont une valeur différente de celle de dev, vérifié par comparaison des empreintes des deux secrets et non des valeurs en clair
- [ ] #3 Les 5 clés du groupe C sont des clés neuves émises depuis le même compte fournisseur, et la clé Algolia de prod est restreinte à l'index media_items_prod — prouvé par un appel réel sur media_items_dev avec la clé prod, qui doit échouer
- [ ] #4 Les 18 clés du groupe B sont identiques à celles de dev ; en particulier GOOGLE_CLIENT_ID, GOOGLE_NATIVE_AUDIENCE_IOS et GOOGLE_NATIVE_AUDIENCE_ANDROID sont égales aux valeurs du profil production de mobile/eas.json
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
<!-- SECTION:NOTES:END -->
