# Runtime Lambda de l'API interactive

## Architecture

L'API FastAPI et les workers asynchrones restent sur AWS Lambda ARM64, mais ils
ne partagent plus le même artefact :

| Runtime | Dockerfile | Tag de bootstrap | Déploiement courant |
|---|---|---|---|
| API interactive | `infrastructure/docker/lambda-api.Dockerfile` | `api-latest` | digest de l'image `api-<git-sha>` |
| Workers SQS | `infrastructure/docker/lambda.Dockerfile` | `worker-latest` | digest partagé de l'image `worker-<git-sha>` |

Le groupe Python `worker` contient les dépendances strictement asynchrones,
notamment `trafilatura`. `yt-dlp` reste dans le runtime partagé/API car le
resolver Instagram l'utilise lors de `POST /api/media/ingest-url` avant la mise
en file. Les workers conservent leurs commandes propres dans
`lambda_workers.tf`.

Le workflow `deploy-lambda.yml` détecte les chemins affectés. Un changement
API-only ne redéploie pas les workers, un changement worker-only ne redéploie
pas l'API, et les composants partagés (`core`, `utils`, `pyproject.toml`)
reconstruisent les deux runtimes. Lambda reçoit toujours une URI par digest ;
les tags `*-latest` servent seulement à amorcer un nouvel environnement avec
Terraform.

## Protection et health check

- La concurrence API effective vaut 10 par défaut en staging/production. Cette
  réservation gratuite empêche les workers SQS d'épuiser toute la concurrence
  du compte. AWS dev ne dispose pas d'un quota suffisant pour laisser les 10
  exécutions non réservées obligatoires : il utilise donc `-1`. La variable
  nullable `api_reserved_concurrency` surcharge explicitement ces valeurs.
- `api_warmup_enabled` vaut `true`. EventBridge invoque l'API toutes les
  15 minutes par défaut (`api_warmup_schedule_expression`).
- L'événement planifié passe par le même adaptateur Mangum que le trafic public
  et appelle `/api/v1/health/`. La Lambda lève une erreur si le statut HTTP
  n'est pas 200 ou si le corps n'annonce pas `healthy`.
- La validation de release attend `Active:Successful`, puis interroge le health
  endpoint public. Elle échoue sur erreur HTTP ou statut applicatif non sain.
- Les access logs API Gateway incluent `integrationErrorMessage`,
  `error.message` et `error.responseType` pour diagnostiquer les échecs qui se
  produisent avant l'entrée dans le handler Lambda.

Le warm-up représente environ 2 880 invocations par mois. À la durée chaude
observée, son coût reste de l'ordre de quelques centimes et il ne crée aucune
capacité permanente.

## Mesures AWS dev

Mesures prises sur `media-summarizer-api`, ARM64, 1 024 Mo, via le health
endpoint public et les lignes CloudWatch `REPORT` :

| Mesure | Image partagée avant | Image API dédiée après |
|---|---:|---:|
| Taille ECR compressée | 404 533 119 octets | 297 839 156 octets (−26,5 %) |
| Taille locale Docker | ~405,0 Mo (worker équivalent) | 297 841 737 octets |
| Cold `Init Duration` | 3 862,65 ms | 9 163,50 ms sur le premier environnement |
| Première requête publique | 4,92 s | 10,49 s sur le premier environnement |
| Requête publique chaude | 0,60–0,73 s | 0,64–0,66 s |

La réduction d'image est confirmée, mais le premier cold start mesuré après le
déploiement n'est pas plus rapide. L'initialisation inclut le chargement réseau
du secret runtime depuis Secrets Manager et varie indépendamment de la taille
de l'image ; il ne faut donc pas attribuer artificiellement ce résultat à
l'artefact. La mitigation utilisateur validée est le warm-up : après la
première initialisation, le health endpoint public répond en ~0,65 s. Le seuil
de provisioned concurrency ci-dessous reste fondé sur les latences observées,
pas seulement sur la taille ECR.

## Provisioned concurrency : désactivée par défaut

La production reste à la demande. La provisioned concurrency ne doit être
introduite que si, sur sept jours glissants :

1. au moins 1 % des requêtes interactives subissent un cold start ;
2. leur p95 public dépasse 5 secondes alors que le p95 chaud reste inférieur à
   1 seconde ; ou
3. un cold start provoque un 5xx/timeout API Gateway proche de la limite de
   30 secondes.

Le warm-up doit d'abord être confirmé sain. Si ces seuils sont franchis, la
procédure est :

1. publier une version Lambda immuable de l'image API mesurée ;
2. créer un alias `live` pointant vers cette version ;
3. qualifier l'intégration et la permission API Gateway avec l'alias `live` ;
4. créer `aws_lambda_provisioned_concurrency_config` sur l'alias, avec une
   capacité initiale de 1 ;
5. faire publier une nouvelle version et déplacer l'alias par le workflow à
   chaque image API ;
6. vérifier `ProvisionedConcurrencySpilloverInvocations`, p95 et taux de 5xx
   pendant 24 heures avant toute hausse ;
7. revenir à zéro et supprimer l'alias qualifié si le bénéfice mesuré ne
   justifie pas le coût.

Cette activation doit passer par Terraform et une revue dédiée : ne pas lancer
`put-provisioned-concurrency-config` directement, car l'intégration API Gateway
non qualifiée continuerait sinon à appeler `$LATEST` et contournerait la
capacité provisionnée.
