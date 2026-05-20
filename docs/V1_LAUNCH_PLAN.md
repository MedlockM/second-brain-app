# V1 Launch Plan — Media Summarizer

> Plan exhaustif des étapes restantes pour mettre l'application en production.
> Date de rédaction : 2026-05-19. À mettre à jour au fil des étapes.

---

## 0. Périmètre V1 confirmé

### Sources d'ingestion supportées en V1

| Source | Statut code | Bloquant V1 |
|---|---|---|
| Articles web (lecture/extraction) | OK | — |
| YouTube (transcript natif + fallback Deepgram) | OK | — |
| Podcasts (PodcastIndex resolver) | OK | — |
| Audio file (upload direct) | OK | — |
| **X (Twitter)** | OK — worker, resolver, classifier, orchestrator câblés | Clé API à fournir |
| **TikTok** | OK — worker dédié + 2-tier rate limiter (pacing + quota horaire) | — |
| **Instagram** | **BROKEN** — resolver OK, **orchestrator manque le case `SOCIAL_VIDEO + audio_url`** → jobs stuck | **task-100** |
| Shared text | OK | — |

### Méthodes d'authentification V1

| Méthode | Statut | Bloquant V1 |
|---|---|---|
| Email + password | OK (backend + mobile) | — |
| **Sign in with Apple** | Backend OK, **mobile non câblé** | **task-101** + obligatoire pour App Store si Google login présent |
| **Continue with Google** | Backend OK, **mobile non câblé** | **task-101** |
| Magic link | Code legacy retiré (login par mot de passe préféré) | — |
| OAuth Spotify | Différé post-V1 | — |

### Hors périmètre V1 (différé)

- **Stripe** : retiré du repo (Apple/Google interdisent un PSP tiers pour les abonnements in-app). Remplacé par RevenueCat (task-99 livrée).
- **Sentry** : pas intégré. Logs CloudWatch suffisent pour V1.
- **Redis (managé)** : non requis. Les rate limiters TikTok et PodcastIndex ont un fallback local in-process. À envisager seulement si l'on passe à plusieurs workers en parallèle.
- **OAuth Spotify** : différé post-V1.
- **LinkedIn ingestion** (task-60) : différé post-V1.

---

## 1. Tâches d'implémentation restantes (backlog)

| ID | Type | Description | Priorité |
|---|---|---|---|
| ~~task-100~~ | ingestion | ~~Fix orchestrator dispatch `SOCIAL_VIDEO + audio_url` (Instagram)~~ | Done |
| **task-101** | feature/mobile/auth | Câbler Google + Sign in with Apple côté mobile (+ endpoints `/native` côté backend) | **Bloquant V1** (Apple Review 4.8) |

À dispatcher : `./scripts/dispatch_backlog.sh --max-dispatch 1`.

---

## 2. Comptes et abonnements à créer

| Service | Coût | Pourquoi | Statut |
|---|---|---|---|
| **GitHub** (compte + repo privé) | gratuit | Versioning, CI/CD, releases | À créer |
| **AWS** (compte) | usage-based | DynamoDB, S3, SQS, Lambda, EventBridge | À créer |
| **Apple Developer Program** | $99/an | Publication App Store, TestFlight, IAP sandbox | À créer |
| **Google Play Console** | $25 one-time | Publication Play Store, Internal Testing, IAP sandbox | À créer |
| **Expo / EAS** | gratuit (free tier) | Builds iOS/Android | À créer |
| **RevenueCat** | gratuit < $10k MTR | Cross-platform IAP backend | À créer |
| **Google Cloud Console** (OAuth) | gratuit | Sign in with Google : OAuth Client IDs (iOS, Android, Web) + écran de consentement OAuth | À créer |
| **OpenAI** | usage-based | Génération artifacts (summary/notes/flashcards) | À créer |
| **Deepgram** | usage-based | Transcription audio | À créer |
| **Algolia** | gratuit < 10k records | Search lexical | À créer |
| **PodcastIndex.org** | gratuit | Resolver podcasts | À créer |
| **GetInsaver** | usage-based / API key | Resolver Instagram | À créer |
| **X (Developer Platform)** | Free tier OK pour V1 | Lecture API X | À créer |
| **Provider email transactionnel** (SES, Resend, Postmark…) | usage-based | Magic link login | À choisir |

---

## 3. Variables d'environnement / Secrets à renseigner

Ranger dans **AWS Secrets Manager** (production) et `.env` (local).

### 3.1 AWS infra

```bash
AWS_REGION=eu-west-3              # ou us-east-1, à figer
AWS_ACCESS_KEY_ID=...             # clé IAM dédiée backend
AWS_SECRET_ACCESS_KEY=...
ARCHIVE_BUCKET=...
AUDIO_BUCKET=...
DOCUMENT_BUCKET=...
FLASHCARDS_BUCKET=...
# Autres buckets/tables/queues : voir terraform/
```

### 3.2 Auth

```bash
ACCESS_TOKEN_EXPIRE_HOURS=1
COOKIE_SECURE=true
COOKIE_DOMAIN=app.<your-domain>
COOKIE_SAMESITE=lax
EMAIL_FROM=noreply@<your-domain>
SMTP_HOST=...                          # ou SES/Resend
SMTP_USER=...
SMTP_PASSWORD=...

# Google OAuth (Sign in with Google)
GOOGLE_CLIENT_ID=...                   # Web client ID (utilisé côté backend pour vérifier l'audience du id_token)
GOOGLE_CLIENT_SECRET=...               # Optionnel : seulement nécessaire si on garde le flow web /google/callback
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
OPENAI_MODEL=gpt-4o-mini             # ou figé selon coût
DEEPGRAM_API_KEY=...
DEEPGRAM_MODEL=nova-2
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

# Instagram (via GetInsaver API)
GETINSAVER_API_KEY=...
GETINSAVER_TIMEOUT_SECONDS=30
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

1. Créer un repo GitHub privé `media-summarizer-project`.
2. Push de la branche `main` (et `second-brain-project` si on garde un branching).
3. Activer Branch protection sur `main` (require PR + checks).
4. Configurer GitHub Actions (CI minimal : pytest, ruff, mypy, mobile typecheck).
5. **Dispatcher task-100** pour finaliser Instagram avant la suite.

### Phase 2 — Comptes externes (jour 1-2)

1. Apple Developer Program (commande, peut prendre 24-48h).
2. Google Play Console.
3. AWS account + IAM admin user + facturation alarms.
4. Expo / EAS account + lien vers le repo.
5. RevenueCat account + projet + apps iOS/Android (clés générées).
6. Comptes API : OpenAI, Deepgram, Algolia, PodcastIndex, GetInsaver, X Developer.
7. **Google Cloud Console** : créer un projet, activer l'écran de consentement OAuth (External, scopes openid + email + profile), créer **3 OAuth Client IDs** : iOS (avec bundle id), Android (avec SHA-1 du keystore EAS), Web (utilisé par le backend pour vérifier le `aud` du id_token).
8. **Apple Developer** : créer un **Sign in with Apple Service ID** (ex: `com.yourdomain.app.signinwithapple`), créer une **Sign in with Apple Key** (récupérer le `.p8` private key + Key ID), récupérer le Team ID, configurer le Return URL pour le backend.

### Phase 3 — Infrastructure AWS (jour 2-3)

1. Renseigner les variables Terraform (`infrastructure/terraform/terraform.tfvars`).
2. `terraform init && terraform plan` sur l'environnement dev.
3. `terraform apply` → DynamoDB tables, S3 buckets, SQS queues, Lambda functions.
4. Stocker tous les secrets dans **AWS Secrets Manager**.
5. Créer un IAM role pour les workers Lambda avec accès aux ressources.
6. Vérifier que les queues SQS DLQ sont câblées.

### Phase 4 — Tests locaux (jour 3-4)

1. `docker-compose up` (LocalStack + API + workers).
2. Renseigner `.env` local avec les vraies clés API (pas les secrets AWS).
3. Tester chaque source d'ingestion via `POST /api/media/ingest` :
   - URL article → vérifier extraction → artifacts générés
   - URL YouTube → vérifier transcript → artifacts
   - URL podcast (Apple Podcasts ou Spotify) → resolver PodcastIndex → transcript → artifacts
   - URL X (post avec vidéo) → resolver X → transcript → artifacts
   - URL TikTok → worker TikTok → subtitles natifs ou Deepgram → artifacts
   - **URL Instagram (reel)** → resolver Instagram → Deepgram → artifacts (validera task-100)
4. Vérifier les états du job dans la DB : `pending → resolving → transcribing → ready_for_artifacts → completed`.
5. Tester le digest journalier (cron + EventBridge en local).

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
   - Inbox polling → media detail → artifacts
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

1. GitHub Actions : workflow PR (lint + tests + typecheck).
2. GitHub Actions : workflow main (deploy backend Lambda via Terraform ou Serverless).
3. EAS Submit pour TestFlight / Play Internal automatique sur tag `v*`.
4. Stocker AWS keys, RevenueCat keys, Expo token comme **GitHub repo secrets**.
5. Vérifier que rollback est possible (Terraform state versionné en S3).

### Phase 8 — Monitoring & observabilité (jour 7-8)

1. CloudWatch Dashboard avec :
   - Latence API (`API_SLOW_REQUEST_THRESHOLD_MS` → alarmes)
   - Profondeur des queues SQS (alarme si DLQ > 0)
   - Taux d'erreur Deepgram / OpenAI
   - Coût par source (X, TikTok, Instagram, YouTube, podcasts)
2. CloudWatch Alarms → SNS → e-mail.
3. Vérifier que les logs structurés tombent bien dans CloudWatch Logs Insights.
4. Décider si Sentry est utile post-V1 (sinon CloudWatch + Logs Insights suffisent).

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
- [ ] **Apple Sign in with Apple Service ID + Key (.p8) générés** + Team ID, Key ID renseignés
- [ ] Google Play Console activé (immédiat)
- [ ] **Google Cloud Console : 3 OAuth Client IDs créés (iOS, Android, Web) + écran de consentement publié**
- [ ] X Developer App approuvée + bearer token
- [ ] GetInsaver API key obtenue
- [ ] PodcastIndex API key + secret obtenus
- [ ] OpenAI API key + budget configuré
- [ ] Deepgram API key + budget configuré
- [ ] Algolia App créée + index `media_v1` configuré
- [ ] RevenueCat projet + 3 produits par store + webhook configuré
- [ ] Provider e-mail (SES/Resend/Postmark) configuré + DNS validé

---

## 6. Risques connus

| Risque | Mitigation |
|---|---|
| Apple rejette l'app à cause d'IAP via Stripe | Stripe retiré (task-98). RevenueCat conforme. |
| **Apple rejette l'app car Google login présent sans Sign in with Apple** | **task-101** ajoute Sign in with Apple côté mobile. Obligatoire avant soumission App Store. |
| Quota Deepgram explosé par un user TikTok abusif | Rate limiter TikTok 2-tier déjà en place + quotas par user dans `minute_buckets`. |
| GetInsaver API down | Instagram fail visible (status `failed`), pas de cascade. Surveiller en CloudWatch. |
| RevenueCat webhook drop | Réconciliation possible via `GET /api/entitlements/status` qui requête RevenueCat directement. |
| URL X privée / supprimée | Worker X retourne `failed` proprement, message d'erreur à l'utilisateur. |

---

## 7. Hors scope V1 (post-launch)

- LinkedIn ingestion (task-60)
- OCR documents (task-70 benchmark fait, implémentation à dispatcher si pertinent)
- Spotify OAuth pour récupérer la queue d'écoute
- Sentry / DataDog pour observabilité avancée
- Redis managé (ElastiCache) si scale-out
- Algolia → Typesense ou Meilisearch self-hosted si coûts trop élevés
- Web app v2 (le `front/` actuel sera remplacé depuis Stitch)
- Magic link login (code retiré ; éventuellement re-introduit comme fallback en cas de problème SSO)

---

## Appendice A — Commandes utiles

```bash
# Lister les tâches dispatchables
./scripts/dispatch_backlog.sh --dry-run

# Dispatch task-100 (Instagram fix)
./scripts/dispatch_backlog.sh --max-dispatch 1

# Build mobile dev
cd mobile && npx expo prebuild
eas build --platform ios --profile development

# Build mobile preview (TestFlight / Internal)
npm run build:ios:preview
npm run build:android:preview

# Run local stack
docker-compose up

# Run tests
pytest
cd mobile && npm run typecheck && npm run lint
```

## Appendice B — Liens internes

- `AGENTS.md` — guardrails projet
- `CLAUDE.md` — convention de création de tâches
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` — détails techniques mobile
- `docs/PRODUCTION_RELEASE_RUNBOOK.md` — procédure de release
- `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` — pipeline d'ingestion
- `docs/research/` — benchmarks validés (OCR, LLM artifacts, cloud, pricing)
- `infrastructure/terraform/` — provisioning AWS
