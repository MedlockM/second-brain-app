---
id: task-248
title: >-
  Promote the mothballed staging environment to prod and isolate dev from prod
  via AWS Organizations
status: To Do
assignee: []
created_date: '2026-08-12 16:40'
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
- [ ] #1 Aucune ressource `-staging` ne subsiste sur AWS et un environnement `prod` complet existe, créé depuis `envs/prod/` (state `env/prod/terraform.tfstate`)
- [ ] #2 Le secret `media-summarizer-runtime-staging` est supprimé avec `--force-delete-without-recovery` de sorte que son nom ne bloque aucune recréation
- [ ] #3 `envs/prod/main.tf` a `enable_alarms`, `enable_dashboard` et `enable_worker_polling` à `false`, et son commentaire interdisant la veille est remplacé par la consigne réelle (veille temporaire jusqu'au lancement)
- [ ] #4 Le coût quotidien du compte mesuré sur Cost Explorer après conversion ne dépasse pas le niveau d'avant création de staging (~0,233 $/jour), preuve chiffrée à l'appui
- [ ] #5 `envs/staging/` reste présent dans le dépôt et `infrastructure/terraform/README.md` documente que la couche 4 de tf_plan_guard.sh ne joue plus le même rôle entre deux comptes séparés
- [ ] #6 Une organisation AWS existe et un compte membre dédié à prod est créé, dev restant dans le compte 125313707865
- [ ] #7 Un profil AWS assumant un rôle (`role_arn` + `source_profile`) permet de piloter prod sans second jeu de clés, et la procédure est documentée dans infrastructure/terraform/README.md
- [ ] #8 `envs/prod/` pointe sur le backend, la table de verrouillage et le provider du compte prod, et `terraform plan -detailed-exitcode` y renvoie 0 après apply
- [ ] #9 Les Lambdas du compte prod tirent effectivement leur image de l'ECR partagé (policy cross-account ajustée), prouvé par une invocation réelle et non par la seule lecture de la policy
- [ ] #10 Un `terraform plan -detailed-exitcode` dans `envs/dev` renvoie 0 après l'ensemble des opérations : la séparation n'a rien cassé en dev
- [ ] #11 Le rôle OIDC GitHub Actions du compte prod existe et le workflow de déploiement sait cibler prod sans pouvoir atteindre dev
<!-- AC:END -->
