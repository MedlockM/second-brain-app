# Analyse comparative des cloud providers

**Date :** 2 avril 2026
**Contexte :** Second brain media app -- solo dev, Python backend, workers asynchrones, faible trafic au lancement

---

## Table des matieres

1. [Inventaire des dependances AWS actuelles](#1-inventaire-des-dependances-aws-actuelles)
2. [Profil d'usage estime (lancement)](#2-profil-dusage-estime-lancement)
3. [Providers analyses](#3-providers-analyses)
4. [Tableau comparatif synthetique](#4-tableau-comparatif-synthetique)
5. [Analyse detaillee par provider](#5-analyse-detaillee-par-provider)
6. [Impact sur le workflow dev local](#6-impact-sur-le-workflow-dev-local)
7. [Recommandation](#7-recommandation)
8. [Plan de migration (si changement)](#8-plan-de-migration-si-changement)
9. [Sources](#9-sources)

---

## 1. Inventaire des dependances AWS actuelles

L'application utilise massivement les services AWS via `boto3`/`aiobotocore`/`aioboto3`. Voici l'inventaire complet :

### DynamoDB -- Base de donnees NoSQL (14 tables)
- `users`, `processing_jobs`, `auth_tokens`, `credit_transactions`, `stripe_events`
- `subscriptions`, `minute_buckets`, `minute_usage`
- `follows`, `spotify_playlist_follows`, `feed_forecasts`
- `episode_idempotence`, `episode_watchers`, `user_episode_submissions`
- Utilisation intensive des GSI (Global Secondary Indexes)
- Billing mode : PAY_PER_REQUEST (on-demand)

### SQS -- Files de messages (7 queues + 7 DLQ)
- `audio-download-queue`, `transcription-queue`, `summarization-queue`
- `email-notification-queue`, `quiz-queue`, `episode-completed-events`, `spotify-sync-queue`
- Chaque queue a sa Dead Letter Queue (DLQ) avec `maxReceiveCount: 3`
- Long polling (20s), visibility timeout configurable

### S3 -- Stockage objets (4 buckets)
- `media-summarizer-audio` (fichiers audio telecharges)
- `media-summarizer-transcriptions` (transcriptions texte)
- `media-summarizer-summaries` (resumes generes)
- `media-summarizer-quizzes` (quiz generes)

### Lambda -- Fonctions serverless (2 fonctions)
- `spotify-sync-dispatcher` : declenche par EventBridge (cron)
- `spotify-sync-worker` : declenche par SQS

### ECS/Fargate -- Compute (workers)
- Scaling controller Lambda qui lance des tasks Fargate a la demande
- Workers : download, whisper (transcription), summarization, email, quiz, episode-events

### Autres services
- **SES** : envoi d'emails
- **EventBridge** : scheduling (cron pour Spotify sync)
- **CloudWatch** : metriques et alarmes
- **IAM** : roles et policies

### Infrastructure as Code
- **Terraform** pour le provisioning (LocalStack en dev, AWS en prod)
- **LocalStack** pour le dev local (simule DynamoDB, SQS, S3, SES, Lambda, IAM, EventBridge)

---

## 2. Profil d'usage estime (lancement)

| Metrique | Estimation |
|----------|-----------|
| Requetes API/jour | ~100 |
| Messages SQS/jour | ~50-100 (pipeline : download -> transcription -> summarization -> notification) |
| Stockage S3 | < 5 GB (audio temporaire + transcriptions + resumes) |
| Stockage DynamoDB | < 1 GB |
| Compute workers | ~30 min CPU/jour (transcription audio = le plus gourmand) |
| Emails envoyes/jour | ~10-20 |
| Utilisateurs actifs | < 50 |

---

## 3. Providers analyses

### 3.1 AWS (actuel)

**Services utilises :** DynamoDB, SQS, S3, ECS/Fargate, Lambda, SES, EventBridge, CloudWatch

#### Couts estimes (faible trafic, us-east-1)

| Service | Free Tier | Cout estime apres free tier |
|---------|-----------|---------------------------|
| DynamoDB | 25 Go stockage, 25 WCU/RCU provisioned (always free) | ~0 $ (on-demand, < 1M requetes/mois) |
| SQS | 1M requetes/mois (always free) | ~0 $ (~3000 msg/mois << 1M) |
| S3 | 5 Go, 20K GET, 2K PUT (12 mois) | ~0.12 $/mois (5 Go a 0.023 $/Go) |
| Lambda | 1M requetes, 400K Go-s/mois (always free) | ~0 $ (< 1000 invocations/mois) |
| Fargate | Pas de free tier | ~5-15 $/mois (30 min CPU/jour, 0.5 vCPU) |
| SES | 3000 msg/mois gratuits (si envoyes depuis EC2/Lambda) | ~0 $ |
| **Total estime** | | **~5-15 $/mois** |

#### DX et dev local
- **Dev local :** LocalStack simule tous les services AWS --> fonctionne bien mais setup complexe (Docker, Terraform, lambda-builder)
- **Deploiement :** Complexe (Terraform, IAM, VPC, subnets, security groups, task definitions Fargate)
- **Debugging :** CloudWatch Logs, mais navigation complexe pour un debutant
- **Courbe d'apprentissage :** Elevee -- IAM, networking, ECS concepts

#### Avantages
- Exhaustivite des services (tout est couvert)
- Free tier genereux pour le faible trafic
- Scalability quasi illimitee
- LocalStack permet un dev local fidele

#### Inconvenients
- Complexite operationnelle tres elevee pour un solo dev
- ~50 fichiers du codebase contiennent des references boto3/AWS
- Terraform + IAM + VPC = courbe d'apprentissage importante
- Le setup LocalStack ajoute de la complexite (Docker compose avec 7+ services)
- Risque de factures surprises si mauvaise configuration
- Vendor lock-in fort (DynamoDB, SQS, Lambda sont proprietaires)

---

### 3.2 GCP (Google Cloud Platform)

**Services equivalents :** Firestore, Pub/Sub, Cloud Storage, Cloud Run, Cloud Functions, Cloud Tasks

#### Couts estimes

| Service | Free Tier | Cout estime |
|---------|-----------|------------|
| Firestore | 50K lectures/jour, 20K ecritures/jour, 1 Go stockage | ~0 $ (usage faible) |
| Pub/Sub | 10 Go/mois gratuits | ~0 $ (< 10 Go de messages) |
| Cloud Storage | 5 Go Standard, 5K Class A ops, 50K Class B ops/mois | ~0.12 $ (5 Go a 0.023 $/Go) |
| Cloud Run | 2M requetes/mois, 180K vCPU-s, 360K GiB-s | ~0-5 $ (workers en mode scale-to-zero) |
| Cloud Functions | 2M invocations/mois, 400K Go-s | ~0 $ |
| Cloud Scheduler | 3 jobs gratuits/mois | ~0 $ |
| **Total estime** | | **~0-5 $/mois** |

#### DX et dev local
- **Dev local :** Firebase Emulator Suite pour Firestore/Functions -- plus simple que LocalStack mais ne couvre pas Pub/Sub ni Cloud Run
- **Deploiement :** `gcloud run deploy` = une commande. Cloud Run est nettement plus simple que ECS/Fargate
- **Debugging :** Cloud Logging integre, Error Reporting automatique
- **Courbe d'apprentissage :** Moderee (IAM existe mais plus simple qu'AWS)

#### Avantages
- Cloud Run = deploiement container ultra simplifie (1 commande)
- Scale-to-zero natif (pas de cout quand inactif)
- Firestore a un free tier tres genereux
- Firebase Emulator simplifie le dev local pour Firestore
- Meilleure DX que AWS pour un debutant

#### Inconvenients
- Migration DynamoDB -> Firestore = refacto significatif du data model
- Pub/Sub est plus complexe que SQS (concepts d'abonnement)
- Vendor lock-in similaire a AWS (Firestore est proprietaire)
- Cloud Tasks (alternative plus simple a Pub/Sub pour les queues) a des limites
- Moins de documentation communautaire que AWS pour les cas d'usage specifiques

---

### 3.3 Railway

**Type :** PaaS simplifie

#### Couts estimes (plan Hobby a 5 $/mois)

| Ressource | Inclus | Cout supplementaire |
|-----------|--------|-------------------|
| Compute | 5 $ de credits/mois | vCPU : 0.000463 $/min ; RAM : 0.000231 $/min/Go |
| PostgreSQL | Inclus (plugin) | Volume : 0.000004 $/min/Go |
| Redis | Inclus (plugin) | Idem |
| Stockage objets | Non disponible nativement | Doit utiliser S3/R2 externe |
| Egress | 0.05 $/Go | - |
| **Total estime** | | **~5-10 $/mois** (Hobby plan + usage modere) |

#### DX et dev local
- **Dev local :** `railway run` injecte les variables d'env; pas besoin d'emulateurs -- les services tournent en remote
- **Deploiement :** `git push` ou `railway up` -- zero config Dockerfile ou Nixpacks auto-detect
- **Debugging :** Logs en temps reel dans le dashboard, metriques integrees
- **Courbe d'apprentissage :** Tres faible -- le plus simple de tous les providers

#### Avantages
- DX exceptionnelle : deploy en `git push`
- PostgreSQL et Redis en un clic
- Variables d'environnement centralisees
- Pas besoin de comprendre IAM, VPC, networking
- Support Docker natif

#### Inconvenients
- **Pas de message queue native** -- il faudrait utiliser un service externe (BullMQ avec Redis, ou SQS externe)
- **Pas de stockage objets natif** -- besoin de Cloudflare R2 ou S3
- **Pas de scale-to-zero** pour les workers (facture continue)
- **Pas de cron natif robuste** (cron jobs basiques uniquement)
- Limites en termes de scaling avance
- Vendor lock-in PaaS (mais code standard, facilement portable)

---

### 3.4 Fly.io

**Type :** Edge compute, containers

#### Couts estimes

| Ressource | Free Tier (legacy) | Cout estime |
|-----------|-------------------|------------|
| Machines | 3 shared-cpu-1x 256 Mo (legacy) | shared-cpu-1x 256 Mo : ~2 $/mois chacune |
| Volumes | 3 Go gratuits | 0.15 $/Go/mois |
| PostgreSQL | Fly Postgres (self-managed) | ~2-5 $/mois (petite instance) |
| Egress | 30-100 Go gratuits | 0.02 $/Go |
| IPv4 | - | 2 $/mois par IP |
| **Total estime** | | **~10-20 $/mois** (API + 2-3 workers + DB + volumes) |

#### DX et dev local
- **Dev local :** Pas d'emulateur -- dev local standard avec Docker, connexion aux services Fly en remote possible
- **Deploiement :** `fly deploy` -- bonne DX mais configuration `fly.toml` necessaire
- **Debugging :** `fly logs`, `fly ssh console` -- basique mais suffisant
- **Courbe d'apprentissage :** Moderee (concepts de machines, volumes, regions)

#### Avantages
- Scale-to-zero possible (machines s'arretent quand inactives)
- Deploiement global (edge) si besoin
- Machines Fly = conteneurs legers, demarrage rapide
- PostgreSQL managed (via Fly Postgres)

#### Inconvenients
- **Pas de message queue native** -- besoin d'un service externe
- **Pas de stockage objets natif** -- besoin de S3/R2
- Postgres sur Fly est "self-managed" (pas un vrai managed DB, maintenance a la charge du dev)
- Le free tier legacy est en train d'etre deprecie
- Instabilite rapportee par la communaute (incidents frequents en 2024-2025)
- Plus cher que Railway pour un usage similaire

---

### 3.5 Render

**Type :** PaaS

#### Couts estimes

| Service | Free Tier | Cout plan Starter |
|---------|-----------|------------------|
| Web Service | 0.1 CPU, 512 Mo (free, spin down apres 15 min) | 7 $/mois (0.5 CPU, 512 Mo) |
| Background Worker | Identique | 7 $/mois |
| PostgreSQL | 256 Mo RAM, 30 jours | 6 $/mois (Basic) |
| Redis | 25 Mo (free) | 10 $/mois (Starter, 256 Mo) |
| Cron Jobs | - | 1 $/mois minimum |
| Stockage objets | Non disponible | Doit utiliser S3/R2 externe |
| **Total estime** | | **~15-30 $/mois** (API + 2-3 workers + DB + Redis + cron) |

#### DX et dev local
- **Dev local :** Pas d'emulateur specifique -- dev local standard, variables d'env manuelles
- **Deploiement :** Connect GitHub repo, auto-deploy sur push -- tres simple
- **Debugging :** Logs dans le dashboard, basique
- **Courbe d'apprentissage :** Faible

#### Avantages
- Deploiement simple (GitHub integration)
- PostgreSQL managed accessible
- Background Workers et Cron Jobs natifs
- Pricing previsible

#### Inconvenients
- **Pas de message queue native** -- Redis comme queue (BullMQ) ou service externe
- **Pas de stockage objets natif**
- Le free tier spin-down de 15 min = cold starts frequents
- Plus cher que Railway et AWS pour un usage equivalent
- Workers factures en permanence (pas de scale-to-zero)
- Scaling limite compare a AWS/GCP

---

### 3.6 Cloudflare (Workers + R2 + D1 + Queues)

**Type :** Edge serverless

#### Couts estimes (plan Workers Paid a 5 $/mois)

| Service | Inclus dans le plan | Cout supplementaire |
|---------|--------------------|--------------------|
| Workers | 10M requetes/mois, 30M CPU-ms | +0.30 $/M requetes, +0.02 $/M CPU-ms |
| R2 (stockage) | 10 Go gratuit | 0.015 $/Go/mois, egress gratuit |
| D1 (SQLite) | 25B lectures, 50M ecritures/mois, 5 Go | +0.001 $/M lectures, +1 $/M ecritures |
| Queues | 1M operations/mois | +0.40 $/M operations |
| KV | 10M lectures, 1M ecritures/mois | +0.50 $/M lectures |
| **Total estime** | | **~5 $/mois** (plan de base suffit largement) |

#### DX et dev local
- **Dev local :** `wrangler dev` simule Workers, D1, R2, KV, Queues localement -- excellent
- **Deploiement :** `wrangler deploy` -- une commande, zero infra a gerer
- **Debugging :** `wrangler tail` pour les logs en temps reel
- **Courbe d'apprentissage :** Moderee a elevee (paradigme Workers/serverless different)

#### Avantages
- **Cout extremement bas** (5 $/mois couvre largement le profil)
- **R2 : egress gratuit** (pas de frais de sortie, contrairement a S3)
- **Queues natives** (equivalent SQS)
- **D1 : SQLite distribue** -- plus simple que DynamoDB
- Emulateur local complet (`wrangler dev`)
- Scale-to-zero natif
- CDN mondial integre

#### Inconvenients
- **Refonte majeure du code necessaire** : Workers utilise un runtime V8 (JavaScript/WASM), pas Python natif
- **Python sur Workers est experimental** (via Pyodide/WASM) -- pas production-ready pour un backend complexe
- D1 est SQLite : pas de requetes complexes type DynamoDB GSI, mais suffisant pour ce use case
- Limites CPU par invocation (5 min max pour cron triggers)
- Pas de compute long-running (transcription Whisper impossible directement)
- Ecosysteme encore jeune pour les workloads backend complexes

**Verdict Cloudflare :** L'offre est tres attractive en cout, mais le runtime V8/JavaScript est un bloqueur majeur pour un backend Python existant avec des workers longs (transcription audio).

---

### 3.7 Hetzner + services manages

**Type :** VPS / IaaS

#### Couts estimes

| Ressource | Specification | Cout |
|-----------|--------------|------|
| VPS CX22 (ou CAX11 ARM) | 2 vCPU, 4 Go RAM, 40 Go SSD, 20 To trafic | ~4-5 EUR/mois |
| Object Storage | Compatible S3 | ~0.005 EUR/Go (minimum 1 EUR/mois) |
| PostgreSQL (self-hosted sur le VPS) | Sur le meme serveur | 0 $ (inclus) |
| Redis (self-hosted) | Sur le meme serveur | 0 $ (inclus) |
| **Total estime** | | **~5-7 EUR/mois** (~5-8 $) |

#### DX et dev local
- **Dev local :** Dev local classique avec Docker Compose, PostgreSQL, Redis -- le plus proche du dev standard
- **Deploiement :** SSH + Docker Compose ou Coolify/Caprover pour simplifier -- setup initial plus lourd
- **Debugging :** SSH, `docker logs`, outils standard Linux
- **Courbe d'apprentissage :** Elevee (sysadmin, securite, updates, backups)

#### Avantages
- **Cout le plus bas** (VPS puissant pour le prix)
- Pas de vendor lock-in (serveur Linux standard)
- Trafic sortant inclus genereux (20 To)
- Localisation possible en Europe (RGPD)
- Controle total sur l'infrastructure
- Object Storage compatible S3

#### Inconvenients
- **Tout est a gerer soi-meme** : securite, updates OS, backups, SSL, monitoring
- Pas de message queue managee -- doit installer Redis/RabbitMQ soi-meme
- Pas de scaling automatique (il faut migrer vers un VPS plus gros)
- Pas de managed database (PostgreSQL a maintenir soi-meme)
- Single point of failure (un seul serveur)
- **Inadapte pour un solo dev novice en infra** -- trop de responsabilites ops

---

### 3.8 DigitalOcean (App Platform + Managed Services)

**Type :** PaaS + IaaS hybride

#### Couts estimes

| Service | Cout |
|---------|------|
| App Platform (API) | 5-12 $/mois (container basique) |
| App Platform (workers x2-3) | 10-36 $/mois |
| Managed PostgreSQL | 15 $/mois (plus petit plan) |
| Spaces (stockage objets, S3-compatible) | 5 $/mois (250 Go inclus) |
| **Total estime** | | **~35-68 $/mois** |

#### DX et dev local
- **Dev local :** Pas d'emulateur, dev local standard
- **Deploiement :** App Platform = deploiement depuis GitHub, bonne DX
- **Debugging :** Dashboard, logs integres
- **Courbe d'apprentissage :** Faible a moderee

#### Avantages
- Managed PostgreSQL fiable
- Spaces (S3-compatible) simple d'usage
- App Platform simplifie le deploiement
- Bonne documentation

#### Inconvenients
- **Significativement plus cher** que les alternatives pour ce profil
- Pas de message queue native
- App Platform limite en customisation
- Pas de scale-to-zero

---

### 3.9 Supabase (PostgreSQL + Edge Functions)

**Type :** Backend-as-a-Service

#### Couts estimes

| Service | Free Tier | Plan Pro (25 $/mois) |
|---------|-----------|---------------------|
| Database PostgreSQL | 500 Mo | 8 Go inclus |
| Storage | 1 Go | 100 Go inclus |
| Auth | 50K MAU | 100K MAU |
| Edge Functions | 500K invocations | 2M invocations |
| Bandwidth | 5 Go | 250 Go |
| Realtime | 2M messages | Illimite |
| **Total estime** | **0 $/mois (free tier)** | **25 $/mois** |

#### DX et dev local
- **Dev local :** `supabase start` lance PostgreSQL + API + Auth + Storage localement via Docker -- excellente DX
- **Deploiement :** Dashboard ou CLI, migrations SQL integrees
- **Debugging :** Dashboard avec SQL editor, logs
- **Courbe d'apprentissage :** Faible (PostgreSQL standard)

#### Avantages
- Free tier genereux
- PostgreSQL standard (pas de vendor lock-in sur le schema)
- Auth integre (remplacerait la gestion de tokens custom)
- Storage integre (S3-compatible sous le capot)
- Edge Functions pour le compute serverless
- Excellente DX locale (`supabase start`)

#### Inconvenients
- **Pas de message queue native** -- doit utiliser pg_notify, pgmq, ou service externe
- Edge Functions = Deno/TypeScript (pas Python natif pour les workers)
- Le free tier est limite (500 Mo DB, pause apres 1 semaine d'inactivite)
- Workers de longue duree (transcription Whisper) impossibles dans Edge Functions
- Necessite un compute externe pour les workers Python lourds

---

## 4. Tableau comparatif synthetique

| Critere | AWS (actuel) | GCP | Railway | Fly.io | Render | Cloudflare | Hetzner | DigitalOcean | Supabase |
|---------|-------------|-----|---------|--------|--------|------------|---------|-------------|----------|
| **Cout mensuel estime** | 5-15 $ | 0-5 $ | 5-10 $ | 10-20 $ | 15-30 $ | 5 $ | 5-8 $ | 35-68 $ | 0-25 $ |
| **Simplicite deploiement** | Faible | Bonne | Excellente | Bonne | Bonne | Bonne | Faible | Bonne | Bonne |
| **DX locale** | Bonne (LocalStack) | Correcte (emulateurs partiels) | Bonne (`railway run`) | Correcte | Faible | Excellente (`wrangler dev`) | Bonne (Docker standard) | Faible | Excellente (`supabase start`) |
| **Queue de messages** | SQS (natif) | Pub/Sub (natif) | Non (Redis/BullMQ) | Non | Non (Redis) | Queues (natif) | Non (self-hosted) | Non | Non (pgmq) |
| **Base de donnees** | DynamoDB | Firestore | PostgreSQL (plugin) | Postgres (self-managed) | PostgreSQL | D1 (SQLite) | Self-hosted | PostgreSQL managed | PostgreSQL |
| **Stockage objets** | S3 | Cloud Storage | Non (externe) | Non (externe) | Non (externe) | R2 (natif, egress gratuit) | Object Storage | Spaces (S3-compat) | Storage (integre) |
| **Compute async/workers** | Fargate/Lambda | Cloud Run/Functions | Services Docker | Machines Fly | Background Workers | Workers (JS only) | Docker sur VPS | App Platform workers | Edge Functions (Deno) |
| **Cron/Scheduler** | EventBridge | Cloud Scheduler | Basique | Machines schedulees | Cron Jobs (natif) | Cron Triggers (natif) | crontab Linux | App Platform jobs | pg_cron |
| **Scale-to-zero** | Lambda oui, Fargate non | Cloud Run oui | Non | Oui | Non (free tier spin-down) | Oui | Non | Non | Edge Functions oui |
| **Vendor lock-in** | Eleve (DynamoDB, SQS) | Eleve (Firestore) | Faible | Faible | Faible | Modere (Workers runtime) | Aucun | Faible | Faible (PostgreSQL) |
| **Maturite/fiabilite** | Excellente | Excellente | Bonne | Moyenne (incidents) | Bonne | Bonne (Workers mature) | Excellente | Excellente | Bonne |
| **Python backend support** | Natif | Natif | Natif | Natif | Natif | Non (JS/WASM) | Natif | Natif | Partiel (Edge = Deno) |

---

## 5. Analyse detaillee par provider

### Providers elimines pour ce projet

| Provider | Raison d'elimination |
|----------|---------------------|
| **Cloudflare** | Runtime V8/JavaScript incompatible avec le backend Python existant. Workers Python (Pyodide) est experimental. Les workers longs (transcription Whisper, 10+ min) depassent les limites CPU. |
| **Hetzner** | Trop de responsabilites sysadmin pour un solo dev novice. Pas de services manages (queue, DB). Le cout est bas mais le temps ops est eleve. |
| **DigitalOcean** | Significativement plus cher (35-68 $/mois) sans avantage compensatoire clair. Pas de queue native. |
| **Fly.io** | Plus cher que Railway sans avantage clair. Postgres self-managed. Instabilite rapportee. Free tier en depreciation. |
| **Supabase** | Excellent pour le BaaS/auth/stockage, mais ne resout pas le compute Python (workers Whisper). Pourrait etre utilise en complement mais pas en remplacement complet. |

### Finalistes : AWS (actuel) vs GCP vs Railway

#### AWS -- Rester sur l'existant
- **Pour :** Zero effort de migration. Free tier couvre largement l'usage. Tout est deja code et teste.
- **Contre :** Complexite operationnelle disproportionnee pour un solo dev. Le deploiement Fargate necesssite VPC, subnets, security groups, task definitions. 50+ fichiers avec des references boto3. La dette de complexite va s'alourdir avec le temps.

#### GCP (Cloud Run + Firestore)
- **Pour :** Cloud Run est radicalement plus simple que ECS/Fargate (`gcloud run deploy`). Scale-to-zero natif. Cout potentiellement nul avec le free tier.
- **Contre :** Migration DynamoDB -> Firestore = refonte du data layer. ~14 tables DynamoDB avec GSI a migrer. Effort significatif (2-4 semaines).

#### Railway
- **Pour :** DX la plus simple de toutes les options. Deploy en `git push`. PostgreSQL en un clic.
- **Contre :** Pas de queue native (faut passer par Redis/BullMQ ou garder SQS). Pas de stockage objets natif. Workers toujours actifs = cout continu.

---

## 6. Impact sur le workflow dev local

### Situation actuelle (AWS + LocalStack)
```
docker-compose up --profile full
```
Lance 10+ conteneurs : LocalStack, Terraform, API, 6 workers, lambda-builder. Le setup initial est lourd (~2-3 min de demarrage, build des images Docker, provisioning Terraform). Mais une fois lance, le workflow est fidele a la production.

### Si migration vers GCP
- **Firestore :** Firebase Emulator Suite (`firebase emulators:start`) remplace LocalStack pour la DB
- **Cloud Run :** Dev local avec Docker standard, pas d'emulateur necessaire
- **Pub/Sub :** Emulateur disponible (`gcloud beta emulators pubsub start`)
- **Verdict :** Setup plus leger mais emulateurs fragmentes (un par service)

### Si migration vers Railway
- **Dev local :** Docker Compose classique avec PostgreSQL + Redis
- **Pas besoin d'emulateur** -- les services sont standards (PostgreSQL, Redis)
- **Variables d'env :** `railway run` ou fichier `.env` local
- **Verdict :** Le plus simple. Docker Compose avec 3-4 services au lieu de 10+

### Si on reste sur AWS
- **Aucun changement** du workflow actuel
- Possible simplification : remplacer ECS/Fargate par des services plus simples cote deploiement (ex: ECS avec Copilot CLI, ou App Runner)

---

## 7. Recommandation

### Recommandation principale : Rester sur AWS, simplifier le deploiement

**Justification :**

1. **Le cout n'est pas le probleme.** A 5-15 $/mois, AWS est competitif avec toutes les alternatives pour ce profil d'usage. Le free tier AWS (DynamoDB, SQS, Lambda, S3) est l'un des plus genereux.

2. **Le code est deja ecrit et teste.** 50+ fichiers utilisent boto3/aiobotocore. 14 tables DynamoDB avec leurs schemas et GSI. 7 queues SQS avec DLQ et retry logic. Migrer tout ca represente 3-6 semaines de travail minimum, sans valeur ajoutee pour les utilisateurs.

3. **Le vrai probleme est la complexite de deploiement, pas le provider.** ECS/Fargate avec VPC/subnets/security groups est sur-dimensionne pour un solo dev. La solution est de simplifier le deploiement AWS, pas de changer de provider.

### Actions recommandees (par priorite)

#### Action 1 : Remplacer ECS/Fargate par AWS App Runner (effort : 1-2 jours)
App Runner est le "PaaS d'AWS" -- deploiement depuis un container ECR ou GitHub, pas de VPC a gerer, scaling automatique incluant scale-to-zero.
- Supprime le besoin de : VPC, subnets, security groups, task definitions, scaling controller Lambda
- Cout similaire (~5-15 $/mois pour faible trafic)
- Conserve tout le reste (DynamoDB, SQS, S3, Lambda)

#### Action 2 : Utiliser AWS Copilot CLI (alternative a l'action 1)
Copilot abstrait ECS/Fargate derriere une CLI simple :
```bash
copilot init    # Setup initial
copilot deploy  # Deploiement
copilot svc logs # Logs
```
Moins radical que App Runner mais simplifie enormement l'experience ECS.

#### Action 3 : Documenter le deploiement (effort : 1 jour)
Creer un guide step-by-step pour le deploiement production AWS, avec les commandes exactes.

### Recommandation secondaire (si refonte future envisagee)

Si une refonte significative du backend est prevue (ex: passage a un nouveau framework, changement de data model), alors **GCP avec Cloud Run** serait le meilleur choix alternatif :
- Cloud Run = deploiement radicalement plus simple que Fargate
- Firestore couvre le use case NoSQL avec un free tier genereux
- Scale-to-zero natif = cout quasi nul au lancement
- Mais cette migration n'a de sens que couplee a une refonte existante, pas comme projet isole

### Ce qu'il ne faut PAS faire

- **Ne pas migrer vers Railway/Render/Fly.io** : ces PaaS ne proposent pas de queue native ni de stockage objets, donc il faudrait quand meme utiliser AWS SQS + S3, creant un systeme hybride plus complexe que le full-AWS actuel.
- **Ne pas migrer vers Cloudflare** : le runtime JavaScript est incompatible avec le backend Python.
- **Ne pas migrer vers Hetzner** : trop de responsabilites sysadmin pour le profil du developpeur.

---

## 8. Plan de migration (si changement)

### Plan A : Simplification AWS (recommande)

Pas de migration de provider, mais simplification de la couche compute :

| Etape | Action | Effort |
|-------|--------|--------|
| 1 | Evaluer AWS App Runner vs ECS Copilot CLI | 0.5 jour |
| 2 | Prototype deploiement API sur App Runner | 1 jour |
| 3 | Migrer les workers vers App Runner ou ECS via Copilot | 1-2 jours |
| 4 | Supprimer le scaling controller Lambda et la config VPC/Fargate | 0.5 jour |
| 5 | Documenter le nouveau workflow de deploiement | 0.5 jour |
| **Total** | | **3-5 jours** |

### Plan B : Migration vers GCP (si refonte)

| Etape | Action | Effort |
|-------|--------|--------|
| 1 | Creer un adapter layer DB (interface abstraite au-dessus de DynamoDB/Firestore) | 3-5 jours |
| 2 | Migrer les 14 tables DynamoDB vers Firestore (schema + data) | 5-7 jours |
| 3 | Remplacer SQS par Cloud Tasks ou Pub/Sub | 3-4 jours |
| 4 | Remplacer S3 par Cloud Storage (quasi identique via S3-compatible API) | 1 jour |
| 5 | Deployer API + workers sur Cloud Run | 2-3 jours |
| 6 | Remplacer Lambda + EventBridge par Cloud Functions + Cloud Scheduler | 1-2 jours |
| 7 | Supprimer LocalStack, adapter le dev local (Firebase Emulator) | 2-3 jours |
| 8 | Tests d'integration complets | 3-5 jours |
| **Total** | | **20-30 jours** |

---

## 9. Sources

- AWS DynamoDB Pricing : https://aws.amazon.com/dynamodb/pricing/
- AWS SQS Pricing : https://aws.amazon.com/sqs/pricing/
- AWS S3 Pricing : https://aws.amazon.com/s3/pricing/
- AWS Fargate Pricing : https://aws.amazon.com/fargate/pricing/
- AWS Lambda Pricing : https://aws.amazon.com/lambda/pricing/
- AWS Free Tier : https://aws.amazon.com/free/
- GCP Cloud Run Pricing : https://cloud.google.com/run/pricing
- GCP Firestore Pricing : https://cloud.google.com/firestore/pricing
- GCP Cloud Storage Pricing : https://cloud.google.com/storage/pricing
- GCP Pub/Sub Pricing : https://cloud.google.com/pubsub/pricing
- Railway Pricing : https://railway.com/pricing
- Fly.io Pricing : https://fly.io/docs/about/pricing/
- Render Pricing : https://render.com/pricing
- Cloudflare Workers Pricing : https://developers.cloudflare.com/workers/platform/pricing/
- Cloudflare R2 Pricing : https://developers.cloudflare.com/r2/pricing/
- Cloudflare Queues Pricing : https://developers.cloudflare.com/queues/platform/pricing/
- Hetzner Cloud : https://www.hetzner.com/cloud/
- DigitalOcean Pricing : https://www.digitalocean.com/pricing
- Supabase Pricing : https://supabase.com/pricing
- AWS App Runner : https://aws.amazon.com/apprunner/
- AWS Copilot CLI : https://aws.github.io/copilot-cli/
