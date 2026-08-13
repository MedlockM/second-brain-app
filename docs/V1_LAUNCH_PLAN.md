# V1 Launch Plan — Media Summarizer

> Plan exhaustif des étapes restantes pour mettre l'application en production.
> Date de rédaction : 2026-05-19. Dernière mise à jour : **2026-08-13**
> (réconciliation avec le worktree, le backlog, AWS, GitHub Actions, les
> domaines et EAS). Les gates techniques backend qui bloquaient le plan au
> 2026-07-31 sont **fermés** : source synchronisée, CI verte, HEAD déployé,
> runtime API isolé, dev et prod dans deux comptes AWS séparés. Ce qui reste est
> désormais concentré sur **le mobile, le billing, les stores et le légal** —
> plus sur l'infrastructure.

### État de vérité au 2026-08-13

- **Source synchronisée et CI verte** : `main` local et `origin/main` sont au
  même commit (`6b22542`). `Main Branch Checks` **passe** sur ce SHA
  (`task-223` : config ESLint ajoutée + gates Ruff/Mypy résolus ; `task-227` :
  20 violations react-hooks corrigées ; `task-228` : venv local réparé).
  `ruff check .` local → `All checks passed!`.
- **HEAD réellement déployé** : `Deploy Lambda Functions` est vert sur `6b22542`
  et les 16 fonctions dev portent `LastModified = 2026-08-13T18:02`. Le runtime
  AWS n'est plus celui du 2026-06-15.
- **Runtime API isolé (`task-217`, Done le 2026-08-06)** : image API dédiée,
  reserved concurrency configurable, warm-up EventBridge, health gate de release,
  logs API Gateway enrichis, documenté dans `docs/API_LAMBDA_RUNTIME.md`. Mesure
  du 2026-08-13 sur dev : **cold 5,2 s / warm 1,0 s**, contre 25,7 s au
  déclenchement de la tâche.
- **Isolation par comptes AWS séparés (`task-221` + `task-237` + `task-248`)** :
  Terraform éclaté en `envs/{dev,staging,prod}` sur `modules/platform`, 100 % des
  noms physiques suffixés, un state par environnement. **`staging` a été détruit**
  (145 ressources, il était vide) et **`prod` vit dans un compte AWS dédié**
  `866874944541` sous l'organisation `o-7sf5u7j5hd`. 199 ressources créées, health
  prod `HTTP 200`. Les 21 tables legacy non suffixées sont supprimées
  (`task-249`) : dev ne porte plus que 26 tables, toutes `-dev`.
- **Prod est une coquille en veille, volontairement** : `enable_alarms`,
  `enable_dashboard` et `enable_worker_polling` à `false`, et son secret runtime
  contient **0 clé** sur 37 (`task-252`, owner-only). Le health check répond `200`
  parce qu'il ne teste que DynamoDB via le rôle IAM — aucune intégration tierce
  ne fonctionne.
- **Repo passé PUBLIC** : vérifié le 2026-08-13. Conséquences directes — la
  branch protection n'est plus bloquée par le plan GitHub (elle reste **non
  configurée** : `branches/main/protection` → 404, `rulesets` → `[]`), et tout
  identifiant écrit dans un fichier suivi est désormais public (d'où `task-255`
  et `de3ac86`).
- **Mobile inchangé et redevenu le chemin critique** : aucune build EAS Android
  n'existe, la build iOS du 2026-06-11 a expiré, `Mobile Build & Distribute` est
  rouge faute d'`EXPO_TOKEN`. `task-163` ACs #6-#8, `task-164` et `task-165`
  restent ouverts.
- **Production release** : `docs/RELEASE_LOG.md` reste la source de vérité :
  v1.0.0 `Pre-release`, aucun tag (`git tag -l` vide), aucun build production,
  aucune soumission.
- **Backlog quasi vidé** : 237 tâches, dont **13 non-`Done`** (62, 118, 145, 163,
  164, 165, 166, 172, 180, 186, 229, 238, 252). `task-212`/`task-213`
  (architecture LLM) sont **archivées** sur `owner_decision: abandoned`.
  `task-162` a été passée à `Done` le 2026-08-13 : ses 3 ACs étaient cochés et son
  SHA-1 consigné, seul le statut était resté en retard.

### Chemin critique restant, dans l'ordre

Le plan a basculé : l'infrastructure n'est plus le goulot. Ce qui reste, du plus
bloquant au moins bloquant :

1. **Re-run `pytest -m e2e` contre dev** — dernier gate backend ouvert (Phase 4).
2. **Build Android unique + validations device** — `task-163` ACs #6-#8,
   `task-164`, `task-165`, puis `task-166` clôture la Phase 5.
3. **Billing réel** — Phase 6 et `task-238` : `REVENUCAT_WEBHOOK_SECRET`, produits
   IAP, offerings/entitlements, achat et restore en sandbox.
4. **Owner-only, sans substitut possible** — les 37 credentials du secret prod
   (`task-252`), le quota Lambda prod, le KYC Google Play.
5. **Stores et légal** — nom marketing (`task-186`), icônes (`task-180`), domaine
   tranché puis API/privacy/terms réellement hébergés, listings et review accounts.
6. **Hygiène, rapide** — committer les 5 fichiers du worktree, configurer la branch
   protection, renseigner `EXPO_TOKEN`, purger les 3 comptes E2E résiduels de
   `users-dev`.

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
| **Continue with Google** | Code OK — backend + mobile câblés. Backend Web client ID + secret OK dans `.env`. OAuth Web + iOS provisionnés côté Google Cloud | OAuth Client ID Android créé le 2026-08-13 sur le SHA-1 du keystore EAS (`task-162`, sans build) et variable déclarée côté EAS ; restent le build Android unique et l'écran de consentement Google à publier en Production en Phase 10 |

---

## 1. Tâches restantes réellement bloquantes V1

Le backend V1 et le scope produit principal sont largement implémentés côté
code. Les tâches restantes ne sont cependant pas seulement des formalités
stores : plusieurs gates techniques et de sécurité doivent être fermées avant
un staging ou une soumission.

### Bloquants P0 avant prod — **tous fermés au 2026-08-13**

| Zone | Tâches / preuve | Statut au 2026-08-13 |
|---|---|---|
| Isolation API Lambda | `task-217` | **Fait (2026-08-06)** — image API ARM64 dédiée (`infrastructure/docker/lambda-api.Dockerfile`), image workers séparée, reserved concurrency configurable, warm-up EventBridge, health gate de release, logs API Gateway enrichis, `docs/API_LAMBDA_RUNTIME.md`. Mesuré le 2026-08-13 : cold 5,2 s / warm 1,0 s |
| Isolation dev/prod | `task-221` (benchmark, `owner_decision: ok`, option B) → `task-237` → `task-248` | **Fait (2026-08-13)** — `envs/{dev,staging,prod}` sur `modules/platform`, un state par env, 100 % des noms suffixés, `scripts/tf_plan_guard.sh`. Dev reste dans `125313707865`, **prod dans le compte dédié `866874944541`** (organisation `o-7sf5u7j5hd`). `staging` détruit, son répertoire conservé comme référentiel jetable |
| Nettoyage legacy AWS | `task-249` | **Fait** — 21 tables DynamoDB non suffixées supprimées ; il ne reste que 26 tables `-dev` + la table de lock du state |
| Sécurité users legacy | `task-222`, `task-224`, `task-253` | **Corrigé et déployé** — 2026-08-05 : `create_user`, `get_user`, `get_user_by_email`, `update_user` et `POST /api/v1/auth/verify-email` supprimés. 2026-08-12 (`task-224`) : `endpoints/users.py` et `DELETE /api/v1/users/{user_id}` supprimés au profit de `DELETE /api/account`, qui déduit le compte du token. 2026-08-13 (`task-253`) : le 404 de `DELETE /api/account` en dev est corrigé et un **startup guard** échoue au boot si une route critique n'est pas montée. Le code est déployé depuis le 2026-08-13T18:02. **Reste** : le run E2E complet (Phase 4) |
| Dérive de dépendances Lambda | `6b22542` | **Corrigé le 2026-08-13, après incident** — l'API dev a répondu 500 sur toutes les routes pendant ~2 h 20 : le startup guard de `task-253` lisait mal `app.routes` sur FastAPI 0.13x, et les Dockerfiles résolvaient `fastapi>=0.104.0` au build (0.141.1 dans l'image contre 0.116.1 dans `uv.lock` et le venv local) — donc irreproductible localement. Les images installent désormais depuis `uv export --frozen`. **Non commité au 2026-08-13** : la même bascule sur `uv.lock` pour `api.Dockerfile`, `worker.Dockerfile`, `test-orchestrator.Dockerfile`, `pr.yml` et `main.yml` (5 fichiers modifiés dans le worktree) |
| Suppression/export de compte | `mobile/app/settings/delete-account.tsx`, `media_summarizer/core/services/account_deletion_service.py`, `task-224` | **Fait en code (2026-08-12)** — suppression de compte in-app (Account > Delete Account) branchée sur `DELETE /api/account`, qui purge DynamoDB + S3 + Algolia. Le bouton `Export Data` mort est retiré : l'accès et la portabilité passent par `privacy@mediasummarizer.com` sous un mois, documenté dans la privacy policy. Le bouton `Settings` mort reste à traiter hors `task-224` |
| Source + CI | `task-223`, `task-227`, `task-228` | **Fait** — `main` = `origin/main` = `6b22542` ; `Main Branch Checks` **vert** sur ce SHA ; `Deploy Lambda Functions` vert sur ce même SHA. Reste hors P0 : `Mobile Build & Distribute` (cf. Phase 7) |

### Bloquants release immédiats

| Zone | Tâches | Statut |
|---|---|---|
| Re-run E2E AWS dev | Phase 4 | **Seul gate backend encore ouvert.** Le HEAD est déployé depuis le 2026-08-13T18:02 ; aucune preuve de `pytest -m e2e` complet contre ce runtime. À lancer, d'autant que l'incident du jour a montré qu'une image peut différer du lock |
| Mobile dev builds | `task-161`, `task-162`, `task-163` | iOS : `task-161` est `Done`, mais sur une build du 2026-06-11 expirée le 2026-06-25 — le development client reste installé sur l'iPhone owner. Android : keystore (`task-162`) et Client ID en place, **le build unique reste à lancer** (`task-163` ACs #6-#8) |
| Google OAuth Android | `task-163` | **Fait le 2026-08-13** : Client ID Android créé sur le SHA-1 du keystore `task-162`, et `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` déclarée dans l'environnement EAS `development` — donc en place **avant** le build, l'APK ne pourra pas embarquer `""`. Reste le build Android unique et sa validation sur device |
| Validation device non automatisable | `task-164`, `task-165` | À faire sur devices physiques : Apple Sign-In, Google sheet, Safari/Chrome share |
| Maestro V1 | `task-168`, `task-169`, `task-170`, `task-171`, `task-172` | **Plus un bloquant release** — CI en sommeil depuis le 2026-08-13 (`task-254`) le temps que l'UI soit figée ; 168/169/170/171 closes, 172 verrouillée. Cf. Phase 7, section « Maestro E2E CI — en sommeil depuis le 2026-08-13 » |
| Clôture Phase 5 | `task-166` | Mettre ce plan à jour une fois `task-163/164/165` terminées ; la couverture Maestro n'en est plus un prérequis |

### Bloquants pré-soumission stores

| Zone | Tâches | Statut |
|---|---|---|
| Branding app | `task-186` | Nom marketing final requis avant App Store Connect / Play Console |
| App icons | `task-180` | Remplacer les placeholders avant soumission |
| RevenueCat / IAP | Phase 6, `task-238` | `REVENUCAT_WEBHOOK_SECRET` absent ; produits, offerings/entitlements et tests sandbox réels non prouvés ; `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` encore un placeholder dans les trois environnements EAS |
| Domaine production | Phase 10 | Au 2026-08-13 : `secondbrainlabs.com` **résout** mais redirige en `301` vers `sbl.so` ; `api.secondbrainlabs.com` et `api.mediasummarizer.com` sont toujours en `NXDOMAIN`. Le profil EAS production pointe encore vers le second |
| Store/legal | Phase 10 | Les textes existent au dépôt (`docs/compliance/privacy-policy.md`, `terms-of-service.md`, `apple-app-privacy.md`, `google-play-data-safety.md`, `CHECKLIST.md`) mais **ne sont pas hébergés** : `secondbrainlabs.com/privacy` et `/terms` redirigent vers `sbl.so/...` qui répond **404**. Liens in-app absents, listings/screenshots/review accounts à finaliser |

### Prérequis de lancement propres au compte prod (issus de `task-248`)

| Zone | Preuve | Statut |
|---|---|---|
| Credentials runtime prod | `task-252` (`dispatchable: false`, owner-only) | **Bloquant dur.** Le secret `media-summarizer-runtime-prod` contient 0 clé sur 37 : sans lui, aucune transcription, résumé, résolution, recherche, achat, ni même session utilisateur valide (`JWT_SECRET_KEY`) |
| Quota Lambda concurrence prod | demande `L-B99A9384`, 10 → 1000 | **PENDING** côté AWS. Un compte neuf plafonne à 10 exécutions concurrentes. Tant que c'est le cas, `envs/prod/main.tf` porte `api_reserved_concurrency = -1` ; **retirer cette ligne** puis plan + apply dès que le quota passe, sinon l'API se dispute 10 exécutions avec 14 workers |
| Réveil de prod | `envs/prod/main.tf` | Trois booléens à passer à `true` (`enable_alarms`, `enable_dashboard`, `enable_worker_polling`) — ~7,20 $/mois. Une prod qui sert de vrais utilisateurs sans alarmes est une faute ; la veille n'est valide qu'avant lancement |

### Décisions à prendre sans bloquer inutilement le premier build interne

| Zone | Tâches | Décision requise |
|---|---|---|
| ~~Architecture LLM production~~ | ~~`task-212`, `task-213`~~ | **Tranché** : `owner_decision: abandoned` sur le benchmark ; les deux tâches sont archivées. La recommandation (Azure OpenAI multi-région) n'est pas retenue pour V1 — le statu quo OpenAI direct est assumé. À rouvrir seulement si le chatbot entre au scope et que le TPM devient contraignant |
| ~~Langue YouTube Apify~~ | ~~`task-216`~~ | **Fait** (`Done`) — la langue du transcript Apify suit la préférence `reading_language` de l'utilisateur |
| Discord community/support | `task-118` | Utile pour soft launch, non bloquant code. |
| TikTok proxy résidentiel | `task-145` | V2, explicitement non bloquant V1. |
| Fenêtre TTL `processing_jobs` | `task-242` AC #3 | Implémenté en variable `processing_jobs_ttl_days`, défaut **90 j** (recommandation du benchmark). L'AC reste décochée jusqu'à ce que l'owner tranche entre 30/60/90 |

---

## 2. Comptes et abonnements à créer

| Service | Coût | Pourquoi | Statut |
|---|---|---|---|
| **GitHub** (compte + repo **public** depuis le 2026-08-13) | gratuit | Versioning, CI/CD, releases | Bon : source synchronisée, `Main Branch Checks` et `Deploy Lambda Functions` verts sur le HEAD, environnement `production` créé (branche `main` seule autorisée). Six secrets Actions (`AWS_DEPLOY_ROLE_ARN` + les cinq E2E). Manquent `EXPO_TOKEN`, Apple/App Store Connect et le service account Google Play. Le repo étant public, la branch protection est **désormais disponible** mais n'est pas configurée |
| **AWS** (2 comptes, Organizations `o-7sf5u7j5hd`) | usage-based | DynamoDB, S3, SQS, Lambda, EventBridge | Bon : dev dans `125313707865` (déployé sur le HEAD), prod dans `866874944541` (199 ressources, health `200`, **en veille** et secret vide). Aucune alarme active — par conception dans les deux environnements, pas par défaut de provisioning |
| **Apple Developer Program** | $99/an | Publication App Store, TestFlight, IAP sandbox | OK (payé 2026-06-01, validé par Apple ; App ID + Sign in with Apple provisionnés) |
| **Google Play Console** | $25 one-time | Publication Play Store, Internal Testing, IAP sandbox | Payé 2026-06-01 ; statut KYC à revalider par l'owner (aucune preuve plus récente dans le repo) |
| **Expo / EAS** | gratuit (free tier) | Builds iOS/Android | Partiel : compte/projet OK ; ancienne build iOS expirée, aucune Android. Les trois environnements EAS **sont peuplés** (constaté le 2026-08-13) — `development` porte six variables `EXPO_PUBLIC_*` ; seul `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` reste un placeholder |
| **RevenueCat** | gratuit < $10k MTR | Cross-platform IAP backend | Partiel : clés backend et mobiles présentes localement ; webhook secret absent, produits/offering/entitlements et validation sandbox non prouvés |
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

Architecture cible : tous les secrets sont consolidés dans une entrée
**AWS Secrets Manager** par environnement
(`media-summarizer-runtime-<env>`) provisionnée par
`infrastructure/terraform/secrets.tf`. Les Lambda functions chargent ce secret
au cold start et injectent chaque clé du JSON comme variable d'environnement —
le code lit toujours via `os.getenv(...)` sans changement.

**État réel au 2026-08-13** : l'isolation Terraform est faite (`task-237`) et le
secret prod **existe** en tant que coquille dans le compte `866874944541`, mais
il contient **0 clé sur 37** — c'est l'objet de `task-252` (owner uniquement,
`dispatchable: false`). Dans le compte dev, `aws secretsmanager list-secrets` ne
renvoie que `media-summarizer-runtime-dev` (37 clés) et
`media-summarizer-devbox-mobile-env`. `media-summarizer-runtime-staging` a été
supprimé sans fenêtre de récupération par `task-248`, donc son nom est libre si un
staging jetable doit être remonté un jour.

Bootstrap : `terraform -chdir=infrastructure/terraform/envs/<env> apply`. Il n'y a
plus de `terraform.tfvars` à copier (task-237 : un root module par environnement,
valeurs en littéraux dans `envs/<env>/main.tf`) ni de `secret_payload` à remplir
(task-221 §7.3 : un `secret_string` inline fuiterait en clair dans le state).
Terraform ne crée que la coquille vide du secret ; les valeurs y sont poussées
hors-bande par `aws secretsmanager put-secret-value`. Voir
`infrastructure/terraform/README.md`.

Local : **un seul fichier `.env`** à la racine, chargé automatiquement par
`python-dotenv` depuis `media_summarizer/__init__.py` (override=False, donc les
vraies variables d'env priment). Modèle complet : `.env.example` (20 sections
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

`mobile/.env` est gitignored. Contrairement à l'état noté au 2026-07-31, les trois
environnements EAS `development`, `preview` et `production` **contiennent bien**
des variables `EXPO_PUBLIC_*` (vérifié le 2026-08-13 via `eas env:list`) :
`development` en porte six depuis l'ajout du Client ID Android. Les deux
mécanismes coexistent — `EXPO_PUBLIC_API_BASE_URL` n'existe **que** dans le bloc
`env` inline de `mobile/eas.json`, pas côté serveur.

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
ALGOLIA_SEARCH_API_KEY=...           # search-only key
```

Le nom de l'index n'est pas configurable : il vaut `media_items_{ENVIRONMENT}`,
calculé par `utils/algolia_client.py`. La séparation entre environnements est donc
structurelle, pas une variable à renseigner.

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

1. ~~Créer un repo GitHub.~~ **Fait** : `MedlockM/second-brain-app`, branche par défaut `main`. Historique purgé des secrets, `.venv-311/` et scratchpads ; `.gitignore` durci. Premier push : 2026-05-27 (HEAD `eb22f0e`, 174 commits, 553 fichiers). **Le repo est passé public** : vérifié le 2026-08-13 (`visibility: PUBLIC`). C'est ce qui motive `task-255` et `de3ac86` (purge de l'email de login et de l'identité de compte des fichiers suivis) — désormais, tout identifiant écrit dans un fichier suivi est public.
2. **GitHub Actions versionnés** : `.github/workflows/pr.yml`, `main.yml`, `deploy-lambda.yml`, `deploy-lambda-env.yml`, `mobile-build-distribute.yml`, `mobile-store-promote.yml`, `mobile-e2e-maestro.yml`.
3. ✅ **Source synchronisée au 2026-08-13** : `main` local et `origin/main` sont
   tous deux sur `6b22542`. Le worktree porte encore **5 fichiers modifiés non
   commités** (`pr.yml`, `main.yml`, `api.Dockerfile`, `worker.Dockerfile`,
   `test-orchestrator.Dockerfile`) : c'est l'extension du fix `uv.lock` de
   `6b22542` aux images et à la CI restantes — à committer.
4. ✅ **CI verte** (`task-223`, `task-227`, `task-228`) :
   - `Main Branch Checks` **success** sur `6b22542` (2026-08-13T18:00) ;
   - `ruff check .` en local → `All checks passed!` ;
   - la config ESLint manquante a été ajoutée et les 20 violations react-hooks
     corrigées, `rules` remises en `error` ;
   - l'interpréteur du venv local est réparé, donc Mypy est rejouable en local
     autant qu'en CI.
5. **GitHub Actions secrets** : six configurés — `AWS_DEPLOY_ROLE_ARN`,
   `E2E_TEST_USER_EMAIL`, `E2E_TEST_USER_PASSWORD`, `E2E_SEARCH_TEST_TERM`,
   `E2E_REVENUECAT_TEST_KEY`, `E2E_REVENUECAT_APPLE_KEY`. Manquent toujours
   `EXPO_TOKEN` (c'est ce qui fait échouer `Mobile Build & Distribute`),
   Apple/App Store Connect et le service account Google Play. Un environnement
   GitHub `production` existe (créé par `task-248`), restreint à `main`, avec son
   propre `AWS_DEPLOY_ROLE_ARN`.
6. **Branch protection** : la contrainte de plan est **levée** — le repo est
   public, donc la protection est disponible gratuitement. Elle n'est pour autant
   **pas configurée** : `branches/main/protection` → `404 Branch not protected`,
   `rulesets` → `[]`. À faire, en n'y mettant **pas** `Mobile E2E Tests
   (Maestro)` (cf. Phase 7).
7. **Reste à faire** : committer les 5 fichiers ci-dessus, puis configurer la
   branch protection.

### Phase 2 — Comptes externes (jour 1-2)

1. ~~Apple Developer Program.~~ **Fait** : payé 2026-06-01, validé par Apple ; App ID + Sign in with Apple provisionnés.
2. Google Play Console : payé 2026-06-01 ; **statut KYC à revalider par
   l'owner**, aucune preuve plus récente n'étant disponible dans le repo.
3. ~~AWS account + IAM admin user + facturation alarms.~~ **Fait** : compte AWS, IAM admin `second-brain-app-admin` et billing alarm $50/mois configurés.
4. Expo / EAS account + lien vers le repo : **compte/projet faits**. Une build
   iOS development a terminé le 2026-06-11 sur `8c63765`, mais elle a expiré le
   2026-06-25 et ne représente plus le code courant. Aucune build Android
   n'existe. Aucun env EAS development/preview/production n'est configuré.
5. RevenueCat account + projet + clés backend/mobile : **partiellement fait**.
   `REVENUCAT_WEBHOOK_SECRET` est toujours vide au 2026-07-31. Les produits IAP,
   offerings/entitlements, webhook réel et tests sandbox restent à prouver.
6. Comptes API tiers : les clés locales documentées restent présentes pour
   **OpenAI**, **Deepgram**, **PodcastIndex.org**, **X Developer Platform**,
   **Apify**, **LlamaParse**, **Unstructured.io** et **Algolia**. Google OAuth
   backend/iOS et Apple OAuth sont renseignés localement. Le **3ᵉ Client ID
   Google (Android)** est provisionné depuis le 2026-08-13 (`task-163`).
   Restent à provisionner/valider : publication du consent screen Google en
   Production, `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` (encore un placeholder),
   RevenueCat webhook + IAP et secrets runtime staging/prod.
7. **Google Cloud Console** (console.cloud.google.com) :
   - ~~Créer un projet~~ **Fait** : projet `media-summarizer` créé. Le nom du projet est un identifiant interne, peu visible aux users.
   - ~~**APIs & Services → OAuth consent screen (Audience)**~~ **Fait** : Type **External**, scopes `openid`, `email`, `profile` uniquement.
   - ~~**OAuth consent screen → Branding**~~ **Fait** : Branding `Second Brain`, support email, developer contact email.
   - ~~**Audience Test + utilisateur test**~~ **Fait** : mode Test configuré avec utilisateur test. La publication en `Production` est faite plus tard, en Phase 10.
   - **Google Auth Platform → Clients → 3 OAuth Client IDs** (l'ancien chemin
     « APIs & Services → Credentials » a été remplacé par cette section ; URL
     directe `console.cloud.google.com/auth/clients`) :
     - ~~**Web**~~ **Fait** : utilisé par le backend pour vérifier l'`aud` du id_token, et réutilisé côté mobile via `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`.
     - ~~**iOS**~~ **Fait** : avec bundle id du `mobile/app.config.ts` → `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`.
     - ~~**Android**~~ **Fait le 2026-08-13** (`task-163`) : créé avec
       `package=com.secondbrainlabs.core` et le SHA-1 du keystore EAS produit
       par `task-162`, sans qu'aucun build Android n'ait été nécessaire.
       Renseigné dans `mobile/.env` et déclaré dans l'environnement EAS
       `development` → `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`.
       À noter : ce client sert uniquement à ce que Google vérifie la signature
       de l'APK. L'`aud` du id_token reste le client **Web** — c'est bien lui
       que le backend vérifie.
8. **Apple Developer Portal** (developer.apple.com → Certificates, Identifiers & Profiles) :
   - **Bundle ID figé : `com.secondbrainlabs.core`** (décidé 2026-06-07,
     propagé dans `mobile/app.config.ts`, `mobile/ios-share-extension/`, les
     projets natifs générés et les product IDs RevenueCat). Le plugin custom
     `mobile/plugins/withShareExtension.js` a été supprimé par `task-188` au
     profit du plugin officiel `expo-share-intent`.
   - ~~**Identifiers → App IDs**~~ **Fait** : App ID `com.secondbrainlabs.core` créé, capability "Sign in with Apple" activée.
   - ~~**Identifiers → Services IDs**~~ **Fait** : Service ID `com.secondbrainlabs.core.signinwithapple` créé et return URL backend configurée.
   - ~~**Keys → Sign in with Apple Key**~~ **Fait** : clé `.p8` générée, `APPLE_PRIVATE_KEY`, `APPLE_KEY_ID`, `APPLE_TEAM_ID` renseignés.
   - ~~**Membership**~~ **Fait** : Team ID récupéré.

### Phase 3 — Infrastructure AWS (jour 2-3) — **DEV SEULEMENT : DONE 2026-06-08**

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

**État vérifié au 2026-08-13** :

- le health check dev répond `HTTP 200` — **cold 5,2 s, warm 1,0 s** (contre
  25,7 s au déclenchement de `task-217`, désormais `Done`) ;
- les 16 fonctions dev portent `LastModified = 2026-08-13T18:02` : le HEAD est
  bien déployé ;
- dev ne porte plus que **26 tables DynamoDB**, toutes suffixées `-dev`, plus la
  table de lock du state — les 21 tables legacy sont supprimées (`task-249`) ;
- secrets dev : `media-summarizer-runtime-dev` (37 clés) et
  `media-summarizer-devbox-mobile-env` ;
- **0 alarme CloudWatch active**, mais c'est désormais **voulu** :
  `enable_alarms = false` dans `envs/dev/main.tf` (économie assumée en dev) et les
  trois interrupteurs de coût sont à `false` en prod tant qu'elle est en veille.
  Ce n'est plus un défaut de provisioning mais un item de réveil (Phase 8).

**Blocage staging/prod : résolu (`task-221` → `task-237` → `task-248`)**. La
consigne historique « recopier `terraform.tfvars` avec un autre `environment` »
est morte et remplacée par une racine Terraform par environnement. Ce qui a été
livré :

1. `infrastructure/terraform/envs/{dev,staging,prod}` au-dessus de
   `modules/platform`, chaque racine déclarant une clé de backend et un
   `environment` **littéraux** — `terraform -chdir=envs/prod apply` est
   structurellement incapable d'écrire le state de dev ;
2. 100 % des noms physiques suffixés `-<env>`, migration du state dev par blocs
   `moved` (`scripts/gen_moved_blocks.py`) sans jamais laisser Terraform
   remplacer une table ;
3. `deploy-lambda-env.yml` : déploiement environment-aware, images taguées par
   SHA ;
4. `scripts/tf_plan_guard.sh` : garde-fou de plan. Sa **couche 4** (collision de
   noms avec les autres environnements vivants) devient structurellement
   redondante entre dev et prod, puisqu'une frontière de compte les sépare —
   lancer `tf_plan_guard.sh prod tfplan` **sans** troisième argument ;
5. **décision owner du 2026-08-12 : plus de staging.** Pour un développeur solo,
   maintenir trois environnements n'a pas de valeur. `staging` (vide : 0 ligne sur
   24 tables, 0 objet sur 11 buckets, 0 message sur 26 queues) a été détruit —
   145 ressources — et `prod` a été créé **dans un compte AWS dédié**
   `866874944541` sous l'organisation `o-7sf5u7j5hd`. `envs/staging/` reste au
   dépôt comme référentiel permettant de remonter un staging jetable avant une
   migration risquée.

**Résultats prod (compte `866874944541`, créé le 2026-08-13)** :

- 199 ressources créées ; API `GET /api/v1/health/` → `HTTP 200`
  `{"status":"healthy",…}` en 5,4 s à froid ; worker `search_indexing-prod`
  invoqué à vide → `StatusCode 200`, pas de `FunctionError`.
- Les images Lambda sont tirées de l'ECR de **dev** (`125313707865`) : il a fallu
  trois statements pour l'autoriser (principal de service Lambda de prod, root du
  compte consommateur, et l'autorisation côté IAM prod).
- `database: connected` alors que le secret runtime est **vide** — la route de
  santé ne teste que DynamoDB via les noms de tables injectés par Terraform, pas
  les credentials tiers. Ne jamais lire ce `200` comme « prod fonctionne ».
- Deux prérequis de lancement en découlent : `task-252` (37 credentials) et la
  demande de quota Lambda `L-B99A9384` (10 → 1000), toujours `PENDING`.

### Phase 4 — Tests d'intégration contre AWS dev (jour 3-4) — **NON VALIDÉE, RE-RUN COMPLET REQUIS**

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

1. ✅ **Synchroniser et déployer le code courant** — fait le 2026-08-13 : `main` =
   `origin/main` = `6b22542`, `Deploy Lambda Functions` vert, 16 fonctions dev
   redéployées à 18:02.
2. ✅ **Fermer `task-217` et revalider le cold start API** — `Done` le
   2026-08-06 ; cold 5,2 s / warm 1,0 s mesurés le 2026-08-13. Le health check
   est utilisable comme gate de release (`task-217` AC #7).
3. **Re-run complet AWS dev — SEUL GATE BACKEND ENCORE OUVERT** : `pytest -m e2e`
   contre `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`. Aucune preuve
   d'un run complet contre le runtime du 2026-08-13. Ne pas marquer Phase 4 DONE
   tant que ce run n'est pas vert. L'incident du jour (dérive `fastapi` entre
   l'image et `uv.lock`, invisible en local) est l'argument le plus fort en faveur
   d'un run contre le runtime déployé plutôt que d'une validation locale.
4. **Tester le digest journalier** (EventBridge rule). Pas couvert par l'E2E actuelle.
5. ✅ **Purge des comptes/artifacts E2E orphelins** — `task-246` (purge
   rétrospective) et `task-247` (teardown réellement effectif) sont `Done` :
   `scripts/purge_e2e_accounts.py` et `scripts/delete_e2e_account.py` existent, le
   teardown pytest exporte désormais les variables de tables avant tout import
   `media_summarizer` (sans quoi il échouait en silence), et les jobs Maestro
   appellent la suppression en `if: always()` / `continue-on-error`.
   **Résidu constaté le 2026-08-13** : `users-dev` contient encore 3 comptes E2E
   (`e2e-register-31712425508-1-android`, `e2e-task249-1786605697`,
   `e2e-maestro-20260809200952`) à côté du compte owner — antérieurs au fix, à
   passer à la purge.
6. ✅ **Backlog réconcilié** : 237 tâches, 14 non-`Done`. Reste une incohérence
   ponctuelle — `task-162` a ses 3 ACs cochés et son travail consigné mais son
   statut est encore `To Do`.

### Phase 5 — Mobile dev build (jour 4-5) — **EN COURS, NON VALIDÉE AU 2026-08-13 — CHEMIN CRITIQUE**

> Les gates backend étant fermés, cette phase est désormais **ce qui bloque le
> plan**. Elle tient à trois choses : un build Android unique, et deux validations
> manuelles sur device physique.

#### Fait

1. ✅ `task-159` — `scripts/mobile_release_check.sh` ajouté pour valider les prérequis EAS.
2. ✅ `task-160` — `cd mobile && npx expo prebuild` exécuté ; les dossiers natifs iOS/Android existent.
3. ✅ `task-181` — Expo SDK 52 → 55 + `expo-share-intent` 6.x.
4. ✅ `task-187` — Share intent refactoré vers l'API officielle `expo-share-intent` v6.
5. ✅ `task-188` — Fix cold-start race `expo-share-intent` v6 + suppression de la config custom dupliquée.
6. ✅ `task-161` — une build iOS development physique a terminé sur EAS le 2026-06-11
   (`build id 324f110a-8cbe-447c-96bf-2214099348c4`, commit `8c63765`).
   Son artifact a expiré le 2026-06-25, mais le development client reste
   installé et fonctionnel sur l'iPhone owner. Aucun changement natif requis
   n'a été introduit depuis ce build ; task-161 est clôturée sur cette preuve.

7. ✅ 2026-08-13 — `scripts/mobile_release_check.sh` corrigé : il exigeait encore
   `mobile/plugins/withShareExtension.js`, supprimé volontairement par
   `task-188`, et échouait donc à tort alors que le plugin officiel
   `expo-share-intent` est bien configuré (`mobile/app.config.ts:97`). Le script
   passe désormais, avec pour seul `WARN` la variable Android encore vide —
   attendue, elle est levée par `task-163`.
8. ✅ 2026-08-13 — `task-162` : keystore Android créé côté EAS via
   `eas credentials`, **sans aucun build**. SHA-1 :
   `38:D5:13:F4:2F:A9:DA:74:2F:A1:39:E3:17:9A:22:A8:59:58:DD:FD`
   (configuration `Build Credentials aRG08ty5Ek`, alias
   `3d6435c18da4d3d15721839b43347b78`). Détail et SHA-256 dans les notes de
   `task-162`.

#### À faire

1. Variables EAS : contrairement à l'état noté au 2026-07-31, les trois
   environnements `development`/`preview`/`production` contiennent bien cinq
   variables `EXPO_PUBLIC_*` (constaté le 2026-08-13 via `eas env:list`).
   `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` a été ajoutée à l'environnement
   `development` le 2026-08-13, qui porte donc six variables. Reste un trou :
   `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` vaut encore le placeholder
   `your_revenucat_google_api_key_here` dans les trois environnements
   (→ `task-238`). À noter aussi : `EXPO_PUBLIC_API_BASE_URL` n'existe **que**
   dans le bloc `env` inline de `mobile/eas.json`, pas côté serveur — les deux
   mécanismes coexistent.
2. `task-163` — **le prérequis OAuth est levé ; reste le build.** Faits le
   2026-08-13 : l'OAuth Client ID Android est créé dans Google Cloud Console
   avec `package=com.secondbrainlabs.core` et le SHA-1 ci-dessus, et
   `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` est déclarée dans l'environnement EAS
   `development` (six variables `EXPO_PUBLIC_*` désormais). La création du Client
   ID a dû se faire à la main dans l'UI web de la Cloud Console — ni `gcloud` ni
   aucune API publique n'expose la création d'un OAuth client de type Android.
   Reste à lancer `eas build --platform android --profile development`, **une
   seule fois**, puis à valider l'APK sur device (ACs #6 à #8).
   Avertissement détaillé dans le ticket : le profil `development` ne fixe pas
   `environment`, et la doc Expo ne garantit pas le rattachement — contrôler
   l'environnement annoncé dans les premières lignes de log du build, et
   interrompre tout de suite s'il n'est pas `development`.
3. `task-164` — validation iOS sur device physique :
   - Sign in with Apple → user créé/lié → inbox.
   - Continue with Google → `ASWebAuthenticationSession` → user créé/lié → inbox.
   - Share intent Safari → share-confirm → submit → vignette inbox.
4. `task-165` — validation Android sur device physique :
   - Continue with Google sans `DEVELOPER_ERROR`.
   - Apple button absent ou no-op clean.
   - Share intent Chrome URL.
   - Share intent texte/audio.
5. **Couverture Maestro (`task-168` à `task-172`) : plus un prérequis de
   Phase 5.** La CI Maestro est en sommeil depuis le 2026-08-13 (`task-254`) le
   temps que l'UI soit figée. `task-168`, `task-169`, `task-170` et `task-171`
   sont closes sur les 3 flows validés ; `task-172` est verrouillée
   (`dispatchable: false`) jusqu'à ce jalon. État des 7 flows, ce qui reste
   provisionné et travail de réactivation : Phase 7, section « Maestro E2E CI —
   en sommeil depuis le 2026-08-13 ».
6. `task-166` — marquer Phase 5 DONE dans ce plan une fois `task-163`,
   `task-164` et `task-165` closes.
7. ✅ **Hygiène backlog** : `task-162` est passée à `Done` le 2026-08-13 — ses
   3 critères étaient cochés et son SHA-1 consigné, seul le statut était en retard.
   Phase 5 ne dépend donc plus que de `task-163` (ACs #6-#8), `task-164` et
   `task-165`.
8. **Rebuild iOS courant** : `task-161` est `Done` sur la preuve du 2026-06-11,
   mais l'artifact a expiré le 2026-06-25 et le HEAD a beaucoup bougé depuis. Un
   rebuild iOS `development` sera de toute façon nécessaire pour `task-164`, ne
   serait-ce que pour tester le code courant.

### Phase 6 — Tests IAP sandbox (jour 5-6)

> Le code RevenueCat mobile/backend est implémenté (`task-99`) : SDK mobile, paywall, endpoint `POST /api/webhooks/revenucat`, table `revenucat_events`, endpoint entitlements. Ce qui reste en Phase 6 est le setup dashboard/stores et la validation sandbox réelle.
>
> **État 2026-07-31** : `REVENUCAT_API_KEY`,
> `REVENUCAT_PROJECT_ID` et les clés mobiles Apple/Google sont présentes
> localement, mais `REVENUCAT_WEBHOOK_SECRET` est vide. Aucun fichier
> `StoreKit.storekit` ni résultat de test achat/restore n'est présent dans le
> repo.

1. **iOS** :
   - App Store Connect → Apps → IAP → créer 3 produits (correspondance Offerings RevenueCat).
   - StoreKit configuration locale (`mobile/ios/StoreKit.storekit`) pour Xcode
     simulator — fichier toujours absent au 2026-07-31.
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
2. ✅ **État source** : `main` = `origin/main` = `6b22542` ; les runs GitHub
   portent donc bien sur l'état courant. Reste 5 fichiers non commités (fix
   `uv.lock` des images et de la CI, cf. Phase 1).
3. ✅ **Main checks verts** (`task-223`, `task-227`, `task-228`) : `Main Branch
   Checks` est `success` sur `6b22542`. Le pin sur `uv.lock` en cours de commit
   ferme la dernière faille de ce gate — jusqu'à présent la CI installait depuis
   les intervalles de `pyproject.toml` et pouvait donc linter avec un `ruff`/`mypy`
   différent de celui du lock et du poste owner.
4. **Mobile build workflow rouge, et toujours trop agressif** — inchangé :
   `.github/workflows/mobile-build-distribute.yml` lance une build production et
   tente une soumission à chaque push `main` touchant `mobile/**`. Il échoue en
   ~2 s sur `An Expo user account is required to proceed` (`EXPO_TOKEN` vide), pour
   iOS **et** Android, puis échoue une seconde fois en tentant d'ouvrir une issue
   avec un label `ci/cd` inexistant. Trois corrections distinctes : renseigner
   `EXPO_TOKEN`, réserver production à un tag/dispatch explicite (preview/internal
   pour la validation courante), créer le label ou le retirer du workflow.
5. **Secrets GitHub** : six configurés, dont les cinq requis par Maestro
   (`E2E_TEST_USER_EMAIL`/`_PASSWORD`, `E2E_SEARCH_TEST_TERM`,
   `E2E_REVENUECAT_TEST_KEY`, `E2E_REVENUECAT_APPLE_KEY`). Ajouter encore
   `EXPO_TOKEN`, Apple/App Store Connect et le service account Google Play pour
   les workflows de distribution.
6. ✅ **Variables EAS** : les trois environnements sont peuplés (constaté le
   2026-08-13). Seul `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` reste un placeholder
   (`task-238`).
7. **Maestro CI** : **en sommeil depuis le 2026-08-13** (`task-254`). Plus aucun
   déclenchement automatique ; `workflow_dispatch` est le seul point d'entrée.
   Ce n'est plus un gate de release. État des flows et plan de réactivation dans
   la section ci-dessous. À noter : le dernier run automatique, sur `9cb9da5`, est
   rouge — c'est cohérent avec la mise en sommeil, pas une régression à traiter.
8. **Branch protection** : le choix est **tranché de fait** — le repo est public,
   donc la protection est disponible sans upgrade. Elle reste à configurer
   (`404 Branch not protected`, aucun ruleset). Y mettre `Main Branch Checks`, et
   surtout **pas** `Mobile E2E Tests (Maestro)` : le workflow ne se déclenche plus
   tout seul et les PR resteraient bloquées en attente d'un check absent.
9. Vérifier le rollback Lambda avec deux images API/worker immuables après
   `task-217`, puis documenter l'exercice.

#### Maestro E2E CI — en sommeil depuis le 2026-08-13

**Déclencheur de réactivation** : l'UI est figée, c'est-à-dire qu'aucune refonte
d'écran n'est plus prévue. C'est un jalon produit, pas une date. Les flows
vérifient la copie affichée et des `testID` (`Welcome back`, `Good .*`,
`YOUR MEDIA`, `AI Artifacts`, `Choose Your Plan`, `Reader`/`Mix`/`Audio-Heavy`,
`paywall-screen`, `search-result-card`…) : tant qu'un écran peut bouger, chaque
itération de design casse des selectors et la remise au vert est à refaire.

**Ce qui dort** : uniquement les déclencheurs automatiques `push` (branches
`main`, `second-brain-project`) et `pull_request` de
`.github/workflows/mobile-e2e-maestro.yml`, tous deux filtrés sur `mobile/**`.
Ils sont commentés en place ; les restaurer consiste à retirer les marqueurs de
commentaire. `workflow_dispatch` reste intact avec ses deux inputs `platform`
(`android`/`ios`/`both`) et `flow_filter`.

**Ce qui reste provisionné** — rien n'est à recréer à la réactivation :

- les 7 flows de `mobile/.maestro/`, leurs sous-flows `utils/` et la suite
  `suites/tasks_168_170.yaml` ;
- les runners `.github/scripts/run-android-maestro.sh`,
  `run-ios-maestro.sh` et `.github/scripts/lib/maestro-flows.sh`, ainsi que les
  jobs `android-e2e`, `ios-e2e` et `e2e-summary` ;
- les secrets GitHub Actions `E2E_TEST_USER_EMAIL`, `E2E_TEST_USER_PASSWORD`,
  `E2E_SEARCH_TEST_TERM`, la clé publique RevenueCat Test Store
  `E2E_REVENUECAT_TEST_KEY` et l'override optionnel `E2E_API_BASE_URL` ;
- la fixture persistante sur AWS dev : l'article « Commonplace book », arrivé
  `ready_for_artifacts` et indexé Algolia, rattaché au compte de test.

**État réel des 7 flows au 2026-08-13** — c'est l'information qui coûterait le
plus cher à reconstituer plus tard :

| Flow | État | Détail |
|---|---|---|
| `01_login` | ✅ Vert | Émulateur Android API 33 **et** simulateur iOS 18.5, run `31612429695` (`workflow_dispatch` du 2026-08-12) |
| `06_search` | ✅ Vert | Idem — s'appuie sur la fixture « Commonplace book » indexée Algolia |
| `07_paywall` | ✅ Vert | Idem — vérifie l'affichage des trois tiers, aucun achat déclenché |
| `02_share_intake` | ⏸️ Neutralisé volontairement | Réduit à un smoke test auth, tag `skipped`. Le share natif n'est pas pilotable par Maestro (share sheet hors process). Un fallback Appium ciblé est décrit dans `mobile/E2E_TESTING.md`, à n'activer que si une release est bloquée par cette incertitude |
| `03_inbox_visibility` | ❌ Cassé, jamais exécuté en CI | Amorce par `openLink: "media-summarizer://share?url=…"` puis attend `assertVisible: "Save Link"`. Depuis le 2026-06-11, `redirectSystemPath` dans `mobile/app/+native-intent.tsx` teste `path.includes("://share?")` et redirige vers `/(tabs)/inbox` : « Save Link » n'apparaît jamais, le flow échoue à sa première assertion non optionnelle |
| `04_media_detail_progression` | ❌ Cassé, jamais exécuté en CI | Même amorce, même cause |
| `05_artifact_trigger_action` | ❌ Cassé, jamais exécuté en CI | Même amorce, même cause, plus quatre défauts propres listés ci-dessous |

Le run vert du 2026-08-12 a évité 03/04/05 en passant
`flow_filter: suites/tasks_168_170` : les trois flows verts sont donc les seuls
validés, et « suite verte » n'a jamais voulu dire « 7 flows verts ».

**Travail à prévoir à la réactivation**, en distinguant le réamorçage des bugs
de flow déjà identifiés :

1. **Réamorcer 03/04/05 sur la fixture persistante** (« Commonplace book »,
   `ready_for_artifacts`, indexée Algolia) au lieu de simuler un share par deep
   link : se loguer, atteindre l'item depuis l'inbox ou la recherche, et
   dérouler le scénario à partir de là. Effet de bord bénéfique sur 05 :
   `mediaReady` est vrai d'emblée, ce qui supprime l'attente de 120 s sur
   l'apparition du bouton `Generate`.
2. **Corriger quatre défauts du flow 05**, indépendants de l'UI et donc à
   traiter même après refonte :
   - `tapOn: text: "Generate", index: 0` est ambigu : les cinq tuiles rendent un
     bouton dont le texte est exactement `Generate`
     (`mobile/app/media/[id].tsx:1032`) et l'index se décale dès qu'une tuile
     est `ready`. Cibler l'`accessibilityLabel` `Generate Summary`, déjà exposé
     par le composant.
   - `assertVisible: text: "Summary"` est ambigu avec la tuile
     `Detailed summary`.
   - Aucun `assertNotVisible: "Failed"` après le tap, alors que l'UI rend
     `Failed` + `Retry` en cas d'échec : le flow brûle 180 s d'attente avant de
     tomber sur un diagnostic inutile.
   - L'`extendedWaitUntil` sur la regex `Queued|Generating|Ready` peut être
     satisfait d'emblée par une autre tuile déjà `ready`, et le `tapOn: "View"`
     sans index ouvrirait alors le mauvais artifact.
3. **Reprendre la cible finale**, portée par deux tâches déjà au backlog :
   - `task-171` a été clôturée `Done` le 2026-08-13 sur les 3 flows validés ;
     ses notes consignent ce qui manque (run complet des 7 flows, vert sur les
     deux plateformes).
   - `task-172` (Android bloquant sur PR, iOS en nightly/manuel) est verrouillée
     `dispatchable: false` jusqu'à ce jalon — la déverrouiller consiste à
     retirer cette ligne de son front-matter.

**Contrainte de budget CI, inchangée** : l'owner n'a pas de Mac, donc toute
exécution iOS passe par un runner macOS GitHub Actions, facturé x10 sur les
minutes Actions, sur le plan gratuit (2000 min/mois → ~200 min réelles de
macOS). iOS ne redevient donc **jamais** un required check par PR : Android sur
`ubuntu-latest` couvre les régressions logiques, iOS reste manuel ou nightly.

### Phase 8 — Monitoring & observabilité (jour 7-8)

> Le provisioning Terraform de dashboard/alarms a été ajouté (`task-114`, `task-46`), puis adapté à la migration Lambda, puis complété par `task-242` et `task-243`. La validation restante est opérationnelle : réveiller les alarmes en prod et vérifier les signaux CloudWatch réels.
>
> **État 2026-08-13** : AWS retourne toujours **0 alarme active**, mais c'est
> désormais **une conséquence des interrupteurs de coût, pas un trou de
> provisioning** : `enable_alarms = false` en dev (économie assumée) et les trois
> interrupteurs à `false` en prod tant qu'elle est en veille. Le réveil est un
> `apply` de trois booléens, ~7,20 $/mois (1 topic SNS + 43 alarmes ≈ 3,30 $,
> 1 dashboard ≈ 3,00 $, 14 mappings SQS ≈ 0,90 $). Le tableau par environnement est
> dans `infrastructure/terraform/README.md`, section « Cost switches ».
>
> Deux ajouts récents à valider au réveil :
> - `task-242` — l'archiveur de jobs est **réellement déployé** (code réel à la
>   place du placeholder, 4 jobs archivés dans
>   `s3://media-summarizer-archives-…-dev/2026/08/13/`), le TTL de
>   `processing_jobs-dev` est **ENABLED** (variable `processing_jobs_ttl_days`,
>   défaut 90 j) et l'alarme `job_archiver_silent_failure` est câblée et
>   *fireable*. La fenêtre TTL définitive reste à trancher par l'owner (AC #3).
> - `task-243` — `user_media` est branché sur la rétention, la suppression, le
>   backup et l'observabilité ; `docs/DATA_RETENTION.md` est le document de
>   référence des deux horloges (la bibliothèque d'un utilisateur n'a **pas**
>   d'horloge de rétention), et `scripts/check_purge_at_writers.py` fait échouer la
>   CI si un second écrivain de `purge_at` apparaît.

1. CloudWatch Dashboard à vérifier avec :
   - Latence API (`API_SLOW_REQUEST_THRESHOLD_MS` → alarmes)
   - Profondeur des queues SQS (alarme si DLQ > 0, en particulier `document-parsing-queue`)
   - Taux d'erreur Deepgram / OpenAI / **LlamaParse / Unstructured** (logs structurés `parser=llamaparse|unstructured` + `error_code`)
   - Coût par source (X, TikTok, Instagram, YouTube, podcasts, **documents**)
   - Compteur quota LlamaParse (1000 pages/jour free tier) — alarme si fallback Unstructured déclenché plus de N fois/heure
2. CloudWatch Alarms → SNS → e-mail (`enable_alarms = true` en staging/prod).
3. Vérifier que les logs structurés tombent bien dans CloudWatch Logs Insights.

### Phase 9 — ~~Staging end-to-end~~ → **Validation prod avant ouverture** (jour 8-9)

> **Cette phase a changé de nature le 2026-08-12** (décision owner, cf. `task-248`).
> Il n'y a **plus d'environnement staging** : pour un développeur solo, en
> maintenir un troisième n'apportait rien, et il était de toute façon vide. Le
> couple retenu est **dev + prod dans deux comptes AWS séparés**. `envs/staging/`
> reste au dépôt uniquement comme référentiel permettant de remonter un staging
> **jetable** avant une migration risquée (c'est aussi le seul cas où la couche 4
> de `tf_plan_guard.sh` retrouve son utilité).
>
> Les étapes de validation ci-dessous ne disparaissent pas — elles se font
> désormais **contre prod, avant de l'ouvrir aux utilisateurs**, puisque prod
> existe déjà et n'a jamais servi de trafic.

0. ✅ **Isolation débloquée** : `task-237` + `task-248`, cf. Phase 3.
1. ✅ **L'environnement cible existe** : 199 ressources dans le compte
   `866874944541`, health `HTTP 200`. Il est en veille et son secret est vide.
2. **Peupler le secret runtime prod** (`task-252`, owner) puis réveiller les trois
   interrupteurs de coût. Sans ça, aucune des étapes suivantes n'a de sens.
3. **Lever le plafond de concurrence** : quota `L-B99A9384` (10 → 1000) en
   attente ; retirer ensuite `api_reserved_concurrency = -1` de
   `envs/prod/main.tf` et rappliquer.
4. Créer le vrai endpoint/domaine prod (`api.secondbrainlabs.com`, cf. Phase 10
   §0bis) et l'injecter dans EAS + Maestro.
5. Tester depuis un device physique avec une URL réelle de chaque source.
6. Vérifier qu'aucun credential de dev n'a été recopié dans prod (`task-252`
   l'interdit explicitement).
7. Charger 50-100 URLs en parallèle pour vérifier le scaling SQS / Lambda —
   **après** la levée du quota, sinon la mesure ne mesure que le throttling.
8. Vérifier RevenueCat sandbox → backend webhook contre prod.
9. Mesurer cold/warm API, profondeur SQS, DLQ et coût avant ouverture.

### Phase 10 — Pré-lancement (jour 10+)

0. **Rebrand mobile placeholder name** (cf. task-186) — l'app utilise actuellement le nom legacy `Media Summarizer` partout (display name, slug Expo, scheme deep link, share extension iOS). À exécuter **avant** la sous-étape 1 ci-dessous : tous les textes Apple App Store Connect (App Information, screenshots) et Google Play Console + Google OAuth Branding consomment le nom marketing définitif. Coût ~30 min en pré-distribution, beaucoup plus élevé une fois publié. Ne touche pas le bundle id `com.secondbrainlabs.core` (figé). Voir `task-186` pour la checklist exacte des 8-9 endroits à mettre à jour.

0bis. **Couper l'API du custom domain `api.secondbrainlabs.com`** — pendant le dev (Phase 5), l'app mobile + Apple Sign-In Service ID + `APPLE_REDIRECT_URI` côté backend tapent tous l'URL brute API Gateway `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`. En Phase 10, on bascule sur le custom domain. Étapes :
   - **État 2026-08-13** : `secondbrainlabs.com` **résout** désormais, mais renvoie
     un `301` vers `sbl.so` (site tiers), et `sbl.so/privacy` comme `sbl.so/terms`
     répondent **404**. `api.secondbrainlabs.com` et `api.mediasummarizer.com`
     sont toujours en `NXDOMAIN`. Le profil EAS production pointe toujours vers
     `https://api.mediasummarizer.com`. Décider d'abord **quel domaine porte le
     produit** — la redirection vers `sbl.so` suggère que `secondbrainlabs.com`
     n'est pas (ou plus) dédié à cette app —, puis appliquer les étapes ci-dessous
     sur le domaine retenu.
   - Le sous-domaine API doit être créé **et** les pages `/privacy` et `/terms`
     réellement servies sur ce même domaine : Apple et Google exigent une URL de
     politique de confidentialité publiquement atteignable, un `404` derrière une
     redirection est un motif de rejet.
   - Le support Terraform existe déjà dans `infrastructure/terraform/modules/platform/lambda_api.tf` (`api_custom_domain`, `api_zone_id`, `aws_acm_certificate`, API Gateway domain mapping, Route53 record conditionnel) : les ressources sont conditionnées par `count` sur ces deux variables, donc vides tant qu'elles ne sont pas renseignées.
   - Passer `api_custom_domain = "api.secondbrainlabs.com"` et `api_zone_id` au bloc `module "platform"` de `infrastructure/terraform/envs/prod/main.tf`, puis `terraform -chdir=infrastructure/terraform/envs/prod apply`.
   - Créer/valider le DNS Cloudflare ou Route53 selon la zone réellement utilisée. Si Cloudflare reste le DNS autoritaire, créer le CNAME vers le `target_domain_name` exposé par Terraform.
   - `terraform apply` puis vérifier `curl https://api.secondbrainlabs.com/api/v1/auth/apple/callback` → HTTP 302.
   - **Apple Developer Portal** → Identifiers → Service IDs → `com.secondbrainlabs.core.signinwithapple` → Configure → ajouter Domain `secondbrainlabs.com` (déjà présent) et Return URL `https://api.secondbrainlabs.com/api/v1/auth/apple/callback` (déjà présent), **retirer** les entrées `jji077bi8e.execute-api.*` ajoutées en Phase 5.
   - **AWS Secrets Manager** → mettre à jour `APPLE_REDIRECT_URI` vers `https://api.secondbrainlabs.com/api/v1/auth/apple/callback`.
   - **`mobile/eas.json`** → profile `development` et `preview` :
     `EXPO_PUBLIC_API_BASE_URL` repasse à
     `https://api.secondbrainlabs.com`. Attention : le profile `production`
     pointe encore vers `https://api.mediasummarizer.com` au 2026-07-31 ;
     l'aligner sur le domaine choisi avant build production.
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
4. **Légal** — les textes sont **rédigés au dépôt**, ce qui reste est l'hébergement
   et le câblage in-app. Présents depuis le 2026-08-12 :
   `docs/compliance/privacy-policy.md`, `terms-of-service.md`,
   `apple-app-privacy.md` (réponses au questionnaire App Privacy),
   `google-play-data-safety.md` et `CHECKLIST.md`.
   - Politique de confidentialité hébergée publiquement — **pas fait** : le
     chemin `/privacy` répond 404 derrière une redirection (cf. §0bis).
   - CGU avec mention RevenueCat / abonnements — texte prêt, hébergement à faire.
   - Conformité RGPD : droit à l'oubli **implémenté** (cf. ci-dessous) ; accès et
     portabilité traités manuellement par mail sous un mois.
   - Ajouter les liens Privacy/Terms sur login/register et Account.
   - **Fait (`task-224`, 2026-08-12)** : suppression de compte in-app
     (Account > Delete Account → `DELETE /api/account`) qui purge DynamoDB, S3 et
     l'index Algolia ; l'ancienne `DELETE /api/v1/users/{user_id}`, qui ne
     supprimait que la ligne `users`, est supprimée. Le bouton `Export Data` mort
     est retiré, l'accès (art. 15) et la portabilité (art. 20) sont traités
     manuellement par mail sous un mois, documenté en privacy policy §8.
   - **Prérequis déploiement** : appliquer Terraform (`s3:DeleteObject` sur le
     bucket bug-reports) **avant** de déployer l'API, sinon tout user ayant joint
     une capture d'écran reçoit un 500 au lieu d'une suppression. En dev, le code
     est déployé depuis le 2026-08-13 et `task-253` a corrigé le 404 de la route ;
     à revérifier lors du réveil de prod.
   - **État 2026-08-13** : `secondbrainlabs.com/privacy` et `/terms` renvoient un
     `301` vers `sbl.so/...`, qui répond **404**. `mediasummarizer.com` ne résout
     toujours pas.
5. **Site landing minimal** (optionnel) : `<your-domain>` avec CTA App Store / Play Store.
6. **Soft launch** : un seul pays, 100 users, observer 1 semaine avant rollout global.

---

## 5. Ce qui reste **bloqué** sur des credentials externes / owner-only

Les comptes principaux sont largement provisionnés. Les blocages restants sont surtout liés aux stores, aux builds EAS interactifs et aux dashboards tiers.

- [x] AWS account + IAM admin user `second-brain-app-admin` (AdministratorAccess) + alarme billing $50/mois (us-east-1) configurée
- [x] Organisation AWS `o-7sf5u7j5hd` + compte membre prod `866874944541` créés au
  2026-08-13 (`task-248`), profil `[profile prod]` ajouté hors dépôt dans
  `~/.aws/config`. **Irréversibles** : une organisation ne se supprime qu'après
  sortie de tous ses comptes membres, et un compte AWS ne se supprime pas avant
  90 jours de fermeture
- [ ] **Les 37 credentials runtime du secret prod** (`task-252`, owner uniquement,
  `dispatchable: false`) — prod est une coquille vide sans eux : ni transcription,
  ni résumé, ni résolution, ni recherche, ni achat, ni session utilisateur valide
- [ ] **Quota Lambda concurrence du compte prod** : demande `L-B99A9384` (10 → 1000)
  `PENDING` côté AWS. Retirer ensuite `api_reserved_concurrency = -1` de
  `envs/prod/main.tf` et rappliquer
- [x] Apple Developer Program payé ($99) au 2026-06-01, validé par Apple
- [x] **Apple Sign in with Apple Service ID + Key (.p8) + App ID + Team ID + Key ID** provisionnés au 2026-06-08 (cf. Phase 2.8) — toutes les vars Apple dans `.env` renseignées : `APPLE_CLIENT_ID` (Service ID), `APPLE_PRIVATE_KEY` (PEM single-line), `APPLE_REDIRECT_URI` prod, `APPLE_TEAM_ID`, `APPLE_KEY_ID`.
- [ ] Google Play Console payé ($25) au 2026-06-01 — **statut KYC à
  revalider par l'owner**, l'information « en cours » n'a pas été actualisée
  depuis juin
- [x] Google Cloud Console : projet `media-summarizer` créé, OAuth consent screen configuré (Branding `Second Brain`, External, scopes openid+email+profile), mode Test avec utilisateur test ajouté, **3 OAuth Client IDs créés (Web backend + iOS + Android au 2026-08-13)** — `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` dans `.env` racine ; `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB` + `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS` dans `mobile/.env` (naming aligné avec `mobile/app.config.ts`, corrigé 2026-06-08)
- [x] Google Cloud Console **Android OAuth Client ID** — **fait le 2026-08-13**
  (`task-163`), avec `package=com.secondbrainlabs.core` et le SHA-1 du keystore
  EAS `38:D5:13:F4:2F:A9:DA:74:2F:A1:39:E3:17:9A:22:A8:59:58:DD:FD`.
  `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` est renseignée dans `mobile/.env` et
  déclarée dans l'environnement EAS `development` — donc **en place avant** le
  build Android unique, qui reste à lancer
- [ ] Google Cloud Console **publication OAuth (Test → Production)** à faire en Phase 10 juste avant le lancement
- [x] X Developer App approuvée + bearer token (en local dans `.env`)
- [x] Apify API tokens + actor IDs obtenus — en local dans `.env` (Instagram Reel/Post, YouTube, TikTok selon fallback chain)
- [x] LlamaParse API key obtenue (free tier 1000 pages/jour) — en local dans `.env`
- [x] Unstructured.io API key obtenue (15 000 pages gratuites au démarrage) — en local dans `.env`
- [x] PodcastIndex API key + secret obtenus (en local dans `.env`)
- [x] OpenAI API key + budget configuré (en local dans `.env`)
- [x] Deepgram API key + budget configuré (en local dans `.env`)
- [x] Algolia App créée + index configuré (App ID + Admin API key + index name en local dans `.env`)
- [~] RevenueCat — clés backend et mobiles présentes localement, mais
  `REVENUCAT_WEBHOOK_SECRET` reste vide. Restent à faire : webhook sur le futur
  endpoint prod, 3 produits IAP iOS/Android, import dans RC, Entitlements +
  Offerings, comptes sandbox/license testers, achat/restore et propagation vers
  quotas. Côté app, les entrées UI existent désormais (`task-244` : CTA d'upgrade
  dans Account + déclenchement sur refus de quota ; `task-245` : l'état
  d'abonnement est réellement consommé par l'UI) — le paywall n'est donc plus un
  écran orphelin, seul le circuit d'achat réel manque
- [x] Pricing admin secret généré au 2026-06-08 (`PRICING_ADMIN_SECRET` en local dans `.env`, requis pour `PUT /api/pricing/admin`)
- [ ] EAS iOS development build **courante** : l'ancienne build du 2026-06-11
  a expiré et précède le HEAD actuel (`task-161`)
- [x] SHA-1 keystore Android via `eas credentials`, sans build (`task-162`,
  2026-08-13) — aucun build consommé, cf. notes de `task-162`
- [ ] EAS Android development build : toujours aucune build Android ; à lancer
  une seule fois en fin de `task-163`, après déclaration du Client ID
- [~] Variables EAS development/preview/production : contrairement à l'état noté
  au 2026-07-31, les trois environnements sont peuplés (vérifié le 2026-08-13).
  `development` porte six variables depuis l'ajout du Client ID Android.
  Reste `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY`, encore un placeholder dans les trois
  environnements (`task-238`)
- [ ] Nom marketing final : requis avant `task-186`, App Store Connect, Play Console et Google OAuth Branding
- [ ] Icônes finales : `task-180`, requis avant soumission stores
- [ ] Domaines : décider quel domaine porte le produit (`secondbrainlabs.com`
  redirige aujourd'hui vers `sbl.so`), puis rendre le sous-domaine API, `/privacy`,
  `/terms` et l'URL support réellement publics avant la build production
- [x] Architecture LLM production : **tranché** — `owner_decision: abandoned` sur le
  benchmark `task-212` ; `task-212` et `task-213` sont archivées, le statu quo
  OpenAI direct est assumé pour V1
- [ ] Branch protection sur `main` : plus aucun obstacle de plan (repo public), mais
  rien n'est configuré

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
| ~~API interactive indisponible après longue inactivité~~ | **Traité** (`task-217`, 2026-08-06) : image API minimale, reserved concurrency configurable, warm-up EventBridge, health gate de release. Cold 5,2 s / warm 1,0 s au 2026-08-13. |
| ~~Collision/destruction entre dev/staging/prod~~ | **Traité** (`task-237`, `task-248`) : une racine Terraform par environnement, 100 % des noms suffixés, et surtout **une frontière de compte AWS** entre dev et prod — un plan lancé avec les identifiants de prod ne peut rien toucher dans dev. |
| ~~CRUD users legacy non authentifié~~ | **Traité** (`task-222`, `task-224`, `task-253`) : surface legacy supprimée, `DELETE /api/account` déduit le compte du token et purge DynamoDB + S3 + Algolia, startup guard contre les routes silencieusement absentes. |
| ~~État local non poussé sur GitHub~~ | **Traité** : `main` = `origin/main` = `6b22542`, et le SHA déployé est celui qui a passé les gates. |
| Dérive silencieuse entre l'image Lambda et le lockfile | **Cause de l'incident du 2026-08-13** (API dev 500 sur toutes les routes, ~2 h 20) : les Dockerfiles résolvaient les intervalles de `pyproject.toml` au build, donc chaque build produisait une image différente et aucune exécution locale ne pouvait reproduire le bug. Mitigation : installer depuis `uv export --frozen` — fait pour les deux images Lambda, **à committer pour les trois images et les deux workflows restants**. |
| Un health check vert lu comme « l'environnement fonctionne » | `GET /api/v1/health/` ne teste que DynamoDB via le rôle IAM. Prod répond `200` avec un secret runtime **vide**. Ne jamais s'en servir comme preuve qu'un environnement est opérationnel — seul un E2E complet l'établit. |
| Prod ouverte alors qu'elle est en veille | Trois booléens (`enable_alarms`, `enable_dashboard`, `enable_worker_polling`) à repasser à `true`, plus le quota de concurrence et le secret runtime. Une prod servant de vrais utilisateurs sans alarmes est une faute ; la veille n'est acceptable qu'avant lancement. |
| CI donnant un faux sentiment de sécurité | Gates verts au 2026-08-13. Rester vigilant sur trois points : ne pas remettre de `|| true`, ne pas mettre le workflow Maestro en sommeil dans les required checks, et pin les outils via `uv.lock` pour que la CI lint avec les mêmes versions que le poste owner. |
| Build mobile sans secrets runtime | Les trois environnements EAS sont peuplés ; reste `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` (`task-238`) et `EXPO_TOKEN` côté GitHub Actions. `mobile/.env` gitignored ne constitue pas une configuration de build distante. |
| Domaine/légal indisponible | Textes légaux rédigés (`docs/compliance/`) mais **non hébergés** : `/privacy` et `/terms` répondent 404 derrière une redirection vers `sbl.so`. Trancher le domaine, héberger, puis vérifier les URLs depuis un réseau externe avant soumission. |
| ~~Branch protection indisponible~~ | **Obstacle levé** : le repo est public, la protection est disponible sans upgrade. Reste à la configurer — elle ne l'est pas au 2026-08-13. |
| Repo public et fuite d'identifiants | Le dépôt est public depuis peu. `task-255` et `de3ac86` ont purgé l'email de login et l'identité de compte des fichiers suivis ; l'email racine du compte AWS prod est volontairement absent du dépôt. Tout ajout de credential dans un fichier suivi est désormais une fuite publique immédiate. |

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

# Apply infra — un root module par environnement depuis task-237, le state et les
# noms de ressources sont séparés. Jamais depuis infrastructure/terraform/ : ce
# n'est pas un root module.
terraform -chdir=infrastructure/terraform/envs/dev plan
terraform -chdir=infrastructure/terraform/envs/dev apply

# Prod vit dans un autre compte AWS (task-248) : le profil est obligatoire.
AWS_PROFILE=prod terraform -chdir=infrastructure/terraform/envs/prod plan -out=tfplan
# Garde-fou de plan. Sans 3e argument pour prod : la couche 4 (collision de noms)
# est structurellement redondante entre deux comptes séparés.
scripts/tf_plan_guard.sh prod tfplan

# Deploy Lambda containers — deux images distinctes depuis task-217
docker buildx build --platform linux/arm64 --provenance=false --sbom=false -f infrastructure/docker/lambda-api.Dockerfile .
docker buildx build --platform linux/arm64 --provenance=false --sbom=false -f infrastructure/docker/lambda.Dockerfile .

# Purge des comptes E2E orphelins (task-246 / task-247)
python scripts/purge_e2e_accounts.py
python scripts/delete_e2e_account.py <email>
```

## Appendice B — Liens internes

- `AGENTS.md` — guardrails projet
- `CLAUDE.md` — convention de création de tâches
- `.env.example` — gabarit complet des variables (20 sections numérotées)
- `infrastructure/terraform/README.md` — runbook Secrets Manager + Lambda deployment
- `infrastructure/terraform/modules/platform/secrets.tf` — coquille du secret consolidé `media-summarizer-runtime-<env>` (valeurs poussées hors-bande)
- `docs/API_LAMBDA_RUNTIME.md` — runtime API isolé, warm-up, seuil et procédure d'activation de la provisioned concurrency (`task-217`)
- `docs/DATA_RETENTION.md` — les deux horloges de rétention (`task-243`)
- `docs/compliance/` — privacy policy, terms of service, réponses App Privacy (Apple) et Data Safety (Google Play), checklist
- `docs/research/task-221-terraform-multi-env-isolation/README.md` — architecture d'isolation validée (option B)
- `docs/DEVBOX_SETUP.md` — reconstruire un poste de dev complet
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` — détails techniques mobile
- `docs/PRODUCTION_RELEASE_RUNBOOK.md` — procédure de release
- `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` — pipeline d'ingestion
- `infrastructure/terraform/` — provisioning AWS
