# V1 Launch Plan — Media Summarizer

> Plan exhaustif des étapes restantes pour mettre l'application en production.
> Date de rédaction : 2026-05-19. Dernière mise à jour : **2026-07-31**
> (réconciliation avec le worktree, AWS, GitHub Actions et EAS). Le cœur produit
> V1 est largement implémenté, mais l'application n'est pas encore déployable en
> production : seule l'infrastructure AWS dev existe, le code local n'est pas
> synchronisé/déployé, la CI est rouge, les validations E2E/device ne sont pas
> closes et les prérequis stores/billing/compliance restent incomplets.

### État de vérité au 2026-07-31

- **Phase 3 dev uniquement** : l'API AWS dev répond `HTTP 200` à chaud, mais les
  Lambdas n'ont pas été redéployées depuis le 2026-06-15 et `task-217` documente
  deux réponses API Gateway 500 après une longue période d'inactivité, suivies
  d'une première invocation à 25,7 s.
- **Pas de staging/prod isolés** : le Terraform utilise un state unique et des
  noms globaux non suffixés pour les Lambdas, tables et queues. La simple copie
  de `terraform.tfvars` avec un autre `environment` ne permet pas de faire
  coexister proprement dev/staging/prod.
- **Source non synchronisée** : `main` local est 11 commits devant
  `origin/main`, avec un changement Terraform non committé et deux fichiers de
  tâches non suivis. Les derniers checks GitHub portent donc sur un état ancien.
- **CI non verte** : le dernier `Main Branch Checks` échoue sur Ruff et ESLint.
  Localement, `ruff check .` remonte 812 erreurs ; `npm run typecheck` passe mais
  `npm run lint` échoue faute de configuration ESLint.
- **Mobile** : une build iOS development a réussi le 2026-06-11 sur le commit
  `8c63765`, mais son artifact a expiré le 2026-06-25 et elle précède les
  changements récents. Aucune build EAS Android n'existe.
- **Production release** : `docs/RELEASE_LOG.md` reste la source de vérité :
  v1.0.0 `Pre-release`, aucun tag, aucun build production, aucune soumission.
- **Backlog à réconcilier** : certaines tâches `Done` décrivent seulement la
  préparation documentaire (`task-43` à `task-45`) alors que leurs critères
  opérationnels ne sont pas réalisés ; inversement, `task-161` est `To Do`
  malgré une ancienne build iOS réussie. L'index MCP ne voit pas les tâches
  récentes. Les statuts Backlog ne doivent pas servir seuls de preuve de release
  tant que cette incohérence n'est pas corrigée.

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
| **Continue with Google** | Code OK — backend + mobile câblés. Backend Web client ID + secret OK dans `.env`. OAuth Web + iOS provisionnés côté Google Cloud | OAuth Client ID Android à créer après le keystore EAS Android (`task-162`, sans build), puis build Android unique une fois la variable déclarée + écran de consentement Google à publier en Production en Phase 10 |

---

## 1. Tâches restantes réellement bloquantes V1

Le backend V1 et le scope produit principal sont largement implémentés côté
code. Les tâches restantes ne sont cependant pas seulement des formalités
stores : plusieurs gates techniques et de sécurité doivent être fermées avant
un staging ou une soumission.

### Bloquants P0 avant staging/prod

| Zone | Tâches / preuve | Statut au 2026-07-31 |
|---|---|---|
| Isolation API Lambda | `task-217` | **À faire** — séparer l'image API minimale de l'image workers, protéger la concurrence interactive, ajouter warm-up et release health check |
| Isolation dev/staging/prod | `infrastructure/terraform/main.tf`, noms de ressources Terraform | **À faire** — state/workspace et noms de ressources ne permettent pas aujourd'hui trois environnements coexistants |
| Sécurité users legacy | `task-222`, `task-224` | **Corrigé en code** — 2026-08-05 : `create_user`, `get_user`, `get_user_by_email` et `update_user` supprimés ; `POST /api/v1/auth/verify-email` (même classe de faille, non authentifié, mutait `email_verified_at` d'un email arbitraire) supprimé également. 2026-08-12 (`task-224`) : le module `endpoints/users.py` et sa dernière route `DELETE /api/v1/users/{user_id}` sont supprimés, remplacés par `DELETE /api/account` qui déduit le compte du token (plus aucun id en path, donc plus rien à autoriser). **Reste à vérifier après déploiement AWS dev** : rejet effectif des anciennes routes publiques + run E2E complet |
| Suppression/export de compte | `mobile/app/settings/delete-account.tsx`, `media_summarizer/core/services/account_deletion_service.py`, `task-224` | **Fait en code (2026-08-12)** — suppression de compte in-app (Account > Delete Account) branchée sur `DELETE /api/account`, qui purge DynamoDB + S3 + Algolia. Le bouton `Export Data` mort est retiré : l'accès et la portabilité passent par `privacy@mediasummarizer.com` sous un mois, documenté dans la privacy policy. Le bouton `Settings` mort reste à traiter hors `task-224` |
| Source + CI | Git local/GitHub Actions | **À faire** — nettoyer, committer/pousser, corriger Ruff/ESLint/Mypy et obtenir des checks verts sur le SHA réellement déployé |

### Bloquants release immédiats

| Zone | Tâches | Statut |
|---|---|---|
| Déploiement/test backend courant | Phase 4 | Pousser/déployer le HEAD, puis re-run E2E AWS dev complet ; le runtime AWS date du 2026-06-15 |
| Mobile dev builds | `task-161`, `task-162`, `task-163` | iOS : ancienne build réussie mais expirée, **rebuild courant requis** ; Android : `task-162` crée le keystore sans build, `task-163` lance l'unique build |
| Google OAuth Android | `task-163` | À faire après `task-162`, car le SHA-1 du keystore EAS est requis. `task-163` porte aussi la déclaration de `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` côté EAS **puis** le build Android — dans cet ordre, sinon l'APK embarque `""` |
| Validation device non automatisable | `task-164`, `task-165` | À faire sur devices physiques : Apple Sign-In, Google sheet, Safari/Chrome share |
| Maestro V1 | `task-168`, `task-169`, `task-170`, `task-171`, `task-172` | Flows 06 search et 07 paywall absents ; workflow CI cassé avant exécution et résultats masqués par `|| true` |
| Clôture Phase 5 | `task-166` | Mettre ce plan à jour une fois `task-164/165/171/172` terminées |

### Bloquants pré-soumission stores

| Zone | Tâches | Statut |
|---|---|---|
| Branding app | `task-186` | Nom marketing final requis avant App Store Connect / Play Console |
| App icons | `task-180` | Remplacer les placeholders avant soumission |
| RevenueCat / IAP | Phase 6 | `REVENUCAT_WEBHOOK_SECRET` absent ; produits, offerings/entitlements et tests sandbox réels non prouvés |
| Domaine production | Phase 10 | `api.secondbrainlabs.com` et `api.mediasummarizer.com` ne résolvent pas ; le profil EAS production pointe encore vers le second |
| Store/legal | Phase 10 | Privacy/terms non hébergés (`secondbrainlabs.com/privacy` et `/terms` répondent 404), liens in-app absents, listings/screenshots/review accounts à finaliser |

### Décisions à prendre sans bloquer inutilement le premier build interne

| Zone | Tâches | Décision requise |
|---|---|---|
| Architecture LLM production | `task-212`, `task-213` | Benchmark refait avec workload chatbot, `owner_decision: pending`. Trancher avant montée en charge ; un soft launch limité peut explicitement différer la migration si le chatbot reste hors scope V1 |
| Langue YouTube Apify | `task-216` | Follow-up d'optimisation ; la traduction finale task-192 existe déjà, donc non bloquant pour le premier lancement |
| Discord community/support | `task-118` | Utile pour soft launch, non bloquant code. |
| TikTok proxy résidentiel | `task-145` | V2, explicitement non bloquant V1. |

---

## 2. Comptes et abonnements à créer

| Service | Coût | Pourquoi | Statut |
|---|---|---|---|
| **GitHub** (compte + repo privé) | gratuit | Versioning, CI/CD, releases | Partiel : repo OK, mais source locale `ahead 11`, checks rouges, branch protection indisponible sur le plan actuel et seul `AWS_DEPLOY_ROLE_ARN` est configuré dans les Actions secrets |
| **AWS** (compte) | usage-based | DynamoDB, S3, SQS, Lambda, EventBridge | Partiel : compte + infra dev OK ; aucun staging/prod isolé, aucune alarme active, déploiement runtime ancien |
| **Apple Developer Program** | $99/an | Publication App Store, TestFlight, IAP sandbox | OK (payé 2026-06-01, validé par Apple ; App ID + Sign in with Apple provisionnés) |
| **Google Play Console** | $25 one-time | Publication Play Store, Internal Testing, IAP sandbox | Payé 2026-06-01 ; statut KYC à revalider par l'owner (aucune preuve plus récente dans le repo) |
| **Expo / EAS** | gratuit (free tier) | Builds iOS/Android | Partiel : compte/projet OK ; ancienne build iOS expirée, aucune Android, aucune variable configurée dans les environnements EAS development/preview/production |
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

**État réel au 2026-07-31** : seul `media-summarizer-runtime-dev` existe dans
AWS. Aucun secret runtime staging/prod n'est provisionné. Avant d'en créer, il
faut d'abord corriger l'isolation Terraform (state + noms de ressources par
environnement), sinon un `terraform apply` avec `environment = "prod"` ne crée
pas une stack indépendante sûre.

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

`mobile/.env` est gitignored et les environnements EAS
`development`, `preview` et `production` ne contiennent actuellement aucune
variable. Les valeurs nécessaires doivent être créées côté EAS avant toute
nouvelle build distribuée ; le seul `env` versionné dans `mobile/eas.json` est
l'URL API.

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
3. **État source au 2026-07-31** : `main` local est `ahead 11` de
   `origin/main`. Le worktree contient aussi `infrastructure/terraform/ecr.tf`
   modifié et les fichiers `task-216`/`task-217` non suivis. Le dernier runtime
   AWS/GitHub correspond au commit distant `d1497a1`, pas au HEAD local
   `ef172bc`.
4. **CI actuelle rouge** :
   - dernier `Main Branch Checks` (2026-06-15) : Ruff backend et lint mobile KO ;
   - vérification locale 2026-07-31 : `ruff check .` → 812 erreurs ;
     `npm run typecheck` → OK ; `npm run lint` → KO car aucune config ESLint ;
   - Mypy n'a pas pu être revalidé localement car le binaire du venv local a un
     interpréteur invalide ; la CI doit rester la preuve après réinstallation.
5. **GitHub Actions secrets** : seul `AWS_DEPLOY_ROLE_ARN` est configuré.
   `EXPO_TOKEN`, Apple/App Store Connect, Google Play et les credentials E2E
   manquent.
6. **Branch protection** : toujours indisponible sur le repo privé avec le plan
   GitHub actuel (`HTTP 403 Upgrade to GitHub Pro or make this repository
   public`). Tant que ce choix n'est pas fait, documenter un gate manuel
   obligatoire et ne pas présenter les checks comme protégés.
7. **À faire** : nettoyer le worktree, réconcilier le backlog, committer/pousser,
   réparer les checks et obtenir plusieurs runs verts sur le SHA destiné au
   déploiement.

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
   backend/iOS et Apple OAuth sont renseignés localement. Restent à
   provisionner/valider : **Android OAuth Client ID**, publication du consent
   screen Google en Production, variables EAS, RevenueCat webhook + IAP et
   secrets runtime staging/prod.
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

**État vérifié au 2026-07-31** :

- le health check dev répond `HTTP 200` à chaud ;
- les Lambdas ont été modifiées pour la dernière fois le 2026-06-15 ;
- seul le secret `media-summarizer-runtime-dev` existe ;
- le dashboard `media-summarizer-pipeline-observability` existe ;
- **0 alarme CloudWatch media-summarizer est active** ;
- `task-217` est ouverte après deux 500 au réveil et une première invocation à
  25,7 s.

**Blocage staging/prod découvert lors de la réconciliation** : ne pas appliquer
la consigne historique « recopier `terraform.tfvars` avec un autre
`environment` » en l'état. Le backend Terraform utilise une seule clé de state
S3 (`infrastructure/terraform.tfstate`) et la majorité des ressources ont des
noms globaux (`users`, `processing_jobs`, `media-summarizer-api`, queues sans
suffixe). Il faut d'abord :

1. définir la stratégie de state/workspaces par environnement ;
2. suffixer ou paramétrer tous les noms qui doivent coexister ;
3. rendre le workflow de déploiement explicitement environnement-aware ;
4. vérifier qu'un plan staging ne modifie/détruit aucune ressource dev ;
5. seulement ensuite créer staging puis prod avec `enable_alarms = true`.

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

1. **Synchroniser et déployer le code courant** : au 2026-07-31, le runtime AWS
   date du 2026-06-15 tandis que le HEAD local est 11 commits devant
   `origin/main`. Un E2E contre le runtime actuel ne validerait donc pas la
   codebase courante.
2. **Fermer `task-217` et revalider le cold start API** avant d'utiliser le
   health check comme gate de release.
3. **Re-run complet AWS dev** : `pytest -m e2e` contre
   `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com` après
   push/déploiement. Ne pas marquer Phase 4 DONE tant que ce run n'est pas vert.
4. **Tester le digest journalier** (EventBridge rule). Pas couvert par l'E2E actuelle.
5. **Mettre en place une purge automatique** des artifacts E2E orphelins en cas de crash pytest non-recoverable (Ctrl-C). Aujourd'hui le teardown manque ce cas — script de cleanup à ajouter dans `scripts/`.
6. **Réconcilier le backlog** : l'index MCP Backlog ne voit pas les tâches
   récentes et retourne d'anciens intitulés pour certains IDs. Ne pas utiliser
   les statuts `Done` comme preuve de release avant correction de l'index.

### Phase 5 — Mobile dev build (jour 4-5) — **EN COURS, NON VALIDÉE AU 2026-07-31**

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

#### À faire

0. Corriger `scripts/mobile_release_check.sh` : le script exige encore
   `mobile/plugins/withShareExtension.js`, supprimé volontairement par
   `task-188`. Il échoue donc à tort alors que le plugin officiel
   `expo-share-intent` est configuré.
1. Configurer les variables EAS pour development/preview/production. Les trois
   environnements sont vides au 2026-07-31 et `mobile/.env` est gitignored.
2. `task-162` — créer le keystore Android via `eas credentials --platform android`
   et relever son SHA-1. **Pas de build ici** : `mobile/app.config.ts:114-115`
   cuit `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` dans `extra` au moment du build,
   donc un APK construit avant l'existence du Client ID embarque `""` de façon
   définitive. Créer le keystore seul évite le double build.
3. `task-163` — créer l'OAuth Client ID Android dans Google Cloud Console avec
   `package=com.secondbrainlabs.core` + SHA-1 EAS, déclarer
   `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` côté EAS (secret projet ou bloc `env`
   du profil `development` de `mobile/eas.json`), **puis seulement** lancer
   `eas build --platform android --profile development` — une seule fois.
4. `task-164` — validation iOS sur device physique :
   - Sign in with Apple → user créé/lié → inbox.
   - Continue with Google → `ASWebAuthenticationSession` → user créé/lié → inbox.
   - Share intent Safari → share-confirm → submit → vignette inbox.
5. `task-165` — validation Android sur device physique :
   - Continue with Google sans `DEVELOPER_ERROR`.
   - Apple button absent ou no-op clean.
   - Share intent Chrome URL.
   - Share intent texte/audio.
6. `task-168` — valider en CI le flow login/register email/password étendu.
7. `task-169` — valider en CI le nouveau flow search Algolia (`06_search.yaml`).
8. `task-170` — configurer les produits RevenueCat puis valider en CI le
   nouveau flow paywall (`07_paywall.yaml`).
9. `task-171` — run complet Maestro sur émulateur Android CI et simulateur iOS
   CI, itérer jusqu'au vert. Aucun appareil Android physique n'est requis pour
   cette couverture logique.
10. `task-172` — rendre Maestro Android réellement obligatoire sur `mobile/**`,
    documenter le lancement local.
11. `task-166` — marquer Phase 5 DONE dans ce plan une fois les tâches ci-dessus closes.

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
2. **État source** : `main` local est `ahead 11` et dirty ; les runs GitHub ne
   prouvent pas l'état courant.
3. **Main checks rouges** :
   - backend : `ruff check .` échoue massivement ; revoir le scope/exclusions et
     corriger les erreurs applicatives ;
   - mobile : typecheck OK, lint KO faute de config ESLint ;
   - Mypy doit être rejoué en CI après réparation du gate Ruff.
4. **Mobile build workflow rouge et trop agressif** :
   `.github/workflows/mobile-build-distribute.yml` lance une build production
   et tente une soumission pour chaque push `main` touchant `mobile/**`.
   Réserver les builds/submissions production à un tag ou un dispatch explicite
   et utiliser preview/internal pour la validation courante.
5. **Secrets GitHub** : les quatre secrets Maestro requis sont configurés
   (`E2E_TEST_USER_*`, `E2E_SEARCH_TEST_TERM`, clé publique RevenueCat Test
   Store). Ajouter encore `EXPO_TOKEN`, Apple/App Store Connect et le
   service account Google Play pour les workflows de distribution.
6. **Variables EAS** : aucune variable n'existe dans
   development/preview/production ; les créer avant rebuild.
7. **Maestro CI** : source réparée avec Maestro 2.8, binaires Release autonomes,
   émulateur Android, simulateur iOS manuel, rapports JUnit et vrais codes de
   sortie. Le compte AWS dev est préchargé pour Search. Le premier run de cette
   version attend encore son commit/push ; le paywall restera rouge tant que
   les trois produits ne sont pas exposés par l'offering RevenueCat.
8. **Branch protection** : choisir GitHub Pro/repo public ou formaliser un gate
   manuel ; la protection n'est pas disponible avec le plan privé actuel.
9. Vérifier le rollback Lambda avec deux images API/worker immuables après
   `task-217`, puis documenter l'exercice.

### Phase 8 — Monitoring & observabilité (jour 7-8)

> Le provisioning Terraform de dashboard/alarms a été ajouté (`task-114`, `task-46`), puis adapté à la migration Lambda. La validation restante est opérationnelle : activer les alarmes en staging/prod et vérifier les signaux CloudWatch réels.
>
> **État 2026-07-31** : le dashboard
> `media-summarizer-pipeline-observability` existe, mais AWS retourne
> **0 alarme `media-summarizer*` active**. Le monitoring n'est donc pas un gate
> opérationnel aujourd'hui.

1. CloudWatch Dashboard à vérifier avec :
   - Latence API (`API_SLOW_REQUEST_THRESHOLD_MS` → alarmes)
   - Profondeur des queues SQS (alarme si DLQ > 0, en particulier `document-parsing-queue`)
   - Taux d'erreur Deepgram / OpenAI / **LlamaParse / Unstructured** (logs structurés `parser=llamaparse|unstructured` + `error_code`)
   - Coût par source (X, TikTok, Instagram, YouTube, podcasts, **documents**)
   - Compteur quota LlamaParse (1000 pages/jour free tier) — alarme si fallback Unstructured déclenché plus de N fois/heure
2. CloudWatch Alarms → SNS → e-mail (`enable_alarms = true` en staging/prod).
3. Vérifier que les logs structurés tombent bien dans CloudWatch Logs Insights.

### Phase 9 — Staging end-to-end (jour 8-9)

0. **Débloquer l'isolation Terraform** : state et noms de ressources séparés
   par environnement, avec preuve qu'un plan staging ne touche pas dev.
1. Déployer l'environnement `staging` séparé de `dev` et `prod`, son secret
   runtime et ses alarmes.
2. Créer un vrai endpoint/domaine staging et l'injecter dans EAS + Maestro.
3. Tester depuis un device physique avec une URL réelle de chaque source.
4. Vérifier qu'aucun secret prod ne fuit en staging.
5. Charger 50-100 URLs en parallèle pour vérifier le scaling SQS / Lambda.
6. Vérifier RevenueCat sandbox → backend webhook en staging.
7. Mesurer cold/warm API, profondeur SQS, DLQ et coût avant passage prod.

### Phase 10 — Pré-lancement (jour 10+)

0. **Rebrand mobile placeholder name** (cf. task-186) — l'app utilise actuellement le nom legacy `Media Summarizer` partout (display name, slug Expo, scheme deep link, share extension iOS). À exécuter **avant** la sous-étape 1 ci-dessous : tous les textes Apple App Store Connect (App Information, screenshots) et Google Play Console + Google OAuth Branding consomment le nom marketing définitif. Coût ~30 min en pré-distribution, beaucoup plus élevé une fois publié. Ne touche pas le bundle id `com.secondbrainlabs.core` (figé). Voir `task-186` pour la checklist exacte des 8-9 endroits à mettre à jour.

0bis. **Couper l'API du custom domain `api.secondbrainlabs.com`** — pendant le dev (Phase 5), l'app mobile + Apple Sign-In Service ID + `APPLE_REDIRECT_URI` côté backend tapent tous l'URL brute API Gateway `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`. En Phase 10, on bascule sur le custom domain. Étapes :
   - **État 2026-07-31** : `api.secondbrainlabs.com` ne résout pas et
     `api.mediasummarizer.com` ne résout pas non plus. Le profil EAS production
     pointe toujours vers `https://api.mediasummarizer.com`.
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
4. **Légal** :
   - Politique de confidentialité hébergée publiquement.
   - CGU avec mention RevenueCat / abonnements.
   - Conformité RGPD : droit à l'oubli, accès et portabilité.
   - Ajouter les liens Privacy/Terms sur login/register et Account.
   - **Fait (`task-224`, 2026-08-12)** : suppression de compte in-app
     (Account > Delete Account → `DELETE /api/account`) qui purge DynamoDB, S3 et
     l'index Algolia ; l'ancienne `DELETE /api/v1/users/{user_id}`, qui ne
     supprimait que la ligne `users`, est supprimée. Le bouton `Export Data` mort
     est retiré, l'accès (art. 15) et la portabilité (art. 20) sont traités
     manuellement par mail sous un mois, documenté en privacy policy §8.
   - **Prérequis déploiement** : appliquer Terraform (`s3:DeleteObject` sur le
     bucket bug-reports) **avant** de déployer l'API, sinon tout user ayant joint
     une capture d'écran reçoit un 500 au lieu d'une suppression.
   - **État 2026-07-31** : `secondbrainlabs.com/privacy` et `/terms` répondent
     404 ; les anciens domaines `mediasummarizer.com` ne résolvent pas.
5. **Site landing minimal** (optionnel) : `<your-domain>` avec CTA App Store / Play Store.
6. **Soft launch** : un seul pays, 100 users, observer 1 semaine avant rollout global.

---

## 5. Ce qui reste **bloqué** sur des credentials externes / owner-only

Les comptes principaux sont largement provisionnés. Les blocages restants sont surtout liés aux stores, aux builds EAS interactifs et aux dashboards tiers.

- [x] AWS account + IAM admin user `second-brain-app-admin` (AdministratorAccess) + alarme billing $50/mois (us-east-1) configurée
- [x] Apple Developer Program payé ($99) au 2026-06-01, validé par Apple
- [x] **Apple Sign in with Apple Service ID + Key (.p8) + App ID + Team ID + Key ID** provisionnés au 2026-06-08 (cf. Phase 2.8) — toutes les vars Apple dans `.env` renseignées : `APPLE_CLIENT_ID` (Service ID), `APPLE_PRIVATE_KEY` (PEM single-line), `APPLE_REDIRECT_URI` prod, `APPLE_TEAM_ID`, `APPLE_KEY_ID`.
- [ ] Google Play Console payé ($25) au 2026-06-01 — **statut KYC à
  revalider par l'owner**, l'information « en cours » n'a pas été actualisée
  depuis juin
- [x] Google Cloud Console : projet `media-summarizer` créé, OAuth consent screen configuré (Branding `Second Brain`, External, scopes openid+email+profile), mode Test avec utilisateur test ajouté, **2 OAuth Client IDs créés (Web backend + iOS)** — `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` dans `.env` racine ; `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB` + `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS` dans `mobile/.env` (naming aligné avec `mobile/app.config.ts`, corrigé 2026-06-08)
- [ ] Google Cloud Console **Android OAuth Client ID** à créer en Phase 5 après
  le premier build Android ; aucune build Android ni SHA-1 EAS n'existe au
  2026-07-31 → `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`
- [ ] Google Cloud Console **publication OAuth (Test → Production)** à faire en Phase 10 juste avant le lancement
- [x] X Developer App approuvée + bearer token (en local dans `.env`)
- [x] Apify API tokens + actor IDs obtenus — en local dans `.env` (Instagram Reel/Post, YouTube, TikTok selon fallback chain)
- [x] LlamaParse API key obtenue (free tier 1000 pages/jour) — en local dans `.env`
- [x] Unstructured.io API key obtenue (15 000 pages gratuites au démarrage) — en local dans `.env`
- [x] PodcastIndex API key + secret obtenus (en local dans `.env`)
- [x] OpenAI API key + budget configuré (en local dans `.env`)
- [x] Deepgram API key + budget configuré (en local dans `.env`)
- [x] Algolia App créée + index configuré (App ID + Admin API key + index name en local dans `.env`)
- [~] RevenueCat — clés backend et mobiles présentes localement au 2026-07-31,
  mais `REVENUCAT_WEBHOOK_SECRET` reste vide. Restent à faire : webhook sur le
  futur endpoint staging/prod, 3 produits IAP iOS/Android, import dans RC,
  Entitlements + Offerings, comptes sandbox/license testers, achat/restore et
  propagation vers quotas
- [x] Pricing admin secret généré au 2026-06-08 (`PRICING_ADMIN_SECRET` en local dans `.env`, requis pour `PUT /api/pricing/admin`)
- [ ] EAS iOS development build **courante** : l'ancienne build du 2026-06-11
  a expiré et précède le HEAD actuel (`task-161`)
- [ ] SHA-1 keystore Android via `eas credentials`, sans build (`task-162`)
- [ ] EAS Android development build : aucune build Android au 2026-07-31 ;
  lancée une seule fois en fin de `task-163`, après déclaration du Client ID
- [ ] Variables EAS development/preview/production : aucun env configuré ;
  injecter API URL, OAuth, RevenueCat et feedback selon le profil
- [ ] Nom marketing final : requis avant `task-186`, App Store Connect, Play Console et Google OAuth Branding
- [ ] Icônes finales : `task-180`, requis avant soumission stores
- [ ] Domaines : rendre `api.secondbrainlabs.com`, `/privacy`, `/terms` et
  l'URL support publics avant la build production
- [ ] Architecture LLM production : valider ou différer explicitement
  `task-212` selon le scope chatbot du soft launch

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
| API interactive indisponible après longue inactivité | Fermer `task-217` : image API minimale, reserved concurrency configurable, warm-up et health gate public mesuré. |
| Collision/destruction entre dev/staging/prod | Séparer state/workspaces et suffixer les ressources avant tout plan/apply hors dev. |
| CRUD users legacy non authentifié | Retirer/isoler la surface publique legacy et implémenter une suppression de compte authentifiée + purge complète avant production. |
| État local non poussé sur GitHub | `main` local est `ahead 11` et dirty ; avant de valider CI/CD ou préparer stores, committer/pousser puis relancer les workflows GitHub. |
| CI donnant un faux sentiment de sécurité | Corriger Ruff/ESLint/Mypy ; retirer les `|| true` de Maestro ; ne déployer que le SHA ayant passé les gates. |
| Build mobile sans secrets runtime | Créer les variables EAS par environnement ; `mobile/.env` gitignored ne constitue pas une configuration de build distante. |
| Domaine/légal indisponible | Rendre l'API production, privacy, terms et support publics avant soumission ; vérifier les URLs depuis un réseau externe. |
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

# Apply infra — un root module par environnement depuis task-237, le state et les
# noms de ressources sont séparés. Jamais depuis infrastructure/terraform/ : ce
# n'est pas un root module.
terraform -chdir=infrastructure/terraform/envs/dev plan
terraform -chdir=infrastructure/terraform/envs/dev apply

# Deploy Lambda container (GitHub Actions target; local equivalent uses the same Dockerfile/ECR)
docker buildx build --platform linux/arm64 --provenance=false --sbom=false -f infrastructure/docker/lambda.Dockerfile .
```

## Appendice B — Liens internes

- `AGENTS.md` — guardrails projet
- `CLAUDE.md` — convention de création de tâches
- `.env.example` — gabarit complet des variables (20 sections numérotées)
- `infrastructure/terraform/README.md` — runbook Secrets Manager + Lambda deployment
- `infrastructure/terraform/secrets.tf` — secret consolidé `media-summarizer-runtime-<env>`
- `infrastructure/terraform/terraform.tfvars.example` — modèle `secret_payload` à recopier
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` — détails techniques mobile
- `docs/PRODUCTION_RELEASE_RUNBOOK.md` — procédure de release
- `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` — pipeline d'ingestion
- `infrastructure/terraform/` — provisioning AWS
