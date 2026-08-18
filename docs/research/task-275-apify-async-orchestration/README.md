---
owner_decision: ok   # pending | ok | abandoned | redo | more
---

# Benchmark : orchestration non bloquante des fallbacks Apify

## Owner Validation

**Decision**: ce qui est recommandé
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

**Démarrer chaque run Apify de façon asynchrone avec un webhook ad hoc couvrant tous les états
terminaux, puis reprendre le pipeline par un message SQS. Ajouter au démarrage un unique message
SQS différé de réconciliation : à l'échéance, il ne fait rien si le callback a déjà été traité ;
sinon il relit le run chez Apify et reprend son résultat terminal ou échoue explicitement.**

Cette forme est recommandée pour **Instagram et TikTok**. Le code commun doit séparer :

1. un adaptateur Apify qui démarre le run, enregistre le webhook et renvoie immédiatement son
   `run_id` ;
2. les décodeurs propres à chaque actor ;
3. la reprise propre à chaque plateforme après lecture du dataset.

Le chemin recommandé est :

1. Le worker essaie le chemin gratuit yt-dlp, inchangé.
2. Sur le seul embranchement qui requiert Apify, il persiste un état `starting` et un identifiant
   d'essai sur le `ProcessingJob`.
3. Il démarre le run avec un webhook ad hoc pour `SUCCEEDED`, `FAILED`, `ABORTED` et `TIMED-OUT`.
   Le payload inclut l'identifiant du job et de l'essai ; le header d'autorisation porte un secret
   chargé depuis le secret runtime. Aucune valeur d'authentification n'est suivie dans Git.
4. Dès que l'API Apify répond, le worker persiste le `run_id`, publie un backstop avec
   `DelaySeconds=900`, puis rend la main. Il n'attend ni ne poll le provider.
5. `POST /api/webhooks/apify` authentifie l'appel, vérifie le couple job/run, puis publie un message
   de continuation. Il répond en `2xx` seulement après l'écriture durable sur SQS.
6. Le message de continuation relit le run et son dataset avec le token Apify côté serveur, puis
   continue exactement le chemin actuel de la plateforme. Le payload du webhook n'est jamais pris
   comme source de vérité pour le dataset.
7. Le backstop à 15 minutes relit le run si le job attend encore. Un run réussi est repris, un run
   terminal en échec est propagé, et une absence de statut exploitable devient un échec explicite.
   Le run Apify doit lui-même avoir un timeout inférieur, recommandé à **600 s**, afin que le
   backstop soit réellement terminal et non un heartbeat.

La recommandation supporte donc un ralentissement du provider de 100 s à 10 minutes sans augmenter
le temps d'exécution Lambda. Elle ne promet pas une attente infinie : au-delà de la limite provider,
le bon résultat produit est un échec observable et rejouable, pas un item éternellement
`extracting`.

### Conséquence sur les timeouts

- Worker Instagram : **300 s → 60 s** (`-240 s`, soit `-80 %`).
- Worker TikTok : **120 s → 60 s** (`-60 s`, soit `-50 %`).
- Visibilité des deux queues : **au moins 6 × 60 s = 360 s**, conformément à la recommandation AWS
  pour une event source Lambda/SQS. Le backstop est un nouveau message différé ; il ne dépend pas de
  la visibilité du message initial.

60 s couvre le plafond yt-dlp actuel de 30 s, le démarrage court du run Apify et les écritures
DynamoDB/SQS, avec une réserve. Ce chiffre doit être confirmé par les métriques de durée après
déploiement ; il ne doit pas être remonté pour absorber la durée de l'actor, puisque cette durée ne
vit plus dans la Lambda.

### Décision transverse TikTok

**Oui, TikTok doit adopter la même forme.** Son endpoint actuel
`run-sync-get-dataset-items` bloque une Lambda de 120 s, ne rend aucun `run_id` quand la connexion
est perdue, et la documentation Apify déconseille ce endpoint pour les nouvelles intégrations.
Instagram et TikTok diffèrent seulement par l'input actor et par le décodage du dataset, pas par
l'orchestration. Garder deux formes créerait deux politiques de retry, deux budgets et deux classes
d'incident pour le même provider.

YouTube présente aussi le même appel synchrone dans le dépôt, mais **son changement n'est pas un
critère de task-275**. La tâche `task-277` propose déjà une généralisation aux trois workers. L'owner
doit conserver un seul ticket d'implémentation après validation de ce benchmark : exécuter à la fois
`task-276` et `task-277` ferait deux fois le même chantier. Si `task-277` est conservée, son backstop
doit intégrer la réconciliation décrite ici au lieu de marquer aveuglément un run réussi comme
échoué parce que son callback s'est perdu.

## 1. Périmètre et faits d'entrée

### 1.1 Incident mesuré

Les chiffres ci-dessous viennent de `task-274`, des runs visibles dans le compte Apify et des logs
CloudWatch du 17 août 2026 :

| Fait | Mesure | Source reproductible |
|---|---:|---|
| Runs Instagram Apify récents | **63 à 100 s**, 6/6 `SUCCEEDED` | `task-274`; Apify Console → actor `apify/instagram-reel-scraper` → Runs, journée du 2026-08-17 |
| Même actor en juin | **6 à 9 s** | `task-274`; même vue Apify, journée du 2026-06-10 |
| Refus yt-dlp depuis Lambda | **6/6** | `task-274`; événement `instagram.reel.ytdlp_ip_blocked` dans le log group du worker/API dev |
| Plafond HTTP API | **30 s**, non augmentable | `infrastructure/terraform/modules/platform/lambda_api.tf:91` et [quotas HTTP API AWS](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html) |
| Worker Instagram après task-274 | Lambda **300 s**, SQS **1 800 s** | `infrastructure/terraform/modules/platform/lambda_workers.tf` et `sqs.tf` |
| Worker TikTok actuel | Lambda **120 s**, SQS **720 s** | mêmes fichiers Terraform |

Les 63-100 s sont la durée du run provider. Instagram dépense encore environ 2,5 s dans yt-dlp
avant de basculer. L'API mobile répond maintenant avant ce travail grâce à task-274 ; dans la suite,
« latence de save » distingue donc :

- l'acquittement HTTP, déjà asynchrone et inchangé par toutes les options ;
- le temps jusqu'à ce que le média quitte l'état de traitement.

### 1.2 Implémentation locale auditée

| Plateforme | Appel courant | Attente dans Lambda | Problème structurel |
|---|---|---:|---|
| Instagram | `POST /acts/{id}/runs`, puis `GET /actor-runs/{run_id}` toutes les 3 s | jusqu'au budget de la Lambda 300 s | le `run_id` existe, mais la Lambda attend et une redélivrance peut démarrer un second run |
| TikTok | `run-sync-get-dataset-items`, timeout client 120 s | jusqu'à 120 s | si la connexion casse, le run continue mais le caller ne reçoit ni état ni dataset |
| Deepgram | SQS puis pull/push dans un second worker | aucune attente dans le producer | précédent utile de **frontière asynchrone**, pas de callback provider existant |

Fichiers lus :

- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`
- `media_summarizer/workers/instagram_ingestion_worker.py`
- `media_summarizer/workers/tiktok_ingestion_worker.py`
- `media_summarizer/workers/lambda_handlers.py`
- `media_summarizer/utils/invocation_budget.py`
- `infrastructure/terraform/modules/platform/{lambda_workers,sqs}.tf`
- `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`
- benchmarks `task-107` et `task-140`

### 1.3 Hors périmètre

Le proxy résidentiel ne fait pas partie de cette décision. Il réduit la fréquence du fallback ; il
ne rend pas le fallback capable d'attendre sans Lambda. Il reste différé en V2 dans `task-145`.
La recommandation ci-dessus reste nécessaire si le fallback ne représente demain que 5 % des
saves, et elle reste correcte s'il en représente 100 % comme Instagram pendant l'incident.

## 2. Critères et hypothèses de volume

Les options sont comparées sur :

- latence d'acquittement et latence jusqu'au résultat, chemin heureux et chemin bloqué ;
- coût provider et coût AWS incrémental ;
- nouvelle infrastructure, surface publique et authentification ;
- sémantique de retry, doublons et callback absent ;
- comportement si le provider passe de 100 s à plusieurs minutes ;
- convergence Instagram/TikTok.

Les trois volumes sont des **fallbacks Apify par mois**, pas des saves totales :

| Scénario | Fallbacks/mois | Lecture |
|---|---:|---|
| Dev / tout début | 100 | quelques saves par jour |
| Lancement | 1 000 | quelques dizaines par jour |
| Haut V1 | 10 000 | proche de l'hypothèse de `task-140` (300 URLs/jour) |

La comparaison ne suppose aucun taux de fallback. À 100 % de blocage, le volume de fallbacks égale
le volume de saves ; si un proxy V2 réduit ce taux, toutes les lignes baissent proportionnellement.

## 3. Résumé comparatif

| Option | Lambda attend le run ? | Détection du résultat | Callback absent | Surface publique | Ralentissement > 5 min | Verdict |
|---|:---:|---|---|---|---|---|
| A. Webhook ad hoc + SQS + backstop | **Non** | événement terminal puis une reprise SQS | réconciliation unique à 15 min | un endpoint authentifié | supporté jusqu'au timeout actor choisi (10 min recommandé) | **Recommandée** |
| B. Auto-ré-enqueue SQS | Non | polling périodique, par ex. 15 s | sans objet | aucune | supporté jusqu'à la deadline applicative | second choix |
| C. `waitForFinish` / run-sync | **Oui**, jusqu'à 60/300 s | réponse longue, puis polling si non terminale | sans objet | aucune | fragile ; la durée est seulement déplacée | rejetée |
| D1. Step Functions Standard, callback | Non | task token + callback + timeout | `Timeout`/`Catch` durable | endpoint toujours nécessaire | jusqu'à un an | rejetée pour V1 |
| D2. Step Functions Express, polling | pas de Lambda pendant `Wait` | boucle Wait/HTTP | sans objet | aucune | **plafond dur 5 min** | rejetée |
| E. Garder le polling Lambda 300 s | **Oui** | polling 3 s | sans objet | aucune | échoue dès que le plafond bouge encore | rejetée |

## 4. Analyse des options

### 4.1 A — Webhook Apify ad hoc + continuation SQS + backstop (recommandée)

Apify permet d'attacher des webhooks à un run au moment de son démarrage. Les événements disponibles
couvrent succès, échec, abandon et timeout. Le webhook POST peut avoir un payload et des headers
templatisés. C'est la seule option évaluée qui :

- ne facture aucune attente Lambda ;
- réagit dès la transition terminale, sans cadence de polling ;
- conserve le `run_id` pour relire le statut et le dataset ;
- utilise le système de livraison provider, qui retente un non-`2xx` 11 fois avec backoff, jusqu'à
  environ 32 heures ;
- reste testable et récupérable grâce au backstop indépendant.

Apify prévient que la livraison peut être dupliquée. Le callback et la continuation doivent donc
être idempotents. Le endpoint ne fait aucun travail long : validation, écriture SQS, réponse. Apify
impose un timeout HTTP de deux minutes, mais le endpoint cible doit répondre bien avant le plafond
HTTP API de 30 s.

**Callback perdu.** Un webhook n'est pas une queue que nous contrôlons. Le backstop différé est
obligatoire même avec les 11 retries Apify. À 15 minutes :

1. job déjà repris ou terminal → `no-op` ;
2. job en attente avec `run_id` → `GET` du run ; succès = continuation normale, autre terminal =
   échec typé ;
3. run encore actif au-delà de son timeout contractuel, statut introuvable ou `run_id` absent →
   échec explicite `apify_callback_timeout`, métrique et message de failure.

Ce n'est pas un heartbeat. Il y a exactement un backstop par essai. Le timeout actor de 600 s est
séparé du timeout Lambda et laisse cinq minutes à la livraison/retry avant la réconciliation.

**Double-écriture start-run / DynamoDB.** L'API Run Actor ne documente pas de clé d'idempotence pour
le démarrage du run. Il reste donc une fenêtre entre l'acceptation du POST par Apify et la
persistance du `run_id`. La réduction de risque est :

- état conditionnel `starting` persisté avant le POST ;
- identifiant d'essai unique inclus dans le webhook ;
- une redélivrance voyant `starting` ne démarre pas immédiatement un autre run ;
- si le callback arrive avant l'écriture du `run_id`, il peut lier conditionnellement le run au bon
  essai après vérification serveur-à-serveur ;
- si réponse et callback sont tous deux perdus, le backstop échoue l'essai au lieu de facturer
  automatiquement un second run impossible à corréler.

Cette fenêtre ne peut pas être supprimée par `waitForFinish`, l'auto-polling ou Step Functions :
toutes les options commencent par le même appel externe non transactionnel.

### 4.2 B — Auto-ré-enqueue SQS avec `DelaySeconds` (second choix)

Le worker démarre le run, persiste son ID, poste un message `poll` différé, puis rend la main. Chaque
message lit le statut ; `RUNNING` reposte un message et un état terminal continue le pipeline.

Avantages :

- aucune route publique ni secret entrant ;
- aucune ressource AWS nouvelle ;
- ralentissement provider indépendant d'une invocation Lambda ;
- sémantique at-least-once déjà connue du dépôt.

Inconvénients :

- une cadence de 15 s ajoute 0 à 15 s de latence (7,5 s en moyenne) avant même le pickup SQS ;
- un run de 63-100 s produit 5 à 7 invocations de polling ;
- le code réimplémente un petit moteur d'orchestration, avec deadline, compteur, status et
  idempotence ;
- plus le provider ralentit, plus nous le pollons et plus les logs/invocations augmentent.

Amazon SQS limite `DelaySeconds` à 15 minutes. Ce n'est pas un problème pour un polling de secondes
ou un backstop de 15 minutes, mais cela montre que SQS n'est pas un scheduler général.

**Pourquoi ce n'est pas le premier choix.** Son avantage de sécurité est réel, mais le webhook
authentifié réutilise un pattern public déjà présent dans l'application et Apify fournit des retries
de livraison. Le webhook donne un signal immédiat ; le backstop SQS garde l'indépendance nécessaire.
La recommandation retient donc SQS pour la durabilité, pas pour poller continuellement.

### 4.3 C — `waitForFinish` et `run-sync-get-dataset-items` (rejetée)

Le paramètre `waitForFinish` de `POST /runs` vaut 0 par défaut et **60 s maximum**. Si le run ne
termine pas, la réponse contient simplement un statut transitoire. Il réduit éventuellement le
nombre de GET, mais la Lambda reste ouverte pendant toute l'attente.

Sur les six runs mesurés à 63-100 s :

- tous franchissent les 60 s ;
- chaque invocation paie donc 60 s de vide ;
- une continuation ou un polling reste nécessaire après la réponse ;
- un ralentissement à 5 minutes ne change rien à la faiblesse de l'architecture.

Le endpoint synchrone utilisé par TikTok peut attendre 300 s. Apify indique que la connexion peut se
casser avant, que le run continue alors sans rendre son statut au caller, et que ce endpoint hérité
n'est pas recommandé pour les nouvelles intégrations. Il déplace le polling dans Apify ; il ne
supprime pas l'attente distribuée.

### 4.4 D — Step Functions (rejetée pour ce périmètre)

#### Standard avec callback

Un workflow Standard peut attendre un task token jusqu'à un an, possède un historique durable et
une exécution exactement une fois hors retries explicitement configurés. Il faudrait néanmoins :

- une state machine et son rôle IAM ;
- un endpoint public pour transformer le webhook Apify en `SendTaskSuccess`/`SendTaskFailure` ;
- des Lambdas ou des HTTP Tasks pour le démarrage et la lecture du dataset ;
- des timeouts/catches et des alarmes supplémentaires ;
- éventuellement une EventBridge Connection, qui crée son propre secret Secrets Manager, si les
  appels Apify sont faits directement par HTTP Task.

Cette solution traite élégamment un portefeuille de workflows externes complexes. Pour deux
fallbacks linéaires dont l'état vit déjà dans DynamoDB/SQS, elle duplique le moteur durable existant
et ajoute une deuxième vue opérationnelle. Elle ne supprime pas la surface publique du webhook.

#### Express avec `Wait`/polling

Express est moins cher et adapté au haut volume, mais :

- exécution at-least-once ;
- durée maximale de **5 minutes** ;
- pas de pattern `.waitForTaskToken` ;
- facturation de toute la durée du workflow, même pendant `Wait` ;
- boucle de polling toujours présente.

Le plafond de 5 minutes contredit précisément le critère « résister au prochain ralentissement ».

**Seuil de réexamen.** Revenir à Step Functions Standard si le produit orchestre au moins trois à
cinq providers externes long-running avec fan-out, étapes parallèles, compensations ou approbations.
Ce n'est pas l'état de V1.

### 4.5 E — Conserver la Lambda 300 s et le polling actuel (rejetée)

Ce choix fait fonctionner le chiffre d'hier, pas l'architecture :

- 100 s est déjà 10 × la durée de juin ;
- le plafond Lambda absolu est 900 s ;
- la durée provider est facturée côté Apify même si la Lambda meurt ;
- la redélivrance SQS peut démarrer et facturer un nouveau run ;
- une invocation longue immobilise de la concurrence et élargit la visibilité SQS.

L'utilitaire `invocation_budget.py` de task-274 est un bon garde-fou transitoire : il empêche la
Lambda de mourir avant ses écritures terminales. Il ne transforme pas le polling en architecture
non bloquante.

## 5. Latence

| Option | Acquittement HTTP | Chemin yt-dlp heureux | Chemin provider bloqué, avant transcription aval |
|---|---|---|---|
| Polling actuel | inchangé, rapide depuis task-274 | ~2 s mesurées, inchangé | ~2,5 s + 63-100 s + granularité de poll 0-3 s |
| Webhook + SQS | inchangé | inchangé | ~2,5 s + durée actor + livraison webhook + un pickup SQS |
| Auto-ré-enqueue 15 s | inchangé | inchangé | ~2,5 s + durée actor + 0-15 s + pickup SQS |
| `waitForFinish=60` | inchangé | inchangé | au moins 60 s bloquées, puis continuation si le run dépasse 60 s |
| Step Functions callback | inchangé | inchangé | durée actor + webhook + reprise workflow/SQS |
| Step Functions Express polling | inchangé | inchangé | durée actor + 0-cadence de poll, échec dur à 5 min |

AWS ne publie pas de SLA de latence unitaire pour le pickup d'une event source SQS. Le mapping du
dépôt utilise `batch_size=1` et la fenêtre par défaut de 0 s, donc il ne retarde pas volontairement
pour remplir un batch. Le tout premier probe de task-274 a été consommé en environ 20 s sur un worker
qui n'avait encore jamais été invoqué ; c'est une borne observée de cold path, pas une garantie.

Le webhook peut donc ajouter un hop par rapport au polling dans la même invocation. C'est un
compromis assumé : l'objectif premier est que 10 minutes provider consomment 10 minutes provider,
pas 10 minutes Lambda. Un SLO raisonnable à mesurer après déploiement est « callback reçu → message
de continuation commencé en moins de 30 s au p95 ».

## 6. Coûts

### 6.1 Tarifs utilisés, eu-west-3, relevés le 2026-08-18

Les valeurs AWS viennent des index JSON officiels du Price List Service, version courante :

| Service | Tarif |
|---|---:|
| Lambda arm64 | **0,0000133334 USD / GB-s** (tier 1) |
| Lambda request | **0,20 USD / million** après free tier |
| SQS Standard | **0,40 USD / million** de requêtes (tier 1) |
| API Gateway HTTP API | **1,17 USD / million** de requêtes (premiers 300 M) |
| Step Functions Standard | **0,0000297 USD / transition** à Paris |
| Step Functions Express | **1 USD / million d'exécutions** + **0,00001667 USD / GB-s** (tier 1) |

Sources : [AWS Lambda Price List](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/eu-west-3/index.json),
[SQS Price List](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSQueueService/current/eu-west-3/index.json),
[API Gateway Price List](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonApiGateway/current/eu-west-3/index.json),
[Step Functions Price List](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonStates/current/eu-west-3/index.json).
Les free tiers sont partagés avec le reste du compte ; les tables ci-dessous montrent le coût brut
afin de ne pas les compter deux fois.

### 6.2 Coût provider, identique entre les architectures

Une architecture ne doit pas choisir un nouvel actor ; les prix ci-dessous établissent seulement
l'ordre de grandeur que le coût de coordination protège contre les runs dupliqués :

| Actor courant | Prix affiché | 100 runs | 1 000 runs | 10 000 runs |
|---|---:|---:|---:|---:|
| Instagram Reel Scraper, plan sans remise | 0,001 USD start + 0,0026 USD/reel | 0,36 USD | 3,60 USD | 36,00 USD |
| Instagram Reel Scraper, remise Gold | 0,001 USD start + 0,001 USD/reel | 0,20 USD | 2,00 USD | 20,00 USD |
| Best TikTok Transcripts Scraper | 1 USD / 1 000 résultats | 0,10 USD | 1,00 USD | 10,00 USD |

Sources : [prix Instagram Reel Scraper](https://apify.com/apify/instagram-reel-scraper/pricing) et
[prix Best TikTok Transcripts Scraper](https://apify.com/scrape-creators/best-tiktok-transcripts-scraper).
Le champ `usageTotalUsd` du run est la mesure de facturation à conserver en observabilité ; les
créateurs d'actors peuvent faire évoluer leurs prix indépendamment de ce benchmark.

### 6.3 Coût du temps Lambda éliminé

Les workers sont arm64, 512 MiB. Attendre 63-100 s coûte donc :

`0,5 GB × durée × 0,0000133334 = 0,000420 à 0,000667 USD par fallback`.

| Fallbacks/mois | Coût brut du seul wait 63-100 s |
|---:|---:|
| 100 | 0,042-0,067 USD |
| 1 000 | 0,420-0,667 USD |
| 10 000 | 4,20-6,67 USD |

Le montant n'est pas le risque principal, mais à 10 000 runs il devient du même ordre que le coût
actor TikTok. Surtout, le coût et le risque de timeout croissent linéairement avec un ralentissement
que nous ne contrôlons pas.

### 6.4 Coût de coordination comparé

Ces bornes excluent la courte durée active des appels HTTP/DynamoDB, identique ou dépendante de la
latence réseau, et isolent les prix déterministes :

| Option | Hypothèse | Coût fixe/run hors compute court | 100 | 1 000 | 10 000 |
|---|---|---:|---:|---:|---:|
| Webhook + continuation + backstop | 1 HTTP API, 3 invocations, 2 messages SQS (send/receive/delete) | < 0,000005 USD | < 0,0005 | < 0,005 | < 0,05 |
| Auto-poll SQS | 5-7 cycles ; 1 invocation + 3 ops SQS/cycle | 0,000007-0,000010 USD | 0,0007-0,0010 | 0,007-0,010 | 0,07-0,10 |
| `waitForFinish=60` | 60 s × 512 MiB | ~0,000400 USD | 0,040 | 0,400 | 4,00 |
| Step Functions Standard polling | 17-23 transitions pour 5-7 polls | 0,000505-0,000683 USD | 0,050-0,068 | 0,505-0,683 | 5,05-6,83 |
| Step Functions Standard callback | 4-6 transitions, endpoint non inclus | 0,000119-0,000178 USD | 0,012-0,018 | 0,119-0,178 | 1,19-1,78 |
| Step Functions Express | 63-100 s à 64 MiB, tasks non incluses | 0,000067-0,000105 USD | 0,007-0,011 | 0,067-0,105 | 0,67-1,05 |

Le calcul ne décide pas seul : toutes les options asynchrones sont petites devant le provider aux
volumes V1. Il confirme toutefois que Step Functions Standard polling paierait presque autant de
transitions que la Lambda actuelle paie de wait, alors que webhook + SQS réutilise l'infrastructure
existante.

## 7. Sécurité du callback

Apify documente un secret dans l'URL ou dans un headers template ; il ne documente pas de signature
HMAC du payload. Le design doit donc traiter le callback comme une entrée Internet non fiable.

Contrôles requis, dans cet ordre :

1. Route dédiée `POST /api/webhooks/apify`, sans auth utilisateur et sans route `/api/v1/`.
2. Secret aléatoire dans un header d'autorisation, chargé depuis le secret runtime et comparé en
   temps constant. Préférer le header à un query param, car les URLs sont davantage journalisées.
3. Limite de taille et parsing JSON strict avant toute lecture externe.
4. Valeurs autorisées pour `event_type`, plateforme et actor ; rejet de toute autre forme.
5. Lecture du job par son identifiant, puis correspondance conditionnelle de l'identifiant d'essai
   et du `run_id`. Un callback ne choisit jamais librement un job à reprendre.
6. `GET` serveur-à-serveur du run avec le token Apify : vérifier actor, statut terminal et dataset.
   Ne pas suivre une URL ou lire un dataset fourni arbitrairement par le payload entrant.
7. Écriture conditionnelle/idempotente avant l'envoi de continuation. Une livraison doublée renvoie
   `2xx` sans second message Deepgram ni seconde finalisation.
8. Répondre `2xx` seulement après l'écriture SQS. Un échec transitoire doit rester non-`2xx` pour
   déclencher les retries Apify.
9. Allowlist des IP statiques de livraison Apify seulement en défense secondaire ; le secret et la
   vérification serveur-à-serveur restent les contrôles d'identité.
10. Métriques : auth refusée, callback inconnu, mismatch run/job, doublon, reprise, backstop utilisé,
    callback manquant et latence `finishedAt → receivedAt`.

Le header `X-Apify-Webhook` est ajouté par la plateforme mais n'est pas documenté comme preuve
cryptographique. Sa présence seule n'authentifie rien.

## 8. Sémantique de retry et états durables

Un modèle minimal évite de confondre retry du message et nouveau run payant :

| État Apify du job | Événement autorisé | Action |
|---|---|---|
| absent | branche fallback | écriture conditionnelle `starting` + identifiant d'essai |
| `starting` | réponse start-run | lier le `run_id`, écrire deadline et `waiting_callback` |
| `starting` | redélivrance du message initial | ne pas redémarrer ; laisser callback/backstop résoudre |
| `waiting_callback` | callback valide | transition conditionnelle `callback_received`, enqueue continuation |
| `waiting_callback` | backstop | relire Apify et produire la même continuation ou un échec terminal |
| `callback_received` | callback dupliqué/backstop | no-op `2xx` |
| job terminal | tout callback tardif | no-op `2xx`, métrique `late_callback` |

Les événements `FAILED`, `ABORTED` et `TIMED-OUT` doivent être enregistrés dès le départ. Un webhook
sur le seul succès recréerait le cas silencieux qu'on cherche à supprimer.

Les retries SQS sont at-least-once. AWS recommande des handlers idempotents et une visibilité d'au
moins six fois le timeout Lambda. Le dépôt utilise déjà les partial batch responses ; elles doivent
rester actives pour ne redélivrer que le record en échec.

## 9. Résilience et exploitation

| Incident | Polling actuel | Recommandation |
|---|---|---|
| Actor passe de 100 s à 5 min | Lambda proche/au-delà de son plafond, risque de run perdu | aucun wait Lambda ; callback normal |
| Actor passe à 8 min | nouveau relèvement nécessaire | toujours dans le timeout actor 10 min |
| Endpoint indisponible 2 min | sans objet | retries Apify ; backstop reste armé |
| Les 11 livraisons échouent | sans objet | backstop relit et reprend le run à 15 min |
| Callback livré deux fois | sans objet | transition conditionnelle, second appel no-op |
| Message de continuation livré deux fois | travail aval potentiellement doublé | token d'essai + état conditionnel avant Deepgram/finalisation |
| Worker meurt après start-run | SQS redémarre et peut payer un autre run | état `starting`, callback porte l'essai, pas de restart immédiat |
| Run ne devient jamais terminal | Lambda finit par mourir | timeout actor 10 min, backstop 15 min, échec explicite |

Observabilité permanente recommandée :

- distribution `apify_run_duration_seconds` par actor et plateforme ;
- `apify_callback_delivery_lag_seconds` ;
- compteurs `callback_success`, `callback_duplicate`, `callback_auth_rejected`,
  `backstop_recovered`, `backstop_failed` ;
- âge du plus vieux job `waiting_callback` ;
- nombre de runs Apify par `media_key`/essai afin de détecter une double facturation.

## 10. Rejets synthétiques

- **Auto-ré-enqueue SQS** : techniquement viable et meilleur fallback si aucun endpoint public n'est
  acceptable, mais plus lent et plus bavard que le signal terminal natif. Gardé uniquement comme
  backstop unique.
- **`waitForFinish`** : rejeté car il fait attendre jusqu'à 60 s et ne couvre déjà aucun des six
  runs les plus lents sans continuation. Il déplace le wait, il ne l'enlève pas.
- **`run-sync-get-dataset-items`** : rejeté car il attend jusqu'à 300 s, peut perdre la réponse sans
  annuler le run et est déconseillé par Apify pour les nouvelles intégrations.
- **Step Functions Standard** : robuste mais disproportionné ; plus de ressources, IAM, secrets et
  coût pour une séquence linéaire déjà durable dans DynamoDB/SQS.
- **Step Functions Express** : rejeté car son plafond de 5 min est le prochain incident annoncé et
  son modèle reste at-least-once.
- **Lambda 300/900 s** : rejetée car elle couple le coût et la réussite à une durée provider qui a
  déjà varié d'un facteur dix.

## 11. Sources Internet

Sources primaires consultées le 2026-08-18 :

### Apify

- [Run Actor — endpoint asynchrone, `waitForFinish` max 60 s, webhooks](https://docs.apify.com/api/v2/actors-runs-post)
- [Run task synchronously and get dataset items — timeout 300 s et endpoint déconseillé](https://docs.apify.com/api/v2/actor-task-run-sync-get-dataset-items-get)
- [Get run — lecture de statut et storages](https://docs.apify.com/api/v2/actor-run-get)
- [Événements webhook disponibles](https://docs.apify.com/integrations/webhooks/events)
- [Actions webhook — retries, doublons, sécurité, headers et timeout](https://docs.apify.com/integrations/webhooks/actions)
- [Webhooks ad hoc attachés à un run](https://docs.apify.com/integrations/webhooks/ad-hoc-webhooks)
- [Création de webhook et clé d'idempotence du webhook](https://docs.apify.com/api/v2/webhooks-post)
- [Authentification et portée des tokens Apify](https://docs.apify.com/integrations/api)
- [Usage et compute units](https://docs.apify.com/actors/running/usage-and-resources)
- [Prix Instagram Reel Scraper](https://apify.com/apify/instagram-reel-scraper/pricing)
- [Prix TikTok Transcripts Scraper](https://apify.com/scrape-creators/best-tiktok-transcripts-scraper)

### AWS

- [Lambda + SQS : at-least-once et idempotence](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [Configuration SQS/Lambda : visibilité ≥ 6 × timeout](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html)
- [Partial batch responses et retries](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html)
- [SQS DelaySeconds : 15 minutes maximum](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-delay-queues.html)
- [Step Functions Standard vs Express](https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html)
- [Wait state et limites de durée](https://docs.aws.amazon.com/step-functions/latest/dg/state-wait.html)
- [Callback avec task token](https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-resource.html)
- [HTTP Tasks et EventBridge Connections](https://docs.aws.amazon.com/step-functions/latest/dg/call-https-apis.html)
- [Prix Step Functions](https://aws.amazon.com/step-functions/pricing/)
- [Timeout Lambda maximum 900 s](https://docs.aws.amazon.com/lambda/latest/dg/configuration-timeout.html)
- [Timeout HTTP API maximum 30 s](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html)

## 12. Contrôle des critères de task-275

| AC | Couverture |
|---|---|
| #1 | front-matter `owner_decision: pending` et section Owner Validation en tête |
| #2 | sections 2 à 9 : latence, coût, infra/attaque, auth, retries, callback absent, ralentissement |
| #3 | section 4.3 : limite 60 s et démonstration qu'elle relocalise le wait |
| #4 | recommandation unique, section 10, réduction 300→60 s et 120→60 s |
| #5 | section 1.1 : 63-100 s, 6-9 s, 6/6 et plafond 30 s avec sources locales/officielles |
| #6 | section 1.3 : proxy V2 task-145, recommandation indépendante de sa fréquence |
| #7 | recommandation transverse : TikTok adopte la même orchestration |
| #8 | seul ce README de recherche et la tâche backlog sont modifiés ; aucun code ni Terraform |
