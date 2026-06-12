# V1 Launch Plan — Media Summarizer

> Plan exhaustif des étapes restantes pour mettre l'application en production.
> Date de rédaction : 2026-05-19. Dernière mise à jour : 2026-06-12 (réconciliation avec le backlog local et l'état du worktree). Phase 3 AWS dev est déployée. La suite E2E Phase 4 couvre désormais toutes les sources V1 et les fallback chains critiques, mais un re-run complet contre AWS dev reste à faire après les derniers changements locaux. Phase 5 est en cours : prebuild + préparation EAS faits, builds dev iOS/Android et validations device encore à exécuter.

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
| **Instagram** | OK — Apify resolver Reel/IGTV + Post image/carousel ; Comment Scraper et legacy video-post branch supprimés (`task-173`) | — |
| Shared text | OK | — |
| **Documents (PDF/DOCX/PPTX)** | OK — LlamaParse resolver (primary) + Unstructured resolver (fallback) + document_parsing worker câblés | — |

### Méthodes d'authentification V1

| Méthode | Statut | Bloquant V1 |
|---|---|---|
| Email + password | OK (backend + mobile) | — |
| **Sign in with Apple** | Code OK — backend + mobile câblés. Obligatoire App Store car Google login présent | OK (chaîne Apple Developer complète provisionnée 2026-06-08 : Service ID, Sign in with Apple Key `.p8`, Team ID, Key ID, Return URL prod renseignés dans `.env`) |
| **Continue with Google** | Code OK — backend + mobile câblés. Backend Web client ID + secret OK dans `.env`. OAuth Web + iOS provisionnés côté Google Cloud | OAuth Client ID Android à créer après le premier build EAS Android + écran de consentement Google à publier en Production en Phase 10 |

---

## 1. Tâches restantes réellement bloquantes V1

Le backend V1 et le scope produit principal sont implémentés côté code. Les tâches restantes sont majoritairement des gates de release, des validations sur device, des credentials externes et de la préparation stores.

### Bloquants release immédiats

| Zone | Tâches | Statut |
|---|---|---|
| Mobile dev builds | `task-161`, `task-162` | À faire manuellement par l'owner : EAS build iOS + Android development clients |
| Google OAuth Android | `task-163` | À faire après `task-162`, car le SHA-1 du keystore EAS est requis |
| Validation device non automatisable | `task-164`, `task-165` | À faire sur devices physiques : Apple Sign-In, Google sheet, Safari/Chrome share |
| Maestro V1 | `task-168`, `task-169`, `task-170`, `task-171`, `task-172` | Compléter login/register, search, paywall, run complet local, puis PR check |
| Clôture Phase 5 | `task-166` | Mettre ce plan à jour une fois `task-164/165/171/172` terminées |

### Bloquants pré-soumission stores

| Zone | Tâches | Statut |
|---|---|---|
| Branding app | `task-186` | Nom marketing final requis avant App Store Connect / Play Console |
| App icons | `task-180` | Remplacer les placeholders avant soumission |
| RevenueCat / IAP | Phase 6 | Produits IAP, entitlements/offering, webhook secret et tests sandbox restent à finaliser |
| Store/legal | Phase 10 | Privacy policy, CGU, store listings, screenshots, review accounts, rollout |

### À clarifier avant de les intégrer à V1

| Zone | Tâches | Décision requise |
|---|---|---|
| Langue de lecture + traduction transcript | `task-189`, `task-190`, `task-191`, `task-192` | Créées le 2026-06-11, pas encore intégrées au présent launch plan comme blockers V1. Décider explicitement : V1 ou post-V1. |
| Discord community/support | `task-118` | Utile pour soft launch, non bloquant code. |
| TikTok proxy résidentiel | `task-145` | V2, explicitement non bloquant V1. |

---

## 2. Comptes et abonnements à créer

| Service | Coût | Pourquoi | Statut |
|---|---|---|---|
| **GitHub** (compte + repo privé) | gratuit | Versioning, CI/CD, releases | OK (`MedlockM/second-brain-app`, privé, créé 2026-05-27) |
| **AWS** (compte) | usage-based | DynamoDB, S3, SQS, Lambda, EventBridge | OK (compte + IAM admin + billing alarm $50/mois configurés ; infra dev déployée en Phase 3) |
| **Apple Developer Program** | $99/an | Publication App Store, TestFlight, IAP sandbox | OK (payé 2026-06-01, validé par Apple ; App ID + Sign in with Apple provisionnés) |
| **Google Play Console** | $25 one-time | Publication Play Store, Internal Testing, IAP sandbox | Payé 2026-06-01, KYC en cours |
| **Expo / EAS** | gratuit (free tier) | Builds iOS/Android | OK (compte créé 2026-06-10, `eas-cli` installé localement, `eas whoami` validé) |
| **RevenueCat** | gratuit < $10k MTR | Cross-platform IAP backend | Partiel : projet + app iOS + public iOS key + secret backend OK ; webhook, produits IAP, offerings/entitlements et app Android restent à finaliser |
| **Google Cloud Console** (OAuth) | gratuit | Sign in with Google : OAuth Client IDs (iOS, Android, Web) + écran de consentement OAuth | Partiel : projet + consent screen Test + OAuth Web backend + OAuth iOS OK ; OAuth Android et publication Production restent à faire |
| **OpenAI** | usage-based | Génération artifacts (summary/notes/flashcards) | OK (compte créé, clé en local dans `.env`) |
| **Deepgram** | usage-based | Transcription audio | OK (compte créé, clé en local dans `.env`) |
| **Algolia** | gratuit < 10k records | Search lexical | OK (App ID + Admin API key + index name en local dans `.env`) |
| **PodcastIndex.org** | gratuit | Resolver podcasts | OK (compte créé, clé+secret en local dans `.env`) |
| **Apify** | usage-based / API token | Resolver Instagram (Reel + Post) + fallback YouTube/TikTok selon source | OK (tokens/actor IDs en local dans `.env`) |
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
2. **GitHub Actions versionnés** : `.github/workflows/pr.yml`, `main.yml`, `deploy-lambda.yml`, `mobile-build-distribute.yml`, `mobile-store-promote.yml`, `mobile-e2e-maestro.yml`.
3. **À vérifier après push** : le worktree local `main` est très en avance sur `origin/main` au 2026-06-12 (`ahead 222`) et contient encore des changements non committés. Les derniers runs GitHub visibles datent du 2026-05-27 et échouent ; ils ne reflètent pas l'état local actuel.
4. **Branch protection** : à activer/valider après synchronisation GitHub. L'API GitHub retourne `HTTP 403` sur la lecture de branch protection du repo privé avec le plan actuel (`Upgrade to GitHub Pro or make this repository public`), donc ce gate n'est pas prouvé.
5. Bascule du worktree de dev local vers le nouveau `origin` faite ; prochaine étape : nettoyer/committer les changements locaux puis pousser.

### Phase 2 — Comptes externes (jour 1-2)

1. ~~Apple Developer Program.~~ **Fait** : payé 2026-06-01, validé par Apple ; App ID + Sign in with Apple provisionnés.
2. Google Play Console : payé 2026-06-01, **KYC en cours**.
3. ~~AWS account + IAM admin user + facturation alarms.~~ **Fait** : compte AWS, IAM admin `second-brain-app-admin` et billing alarm $50/mois configurés.
4. ~~Expo / EAS account + lien vers le repo.~~ **Fait** : compte Expo créé 2026-06-10, `eas-cli` installé, `eas whoami` validé. `expo.projectId` est présent dans `mobile/app.config.ts`.
5. RevenueCat account + projet + app iOS + clés backend/iOS : **partiellement fait**. Restent : webhook, produits IAP, offerings/entitlements, app Android.
6. Comptes API tiers : tous configurés au 2026-06-01 (clés présentes dans `.env`) — **OpenAI**, **Deepgram**, **PodcastIndex.org**, **X Developer Platform**, **Apify**, **LlamaParse**, **Unstructured.io**, **Algolia**. **Google OAuth backend** également déjà provisionné (`GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` en local dans `.env`). **Apple OAuth backend OK au 2026-06-08** : chaîne complète provisionnée — `APPLE_CLIENT_ID` (Service ID), `APPLE_PRIVATE_KEY` (`.p8` PEM single-line), `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_REDIRECT_URI` prod renseignés dans `.env`. **`PRICING_ADMIN_SECRET` généré au 2026-06-08** (`openssl rand -hex 32`, en local dans `.env`). Restent à provisionner : **Android OAuth Client ID** (à différer en Phase 5 après le build Android EAS) + **publication écran de consentement Test → Production** côté **Google Cloud Console** (Phase 10), **RevenueCat webhook + produits IAP + offerings/entitlements + app Android**.
7. **Google Cloud Console** (console.cloud.google.com) :
   - ~~Créer un projet~~ **Fait** : projet `media-summarizer` créé. Le nom du projet est un identifiant interne, peu visible aux users.
   - ~~**APIs & Services → OAuth consent screen (Audience)**~~ **Fait** : Type **External**, scopes `openid`, `email`, `profile` uniquement.
   - ~~**OAuth consent screen → Branding**~~ **Fait** : Branding `Second Brain`, support email, developer contact email.
   - ~~**Audience Test + utilisateur test**~~ **Fait** : mode Test configuré avec utilisateur test. La publication en `Production` est faite plus tard, en Phase 10.
   - **APIs & Services → Credentials → 3 OAuth Client IDs** :
     - ~~**Web**~~ **Fait** : utilisé par le backend pour vérifier l'`aud` du id_token, et réutilisé côté mobile via `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`.
     - ~~**iOS**~~ **Fait** : avec bundle id du `mobile/app.config.ts` → `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`.
     - **Android** (avec package name + SHA-1 du keystore EAS) → `EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID`. **À faire en Phase 5** après le premier build Android EAS, quand le SHA-1 keystore est connu.
8. **Apple Developer Portal** (developer.apple.com → Certificates, Identifiers & Profiles) :
   - **Bundle ID figé : `com.secondbrainlabs.core`** (décidé 2026-06-07, propagé dans `mobile/app.config.ts`, `mobile/plugins/withShareExtension.js`, `mobile/ios-share-extension/`, RevenueCat product IDs). Identique côté Apple (App ID + Service ID radical) et Google Play (package name) pour la cohérence cross-platform et les liens universels.
   - ~~**Identifiers → App IDs**~~ **Fait** : App ID `com.secondbrainlabs.core` créé, capability "Sign in with Apple" activée.
   - ~~**Identifiers → Services IDs**~~ **Fait** : Service ID `com.secondbrainlabs.core.signinwithapple` créé et return URL backend configurée.
   - ~~**Keys → Sign in with Apple Key**~~ **Fait** : clé `.p8` générée, `APPLE_PRIVATE_KEY`, `APPLE_KEY_ID`, `APPLE_TEAM_ID` renseignés.
   - ~~**Membership**~~ **Fait** : Team ID récupéré.

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

### Phase 4 — Tests d'intégration contre AWS dev (jour 3-4) — **SUITE ÉTENDUE 2026-06-12, RE-RUN COMPLET REQUIS**

> **Décision 2026-05-28 puis 2026-06-09** : pas de LocalStack (purgé via task-130). Tests E2E directement contre l'API Gateway dev.
>
> **Évolution 2026-06-09 → 2026-06-12** : on n'utilise plus uvicorn local pour les tests d'intégration. L'API + les workers tournent en Lambda sur AWS dev (Phase 3) ; on tape directement l'API Gateway via une suite pytest E2E versionnée (`tests/e2e/`). Les tests qui étaient des skeletons skipped au 2026-06-09 sont maintenant activés en `@pytest.mark.e2e` pour toutes les sources V1 déclarées.

#### Suite E2E pytest (`tests/e2e/`)

- `pytest -m e2e` lance toute la suite contre `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com` (override via `API_BASE_URL`).
- `tests/e2e/conftest.py` crée un user de test (email horodaté `e2e-test-<ts>-<uuid>@test.local`) au début de session, ingère un article Wikipedia partagé pour les tests d'artifacts, supprime tout en teardown (user + auth_tokens + processing_jobs + artifacts + tags + folders).
- Marqueur `@pytest.mark.e2e` ; suite skipped par défaut (`pytest` sans `-m` lance uniquement les unit tests).
- Détails et runbook : `tests/e2e/README.md`.

#### Statut par source au 2026-06-12

| Source | Statut E2E | Référence |
|---|---|---|
| Health check API | ✅ passing | `tests/e2e/test_health.py` |
| **Article web** (Wikipedia) | ✅ passing en 15s | `test_phase4_ingestion.py::test_article_reaches_completed` |
| **Artifacts on-demand** : summary, notes, flashcards, quiz | ✅ tous les 4 passing en ~5s chacun | `test_phase4_ingestion.py::test_artifact_*_e2e` |
| **YouTube** (Apify) | ✅ passing depuis task-132 (2026-06-09) | `test_phase4_other_sources.py::test_youtube_ingestion` |
| Podcast direct audio URL | Test actif, non skipped ; re-run complet requis après derniers changements locaux | `test_phase4_other_sources.py::test_podcast_via_direct_audio_url` |
| Podcast via PodcastIndex / Apple Podcasts URL | Test actif, non skipped ; fixes `task-138`, `task-148`, `task-155`, `task-157` terminés | `test_phase4_other_sources.py::test_podcast_via_podcastindex` |
| X (Twitter) | Test actif, non skipped ; worker/API token configurés | `test_phase4_other_sources.py::test_x_ingestion` |
| TikTok happy path | Test actif, non skipped ; yt-dlp captions + fallback Apify V1 en place | `test_phase4_other_sources.py::test_tiktok_ingestion` |
| Instagram | Test actif, non skipped ; Apify resolver migré et corrigé | `test_phase4_other_sources.py::test_instagram_ingestion` |
| Document upload (PDF/DOCX/PPTX) | Test actif, non skipped ; endpoint multipart `/api/media/upload` + LlamaParse primary | `test_phase4_other_sources.py::test_document_upload` |

#### Fallback chains E2E au 2026-06-12

| Fallback | Statut | Référence |
|---|---|---|
| TikTok yt-dlp IP-block → Apify | Test actif avec sentinel per-request `__e2e_force_ip_block__=1`; `task-185` reste à réconcilier dans le backlog car le code/test semblent déjà présents | `tests/e2e/test_fallback_chains.py::test_tiktok_apify_fallback` |
| Instagram IP-block forcé → Apify Reel Scraper | Test actif avec sentinel per-request | `tests/e2e/test_fallback_chains.py::test_instagram_apify_fallback` |
| Document LlamaParse failure → Unstructured | Test actif avec sentinel filename | `tests/e2e/test_fallback_chains.py::test_document_unstructured_fallback` |
| Deepgram pull→push automatique | Supprimé du scope E2E après `task-158` : les producteurs déclarent explicitement leur mode Deepgram | Commentaire en fin de `tests/e2e/test_fallback_chains.py` |

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
- **task-133** — Fix 4 bugs bloquant la complétion Phase 4 : TikTok `mark_extracting`, import circulaire document, fixture podcast, transcript Instagram vide ✅
- **task-134** — Fix TikTok worker : `ProcessingJob.episode_url` inexistant ✅
- **task-135** — Provision queue Instagram manquante en Terraform ✅
- **task-136** — Fix Algolia API key corrompue par commentaire trailing dans Secrets Manager ✅
- **task-137** — Fix Deepgram worker : floats → Decimal pour DynamoDB ✅
- **task-138** — Fix `/api/v1/podcasts/submit` : classification plateforme au lieu de `source_platform=rss` hardcodé ✅
- **task-139** — Fix fallback Deepgram sur CDN URLs bloquées par politiques IP source ✅
- **task-140** — Benchmark TikTok extraction strategies given Lambda IP blocking ✅
- **task-141** — Audit workers + application du fix `mark_extracting`/`episode_url` à Instagram ✅
- **task-142** — Endpoint et pipeline upload audio direct MP3/M4A/WAV ✅
- **task-143** — Fix mismatch queue `EPISODE_COMPLETION_EVENTS_QUEUE` vs `EPISODE_COMPLETED_EVENTS_QUEUE` ✅
- **task-144** — Ajout fallback Apify TikTok V1 ✅
- **task-146** — Migration Instagram vers `InstagramApifyResolver` existant ✅
- **task-147** — Fix `media_completed_events` : event type `episode_completion_status` ignoré ✅
- **task-148** — Fix PodcastIndex resolver : Apple Podcasts URL rejetée après task-138 ✅
- **task-149** — E2E TikTok yt-dlp → Apify fallback ✅
- **task-150** — E2E Instagram Apify → Deepgram fallback ✅
- **task-151** — E2E document LlamaParse → Unstructured fallback ✅
- **task-152** — E2E Deepgram pull→push fallback, ensuite retiré/ajusté par `task-158` ✅
- **task-153** — Fix Instagram Apify resolver : `APIFY_INSTAGRAM_API_TOKEN` manquant ✅
- **task-154** — Provision table `media_watchers` manquante ✅
- **task-155** — Fix PodcastIndex credentials non chargés par Lambda ✅
- **task-156** — Fix Instagram Apify input field `directUrls` ✅
- **task-157** — Fix matching Apple Podcasts `?i=` vers épisodes PodcastIndex ✅
- **task-158** — Deepgram mode explicite par producer/worker ✅
- **task-167** — Mise à jour des fallback-chain E2E après refactor Deepgram mode ✅
- **task-173** — Simplification Instagram : suppression Comment Scraper + legacy video-post branch ✅
- **task-176** — Podcasting 2.0 transcript short-circuit reconnecté ✅
- **task-177** — YouTube fallback chain alignée sur TikTok : yt-dlp → Apify → Deepgram ✅
- **task-178** — Fallback Deepgram sur media URL résolue par Apify pour TikTok ✅
- **task-179** — Documentation providers/fallback chains mise à jour ✅

#### Reste à faire

1. **Re-run complet AWS dev** : `pytest -m e2e` contre `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com` après push/déploiement des derniers changements locaux. Ne pas marquer Phase 4 DONE tant que ce run n'est pas vert.
2. **Tester le digest journalier** (EventBridge rule). Pas couvert par l'E2E actuelle.
3. **Mettre en place une purge automatique** des artifacts E2E orphelins en cas de crash pytest non-recoverable (Ctrl-C). Aujourd'hui le teardown manque ce cas — script de cleanup à ajouter dans `scripts/`.
4. **Réconcilier le backlog** : `task-185` est encore `To Do` alors que le sentinel TikTok apparaît déjà dans le worker et le test E2E. À vérifier puis fermer ou rouvrir proprement selon le résultat du re-run.

### Phase 5 — Mobile dev build (jour 4-5) — **EN COURS 2026-06-12**

#### Fait

1. ✅ `task-159` — `scripts/mobile_release_check.sh` ajouté pour valider les prérequis EAS.
2. ✅ `task-160` — `cd mobile && npx expo prebuild` exécuté ; les dossiers natifs iOS/Android existent.
3. ✅ `task-181` — Expo SDK 52 → 55 + `expo-share-intent` 6.x.
4. ✅ `task-187` — Share intent refactoré vers l'API officielle `expo-share-intent` v6.
5. ✅ `task-188` — Fix cold-start race `expo-share-intent` v6 + suppression de la config custom dupliquée.

#### À faire

1. `task-161` — `eas build --platform ios --profile development` (manuel owner-only, 2FA Apple/EAS).
2. `task-162` — `eas build --platform android --profile development` + récupération du SHA-1 keystore EAS (manuel owner-only).
3. `task-163` — créer l'OAuth Client ID Android dans Google Cloud Console avec `package=com.secondbrainlabs.core` + SHA-1 EAS.
4. `task-164` — validation iOS sur device physique :
   - Sign in with Apple → user créé/lié → inbox.
   - Continue with Google → `ASWebAuthenticationSession` → user créé/lié → inbox.
   - Share intent Safari → share-confirm → submit → vignette inbox.
5. `task-165` — validation Android sur device physique :
   - Continue with Google sans `DEVELOPER_ERROR`.
   - Apple button absent ou no-op clean.
   - Share intent Chrome URL.
   - Share intent texte/audio.
6. `task-168` — étendre Maestro login/register email/password.
7. `task-169` — ajouter Maestro search Algolia.
8. `task-170` — ajouter Maestro paywall (affichage des 3 tiers RevenueCat, sans achat).
9. `task-171` — run complet Maestro local iOS + Android, itérer jusqu'au vert.
10. `task-172` — brancher Maestro Android comme PR check obligatoire sur `mobile/**`, documenter le lancement local.
11. `task-166` — marquer Phase 5 DONE dans ce plan une fois les tâches ci-dessus closes.

### Phase 6 — Tests IAP sandbox (jour 5-6)

> Le code RevenueCat mobile/backend est implémenté (`task-99`) : SDK mobile, paywall, endpoint `POST /api/webhooks/revenucat`, table `revenucat_events`, endpoint entitlements. Ce qui reste en Phase 6 est le setup dashboard/stores et la validation sandbox réelle.

1. **iOS** :
   - App Store Connect → Apps → IAP → créer 3 produits (correspondance Offerings RevenueCat).
   - StoreKit configuration locale (`mobile/ios/StoreKit.storekit`) pour Xcode simulator — fichier non présent au 2026-06-12.
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

1. ✅ Workflows versionnés :
   - `.github/workflows/pr.yml` — backend `ruff`/`mypy`, mobile `typecheck`/`lint`.
   - `.github/workflows/main.yml` — checks sur push `main`.
   - `.github/workflows/deploy-lambda.yml` — build/push image Lambda + update functions.
   - `.github/workflows/mobile-build-distribute.yml` — EAS build/submit.
   - `.github/workflows/mobile-store-promote.yml` — promotion stores.
   - `.github/workflows/mobile-e2e-maestro.yml` — Maestro Android/iOS.
2. À faire : pousser le HEAD local actuel vers GitHub. Tant que `main` local est `ahead 222` de `origin/main`, les runs GitHub ne prouvent rien sur l'état courant.
3. À faire : configurer les GitHub repo secrets nécessaires (`AWS_DEPLOY_ROLE_ARN`, `EXPO_TOKEN`, Apple/App Store Connect, Google Play service account, RevenueCat si utilisé dans CI, E2E test user/API base URL).
4. À faire : activer/valider branch protection sur `main` avec checks requis. L'accès branch protection est bloqué par le plan GitHub actuel sur repo privé, sauf upgrade GitHub Pro ou repo public.
5. À faire : vérifier rollback Lambda (retag image précédente ECR + update Lambda) et documenter l'exercice.

### Phase 8 — Monitoring & observabilité (jour 7-8)

> Le provisioning Terraform de dashboard/alarms a été ajouté (`task-114`, `task-46`), puis adapté à la migration Lambda. La validation restante est opérationnelle : activer les alarmes en staging/prod et vérifier les signaux CloudWatch réels.

1. CloudWatch Dashboard à vérifier avec :
   - Latence API (`API_SLOW_REQUEST_THRESHOLD_MS` → alarmes)
   - Profondeur des queues SQS (alarme si DLQ > 0, en particulier `document-parsing-queue`)
   - Taux d'erreur Deepgram / OpenAI / **LlamaParse / Unstructured** (logs structurés `parser=llamaparse|unstructured` + `error_code`)
   - Coût par source (X, TikTok, Instagram, YouTube, podcasts, **documents**)
   - Compteur quota LlamaParse (1000 pages/jour free tier) — alarme si fallback Unstructured déclenché plus de N fois/heure
2. CloudWatch Alarms → SNS → e-mail (`enable_alarms = true` en staging/prod).
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
   - Le support Terraform existe déjà dans `infrastructure/terraform/lambda_api.tf` (`api_custom_domain`, `api_zone_id`, `aws_acm_certificate`, API Gateway domain mapping, Route53 record conditionnel).
   - Renseigner `api_custom_domain = "api.secondbrainlabs.com"` et `api_zone_id` dans `terraform.tfvars`, puis `terraform apply`.
   - Créer/valider le DNS Cloudflare ou Route53 selon la zone réellement utilisée. Si Cloudflare reste le DNS autoritaire, créer le CNAME vers le `target_domain_name` exposé par Terraform.
   - `terraform apply` puis vérifier `curl https://api.secondbrainlabs.com/api/v1/auth/apple/callback` → HTTP 302.
   - **Apple Developer Portal** → Identifiers → Service IDs → `com.secondbrainlabs.core.signinwithapple` → Configure → ajouter Domain `secondbrainlabs.com` (déjà présent) et Return URL `https://api.secondbrainlabs.com/api/v1/auth/apple/callback` (déjà présent), **retirer** les entrées `jji077bi8e.execute-api.*` ajoutées en Phase 5.
   - **AWS Secrets Manager** → mettre à jour `APPLE_REDIRECT_URI` vers `https://api.secondbrainlabs.com/api/v1/auth/apple/callback`.
   - **`mobile/eas.json`** → profile `development` et `preview` : `EXPO_PUBLIC_API_BASE_URL` repasse à `https://api.secondbrainlabs.com`. Attention : le profile `production` pointe encore vers `https://api.mediasummarizer.com` au 2026-06-12 ; l'aligner sur le domaine choisi avant build production.
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

## 5. Ce qui reste **bloqué** sur des credentials externes / owner-only

Les comptes principaux sont largement provisionnés. Les blocages restants sont surtout liés aux stores, aux builds EAS interactifs et aux dashboards tiers.

- [x] AWS account + IAM admin user `second-brain-app-admin` (AdministratorAccess) + alarme billing $50/mois (us-east-1) configurée
- [x] Apple Developer Program payé ($99) au 2026-06-01, validé par Apple
- [x] **Apple Sign in with Apple Service ID + Key (.p8) + App ID + Team ID + Key ID** provisionnés au 2026-06-08 (cf. Phase 2.8) — toutes les vars Apple dans `.env` renseignées : `APPLE_CLIENT_ID` (Service ID), `APPLE_PRIVATE_KEY` (PEM single-line), `APPLE_REDIRECT_URI` prod, `APPLE_TEAM_ID`, `APPLE_KEY_ID`.
- [ ] Google Play Console **payé ($25) au 2026-06-01, KYC en cours** (vérification d'identité quelques jours)
- [x] Google Cloud Console : projet `media-summarizer` créé, OAuth consent screen configuré (Branding `Second Brain`, External, scopes openid+email+profile), mode Test avec utilisateur test ajouté, **2 OAuth Client IDs créés (Web backend + iOS)** — `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` dans `.env` racine ; `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB` + `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS` dans `mobile/.env` (naming aligné avec `mobile/app.config.ts`, corrigé 2026-06-08)
- [ ] Google Cloud Console **Android OAuth Client ID** à créer en Phase 5 après le premier `eas build --platform android --profile development` (SHA-1 keystore EAS requis) → `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`
- [ ] Google Cloud Console **publication OAuth (Test → Production)** à faire en Phase 10 juste avant le lancement
- [x] X Developer App approuvée + bearer token (en local dans `.env`)
- [x] Apify API tokens + actor IDs obtenus — en local dans `.env` (Instagram Reel/Post, YouTube, TikTok selon fallback chain)
- [x] LlamaParse API key obtenue (free tier 1000 pages/jour) — en local dans `.env`
- [x] Unstructured.io API key obtenue (15 000 pages gratuites au démarrage) — en local dans `.env`
- [x] PodcastIndex API key + secret obtenus (en local dans `.env`)
- [x] OpenAI API key + budget configuré (en local dans `.env`)
- [x] Deepgram API key + budget configuré (en local dans `.env`)
- [x] Algolia App créée + index configuré (App ID + Admin API key + index name en local dans `.env`)
- [~] RevenueCat — **partiellement provisionné au 2026-06-08** : projet `Second Brain Labs` créé, app iOS configurée (Bundle ID `com.secondbrainlabs.core` + In-App Purchase Key `.p8` + Key ID + Issuer ID), Public iOS API key `appl_...` renseignée dans `mobile/.env` comme `EXPO_PUBLIC_REVENUCAT_APPLE_KEY`, **Secret API key backend `sk_...` créée** (scopes least-privilege : Customers/Subscriptions/Purchases `read` + Entitlements `read`) → `REVENUCAT_API_KEY` + `REVENUCAT_PROJECT_ID` renseignés dans `.env` racine. **Restent à faire** : (a) configurer le **webhook** maintenant que l'API est déployée Phase 3 (URL `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com/api/webhooks/revenucat`) → `REVENUCAT_WEBHOOK_SECRET` ; (b) créer **3 produits IAP iOS** dans App Store Connect (Phase 6) : `com.secondbrainlabs.core.text_only_monthly`, `.mix_monthly`, `.audio_heavy_monthly` ; (c) importer les produits dans RC + créer **Entitlements + Offerings** ; (d) app Android RC + 3 produits Android (différé)
- [x] Pricing admin secret généré au 2026-06-08 (`PRICING_ADMIN_SECRET` en local dans `.env`, requis pour `PUT /api/pricing/admin`)
- [ ] EAS iOS development build : manuel owner-only (`task-161`)
- [ ] EAS Android development build + SHA-1 keystore : manuel owner-only (`task-162`)
- [ ] Nom marketing final : requis avant `task-186`, App Store Connect, Play Console et Google OAuth Branding
- [ ] Icônes finales : `task-180`, requis avant soumission stores

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
| État local non poussé sur GitHub | `main` local est en avance sur `origin/main`; avant de valider CI/CD ou préparer stores, committer/pousser puis relancer les workflows GitHub. |
| Branch protection indisponible sur repo privé avec le plan GitHub actuel | Upgrade GitHub Pro ou rendre le repo public, sinon documenter explicitement que le required-check gate est manuel avant launch. |

---

## Appendice A — Commandes utiles

```bash
# Build mobile dev
cd mobile && npx expo prebuild
eas build --platform ios --profile development

# Build mobile preview (TestFlight / Internal)
npm run build:ios:preview
npm run build:android:preview

# Run E2E contre AWS dev (Phase 4)
API_BASE_URL=https://jji077bi8e.execute-api.eu-west-3.amazonaws.com pytest -m e2e

# Lint & type checks
ruff check .
mypy media_summarizer
cd mobile && npm run typecheck && npm run lint

# Apply infra (depuis infrastructure/terraform/)
terraform plan
terraform apply

# Deploy Lambda container (GitHub Actions target; local equivalent uses the same Dockerfile/ECR)
docker buildx build --platform linux/arm64 --provenance=false --sbom=false -f infrastructure/docker/lambda.Dockerfile .
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
