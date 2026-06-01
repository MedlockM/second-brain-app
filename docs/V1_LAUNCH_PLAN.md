# V1 Launch Plan — Media Summarizer

> Plan exhaustif des étapes restantes pour mettre l'application en production.
> Date de rédaction : 2026-05-19. Dernière mise à jour : 2026-06-01.

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
| **Sign in with Apple** | Code OK — backend + mobile câblés. Obligatoire App Store car Google login présent | Toute la chaîne Apple Developer à provisionner : Service ID, Sign in with Apple Key (.p8), Team ID, Key ID, Return URL prod |
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
| **Expo / EAS** | gratuit (free tier) | Builds iOS/Android | À créer |
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
AWS_DEFAULT_REGION=eu-west-3       # ou us-east-1, à figer
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
APPLE_CLIENT_ID=...                    # Service ID (ex: com.yourdomain.app.signinwithapple)
APPLE_REDIRECT_URI=https://api.<your-domain>/api/v1/auth/apple/callback
```

Côté mobile (`mobile/.env` ou EAS secrets) :

```bash
# Google OAuth client IDs créés dans Google Cloud Console
EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=...
EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID=...
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=...   # même valeur que GOOGLE_CLIENT_ID côté backend
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
APIFY_API_TOKEN=...
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

Côté mobile (`mobile/.env` ou EAS secrets) :

```bash
REVENUECAT_IOS_API_KEY=appl_...      # public key iOS
REVENUECAT_ANDROID_API_KEY=goog_...  # public key Android
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
4. Expo / EAS account + lien vers le repo.
5. RevenueCat account + projet + apps iOS/Android (clés générées).
6. Comptes API tiers : tous configurés au 2026-06-01 (clés présentes dans `.env`) — **OpenAI**, **Deepgram**, **PodcastIndex.org**, **X Developer Platform**, **Apify**, **LlamaParse**, **Unstructured.io**, **Algolia**. **Google OAuth backend** également déjà provisionné (`GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` en local dans `.env`). **Apple OAuth backend NON provisionné** : `.env` ne contient que des placeholders du template (`APPLE_CLIENT_ID` placeholder, `APPLE_PRIVATE_KEY` placeholder, `APPLE_REDIRECT_URI` URL localhost de dev) ; `APPLE_TEAM_ID` + `APPLE_KEY_ID` vides. Restent à provisionner : **toute la chaîne Apple Developer** (Service ID `APPLE_CLIENT_ID`, Sign in with Apple Key `.p8` → `APPLE_PRIVATE_KEY`, Team ID, Key ID, Return URL prod `APPLE_REDIRECT_URI`), **3 OAuth Client IDs publics** (iOS, Android, Web Expo) + écran de consentement publié côté **Google Cloud Console**, **RevenueCat** (projet + 3 produits + webhook), `PRICING_ADMIN_SECRET` (à générer localement avec `openssl rand -hex 32`).
7. **Google Cloud Console** : créer un projet, activer l'écran de consentement OAuth (External, scopes openid + email + profile), créer **3 OAuth Client IDs** : iOS (avec bundle id), Android (avec SHA-1 du keystore EAS), Web (utilisé par le backend pour vérifier le `aud` du id_token).
8. **Apple Developer** : créer un **Sign in with Apple Service ID** (ex: `com.yourdomain.app.signinwithapple`), créer une **Sign in with Apple Key** (récupérer le `.p8` private key + Key ID), récupérer le Team ID, configurer le Return URL pour le backend.

### Phase 3 — Infrastructure AWS (jour 2-3)

1. `cp infrastructure/terraform/terraform.tfvars.example infrastructure/terraform/terraform.tfvars` puis remplir : `environment`, **et tout `secret_payload`** (modèle complet dans le fichier example, voir `infrastructure/terraform/README.md`).
2. `terraform init && terraform plan` sur l'environnement dev.
3. `terraform apply` → DynamoDB tables, S3 buckets, SQS queues, Lambda functions (workers + API), API Gateway HTTP API, ECR repository, **secret consolidé `media-summarizer-runtime-<env>`** créé par `secrets.tf`.
4. Build and push the Lambda container image: `docker build -f infrastructure/docker/lambda.Dockerfile -t <ecr-url>:worker-latest . && docker push`. Tag as `api-latest` as well (same image, different CMD).
5. Vérifier que `aws_secretsmanager_secret.runtime` contient bien toutes les clés (Console AWS → Secrets Manager). Le `lifecycle { ignore_changes }` permet une rotation manuelle ultérieure sans replan.
6. Confirmer que l'IAM policies `lambda-worker-policy` et `lambda-api-policy` sont attachées aux Lambda execution roles.
7. Vérifier que les queues SQS DLQ sont câblées et que chaque queue a un event source mapping vers sa Lambda.

### Phase 4 — Tests d'intégration contre AWS dev (jour 3-4)

> **Décision 2026-05-28** : on n'utilise pas LocalStack en V1. Pour un projet solo,
> les coûts AWS dev (DynamoDB on-demand + S3 + SQS + Lambda) sont négligeables
> face aux coûts variables OpenAI/Deepgram/LlamaParse qui sont identiques local
> ou cloud, et LocalStack introduit des écarts de fidélité (IAM, EventBridge,
> Secrets Manager, edge cases SQS) qui font perdre plus de temps qu'ils n'en
> économisent. On lance l'API + workers Python en local avec un `.env` pointant
> directement sur l'environnement AWS `dev`.

1. Renseigner le `.env` racine avec les credentials AWS dev (gabarit complet dans `.env.example`). `python-dotenv` le charge automatiquement à l'import via `media_summarizer/__init__.py` ; en prod les vraies env vars priment (`override=False`).
2. Lancer l'API et les workers Python en local (hot-reload), pointant sur les vraies ressources AWS dev (DynamoDB, S3, SQS, Secrets Manager).
3. Tester chaque source d'ingestion via `POST /api/media/ingest` :
   - URL article → vérifier extraction → artifacts générés
   - URL YouTube → vérifier transcript → artifacts
   - URL podcast (Apple Podcasts ou Spotify) → resolver PodcastIndex → transcript → artifacts
   - URL X (post avec vidéo) → resolver X → transcript → artifacts
   - URL TikTok → worker TikTok → subtitles natifs ou Deepgram → artifacts
   - **URL Instagram (reel)** → resolver Instagram → Deepgram → artifacts
   - **Upload PDF/DOCX/PPTX** → worker `document_parsing` → LlamaParse (primaire) ou Unstructured (fallback) → artifacts
4. Vérifier les états du job dans DynamoDB dev : `pending → resolving → transcribing → ready_for_artifacts → completed`.
5. Tester le digest journalier (EventBridge rule sur l'env dev).
6. Nettoyer périodiquement les données dev (script de purge ou TTL DynamoDB) pour éviter d'accumuler du bruit entre les sessions de test.

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

1. **Apple App Store** :
   - App Store Connect : screenshots (5 par device), description, mots-clés, politique de confidentialité.
   - Compléter le App Privacy questionnaire.
   - Soumettre pour review (1-3 jours).
2. **Google Play Store** :
   - Play Console : assets, description, classification, politique de confidentialité.
   - Closed Testing → Open Testing → Production rollout.
3. **Légal** :
   - Politique de confidentialité hébergée publiquement.
   - CGU avec mention RevenueCat / abonnements.
   - Conformité RGPD : droit à l'oubli, export des données.
4. **Site landing minimal** (optionnel) : `<your-domain>` avec CTA App Store / Play Store.
5. **Soft launch** : un seul pays, 100 users, observer 1 semaine avant rollout global.

---

## 5. Ce qui reste **bloqué** sur des credentials externes

Une fois ces inscriptions faites, plus aucun blocage code :

- [ ] Apple Developer Program activé (peut prendre 24-48h)
- [ ] **Apple Sign in with Apple Service ID + Key (.p8) générés** + Team ID, Key ID renseignés (toutes les vars Apple sont des placeholders du template dans `.env` : `APPLE_CLIENT_ID` placeholder `com.yourdomain.app.signinwithapple`, `APPLE_PRIVATE_KEY` placeholder PEM, `APPLE_REDIRECT_URI` URL localhost de dev, `APPLE_TEAM_ID` + `APPLE_KEY_ID` vides)
- [ ] Google Play Console activé (immédiat)
- [ ] **Google Cloud Console : 3 OAuth Client IDs créés (iOS, Android, Web) + écran de consentement publié** (`GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` côté backend déjà renseignés ; les 3 client IDs mobile/web restent à créer côté Google Cloud)
- [x] X Developer App approuvée + bearer token (en local dans `.env`)
- [x] Apify API token + 3 actor IDs (Reel + Post + Comment Scrapers) obtenus — en local dans `.env`
- [x] LlamaParse API key obtenue (free tier 1000 pages/jour) — en local dans `.env`
- [x] Unstructured.io API key obtenue (15 000 pages gratuites au démarrage) — en local dans `.env`
- [x] PodcastIndex API key + secret obtenus (en local dans `.env`)
- [x] OpenAI API key + budget configuré (en local dans `.env`)
- [x] Deepgram API key + budget configuré (en local dans `.env`)
- [x] Algolia App créée + index configuré (App ID + Admin API key + index name en local dans `.env`)
- [ ] RevenueCat projet + 3 produits par store + webhook configuré (`REVENUCAT_API_KEY` + `REVENUCAT_PROJECT_ID` + `REVENUCAT_WEBHOOK_SECRET` vides dans `.env`)
- [ ] Pricing admin secret généré (`PRICING_ADMIN_SECRET` vide dans `.env`, requis pour `PUT /api/pricing/admin`)

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
