---
id: task-248
title: >-
  Promote the mothballed staging environment to prod and isolate dev from prod
  via AWS Organizations
status: Done
assignee: []
created_date: '2026-08-12 16:40'
updated_date: '2026-09-03 11:05'
labels:
  - infra
  - terraform
  - release
  - security
  - implementation
dependencies:
  - task-237
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Transformer l'environnement `staging` (aujourd'hui en veille) en `prod`, le **laisser en veille** pour qu'il ne consomme rien, puis isoler dev et prod dans **deux comptes AWS séparés** via AWS Organizations.

Décision owner du 2026-08-12, en trois volets indissociables :
1. `staging` devient `prod` — inutile de maintenir trois environnements pour un développeur solo (cf. task-237, notes du 2026-08-12).
2. `prod` reste **en veille** jusqu'au lancement réel : `enable_alarms`, `enable_dashboard` et `enable_worker_polling` à `false`. L'owner ne veut payer aucun environnement inutilisé.
3. L'isolation dev/prod passe par des **comptes AWS séparés** (Organizations), pas par des suffixes de noms. C'est l'équivalent le plus proche des resource groups Azure : les « Resource Groups » AWS ne sont que des vues par tags, sans frontière de permission ni de facturation.

## Lire d'abord

- `docs/research/task-221-terraform-multi-env-isolation/README.md` — architecture validée (option B : une racine Terraform par environnement au-dessus de `modules/platform`), et §7.3 sur les secrets.
- `backlog/tasks/task-237 …` notes du 2026-08-12 — chiffrage Cost Explorer et mécanique des trois interrupteurs de coût.
- `infrastructure/terraform/README.md` section « Cost switches » — tableau par environnement.

## État constaté le 2026-08-12 (vérifié côté AWS)

- Compte unique `125313707865`, région `eu-west-3`, **membre d'aucune organisation** (`AWSOrganizationsNotInUseException`).
- `envs/prod/main.tf` **existe déjà et n'a jamais été appliqué** ; `terraform validate` passe. Son écart avec dev se limite aux commentaires et aux interrupteurs de coût.
- `staging` est **entièrement vide** : 0 ligne sur ses 24 tables, 0 objet sur ses 11 buckets. Rien à migrer.
- `staging` est en veille depuis `5845ec7` : 0 alarme, pas de dashboard, pas de topic SNS, 13 des 14 mappings SQS `Disabled`. Les 24 tables, 11 buckets, 26 queues, 15 Lambdas et le secret sont intacts.
- Le secret `media-summarizer-runtime-staging` contient **0 clé** (dev en a 37).

## Volet 1 — staging → prod

Le token d'environnement est porté par **tous** les noms physiques (`local.suffix`), et il est `ForceNew` sur la quasi-totalité des ressources : ce n'est donc pas un renommage mais un `destroy` + `apply`. C'est sans risque **parce que staging est vide** — vérifier ce fait à nouveau avant d'agir, ne pas le prendre pour acquis.

Piège identifié : Secrets Manager retient un nom supprimé **7 à 30 jours**. Supprimer `media-summarizer-runtime-staging` avec `--force-delete-without-recovery`, sinon le nom reste bloqué.

Conserver `envs/staging/` **dans le dépôt** même sans environnement staging vivant : c'est le référentiel qui permet de remonter un staging jetable avant une migration risquée. En revanche la couche 4 de `scripts/tf_plan_guard.sh` a besoin d'un **second environnement vivant** pour son contrôle croisé — après conversion c'est le couple dev+prod qui la satisfait, à condition que les deux soient dans le même compte. Une fois les comptes séparés, la couche 4 devient structurellement inutile entre dev et prod (frontière de compte) : documenter ce changement de nature plutôt que de laisser croire qu'elle protège encore.

## Volet 2 — prod en veille

`envs/prod/main.tf` a aujourd'hui les trois interrupteurs à `true` avec un commentaire interdisant explicitement de mettre prod en veille. Ce commentaire a été écrit **avant** cette décision : le mettre à jour au lieu de le contourner silencieusement, et y consigner que la veille est temporaire (jusqu'au lancement) et non un choix d'architecture. Une prod servant de vrais utilisateurs sans alarmes est une faute ; une prod en veille avant lancement n'en est pas une. Le réveil doit rester un `apply` de trois booléens.

## Volet 3 — isolation par comptes séparés

Créer l'organisation, puis un compte membre dédié à prod (dev reste dans le compte actuel `125313707865`, qui porte l'historique).

Point à lever explicitement, c'était l'inquiétude de l'owner : **cela n'impose pas de changer d'identifiants**. Un profil dans `~/.aws/config` avec `role_arn` + `source_profile` suffit — `aws --profile prod …` assume le rôle depuis les clés existantes. Aucune reconnexion, aucun second jeu de clés à gérer.

Le vrai coût est le socle à reconstruire dans le nouveau compte :
- bucket de state S3 + table de verrouillage. Attention : `media-summarizer-tfstate-lock` est **partagée par les quatre backends** (`envs/{dev,staging,prod}` et `shared/`) ; le compte prod aura besoin de la sienne.
- rôle OIDC GitHub Actions pour le compte prod (cf. task-221 §7.2 points 3-4, jamais faits : aucun GitHub Environment n'existe).
- `provider` et `backend` de `envs/prod/` repointés sur le nouveau compte.
- **ECR devient cross-account** : `shared/ecr.tf` documente une seule *repository* pour tous les environnements, à dessein (§7.1 — l'image validée doit être bit-identique à celle livrée en prod, la promotion se fait par digest). La policy actuelle est verrouillée sur `arn:aws:lambda:eu-west-3:125313707865:function:*` : elle doit être élargie au compte prod, sinon les Lambdas prod ne peuvent pas tirer leur image. Décider et documenter si l'ECR reste dans le compte dev ou déménage.
- La facturation reste consolidée au niveau de l'organisation : le coût par environnement devient lisible via le compte, ce qui est un bénéfice attendu de ce volet.

## Hors périmètre

Peupler le secret runtime de prod avec ses 37 credentials distincts (RevenueCat **live**, `JWT_SECRET_KEY` propre, clés Apify/Deepgram/OpenAI séparées, `ALGOLIA_INDEX_NAME` distinct). Cela demande des credentials que seul l'owner détient, et le benchmark §7.3 interdit de recopier ceux de dev. Reste aussi hors périmètre : le domaine public (`api.secondbrainlabs.com` ne résout pas), les produits App Store et tout ce qui relève de la Phase 10.

## Ordre recommandé

Séparer les comptes **avant** de peupler prod : refaire la manœuvre après avoir des abonnés payants coûte une migration de données, alors qu'aujourd'hui prod est vide. Si l'owner préfère différer le volet 3, livrer les volets 1 et 2 en entier et le dire explicitement plutôt que de livrer un volet 3 à moitié.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Aucune ressource `-staging` ne subsiste sur AWS et un environnement `prod` complet existe, créé depuis `envs/prod/` (state `env/prod/terraform.tfstate`)
- [x] #2 Le secret `media-summarizer-runtime-staging` est supprimé avec `--force-delete-without-recovery` de sorte que son nom ne bloque aucune recréation
- [x] #3 `envs/prod/main.tf` a `enable_alarms`, `enable_dashboard` et `enable_worker_polling` à `false`, et son commentaire interdisant la veille est remplacé par la consigne réelle (veille temporaire jusqu'au lancement)
- [ ] #4 Le coût quotidien du compte mesuré sur Cost Explorer après conversion ne dépasse pas le niveau d'avant création de staging (~0,233 $/jour), preuve chiffrée à l'appui
- [x] #5 `envs/staging/` reste présent dans le dépôt et `infrastructure/terraform/README.md` documente que la couche 4 de tf_plan_guard.sh ne joue plus le même rôle entre deux comptes séparés
- [x] #6 Une organisation AWS existe et un compte membre dédié à prod est créé, dev restant dans le compte 125313707865
- [x] #7 Un profil AWS assumant un rôle (`role_arn` + `source_profile`) permet de piloter prod sans second jeu de clés, et la procédure est documentée dans infrastructure/terraform/README.md
- [x] #8 `envs/prod/` pointe sur le backend, la table de verrouillage et le provider du compte prod, et `terraform plan -detailed-exitcode` y renvoie 0 après apply
- [x] #9 Les Lambdas du compte prod tirent effectivement leur image de l'ECR partagé (policy cross-account ajustée), prouvé par une invocation réelle et non par la seule lecture de la policy
- [x] #10 Un `terraform plan -detailed-exitcode` dans `envs/dev` renvoie 0 après l'ensemble des opérations : la séparation n'a rien cassé en dev
- [x] #11 Le rôle OIDC GitHub Actions du compte prod existe et le workflow de déploiement sait cibler prod sans pouvoir atteindre dev
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Les trois volets sont livrés. **9 AC sur 11 sont cochés ; #4 et #10 restent ouverts**, pour des raisons qui ne sont pas des oublis (détail plus bas).

### Actions irréversibles effectuées (2026-08-12 / 2026-08-13)

1. **Organisation AWS créée** : `o-7sf5u7j5hd`, compte de gestion `125313707865`, feature set `ALL`. Une organisation ne se supprime qu'après avoir sorti tous les comptes membres.
2. **Compte membre créé** : `866874944541` / `media-summarizer-prod`. Son email de connexion est un alias `+aws-prod` de l'email racine du compte de gestion — **volontairement non consigné ici** : l'email racine d'un compte AWS est la moitié d'une réinitialisation de mot de passe et ce dépôt est public. Le propriétaire le retrouve dans la console Organizations ou son gestionnaire de mots de passe. `OrganizationAccountAccessRole` créé par AWS, accès facturation `ALLOW`. **Un compte AWS ne se supprime pas avant 90 jours de fermeture.**
3. **145 ressources staging détruites** (`Apply complete! Resources: 0 added, 0 changed, 145 destroyed`).
4. **`media-summarizer-runtime-staging` supprimé sans fenêtre de récupération.**
5. **Protection contre suppression retirée sur 24 tables staging** (toutes détruites depuis).
6. **Policy du repository ECR partagé remplacée** : elle était écrite automatiquement par Lambda et hors Terraform, elle est désormais gérée par `shared/ecr.tf`.
7. **Backend prod créé** : bucket `media-summarizer-tfstate-866874944541` + table `media-summarizer-tfstate-lock` dans le compte prod.
8. **199 ressources prod créées.**
9. **`[profile prod]` ajouté à `~/.aws/config`** (hors dépôt, nécessaire à l'AC #7).
10. **GitHub Environment `production` créé** (id 19802739056), branche `main` seule autorisée, secret d'environnement `AWS_DEPLOY_ROLE_ARN` renseigné.
11. **Augmentation de quota Lambda accordée** dans le compte prod : quota `L-B99A9384` (exécutions concurrentes, 10 → 1000), déposée puis **accordée le 2026-08-13** — `get-service-quota` retourne `Value: 1000.0` et la demande est `CASE_CLOSED` (relevé le 2026-09-03 ; ce fichier l'annonçait `PENDING` à tort dans l'intervalle). L'identifiant de la demande n'est pas consigné ici (dépôt public) ; il se retrouve via `aws service-quotas list-requested-service-quota-change-history --service-code lambda` avec le profil prod.

### Preuves collectées avant chaque destruction

staging était bien vide, vérifié et non supposé : **0 ligne** sur 24 tables (`scan --select COUNT`, seul compteur fiable — `describe-table ItemCount` ne se rafraîchit que toutes les ~6 h), **0 objet / 0 version / 0 delete marker** sur 11 buckets, **0 message** (visibles + en vol + différés) sur 26 queues, **0 clé** dans le secret runtime.

Ancre de rollback prise avant le `destroy` : `s3://media-summarizer-tfstate-125313707865/env/staging/terraform.tfstate` version `WxltPY9sH8uQ8rx8H7EsEwGEQKs4iM1g` (2026-08-12T15:45:49Z, 555 862 octets).

Plan de démolition passé au crible : 145 actions, **toutes** des suppressions, **aucune** chaîne `-dev` dans le JSON du plan. Les trois seules ressources sans « staging » dans leur identité sont des sous-ressources de l'API `fbz3cdgqll`, confirmée être `media-summarizer-api-staging`.

Après coup, **15 familles de ressources rapportent 0 objet `-staging`** (DynamoDB, S3, SQS, Lambda, log groups, rôles IAM, policies IAM, API Gateway, alarmes, dashboards, SNS, règles EventBridge, secrets, schedulers, coffres de sauvegarde). `list-secrets --include-planned-deletion` ne renvoie plus que `media-summarizer-runtime-dev`, donc le nom staging n'est pas simplement programmé pour suppression : il est libre.

### Détail technique du volet 1

`prevent_destroy = true` (22 tables + 11 buckets) aurait fait échouer le `destroy` dès le plan. Contournement documenté par HashiCorp : `prevent_destroy` est lu **dans la configuration**, donc il ne s'applique plus à une ressource dont la configuration a disparu. Une racine jetable pointant sur la même clé de backend et ne déclarant **aucune** ressource produit donc un plan de suppression intégral. Elle a été supprimée après usage.

`deletion_protection_enabled = true` est en revanche un garde-fou côté AWS que le provider ne lève pas : `update-table --no-deletion-protection-enabled` sur les 24 tables d'abord.

Le module ne fixe pas `recovery_window_in_days`, donc `destroy` **programme** la suppression du secret à 30 jours au lieu de la faire — ce qui aurait bloqué le nom et fait échouer l'AC #2. Séquence de sortie : `restore-secret` puis `delete-secret --force-delete-without-recovery` (l'option est refusée sur un secret déjà programmé pour suppression).

### Mur AWS rencontré sur le premier apply de prod

Un compte AWS **neuf** reçoit un quota Lambda « Concurrent executions » de **10** au lieu de 1000 (mesuré : 10 en prod, 1000 en dev), et AWS refuse toute réservation qui laisserait moins de 10 non réservés. Le module réserve 10 pour l'API hors dev, ce qui est donc arithmétiquement impossible ici :

```
PutFunctionConcurrency: InvalidParameterValueException: Specified ReservedConcurrentExecutions
for function decreases account's UnreservedConcurrentExecution below its minimum value of [10].
```

L'apply s'est arrêté là (189 ressources créées, la Lambda API marquée `tainted`, ses 5 dépendants jamais créés). Traitement : augmentation de quota demandée (cf. plus haut), puis `api_reserved_concurrency = -1` posé **dans `envs/prod/main.tf`** avec le commentaire qui explique pourquoi et qui en fait un prérequis de lancement explicite. La Lambda a été `untaint`ée après vérification directe qu'elle était `State=Active` / `LastUpdateStatus=Successful` — la seule opération en échec portait sur un appel séparé dont la valeur cible a changé. Apply suivant : 5 ressources, sans erreur.

**Prérequis de lancement pour l'owner — résolu à moitié le 2026-09-03.** Le quota est passé à 1000 le 2026-08-13 et la ligne `api_reserved_concurrency = -1` a été supprimée d'`envs/prod/main.tf` le 2026-09-03, ce qui rend au module son défaut non-dev de 10. **Il reste le plan + apply prod manuel** : tant qu'il n'a pas tourné, AWS ne connaît toujours aucune réservation et l'API se dispute le pool commun avec les 14 workers, ce qui throttlerait à la première charge réelle. L'arithmétique qui bloquait est maintenant satisfaite : 1000 − 10 = 990 non réservées, très au-dessus du minimum de 10 exigé par `PutFunctionConcurrency`.

### AC #9 — preuve par invocation réelle, pas par lecture de policy

- API : `GET https://f45y1buebe.execute-api.eu-west-3.amazonaws.com/api/v1/health/` → **HTTP 200**, `{"status":"healthy","service":"Media Summarizer API","database":"connected","version":"1.0.0"}`, 5,4 s (démarrage à froid, donc pull d'image inclus).
- Worker : `lambda invoke media-summarizer-worker-search_indexing-prod` avec `{"Records":[]}` → `StatusCode 200`, `FunctionError` nul, réponse `{"batchItemFailures": []}`.
- `Code.ImageUri` des deux fonctions : `125313707865.dkr.ecr.eu-west-3.amazonaws.com/media-summarizer-lambda:{api,worker}-latest`, soit un registre d'un **autre compte** que celui des fonctions.

À noter : `database: connected` alors que le secret runtime de prod est **vide**. La route de santé ne teste que DynamoDB via les noms de tables injectés par Terraform, pas les credentials tiers. Le secret reste à peupler (task-252, owner).

Il a fallu trois statements pour que ça marche, pas un : le principal de service Lambda de prod (`aws:sourceArn` sur le compte consommateur), **le root du compte consommateur** (sans quoi `CreateFunction` échoue avant même que le principal de service soit consulté), et l'autorisation côté IAM de prod. Une policy de repository seule n'autorise rien si le compte du principal ne l'autorise pas.

### AC #5 — la couche 4 de tf_plan_guard.sh change de nature

Exécutée avec le profil prod, elle échoue désormais exactement comme l'isolation de comptes le veut :

```
== Layer 4: no name collision with the live environments ==========
Error: Failed to load state: Unable to access object "env/dev/terraform.tfstate" in S3 bucket
"media-summarizer-tfstate-125313707865": ... StatusCode: 403 ... api error Forbidden
```

Ce n'est pas un blocage : la couche 4 est **structurellement redondante** entre deux comptes. Tables, queues, Lambdas, log groups et rôles sont cadrés par compte + région, donc un plan exécuté avec les identifiants de prod ne peut ni créer ni modifier ni supprimer un objet du compte dev même à noms identiques ; et les noms de buckets S3, seuls noms globaux, portent aussi l'identifiant de compte (`media-summarizer-transcripts-866874944541-prod`). La consigne est donc de lancer `scripts/tf_plan_guard.sh prod tfplan` **sans** troisième argument. La couche 4 garde toute sa valeur là où elle s'applique encore : deux environnements dans le même compte, c'est-à-dire le jour où `envs/staging` est appliqué.

Le contrôle croisé a tout de même été fait à la main, une fois, avec les deux profils : la seule intersection entre les 154 noms planifiés de prod et les 170 noms vivants de dev est `$default`, le littéral de stage API Gateway v2, cadré par un identifiant d'API et non un nom global.

### AC #4 — non observable aujourd'hui, chiffres bruts fournis

Cost Explorer a **~24 h de retard** : au 2026-08-13, la journée du 13 renvoie un tableau vide. Le démontage de staging date du 12 en fin de journée et prod a été créé le 13 au matin, donc **aucune journée complète post-conversion n'est encore mesurable**. Ce qui est mesuré (`ce get-cost-and-usage`, `UnblendedCost`, groupé par compte lié) :

| Jour | Coût | Contexte |
|---|---|---|
| 2026-08-07 | 0,2321 $ | avant staging |
| 2026-08-08 | 0,2321 $ | avant staging |
| 2026-08-09 | 0,2330 $ | avant staging |
| 2026-08-10 | 0,2345 $ | avant staging |
| 2026-08-11 | 0,2949 $ | staging vivant, en veille |
| 2026-08-12 | 0,2887 $ | démontage en cours de journée |
| 2026-08-13 | pas de donnée | latence Cost Explorer |

`ce get-cost-forecast` renvoie ~0,288 $/jour, mais il ne fait qu'extrapoler le 12 août — journée qui contenait encore staging — donc **il ne prouve rien** sur l'état stationnaire et n'est pas cité comme preuve.

Attente raisonnée, non vérifiée : retour vers ~0,233 $/jour. Le delta net attendu est proche de zéro (un secret détruit côté dev à ~0,013 $/jour, un secret créé côté prod au même prix ; tables en PAY_PER_REQUEST, buckets vides et log groups sans données ne coûtent rien à vide) et les trois interrupteurs de coût sont à `false` en prod.

**Pour clore l'AC**, rejouer à partir du 2026-08-15 :

```bash
AWS_PROFILE=second-brain-app aws ce get-cost-and-usage --region us-east-1 \
  --time-period Start=2026-08-14,End=2026-08-16 --granularity DAILY \
  --metrics UnblendedCost --group-by Type=DIMENSION,Key=LINKED_ACCOUNT
```

La facturation étant consolidée, ce groupement donne le coût par compte, donc par environnement — bénéfice attendu du volet 3, désormais disponible.

### AC #10 — laissé ouvert, et ce n'est pas dû à cette task

`terraform plan -detailed-exitcode` dans `envs/dev` renvoie **2**, mais il renvoyait déjà 2 **avant** toute intervention : dérive préexistante de task-242 (`aws_cloudwatch_log_metric_filter.job_archiver_objects_archived` et `..._remove_records` présents dans le state, absents de la configuration, plus un `source_code_hash` non déterministe sur `aws_lambda_function.job_archiver`). Aucun de ces trois éléments n'a de rapport avec les comptes, l'ECR, staging ou prod. Appliquer ce nettoyage aurait été s'arroger le périmètre d'une autre task.

Second obstacle, indépendant : **le state de dev est modifié en parallèle par un autre agent**. Il a été écrit 5 fois ce matin (07:09, 07:26, 07:27, 07:28, 07:37 UTC) pendant que je ne travaillais que sur prod, et trois autres worktrees d'agents sont actifs. Ma mesure de référence était `0 to add, 1 to change, 7 to destroy`, elle est maintenant `0 to add, 1 to change, 2 to destroy` : les 5 différences (alarmes et topic SNS) ont été nettoyées par quelqu'un d'autre. Un `0` obtenu dans ces conditions ne prouverait rien sur mon travail.

Ce qui **est** prouvé à la place, et qui est l'intention de l'AC (« la séparation n'a rien cassé en dev ») :

- Le diff de cette task ne touche **ni `modules/platform/`, ni `envs/dev/`** : uniquement `envs/prod/`, `shared/`, `scripts/`, `.github/workflows/` et de la documentation.
- La seule dépendance de dev envers mes modifications est `data.terraform_remote_state.shared.outputs.lambda_ecr_repository_url` ; l'URL du repository est inchangée, seule une policy a été ajoutée.
- `terraform plan -detailed-exitcode` dans `shared/` renvoie **0** : la reprise en main de la policy ECR est appliquée et convergée.
- Le plan de dev ne propose **aucune** action liée aux comptes, à l'ECR ou à prod.

### Décision documentée : l'ECR reste dans le compte dev

Le déplacer imposerait de repousser toutes les images, et un repush **change les digests** — ce qui détruit la seule propriété pour laquelle ce repository unique existe (« le digest qui tourne en prod est le digest validé en dev »). Coût accepté et écrit dans `shared/ecr.tf` : prod dépend au runtime d'une ressource du compte dev, supprimer ce repository casse tout démarrage à froid de prod. La forme propre à terme est un troisième compte « shared-services » ; c'est un simple déménagement le jour où on le veut, et de la sur-ingénierie pour une organisation d'un seul développeur.

### Isolation du déploiement (AC #11)

Deux couches indépendantes, et la seconde est une trouvaille utile :

1. Le rôle `media-summarizer-gha-deploy-prod` vit dans `866874944541` et toutes les ARN de sa policy sont des ARN de ce compte (`LambdaDeployProdOnly` = `arn:aws:lambda:eu-west-3:866874944541:function:media-summarizer-*-prod`).
2. La policy de confiance du rôle **dev** existant est verrouillée sur `repo:MedlockM/second-brain-app:ref:refs/heads/main`, alors que celle de prod est verrouillée en `StringEquals` sur `repo:MedlockM/second-brain-app:environment:production`. Comme le job `promote-prod` déclare `environment: production`, GitHub lui délivre le sujet `environment:production`, **qui ne correspond pas** à la confiance du rôle dev : le job prod ne peut pas assumer le rôle dev, même avec son ARN. Symétriquement, les jobs de déploiement dev ne déclarent aucun environnement, donc ils ne peuvent pas produire le sujet qu'exige le rôle prod.

Nuance à énoncer clairement plutôt que de la masquer : le rôle prod **peut** lire une ressource du compte dev, le repository ECR partagé, en **pull seul** (`EcrPullSharedRepository`, aucune action de push). C'est la dépendance partagée voulue et documentée, pas un accès à l'environnement dev.

Le job prod est un **promote**, pas un build : il ne compile rien, il repointe les fonctions prod sur un digest qu'un push sur `main` a déjà construit et validé en dev. Le rôle prod n'a délibérément aucun droit de push ECR, donc prod ne peut pas exécuter des octets qui n'ont jamais existé en dev. Déclenchement : `workflow_dispatch` avec l'entrée `image_tag`.

### Non fait, volontairement

- **Aucun test automatisé n'a été ajouté** (règle du dépôt pour les agents d'implémentation). Aucun AC n'en demandait ici.
- Le secret runtime de prod reste **vide** (hors périmètre, task-252, owner).
- La réservation de concurrence de l'API prod est désactivée en attendant le quota (voir plus haut).
- Le rôle GitHub Actions de dev (`media-summarizer-gha-deploy` dans `125313707865`) reste **non géré par Terraform**, créé à la main hors bande. C'est un écart connu, signalé en tête de `envs/prod/gha_oidc.tf` ; l'adopter dans le state de dev est un chantier à part.

## 2026-08-13 — vérification du dispatcher après merge : AC #10 coché, AC #4 reste ouvert

**AC #10 est coché sur preuve relevée par le dispatcher après le merge, pas par l'agent.** L'agent avait raison de le laisser ouvert au moment où il travaillait : `envs/dev` portait alors un diff étranger à ce ticket (2 metric filters orphelins + un `source_code_hash` non déterministe) provenant de task-242, dispatchée **en parallèle** sur la même dev. Il a eu raison de ne pas appliquer ce diff et de ne pas réécrire le critère.

Ce diff a été fermé par le merge de task-242 dans `main` (les metric filters `JobArchiverRemoveRecords` / `JobArchiverObjectsArchived` sont désormais dans le code, donc plus orphelins). Rejeu par le dispatcher sur `main` après les trois merges :

```
terraform plan -detailed-exitcode -lock-timeout=120s   # dans infrastructure/terraform/envs/dev
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

Verrou acquis puis relâché normalement. **La séparation dev/prod n'a donc rien cassé en dev** — c'est exactement ce que le critère demandait. Les trois racines (`envs/dev`, `envs/prod`, `shared`) passent aussi `terraform validate`.

**AC #4 reste décoché à juste titre** — et ce n'est pas un oubli à requalifier plus tard : Cost Explorer a ~24 h de latence et ne renvoie aucune donnée pour le 2026-08-13. Le critère devient mesurable **à partir du 2026-08-14**. L'agent a explicitement refusé de citer `get-cost-forecast` (~0,288 $) comme preuve, puisque cette extrapolation porte sur une journée qui contenait encore staging — c'est le bon réflexe. La commande de rejeu exacte est dans ses notes plus haut.

Cette tâche est passée à `Done` avec l'AC #4 ouvert **pour une raison de sûreté** : la laisser en `To Do` la rendrait ré-dispatchable, et un agent relancé sur un ticket dont les volets 1 et 3 sont irréversibles (organisation créée, compte `866874944541` non supprimable avant 90 jours, 145 ressources staging détruites) pourrait tenter de refaire un travail destructeur déjà accompli. La vérification de coût est un contrôle d'une minute qui appartient au propriétaire, pas un motif de rouvrir ce chantier.
<!-- SECTION:NOTES:END -->
