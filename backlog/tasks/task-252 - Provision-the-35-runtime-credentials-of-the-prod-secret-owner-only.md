---
id: task-252
title: Provision the 35 runtime credentials of the prod secret (owner only)
status: Done
assignee: []
created_date: '2026-08-13 07:30'
updated_date: '2026-09-03 16:20'
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
> Cette tâche manipule des credentials tiers que **seul l'owner détient**. Aucun
> agent ne doit tenter de les obtenir, de les fabriquer ni de les deviner. Le
> verrou `dispatchable: false` du front-matter est lu par
> `scripts/dispatch_backlog.sh` (denylist impérative injectée dans le prompt du
> dispatcher), indépendamment du statut, de la priorité, des labels et des
> dépendances. **Le verrou reste en place bien que la tâche soit `Done`** : elle
> décrit la composition d'un secret de production et sert de référence de
> rotation.

## Résultat — fait le 2026-09-03

`media-summarizer-runtime-prod` (compte `866874944541`, eu-west-3) est passé de
`{}` à **35 clés**. Le bloquant de lancement dur est levé.

| | Clés | Vérification |
|---|---|---|
| Recopiées à l'identique depuis dev | 30 | empreintes sha256 comparées clé par clé, jamais les valeurs en clair |
| Générées pour prod | 3 | `JWT_SECRET_KEY`, `PRICING_ADMIN_SECRET`, `REVENUCAT_WEBHOOK_SECRET` — 32 octets aléatoires en hex |
| Dérivées du domaine prod | 2 | `APPLE_REDIRECT_URI`, `GOOGLE_REDIRECT_URI` |
| Mortes, volontairement absentes | 5 | cf. plus bas |
| Valeurs vides | 0 | contrôlé après écriture |

La copie a été faite **de Secret Manager à Secret Manager**, sans fichier
intermédiaire dans le dépôt et sans qu'aucune valeur transite par une sortie
console : lecture du secret dev en fichier temporaire `0600`, transformation
`jq`, `put-secret-value --secret-string file://…`, puis `shred`. Le hash de
`APPLE_PRIVATE_KEY` est identique de part et d'autre, ce qui prouve que le `.p8`
multiligne a fait l'aller-retour JSON sans altération — c'était le seul risque
de corruption silencieuse du procédé.

**Preuve d'exécution réelle, pas seulement de lecture du secret** :
`POST https://f45y1buebe.execute-api.eu-west-3.amazonaws.com/api/webhooks/revenucat`
répond `401 Invalid authorization` sur un Bearer faux et `400 Missing event type`
sur le bon Bearer avec un corps `{}`. Le `400` sort de
`revenucat_webhook.py:676`, donc **après** le contrôle d'autorisation de la
ligne 653 et **avant** tout accès DynamoDB : la Lambda de prod a fait un cold
start, lu le secret, et compare bien contre la valeur générée ici. Un `500`
aurait signifié un secret absent, un `401` une valeur fausse.

### Les 5 clés mortes, volontairement absentes de prod

`ALGOLIA_INDEX_NAME` · `COOKIE_DOMAIN` · `APIFY_INSTAGRAM_COMMENT_ACTOR_ID` ·
`REVENUCAT_API_KEY` · `REVENUCAT_PROJECT_ID`

Aucune n'a de lecteur dans le dépôt. Les trois premières sont déjà documentées
comme mortes (`docs/DEVBOX_SETUP.md:200-208`, `task-293`, `task-173`) et
`task-312` les retire du secret dev. Les deux dernières sont la correction du
2026-09-03 : `config.py:84` et `:86` les affectent et **aucun autre code ne les
consomme**. `REVENUCAT_API_KEY` est le bearer que l'owner utilise pour piloter le
dashboard RevenueCat par l'API v2 (`docs/REVENUECAT_ENTITLEMENTS.md:147`,
`task-238` AC#4, `task-261`), lu depuis le `.env` racine — c'est un credential
**d'outillage**, pas de runtime. Il n'a rien à faire dans un secret que seules
les Lambdas lisent.

Recopier une clé morte dans un secret neuf, c'est fabriquer du legacy de zéro.
D'où 40 clés en dev, 5 mortes, **35 vivantes** — et le titre corrigé de 37 à 35
le 2026-09-03.

### Les 5 clés dont la valeur diffère de dev

| Clé | Pourquoi | Qui l'a produite |
|---|---|---|
| `JWT_SECRET_KEY` | Secret partagé ⇒ un token émis par dev est **accepté par prod**. Les deux environnements ne forment plus qu'un domaine de confiance | générée, 32 octets hex |
| `PRICING_ADMIN_SECRET` | Idem sur l'endpoint admin pricing | générée, 32 octets hex |
| `REVENUCAT_WEBHOOK_SECRET` | Chaque intégration webhook RevenueCat porte son propre en-tête `Authorization` ⇒ la valeur **doit** différer, pour une raison structurelle | générée, 32 octets hex |
| `APPLE_REDIRECT_URI` | URL d'environnement. Celle de dev pointe sur l'API Gateway de dev | dérivée du domaine prod |
| `GOOGLE_REDIRECT_URI` | Idem | dérivée du domaine prod |

`JWT_SECRET_KEY` de prod fait **256 bits**. Celui de dev n'en fait que 23
caractères, soit ~138 bits, sous le minimum que la RFC 7518 impose à HS256 —
l'algorithme effectivement utilisé (`utils/auth_utils.py:97`). Ce n'est pas un
sujet de cette tâche mais **dev reste sous-dimensionné** ; à rotater à
l'occasion.

Les deux redirect URI valent
`https://f45y1buebe.execute-api.eu-west-3.amazonaws.com/api/auth/{apple,google}/callback`,
soit l'API Gateway de prod, exactement comme dev pointe sur la sienne.

**Corrigé le 2026-09-03 après signalement de l'owner.** Elles ont d'abord été
écrites sur `api.secondbrainlabs.com`, en s'appuyant sur ce plan qui donnait ce
Return URL pour « déjà enregistré » chez Apple. **L'owner ne possède aucun
domaine** — ni celui-là, ni un autre. `secondbrainlabs.com` appartient à un
tiers : il résout et renvoie `301` vers `sbl.so`, qui refuse la connexion. La
correction n'a touché que ces deux clés, les 33 autres empreintes étant
inchangées après réécriture.

Impact fonctionnel de l'erreur : **nul**, vérifié et non supposé. Ces deux clés
ne sont lues que par `/{apple,google}/login` et `/{apple,google}/callback`
(`auth_social.py:180-226` et `:400-445`), le flux **web**. L'app mobile n'appelle
que `/{apple,google}/native` (`mobile/src/services/authService.ts:84` et `:104`),
qui valide l'`id_token` contre les audiences natives et n'utilise aucun redirect
URI. Aucun client web n'existe (`docs/AUTHENTICATION_SETUP.md:14`). Les deux
valeurs sont donc inertes dans les deux environnements, et le resteront jusqu'à
ce qu'un flux web existe.

La leçon, elle, n'est pas inerte : **ne jamais déduire d'un plan qu'un domaine est
détenu**, ni d'une réponse DNS. Cf. Phase 10 §0bis, qui trace comment
`task-115` (« domaine prévu, à acheter ») s'est transformé en fait acquis.

### Décisions de l'owner, à ne pas rejouer

Le critère a changé le 2026-09-03, et c'est ce changement qui a produit la
composition ci-dessus. La question n'est plus « cette clé risque-t-elle de
fuiter » mais **« partager cette clé fait-elle qu'un test en dev modifie
automatiquement le comportement de prod »**. Constat qui fonde tout le reste :
les deux secrets sont des **objets AWS distincts dans deux comptes distincts**,
donc recopier une valeur ne crée **aucun lien vivant** — changer la valeur de dev
demain ne touche pas prod. Le couplage ne peut venir que du **tiers derrière la
clé**, et il existe alors que les clés soient identiques ou non. Corollaire
contre-intuitif : dans la plupart des cas, **dupliquer la clé ne répare rien** ;
il faut dupliquer le compte ou scoper la clé.

- **`ALGOLIA_API_KEY` se recopie.** La version précédente de cette tâche la
  classait « clé neuve obligatoire » parce que c'est une clé Admin portée sur
  toute l'application, donc capable d'effacer l'index prod. Vérification faite,
  c'est une **capacité** et non un couplage : `utils/algolia_client.py:66-92` ne
  fait que `set_settings` sur `media_items_{ENVIRONMENT}`, et le seul code qui
  appelle `list_indices`/`delete_index` est le script one-shot
  `scripts/migrate_algolia_to_shared_index.py`, dont le motif
  `^(.+)_user_(.+)$` ne peut pas matcher `media_items_*`. En l'état du code, dev
  n'écrit jamais dans l'index prod. **Conséquence assumée** : la capacité
  destructive croisée reste ouverte — un `curl` à la main, un futur script ou un
  agent peut viser l'index prod avec la clé dev. Algolia autorise un nombre
  illimité de clés scopées par index (« Indices: the indices that are
  accessible »), donc la réparation reste gratuite et disponible si le besoin
  apparaît.
- **`APIFY_WEBHOOK_SECRET` se recopie.** Le webhook Apify est configuré **par
  run** — `infrastructure/apify_adapter.py:146-147` envoie l'URL de callback et
  le secret à la création de chaque run. Il n'existe aucun rendez-vous partagé
  entre les environnements, donc aucun couplage.
- **`OPENAI_API_KEY` et `DEEPGRAM_API_KEY` se recopient**, contre la
  recommandation. Un project dédié était gratuit et fermait complètement le
  couplage des deux côtés : OpenAI documente « create separate projects for your
  staging and production environments » avec « custom rate and spend limits per
  project », et Deepgram va plus loin — « Projects in Deepgram are completely
  distinct environments with no connection to one another », « Projects are
  assigned credits », et la recommandation explicite « for best results, use
  different API keys for testing and production ». **Conséquences assumées** :
  rate limits et budget OpenAI communs, crédits Deepgram communs, donc un
  emballement de retries en dev peut throttler ou arrêter prod ; et aucun coût
  par utilisateur n'est attribuable, ce qui touche `task-65`. À rouvrir quand le
  pricing devra s'appuyer sur du réel.
- **Les 3 tokens Apify se recopient.** Ici une clé neuve n'aurait rien réparé :
  les limites Apify sont documentées « per user » et par plan, sans aucun
  plafond par token, et au dépassement « Apify platform services will be
  suspended ». **Conséquence assumée** : crédits communs, un épuisement en dev
  **arrête l'ingestion prod**. La seule réparation serait un second compte.
- **`X_API_BEARER_TOKEN` se recopie**, même raisonnement : les lectures sont
  comptées au niveau du projet, pas de l'app.
- **`CANNY_BOARD_TOKEN` se recopie.** Le couplage est réel — tester le feedback
  depuis l'app dev poste sur le board public que les vrais users lisent — mais
  la réparation est **un board, pas une clé** : la clé API Canny est
  company-level (`developers.canny.io/api-reference`), tandis que les boards
  neufs sont privés par défaut et Canny documente ce motif pour le beta testing.
  À faire le jour où ça pollue.
- **`LLAMAPARSE_API_KEY` et `UNSTRUCTURED_API_KEY` se recopient.** Leurs docs ne
  disent pas à quel niveau le quota est porté ; à vérifier dans les dashboards
  si un épuisement se produit.

### Ce qui reste ouvert, et où ça vit

- 🛑 **Aucun domaine n'est possédé** (owner, 2026-09-03). Ce n'est pas « le
  domaine n'est pas tranché » : rien n'a été acheté. `secondbrainlabs.com` est à
  un tiers, `mediasummarizer.com` et les deux sous-domaines `api.*` sont en
  `NXDOMAIN`, et le profil `production` de `mobile/eas.json` pointe sur
  `api.mediasummarizer.com`, qui n'existe pas. Conséquence sur ce secret :
  `APPLE_REDIRECT_URI` et `GOOGLE_REDIRECT_URI` sont à rejouer par
  `put-secret-value` le jour d'un achat — l'étape est en Phase 10 §0bis. Le reste
  du secret n'est pas concerné. **Prérequis dur de la soumission stores**, en
  revanche : Apple et Google exigent une politique de confidentialité hébergée.
- **`X_API_BEARER_TOKEN` pourrait être périmé au sens du plan tarifaire.**
  Plusieurs sources tierces affirment que X a supprimé son free tier en février
  2026, une autre le décrit encore actif ; elles se contrediennent. À vérifier
  dans la console développeur. Si c'est vrai, c'est un bloquant de l'ingestion X
  sans rapport avec les credentials.

## Historique du périmètre

### Correction du 2026-08-21 : « ne rien recopier de dev » était faux

La première version interdisait de reprendre la moindre valeur de dev, en
s'appuyant sur le benchmark `task-221` §7.3. Vérification faite clé par clé,
**cette consigne aurait produit une prod cassée**. §7.3 a été écrit avant que
RevenueCat, Sign in with Apple et Sign in with Google soient câblés, à une époque
où « une clé par environnement » était encore une abstraction sans app. La seule
partie de §7.3 qui tient toujours : **ne jamais écrire un credential dans le
state Terraform**.

- **Il n'y a qu'une seule app.** Un bundle ID (`com.secondbrainlabs.core`,
  `mobile/app.config.ts:98` et `:125`), un compte Apple Developer, un projet
  Google Cloud, un projet RevenueCat. Les identités OAuth et IAP ne sont pas
  « par environnement » : elles sont **par app**.
- **Le profil `production` de `mobile/eas.json` embarque exactement les mêmes
  `EXPO_PUBLIC_GOOGLE_CLIENT_ID_*` que `development`.** Le binaire qui part sur
  les stores porte ces client IDs. Un backend prod qui n'accepterait pas ces
  audiences refuserait tous les Sign in with Google.
- **`APPLE_NATIVE_AUDIENCE` vaut littéralement le bundle ID.**
- **Les 4 actor IDs Apify sont des identifiants publics** de la marketplace, et
  `DEEPGRAM_MODEL` / `OPENAI_MODEL` ne sont pas des clés mais de la
  configuration.
- **Les 3 tokens Apify sont 3 comptes distincts**, créés par `task-127` pour
  cumuler les crédits gratuits.
- **L'isolation Algolia est structurelle** : `utils/algolia_client.py` dérive
  l'index en `media_items_{ENVIRONMENT}` et
  `modules/platform/runtime_env.tf:103` injecte `ENVIRONMENT = "prod"`. Prod a
  `media_items_prod` sans qu'aucune clé ne le décide.
- **`ALGOLIA_SEARCH_API_KEY`** était lue par le code mais absente de dev *et* de
  Terraform. `task-312` supprime le chemin qui la lisait ; d'où la dépendance,
  qui évitait d'hériter d'une clé à créer pour rien. Elle est bien absente de
  prod.

### Correction du 2026-09-03 : le webhook RevenueCat n'était pas irréductible

La version précédente posait comme question ouverte « RevenueCat n'expose qu'une
URL de webhook par projet, donc qui reçoit les events ? », avec trois issues
possibles. **La prémisse était fausse**, et la doc dit l'inverse : « You can set
up multiple webhook integrations per project », « Select whether to send events
for production purchases, sandbox purchases, or both », et le cas d'usage est
nommé explicitement — « if you use a different backend for production and
sandbox/testing, you can set up two webhook integrations ». Le payload porte
`environment: SANDBOX`, et « RevenueCat itself does not have sandbox and
production environments » : le sandbox est bien un attribut de la transaction,
mais le **routage** est configurable.

C'est l'issue 1, et elle est appliquée. Configuré par l'owner le 2026-09-03 dans
`Integrations` → `Webhooks` :

- l'intégration existante (URL de l'API dev) est restreinte aux **sandbox
  purchases** et garde le secret de dev ;
- une seconde intégration pointe sur l'API prod, restreinte aux **production
  purchases**, avec le secret généré ici.

Le toggle `HMAC webhook signing` est resté **désactivé** : le backend compare
l'en-tête `Authorization` en clair (`revenucat_webhook.py:653`), il
n'implémente pas la vérification HMAC. L'activer casserait le webhook.

C'était le seul couplage dev→prod de la liste qui touchait un flux de paiement,
et il est fermé sans second projet RevenueCat.

## Rotation — comment refaire ce geste

Le secret est un **shell vide créé par Terraform**
(`modules/platform/secrets.tf`) : `secret_payload` n'est pas passé, et
`ignore_changes` empêche Terraform de proposer d'écraser la valeur. Elle se
pousse à la main :

```bash
AWS_PROFILE=prod aws secretsmanager put-secret-value \
  --secret-id media-summarizer-runtime-prod \
  --secret-string file://runtime-secrets.json   # puis shred le fichier local
```

Piège mesuré sur `task-136` : une valeur collée avec un commentaire en fin de
ligne ou un espace final est acceptée par Secrets Manager et casse l'intégration
**silencieusement**. Passer par `jq` plutôt que par un éditeur évite la classe
entière. Contrôler après écriture par empreinte, jamais en affichant la valeur :

```bash
AWS_PROFILE=prod aws secretsmanager get-secret-value \
  --secret-id media-summarizer-runtime-prod --region eu-west-3 \
  --query SecretString --output text | jq -r 'to_entries[]|"\(.key)\t\(.value)"' \
  | while IFS=$'\t' read -r k v; do \
      printf '%s %s\n' "$k" "$(printf '%s' "$v" | sha256sum | cut -c1-12)"; done
```

## Owner notes (pas des critères d'acceptation)

- Le secret n'est relu qu'au **cold start** des Lambdas. Après un
  `put-secret-value`, forcer un cold start avant de conclure que quelque chose ne
  marche pas.
- `enable_alarms`, `enable_dashboard` et `enable_worker_polling` sont à `false`
  sur prod (mise en veille, `envs/prod/main.tf`). **Aucun worker ne consommera de
  file tant que ce n'est pas rebasculé** : ne pas conclure d'un silence que les
  credentials sont faux. Les 35 clés sont en place, mais seule l'API répond.
- Le quota Lambda « Concurrent executions » du compte prod est à **1000 depuis le
  2026-08-13** (`L-B99A9384`, accordé). Ce n'est plus une explication possible
  d'un throttling. En revanche l'`apply` prod qui matérialise la réservation
  reste à faire et **bute sur la protection de suppression
  d'`artifact_idempotence-prod`** (cf. `docs/V1_LAUNCH_PLAN.md`, Phase 9 point 3).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le secret runtime de prod contient exactement les 35 clés vivantes de dev — aucune absente, et aucune des 5 mortes (ALGOLIA_INDEX_NAME, COOKIE_DOMAIN, APIFY_INSTAGRAM_COMMENT_ACTOR_ID, REVENUCAT_API_KEY, REVENUCAT_PROJECT_ID) — vérifié par diff des deux listes de noms de clés
- [x] #2 Les 3 secrets maison de prod (JWT_SECRET_KEY, PRICING_ADMIN_SECRET, REVENUCAT_WEBHOOK_SECRET) ont une valeur différente de celle de dev, vérifié par comparaison des empreintes des deux secrets et non des valeurs en clair
- [ ] #3 ALGOLIA_API_KEY de prod est restreinte à l'index media_items_prod et celle de dev à media_items_dev, prouvé par un appel croisé réel qui doit échouer dans les deux sens
- [x] #4 Les 30 clés recopiées sont identiques à celles de dev ; en particulier GOOGLE_CLIENT_ID, GOOGLE_NATIVE_AUDIENCE_IOS et GOOGLE_NATIVE_AUDIENCE_ANDROID sont égales aux valeurs du profil production de mobile/eas.json
- [x] #5 Aucune valeur ne porte d'espace final ni de commentaire résiduel, et aucune n'est vide — contrôlé sur les 35 clés après écriture
- [x] #6 Aucune valeur n'est committée dans le dépôt
- [x] #7 APPLE_REDIRECT_URI et GOOGLE_REDIRECT_URI sont renseignées avec un endpoint qui existe réellement — l'API Gateway de prod, en miroir de dev — et le bloquant qui reste (aucun domaine n'est possédé) est nommé à l'endroit qui porte la bascule
- [x] #8 Le routage du webhook RevenueCat est tranché et configuré : une intégration par environnement, filtrée sur sandbox d'un côté et production de l'autre
- [x] #9 Une invocation réelle prouve que prod lit et utilise ces credentials, et non la seule lecture du secret
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-13 — Tâche créée à la clôture de `task-237` pour ne pas perdre la trace du
seul reste-à-faire de son critère #7, marqué **suspendu** et non satisfait :
staging existait bien, mais son secret runtime n'a jamais été peuplé — et il ne
devait pas l'être sur staging, que `task-248` a détruit.

2026-08-21 — Tâche réécrite après audit clé par clé du secret dev contre le code,
`mobile/eas.json`, `docs/REVENUECAT_ENTITLEMENTS.md` et les dashboards tiers.
Trois erreurs de la version initiale corrigées : l'ancienne AC #3 exigeait des
« clés live plutôt que sandbox » chez RevenueCat, qui n'a pas ce couple ;
l'ancienne AC #2 exigeait un `ALGOLIA_INDEX_NAME` distinct, or la clé est morte ;
et le décompte avait dérivé. Ajout de la dépendance sur `task-312` selon la règle
« les cleanups d'abord ».

2026-09-03 — **Tâche exécutée et fermée.** Le critère de regroupement a été
remplacé en cours de session : de « cette clé risque-t-elle de fuiter » à
« partager cette clé fait-elle qu'un test en dev modifie automatiquement prod ».
Ce changement vient de l'owner et il est correct — le raisonnement « une copie en
dev est plus exposée que sa copie en prod » confondait *capacité* et *couplage
automatique*, alors que les deux secrets sont des objets AWS distincts dans deux
comptes distincts.

Sous ce critère, le groupe « clé neuve obligatoire » tombe de 5 à 3, et le
travail se déplace vers les tiers à état ou quota partagé. Quatre erreurs de la
version du 2026-09-03 matin ont été corrigées, sourcées auprès des fournisseurs :

- **Le webhook RevenueCat était présenté comme irréductible.** Faux : plusieurs
  intégrations par projet, chacune filtrable sur sandbox ou production. La
  question ouverte est donc résolue par l'issue 1, et configurée.
- **Deepgram était donné comme non séparable.** Faux : les projects Deepgram sont
  des environnements étanches portant leurs propres crédits, et Deepgram
  recommande explicitement des clés distinctes test/prod. L'owner a maintenu la
  recopie ; la conséquence est écrite.
- **`ALGOLIA_API_KEY` était classée « clé neuve obligatoire ».** Reclassée : le
  code ne fait que `set_settings` sur son propre index et le seul script à
  opérations globales ne peut pas matcher `media_items_*`. C'est une capacité,
  pas un couplage. AC #3 reste **non cochée** : la symétrie de scope n'est pas
  faite, par décision de l'owner, et la capacité destructive croisée reste
  ouverte. Un critère non satisfait mais documenté vaut mieux qu'un critère
  réécrit pour être cochable.
- **Deux clés mortes de plus ont été trouvées** en lisant le secret dev plutôt
  que la liste de la tâche : `REVENUCAT_API_KEY` et `REVENUCAT_PROJECT_ID`, que
  la version précédente rangeait dans « identités par app à recopier ». Elles ne
  sont lues que par leur propre affectation dans `config.py`. D'où 35 et non 37,
  et le titre renommé.

Deux erreurs commises pendant l'exécution elle-même, notées parce qu'elles se
reproduiraient.

`APIFY_INSTAGRAM_COMMENT_ACTOR_ID` a d'abord été recopiée, parce que la liste des
clés mortes venait de la tâche et non du dépôt. Corrigée avant clôture.

Les redirect URI, elles, ont été **écrites faux et livrées faux** — d'abord
dérivées sur l'API Gateway de prod, puis « corrigées » vers
`api.secondbrainlabs.com` au motif que la Phase 10 §0bis le vise et donne le
Return URL Apple pour déjà enregistré. **L'owner a signalé le même jour qu'il ne
possède aucun domaine**, et les valeurs sont revenues à l'API Gateway. Le premier
réflexe était donc le bon, et la « correction » était l'erreur.

Ce qui l'a produite : le plan ne distinguait pas un domaine *visé* d'un domaine
*détenu*, et une vérification DNS avait paru confirmer la détention. La règle qui
en sort, écrite en Phase 10 §0bis : **résoudre en DNS ne prouve rien sur la
propriété.** Corollaire de méthode — un artefact du dépôt qui affirme un fait sur
un compte tiers n'est pas une source ; seul le dashboard ou l'owner l'est. Ici,
préférer le miroir de dev (chaque environnement pointe sur son propre gateway)
n'aurait demandé aucune hypothèse externe du tout.
<!-- SECTION:NOTES:END -->
