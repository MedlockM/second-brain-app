# V1 Launch Plan — Media Summarizer

> Plan exhaustif des étapes restantes pour mettre l'application en production.
> Date de rédaction : 2026-05-19. Dernière mise à jour : 2026-06-09 (Phase 3 AWS dev déployée + **Phase 4 article + 4 artifacts + YouTube validés E2E** via la suite pytest `tests/e2e/`). Sources V1 restantes à valider : podcast, X, TikTok, Instagram, PDF.

---

## 0. Périmètre V1 confirmé

### Sources d'ingestion supportées en V1

| Source | Statut code | Bloquant V1 |
|---|---|---|
| Articles web (lecture/extraction) | OK | — |
| YouTube (transcript natif + fallback Deepgram) | OK | — |
| Podcasts (PodcastIndex resolver) | OK | — |
| Audio file (upload direct) | OK | — |
| **X (Twitter)** | OK — worker, resolver, classifier, orchestrator câblés | — |
| **TikTok** | OK — worker dédié + 2-tier rate limiter (pacing + quota horaire) | — |
| **Instagram** | OK — Apify resolver (Reel/Post/Comment Scrapers) + orchestrator dispatch câblés | — |
| Shared text | OK | — |
| **Documents (PDF/DOCX/PPTX)** | OK — LlamaParse resolver (primary) + Unstructured resolver (fallback) + document_parsing worker câblés | — |

### Méthodes d'authentification V1

| Méthode | Statut | Bloquant V1 |
|---|---|---|
| Email + password | OK (backend + mobile) | — |
| **Sign in with Apple** | Code OK — backend + mobile câblés. Obligatoire App Store car Google login présent | OK (chaîne Apple Developer complète provisionnée 2026-06-08 : Service ID, Sign in with Apple Key `.p8`, Team ID, Key ID, Return URL prod renseignés dans `.env`) |
| **Continue with Google** | Code OK — backend + mobile câblés. Backend Web client ID + secret OK dans `.env` | 3 OAuth Client IDs publics (iOS, Android, Web Expo) + écran de consentement publié dans Google Cloud Console |

---

## 1. Tâches d'implémentation restantes (backlog)

Aucune tâche bloquante V1 ouverte côté code au 2026-05-20.

---

## 2. Comptes et abonnements à créer

| Service | Coût | Pourquoi | Statut |
|---|---|---|---|
| **GitHub** (compte + repo privé) | gratuit | Versioning, CI/CD, releases | OK (`MedlockM/second-brain-app`, privé, créé 2026-05-27) |
| **AWS** (compte) | usage-based | DynamoDB, S3, SQS, Lambda, EventBridge | À créer |
| **Apple Developer Program** | $99/an | Publication App Store, TestFlight, IAP sandbox | À créer |
| **Google Play Console** | $25 one-time | Publication Play Store, Internal Testing, IAP sandbox | À créer |
| **Expo / EAS** | gratuit (free tier) | Builds iOS/Android | OK (compte créé 2026-06-10, `eas-cli` installé localement, `eas whoami` validé) |
| **RevenueCat** | gratuit < $10k MTR | Cross-platform IAP backend | À créer |
| **Google Cloud Console** (OAuth) | gratuit | Sign in with Google : OAuth Client IDs (iOS, Android, Web) + écran de consentement OAuth | Compte créé + Web client ID/secret backend OK (en local dans `.env`) ; 3 client IDs publics (iOS, Android, Web Expo) + écran de consentement publié restent à faire |
| **OpenAI** | usage-based | Génération artifacts (summary/notes/flashcards) | OK (compte créé, clé en local dans `.env`) |
| **Deepgram** | usage-based | Transcription audio | OK (compte créé, clé en local dans `.env`) |
| **Algolia** | gratuit < 10k records | Search lexical | OK (App ID + Admin API key + index name en local dans `.env`) |
| **PodcastIndex.org** | gratuit | Resolver podcasts | OK (compte créé, clé+secret en local dans `.env`) |
| **Apify** | usage-based / API token | Resolver Instagram (Reel + Post + Comment Scrapers) | OK (token + 3 actor IDs en local dans `.env`) |
| **LlamaParse** (LlamaIndex Cloud) | gratuit free tier (1000 pages/jour) | Resolver documents primaire (PDF/DOCX/PPTX) | OK (compte créé, clé en local dans `.env`) |
| **Unstructured.io** | 15 000 pages gratuites au début, puis usage-based | Resolver documents fallback | OK (compte créé, clé en local dans `.env`) |
| **X (Developer Platform)** | Free tier OK pour V1 | Lecture API X | OK (compte créé, bearer token en local dans `.env`) |

---

## 3. Variables d'environnement / Secrets à renseigner

Production : tous les secrets sont consolidés dans une seule entrée **AWS Secrets Manager**
(`media-summarizer-runtime-<env>`) provisionnée par `infrastructure/terraform/secrets.tf`.
Les Lambda functions chargent ce secret au cold start et injectent chaque clé du JSON comme
variable d'environnement — le code lit toujours via `os.getenv(...)` sans changement.

Bootstrap : `cp infrastructure/terraform/terraform.tfvars.example terraform.tfvars`,
remplir `secret_payload`, puis `terraform apply`. Voir `infrastructure/terraform/README.md`.

Local : **un seul fichier `.env`** à la racine, chargé automatiquement par
`python-dotenv` depuis `media_summarizer/__init__.py` (override=False, donc les
vraies variables d'env priment). Modèle complet : `.env.example` (18 sections
numérotées). Les anciens `.env.dev` et `.env.prod` sont **legacy et gitignorés**
— ne pas les utiliser ni les recréer.

### 3.1 AWS infra

```bash
AWS_DEFAULT_REGION=eu-west-3
AWS_ACCESS_KEY_ID=...              # clé IAM dédiée backend (production hors Lambda)
AWS_SECRET_ACCESS_KEY=...
ARCHIVE_BUCKET=...
AUDIO_BUCKET=...
DOCUMENT_BUCKET=...
FLASHCARDS_BUCKET=...
# Autres buckets/tables/queues : voir .env.example sections 3-5 et terraform/
```

### 3.2 Auth

```bash
JWT_SECRET_KEY=...                     # 32+ bytes random, généré pour la prod
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
COOKIE_SECURE=true
COOKIE_DOMAIN=app.<your-domain>
COOKIE_SAMESITE=Lax

# Google OAuth (Sign in with Google)
GOOGLE_CLIENT_ID=...                   # Web client ID — vérifie l'`aud` des id_tokens mobiles iOS/Android
GOOGLE_CLIENT_SECRET=...               # Requis pour le flow web /google/callback
GOOGLE_REDIRECT_URI=https://api.<your-domain>/api/v1/auth/google/callback

# Apple OAuth (Sign in with Apple)
APPLE_TEAM_ID=...                      # Visible dans Apple Developer Account → Membership
APPLE_KEY_ID=...                       # Du Sign in with Apple Key généré dans Apple Developer
APPLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
APPLE_CLIENT_ID=...                    # Service ID (ex: com.secondbrainlabs.core.signinwithapple)
APPLE_REDIRECT_URI=https://api.<your-domain>/api/v1/auth/apple/callback
```

Côté mobile (`mobile/.env` ou EAS secrets) :

```bash
# Google OAuth client IDs créés dans Google Cloud Console
# Naming attendu par mobile/app.config.ts : suffixe _<PLATFORM>, pas infixe.
EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB=...    # même valeur que GOOGLE_CLIENT_ID côté backend
EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS=...
EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID=...
```

### 3.3 LLM / Transcription

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-nano-2026-03-17  # défaut V1 ; overrides per-artifact dispo dans .env.example
DEEPGRAM_API_KEY=...
DEEPGRAM_MODEL=nova-3
```

### 3.4 Search

```bash
ALGOLIA_APP_ID=...
ALGOLIA_API_KEY=...                  # admin key (côté backend)
ALGOLIA_INDEX_NAME=media_v1
```

### 3.5 Sources d'ingestion

```bash
# Podcasts
PODCASTINDEXORG_API_KEY=...
PODCASTINDEXORG_API_SECRET=...

# X (Twitter)
X_API_BEARER_TOKEN=...               # OAuth 2.0 bearer

# TikTok — pas de clé externe, utilise le natif
TIKTOK_RATE_LIMIT_PER_HOUR=200       # par défaut, à ajuster

# Instagram (via Apify actors)
APIFY_INSTAGRAM_API_TOKEN=...
APIFY_TIMEOUT_SECONDS=60

# Documents — LlamaParse primaire + Unstructured fallback
LLAMAPARSE_API_KEY=...                 # LlamaIndex Cloud
LLAMAPARSE_TIMEOUT_SECONDS=120
LLAMAPARSE_POLL_INTERVAL=2
LLAMAPARSE_MAX_POLLS=60
UNSTRUCTURED_API_KEY=...
UNSTRUCTURED_API_URL=https://api.unstructuredapp.io
UNSTRUCTURED_TIMEOUT_SECONDS=120
```

### 3.6 RevenueCat (billing)

```bash
REVENUCAT_API_KEY=sk_...             # secret API key (backend)
REVENUCAT_PROJECT_ID=...
REVENUCAT_WEBHOOK_SECRET=...         # configuré dans le dashboard RC
```

Côté mobile (`mobile/.env` ou EAS secrets) — naming attendu par `mobile/app.config.ts` :

```bash
EXPO_PUBLIC_REVENUCAT_APPLE_KEY=appl_...    # public key iOS (RevenueCat dashboard → Apps → ton app iOS)
EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY=goog_...   # public key Android (à différer)
```

### 3.7 Mobile (Expo / EAS)

```bash
EXPO_PUBLIC_API_BASE_URL=https://api.<your-domain>
```

---

## 4. Phases d'exécution (ordre logique)

### Phase 1 — Code & repo (jour 1)

1. ~~Créer un repo GitHub privé.~~ **Fait** : `MedlockM/second-brain-app` (privé), branche par défaut `main`. Historique purgé des secrets, `.venv-311/` et scratchpads ; `.gitignore` durci. Premier push : 2026-05-27 (HEAD `eb22f0e`, 174 commits, 553 fichiers).
2. Activer Branch protection sur `main` (require PR + checks).
3. Configurer GitHub Actions (CI minimal : `ruff`, `mypy` côté backend ; `npm run typecheck` + `npm run lint` côté mobile). Validation fonctionnelle via les phases 4 et 9.
4. Bascule du worktree de dev local : `cd ~/Documents/Perso/dev/media-summarizer-project && git remote rename origin old-origin && git remote add origin git@github.com:MedlockM/second-brain-app.git && git fetch origin` puis travailler désormais contre `origin/main` du nouveau dépôt.

### Phase 2 — Comptes externes (jour 1-2)

1. Apple Developer Program (commande, peut prendre 24-48h).
2. Google Play Console.
3. AWS account + IAM admin user + facturation alarms.
4. ~~Expo / EAS account + lien vers le repo.~~ **Fait** : compte Expo créé 2026-06-10, `eas-cli` installé, `eas whoami` validé. Lien vers le repo (`expo.projectId` dans `app.config.ts`) sera établi automatiquement au premier `eas build` (Phase 5 §2).
5. RevenueCat account + projet + apps iOS/Android (clés générées).
6. Comptes API tiers : tous configurés au 2026-06-01 (clés présentes dans `.env`) — **OpenAI**, **Deepgram**, **PodcastIndex.org**, **X Developer Platform**, **Apify**, **LlamaParse**, **Unstructured.io**, **Algolia**. **Google OAuth backend** également déjà provisionné (`GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` en local dans `.env`). **Apple OAuth backend OK au 2026-06-08** : chaîne complète provisionnée — `APPLE_CLIENT_ID` (Service ID), `APPLE_PRIVATE_KEY` (`.p8` PEM single-line), `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_REDIRECT_URI` prod renseignés dans `.env`. **`PRICING_ADMIN_SECRET` généré au 2026-06-08** (`openssl rand -hex 32`, en local dans `.env`). Restent à provisionner : **Android OAuth Client ID** (à différer en Phase 5 après `eas build:configure`) + **publication écran de consentement Test → Production** côté **Google Cloud Console** (Phase 10), **RevenueCat** (projet + 3 produits + webhook).
7. **Google Cloud Console** (console.cloud.google.com) :
   - **Créer un projet** (ex: `Second Brain`). Le nom du projet est un identifiant interne, peu visible aux users.
   - **APIs & Services → OAuth consent screen (Audience)** : Type **External** (les apps Workspace internes seraient `Internal` mais nécessitent un domaine Google Workspace). Scopes : `openid`, `email`, `profile` uniquement (les scopes "sensitive/restricted" déclencheraient une vérification Google de 4-6 semaines).
   - **OAuth consent screen → Branding** : remplir App name (ex: `Second Brain` — c'est ce que les users voient sur l'écran de consentement, **pas** le nom du projet GCP), logo, user support email, developer contact email.
   - **Audience** : laisser en mode `Test` pendant le développement (max 100 utilisateurs whitelistés) et **s'ajouter soi-même comme "utilisateur test"** pour pouvoir se connecter en dev. La publication en `Production` est faite plus tard, en Phase 10.
   - **APIs & Services → Credentials → 3 OAuth Client IDs** :
     - **Web** (utilisé par le backend pour vérifier l'`aud` du id_token, ET réutilisé côté mobile via `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`) → `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`.
     - **iOS** (avec bundle id du `mobile/app.config.ts`) → `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`.
     - **Android** (avec package name + SHA-1 du keystore EAS) → `EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID`. **À différer en Phase 5** une fois `eas build:configure` exécuté pour récupérer le SHA-1 production.
8. **Apple Developer Portal** (developer.apple.com → Certificates, Identifiers & Profiles) :
   - **Bundle ID figé : `com.secondbrainlabs.core`** (décidé 2026-06-07, propagé dans `mobile/app.config.ts`, `mobile/plugins/withShareExtension.js`, `mobile/ios-share-extension/`, RevenueCat product IDs). Identique côté Apple (App ID + Service ID radical) et Google Play (package name) pour la cohérence cross-platform et les liens universels.
   - **Identifiers → App IDs** : créer un App ID avec `com.secondbrainlabs.core`, et **activer la capability "Sign in with Apple"** dans la liste des capabilities.
   - **Identifiers → Services IDs** : créer le Service ID `com.secondbrainlabs.core.signinwithapple` → c'est la valeur de `APPLE_CLIENT_ID`. Configurer son return URL backend (ex: `https://api.<your-domain>/api/v1/auth/apple/callback`) → c'est la valeur de `APPLE_REDIRECT_URI`. Associer au App ID créé ci-dessus.
   - **Keys → Sign in with Apple Key** : générer une clé associée à l'App ID. Télécharger le fichier `.p8` (=> `APPLE_PRIVATE_KEY`, le contenu PEM single-line avec `\n`) et noter le **Key ID** (=> `APPLE_KEY_ID`). ⚠ **Téléchargement unique** — sauvegarder le `.p8` immédiatement, Apple ne le re-génère pas.
   - **Membership** : récupérer le **Team ID** (=> `APPLE_TEAM_ID`) visible dans le menu Account → Membership.

### Phase 3 — Infrastructure AWS (jour 2-3) — **DEV : DONE 2026-06-08**

Étapes exécutées (dev) :

1. ✅ `infrastructure/terraform/terraform.tfvars` généré depuis `.env` racine (29 clés `secret_payload`, mode 0600, gitignored par `*.tfvars`). Région `eu-west-3`, `enable_alarms = false` (économise ~$4.20/mois en dev — toggle réversible pour staging/prod).
2. ✅ `terraform init` (provider AWS 5.100.0) puis `terraform plan -out=tfplan-dev` → 139 ressources (185 - 46 alarmes désactivées).
3. ✅ `terraform apply` → **140 ressources créées** : 19 DynamoDB tables, 4 S3 buckets + lifecycle, 25 SQS queues + DLQs, 15 Lambda functions (1 API + 14 workers), 14 SQS event source mappings, API Gateway HTTP API, ECR repository, secret consolidé `media-summarizer-runtime-dev` (29 clés), 13 metric filters, 28 log groups, 7 IAM (roles/policies/attachments), CloudWatch dashboard.
4. ✅ Build + push image Lambda : `docker buildx build --platform linux/arm64 --provenance=false --sbom=false ...` (l'absence de `--provenance=false` produit des manifestes OCI que Lambda refuse). Tags `worker-latest` + `api-latest` poussés dans ECR.
5. ✅ Bugs Terraform corrigés en route : (a) bloc `required_providers` dupliqué dans `dynamodb_quota_tables.tf`, (b) `aws_cloudwatch_log_group.lambda_api` dupliqué dans `monitoring.tf`, (c) 37 blocs `attribute {}` single-line invalides reformatés multi-line, (d) `AWS_DEFAULT_REGION` (env var réservée Lambda) retirée de `lambda_workers.tf` + `lambda_api.tf`, (e) 3 metric filters avec dimensions hardcodées corrigées en JSON path selectors `$.field`.
6. ✅ Bug Dockerfile permissions corrigé (`chmod -R a+rX ${LAMBDA_TASK_ROOT}`) — sans ce fix, l'umask 0600 de l'host propage dans l'image et la Lambda runtime user ne peut pas lire les fichiers.
7. ✅ Bug `media_summarizer/utils/database_async.py:get_session()` corrigé : passait `aws_access_key_id` + `aws_secret_access_key` sans le `aws_session_token` que Lambda injecte → `UnrecognizedClientException`. Maintenant on laisse aioboto3 résoudre les credentials via la chaîne standard (sauf si static creds explicites).
8. ✅ IAM `dynamodb:ListTables` ajoutée (action account-wide) au role `media-summarizer-lambda-api` (utilisée par le `/health` check).

**Résultats dev** :
- API endpoint : `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`
- Health check : `GET /api/v1/health/` → `HTTP 200 {"status":"healthy","database":"connected"}` ✨
- ECR repository : `125313707865.dkr.ecr.eu-west-3.amazonaws.com/media-summarizer-lambda`
- Runtime secret ARN : `arn:aws:secretsmanager:eu-west-3:125313707865:secret:media-summarizer-runtime-dev-OyXaYL`
- Coût mensuel attendu (dev sans trafic) : ~$0.50-1/mois (Secrets Manager $0.40 fixe + reste négligeable).

**Pour staging/prod** : recopier `terraform.tfvars` avec `environment = "staging"` ou `"prod"`, mettre `enable_alarms = true` (réactive les 42 alarmes + SNS topics + email subscriptions), réutiliser la même image Lambda dans le même ECR (multi-env partagé).

### Phase 4 — Tests d'intégration contre AWS dev (jour 3-4) — **PARTIELLEMENT DONE 2026-06-09**

> **Décision 2026-05-28 puis 2026-06-09** : pas de LocalStack (purgé via task-130). Tests E2E directement contre l'API Gateway dev.
>
> **Évolution 2026-06-09** : on n'utilise plus uvicorn local pour les tests d'intégration. L'API + les 14 workers tournent en Lambda sur AWS dev (Phase 3) ; on tape directement l'API Gateway via une suite pytest E2E versionnée (`tests/e2e/`). Un re-run prend 30-50 secondes, idempotent, avec teardown automatique.

#### Suite E2E pytest (`tests/e2e/`)

- `pytest -m e2e` lance toute la suite contre `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com` (override via `API_BASE_URL`).
- `tests/e2e/conftest.py` crée un user de test (email horodaté `e2e-test-<ts>-<uuid>@test.local`) au début de session, ingère un article Wikipedia partagé pour les tests d'artifacts, supprime tout en teardown (user + auth_tokens + processing_jobs + artifacts + tags + folders).
- Marqueur `@pytest.mark.e2e` ; suite skipped par défaut (`pytest` sans `-m` lance uniquement les unit tests).
- Détails et runbook : `tests/e2e/README.md`.

#### Statut par source au 2026-06-09

| Source | Statut E2E | Référence |
|---|---|---|
| Health check API | ✅ passing | `tests/e2e/test_health.py` |
| **Article web** (Wikipedia) | ✅ passing en 15s | `test_phase4_ingestion.py::test_article_reaches_completed` |
| **Artifacts on-demand** : summary, notes, flashcards, quiz | ✅ tous les 4 passing en ~5s chacun | `test_phase4_ingestion.py::test_artifact_*_e2e` |
| **YouTube** (Apify) | ✅ passing depuis task-132 (2026-06-09) | `test_phase4_other_sources.py::test_youtube_ingestion` |
| Podcast | ⏭ skip — jamais validé E2E | `test_phase4_other_sources.py::test_podcast_ingestion` |
| X (Twitter) | ⏭ skip — jamais validé E2E | idem |
| TikTok | ⏭ skip — jamais validé E2E | idem |
| Instagram | ⏭ skip — jamais validé E2E | idem |
| Document upload (PDF/DOCX/PPTX) | ⏭ skip — utilise endpoint multipart différent (`/api/media/upload`) | idem |

#### Bugs détectés et fixés en route

Phase 4 a déclenché une cascade de fixes infra/backend :

- **task-119** — Cleanup legacy `ops_alerts` SNS topic + log group dupliqué + `attribute {}` HCL invalide ✅
- **task-120** — Align S3 bucket names env↔terraform + `ProcessingJob.extraction_metadata` field ✅
- **task-121** — Remove deprecated `email` field from summarization worker (legacy SMTP path) ✅
- **task-122** — On-demand artifact pipeline : contract `artifact_id` API↔workers + `media_artifacts` DynamoDB table + worker `quiz` (queue + Lambda + IAM) ✅
- **task-123** — Migrate summarization worker to `artifact_id` contract ✅
- **task-124** — Move `finalize_usage` + `episode_completed` event out of summarization (correctness) ✅
- **task-125** — Audit `JobStatus.SUMMARIZING/NOTIFYING` for dead code removal ✅
- **task-126** — Benchmark YouTube extraction strategies given Lambda IP block ✅
- **task-127** — Split `APIFY_API_TOKEN` per source (Instagram + YouTube separately) ✅
- **task-128** — In-app bug reporting infra ✅
- **task-129** — Migrate YouTube ingestion worker to Apify ✅
- **task-130** — Purge LocalStack runtime + infrastructure ✅
- **task-131** — Fix Apify YouTube actor URL `~` separator + missing `_publish_failure_event` queue ✅
- **task-132** — Fix Apify YouTube actor input payload (HTTP 400 → 200) ✅

#### Reste à faire

1. **Valider les 5 sources skipped** : podcast, X, TikTok, Instagram, document upload. Pour chacune, soumettre une URL réelle, puis flipper le test de `skip` à `e2e` dans `test_phase4_other_sources.py`.
2. **Tester le digest journalier** (EventBridge rule). Pas couvert par l'E2E actuelle.
3. **Mettre en place une purge automatique** des artifacts E2E orphelins en cas de crash pytest non-recoverable (Ctrl-C). Aujourd'hui le teardown manque ce cas — script de cleanup à ajouter dans `scripts/`.

### Phase 5 — Mobile dev build (jour 4-5)

1. `cd mobile && npx expo prebuild` (génère iOS/Android natifs).
2. `eas build --platform ios --profile development` (dev build, requis pour `expo-share-intent`).
3. Installer le dev build sur device physique iOS via TestFlight Internal ou direct install.
4. Idem Android : `eas build --platform android --profile development` + APK sideload.
5. Tester :
   - Email/password login + register
   - **Sign in with Apple** (iOS uniquement) — modal Apple natif → user créé/lié → inbox
   - **Continue with Google** (iOS et Android) — sheet Google natif → user créé/lié → inbox
   - Share intent depuis Safari/Chrome → écran share-confirm → submit
   - Inbox : la vignette du media partagé apparaît immédiatement (insertion optimiste, pas de polling de la liste)
   - Tap sur une vignette en cours de traitement → écran detail avec placeholder « Generating text… » et polling 3s sur `GET /api/media/{id}` jusqu'à `completed`/`failed`
   - Search
   - Paywall (sans achat encore)

### Phase 6 — Tests IAP sandbox (jour 5-6)

1. **iOS** :
   - App Store Connect → Apps → IAP → créer 3 produits (correspondance Offerings RevenueCat).
   - StoreKit configuration locale (`mobile/ios/StoreKit.storekit`) pour Xcode simulator.
   - Sandbox tester accounts dans App Store Connect.
   - Build TestFlight → tester achat avec un compte sandbox.
2. **Android** :
   - Play Console → IAP → créer les mêmes produits.
   - License Tester emails dans Play Console.
   - Build Internal Testing → installer via lien Play Store internal → tester achat.
3. **RevenueCat dashboard** :
   - Vérifier que les Customer Info reflètent l'achat sandbox.
   - Tester le webhook → backend reçoit l'événement → DynamoDB `revenucat_events` est rempli → `subscriptions` table mise à jour → quota élevé.
4. Tester `restorePurchases` depuis l'app (cas user qui réinstalle).

### Phase 7 — CI/CD (jour 6-7)

1. GitHub Actions : workflow PR (`ruff`, `mypy` côté backend ; `npm run typecheck` + `npm run lint` côté mobile).
2. GitHub Actions : workflow main (build Lambda container image, push to ECR, update Lambda functions). See `.github/workflows/deploy-lambda.yml`.
3. EAS Submit pour TestFlight / Play Internal automatique sur tag `v*`.
4. Stocker AWS keys, RevenueCat keys, Expo token comme **GitHub repo secrets**.
5. Vérifier que rollback est possible (re-tag a previous image in ECR and update Lambda).

### Phase 8 — Monitoring & observabilité (jour 7-8)

1. CloudWatch Dashboard avec :
   - Latence API (`API_SLOW_REQUEST_THRESHOLD_MS` → alarmes)
   - Profondeur des queues SQS (alarme si DLQ > 0, en particulier `document-parsing-queue`)
   - Taux d'erreur Deepgram / OpenAI / **LlamaParse / Unstructured** (logs structurés `parser=llamaparse|unstructured` + `error_code`)
   - Coût par source (X, TikTok, Instagram, YouTube, podcasts, **documents**)
   - Compteur quota LlamaParse (1000 pages/jour free tier) — alarme si fallback Unstructured déclenché plus de N fois/heure
2. CloudWatch Alarms → SNS → e-mail.
3. Vérifier que les logs structurés tombent bien dans CloudWatch Logs Insights.

### Phase 9 — Staging end-to-end (jour 8-9)

1. Déployer l'environnement `staging` (séparé de `dev` et `prod`).
2. Tester depuis un device physique avec une URL réelle de chaque source.
3. Vérifier qu'aucun secret prod ne fuit en staging.
4. Charger 50-100 URLs en parallèle pour vérifier le scaling SQS / Lambda.
5. Vérifier RevenueCat sandbox → backend webhook en staging.

### Phase 10 — Pré-lancement (jour 10+)

0. **Rebrand mobile placeholder name** (cf. task-186) — l'app utilise actuellement le nom legacy `Media Summarizer` partout (display name, slug Expo, scheme deep link, share extension iOS). À exécuter **avant** la sous-étape 1 ci-dessous : tous les textes Apple App Store Connect (App Information, screenshots) et Google Play Console + Google OAuth Branding consomment le nom marketing définitif. Coût ~30 min en pré-distribution, beaucoup plus élevé une fois publié. Ne touche pas le bundle id `com.secondbrainlabs.core` (figé). Voir `task-186` pour la checklist exacte des 8-9 endroits à mettre à jour.

0bis. **Couper l'API du custom domain `api.secondbrainlabs.com`** — pendant le dev (Phase 5), l'app mobile + Apple Sign-In Service ID + `APPLE_REDIRECT_URI` côté backend tapent tous l'URL brute API Gateway `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`. En Phase 10, on bascule sur le custom domain. Étapes :
   - Créer le record DNS Cloudflare `api.secondbrainlabs.com` → CNAME vers le `target_domain_name` que Terraform sortira après set de `api_custom_domain` + `api_zone_id` dans `terraform.tfvars`.
   - Provisionner le certificat ACM us-east-1 (requis pour API Gateway custom domain) — ajouter le bloc `aws_acm_certificate` dans `infrastructure/terraform/lambda_api.tf`.
   - `terraform apply` puis vérifier `curl https://api.secondbrainlabs.com/api/v1/auth/apple/callback` → HTTP 302.
   - **Apple Developer Portal** → Identifiers → Service IDs → `com.secondbrainlabs.core.signinwithapple` → Configure → ajouter Domain `secondbrainlabs.com` (déjà présent) et Return URL `https://api.secondbrainlabs.com/api/v1/auth/apple/callback` (déjà présent), **retirer** les entrées `jji077bi8e.execute-api.*` ajoutées en Phase 5.
   - **AWS Secrets Manager** → mettre à jour `APPLE_REDIRECT_URI` vers `https://api.secondbrainlabs.com/api/v1/auth/apple/callback`.
   - **`mobile/eas.json`** → profile `development` et `preview` : `EXPO_PUBLIC_API_BASE_URL` repasse à `https://api.secondbrainlabs.com`. Profile `production` est déjà sur le custom domain.
   - Rebuild EAS dev + preview pour propager la nouvelle URL aux binaires.

1. **Apple App Store Connect** (appstoreconnect.apple.com) :
   - **App Information** : nom marketing affiché aux users (à figer en Phase 10 ; ≠ Bundle ID `com.secondbrainlabs.core`), sous-titre (30 chars max), catégorie primaire/secondaire, contact info, copyright. C'est l'équivalent Apple du "Branding" Google OAuth.
   - **Pricing & Availability** : free vs paid, pays/régions, App Store distribution.
   - **App Privacy** : remplir le questionnaire détaillé sur les données collectées + leur usage. Apple est strict — toute imprécision peut entraîner un rejet ou un retrait post-launch.
   - **App Review Information** : compte de démo (login + password) pour le reviewer Apple, notes éventuelles, contact.
   - **Version 1.0** : screenshots (5 par device-size requis : 6.9", 6.5", iPad), description (4000 chars), promotional text, mots-clés (100 chars), URL support, URL marketing, URL politique de confidentialité publiquement hébergée.
   - **Build** : sélectionner la build TestFlight déjà uploadée + validée.
   - **Soumettre pour review** (1-3 jours, parfois plus).
2. **Google Play Store** :
   - Play Console : assets, description, classification, politique de confidentialité.
   - Closed Testing → Open Testing → Production rollout.
3. **Google Auth Platform (OAuth consent screen → Audience)** :
   - Vérifier le **Branding** : App name = nom marketing (ex. `Second Brain`, **pas** le nom interne du projet GCP), logo, support email, developer contact email.
   - Confirmer que les **scopes** demandés sont uniquement `openid`, `email`, `profile` (non-sensitive). Si d'autres scopes sont ajoutés (Drive, Gmail, etc.), prévoir 4-6 semaines de **vérification Google** + politique de confidentialité publique + vidéo de démo.
   - Section **État de la publication** : cliquer **« Publier l'application »** pour passer de `Test` (limité aux 100 utilisateurs whitelistés) à `Production` (n'importe qui peut se connecter avec Google).
   - Pour les scopes basiques (notre cas), la publication est immédiate sans validation Google supplémentaire — un avertissement "App non vérifiée" peut apparaître initialement chez certains users, à monitorer.
4. **Légal** :
   - Politique de confidentialité hébergée publiquement.
   - CGU avec mention RevenueCat / abonnements.
   - Conformité RGPD : droit à l'oubli, export des données.
5. **Site landing minimal** (optionnel) : `<your-domain>` avec CTA App Store / Play Store.
6. **Soft launch** : un seul pays, 100 users, observer 1 semaine avant rollout global.

---

## 5. Ce qui reste **bloqué** sur des credentials externes

Une fois ces inscriptions faites, plus aucun blocage code :

- [x] AWS account + IAM admin user `second-brain-app-admin` (AdministratorAccess) + alarme billing $50/mois (us-east-1) configurée
- [x] Apple Developer Program payé ($99) au 2026-06-01, validé par Apple
- [x] **Apple Sign in with Apple Service ID + Key (.p8) + App ID + Team ID + Key ID** provisionnés au 2026-06-08 (cf. Phase 2.8) — toutes les vars Apple dans `.env` renseignées : `APPLE_CLIENT_ID` (Service ID), `APPLE_PRIVATE_KEY` (PEM single-line), `APPLE_REDIRECT_URI` prod, `APPLE_TEAM_ID`, `APPLE_KEY_ID`.
- [ ] Google Play Console **payé ($25) au 2026-06-01, KYC en cours** (vérification d'identité quelques jours)
- [x] Google Cloud Console : projet `media-summarizer` créé, OAuth consent screen configuré (Branding `Second Brain`, External, scopes openid+email+profile), mode Test avec utilisateur test ajouté, **2 OAuth Client IDs créés (Web backend + iOS)** — `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` dans `.env` racine ; `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB` + `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS` dans `mobile/.env` (naming aligné avec `mobile/app.config.ts`, corrigé 2026-06-08)
- [ ] Google Cloud Console **Android OAuth Client ID** à créer en Phase 5 après `eas build:configure` (SHA-1 keystore EAS requis) → `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`
- [ ] Google Cloud Console **publication OAuth (Test → Production)** à faire en Phase 10 juste avant le lancement
- [x] X Developer App approuvée + bearer token (en local dans `.env`)
- [x] Apify API token + 3 actor IDs (Reel + Post + Comment Scrapers) obtenus — en local dans `.env`
- [x] LlamaParse API key obtenue (free tier 1000 pages/jour) — en local dans `.env`
- [x] Unstructured.io API key obtenue (15 000 pages gratuites au démarrage) — en local dans `.env`
- [x] PodcastIndex API key + secret obtenus (en local dans `.env`)
- [x] OpenAI API key + budget configuré (en local dans `.env`)
- [x] Deepgram API key + budget configuré (en local dans `.env`)
- [x] Algolia App créée + index configuré (App ID + Admin API key + index name en local dans `.env`)
- [~] RevenueCat — **partiellement provisionné au 2026-06-08** : projet `Second Brain Labs` créé, app iOS configurée (Bundle ID `com.secondbrainlabs.core` + In-App Purchase Key `.p8` + Key ID + Issuer ID), Public iOS API key `appl_...` renseignée dans `mobile/.env` comme `EXPO_PUBLIC_REVENUCAT_APPLE_KEY`, **Secret API key backend `sk_...` créée** (scopes least-privilege : Customers/Subscriptions/Purchases `read` + Entitlements `read`) → `REVENUCAT_API_KEY` + `REVENUCAT_PROJECT_ID` renseignés dans `.env` racine. **Restent à faire** : (a) configurer le **webhook** maintenant que l'API est déployée Phase 3 (URL `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com/api/webhooks/revenucat`) → `REVENUCAT_WEBHOOK_SECRET` ; (b) créer **3 produits IAP iOS** dans App Store Connect (Phase 6) : `com.secondbrainlabs.core.text_only_monthly`, `.mix_monthly`, `.audio_heavy_monthly` ; (c) importer les produits dans RC + créer **Entitlements + Offerings** ; (d) app Android RC + 3 produits Android (différé)
- [x] Pricing admin secret généré au 2026-06-08 (`PRICING_ADMIN_SECRET` en local dans `.env`, requis pour `PUT /api/pricing/admin`)

---

## 6. Risques connus

| Risque | Mitigation |
|---|---|
| Apple rejette l'app car Google login présent sans Sign in with Apple | Sign in with Apple câblé côté mobile. À vérifier sur build TestFlight avant soumission. |
| Quota Deepgram explosé par un user TikTok abusif | Rate limiter TikTok 2-tier déjà en place + quotas par user dans `minute_buckets`. |
| Apify API down | Instagram fail visible (status `failed`), pas de cascade. Surveiller en CloudWatch. Apify team fixes scrapers within 24-72h typically. |
| Quota LlamaParse free tier (1000 pages/jour) dépassé | Fallback Unstructured automatique dans le worker `document_parsing`. Si Unstructured aussi épuisé : job `failed` avec message clair, surveiller en CloudWatch. |
| RevenueCat webhook drop | Réconciliation possible via `GET /api/entitlements/status` qui requête RevenueCat directement. |
| URL X privée / supprimée | Worker X retourne `failed` proprement, message d'erreur à l'utilisateur. |

---

## Appendice A — Commandes utiles

```bash
# Build mobile dev
cd mobile && npx expo prebuild
eas build --platform ios --profile development

# Build mobile preview (TestFlight / Internal)
npm run build:ios:preview
npm run build:android:preview

# Run API + workers en local contre l'env AWS dev (cf. Phase 4)
uvicorn media_summarizer.api.main:app --reload
# (lancer chaque worker dans un terminal séparé selon la doc backend)

# Lint & type checks
ruff check .
mypy media_summarizer
cd mobile && npm run typecheck && npm run lint

# Apply infra (depuis infrastructure/terraform/)
terraform plan
terraform apply
```

## Appendice B — Liens internes

- `AGENTS.md` — guardrails projet
- `CLAUDE.md` — convention de création de tâches
- `.env.example` — gabarit complet des variables (18 sections numérotées)
- `infrastructure/terraform/README.md` — runbook Secrets Manager + Lambda deployment
- `infrastructure/terraform/secrets.tf` — secret consolidé `media-summarizer-runtime-<env>`
- `infrastructure/terraform/terraform.tfvars.example` — modèle `secret_payload` à recopier
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` — détails techniques mobile
- `docs/PRODUCTION_RELEASE_RUNBOOK.md` — procédure de release
- `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` — pipeline d'ingestion
- `infrastructure/terraform/` — provisioning AWS
