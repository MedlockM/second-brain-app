# Plan de Préparation au Déploiement Production - Media Summarizer

## Sommaire

1. [Décisions Stratégiques à Trancher](#décisions-stratégiques-à-trancher)
2. [Chantier 1: Authentification et Contrôle d'Accès](#chantier-1-authentification-et-contrôle-daccès)
3. [Chantier 2: Paiements et Crédits (Stripe)](#chantier-2-paiements-et-crédits-stripe)
4. [Chantier 3: Alignement Modèle de Données / Infrastructure](#chantier-3-alignement-modèle-de-données--infrastructure)
5. [Chantier 4: Durcissement API et Productisation](#chantier-4-durcissement-api-et-productisation)
6. [Chantier 5: Détails Intégration OpenAI](#chantier-5-détails-intégration-openai)
7. [Chantier 6: Observabilité et CI/CD](#chantier-6-observabilité-et-cicd)
8. [Chantier 7: Configuration de Déploiement Production](#chantier-7-configuration-de-déploiement-production)
9. [Chantier 8: Industrialisation Email (SES)](#chantier-8-industrialisation-email-ses)
10. [Plan d'Exécution Phasé](#plan-dexécution-phasé)
11. [Checklists de Validation](#checklists-de-validation)
12. [Annexe: Mapping Variables d'Environnement](#annexe-mapping-variables-denvironnement)

---

## Décisions Stratégiques à Trancher

### Décisions Produit
1. Modèle de monétisation “minutes” (remplace les crédits)
   - Abonnements S/M/L: S=240 min (2€), M=840 min (5€), L=1 980 min (10€)
   - Packs minutes: 100/1,50€; 300/3€; 600/6€; 1 200/10€ (validité 6 mois)
   - Débit au réel (arrondi à la minute), rollover 1 mois des minutes d’abonnement
2. Authentification: OAuth social (Google/Apple) + fallback email/mot de passe (30 jours, httpOnly). Magic Link abandonné.
3. Gratuité de départ (optionnelle): offrir un petit pack de minutes à l’inscription ? (ex: 30 min)
4. Politique d’usage: si pool insuffisant → proposer pack ou upgrade (prorata Stripe)

### Décisions Techniques
1. Infrastructure cible: ECS Fargate (recommandé)
2. Domaine/certificats: domaine acquis + ACM (HTTPS)
3. Région AWS: eu-west-1 (RGPD)
4. Modèle OpenAI: gpt-4-turbo-preview

## Décision V1: Mise en sommeil du système de forecast des minutes

Objectif: retirer le forecast des endpoints publics et des modèles pour la V1 sans supprimer le code, afin de pouvoir le reprendre en V2.

Changements appliqués
- API
  - Router "follows" (gestion des follows + calcul/stockage forecast) non monté → endpoints /api/v1/follows* indisponibles et absents d’OpenAPI.
  - Endpoint /api/v1/podcast-search/episodes: suppression du bloc "forecast" dans la réponse et du calcul associé.
- Modèles
  - Suppression du modèle ForecastInfo et du champ forecast dans EpisodesListResponse (OpenAPI n’expose plus ce schéma).
- Billing
  - /api/v1/billing/me: retrait des champs liés aux réservations/forecast; la réponse ne reflète plus ce concept en V1.
- Code conservé pour V2
  - Le service core/services/forecast_service.py, minute_db (feed_forecasts), les scripts et tests restent en place.

Reprise en V2 (plan de réactivation)
- Remonter le router follows dans api/main.py et réintroduire le modèle ForecastInfo + champ forecast dans EpisodesListResponse.
- Réactiver le bloc forecast dans l’endpoint /episodes et, si besoin, revoir l’agrégat billing pour ré-exposer des métriques de réservation.

---

## Chantier 1: Authentification et Contrôle d'Accès

### 1.1 Objectif
Mettre en place OAuth social (Google/Apple) avec sessions persistantes 30 jours (cookies httpOnly) et fallback local email/mot de passe. Protéger toutes les routes sensibles et corriger/maintenir CORS.

### 1.2 État Actuel
- Auth baseline (local) implémentée:
  - Endpoints: `/api/v1/auth/register`, `/login`, `/refresh`, `/logout`, `/me`
  - Access token court (JWT) + refresh token en cookie httpOnly (30 jours absolus, rotation à chaque refresh)
  - `get_current_user()` valide le JWT et protège les routes sensibles (ex: submit-episode)
  - Modèle `User` enrichi: `password_hash`, `auth_provider`, `provider_id`, `email_verified_at`, etc.
  - CORS aligné sur `CORS_ORIGINS`
- OAuth social (Google/Apple): non implémenté (prévu, cf. PLAN.md)

### 1.3 Changements à Réaliser

#### A. Google OAuth (OIDC)
- Endpoints: `GET /api/v1/auth/google/login` (redirige vers Google), `GET /api/v1/auth/google/callback` (échange code -> id_token)
- Vérifier l’id_token (signature, aud, iss), extraire `sub`, email, name, picture
- Si user existe par email: lien du compte (renseigner `auth_provider=google`, `provider_id=sub`)
- Sinon: créer user (`auth_provider=google`, `provider_id=sub`, `email_verified_at` now)
- Émettre refresh cookie (30j) + access token, puis rediriger frontend (FRONTEND_URL)

#### B. Apple OAuth
- Endpoints: `GET /api/v1/auth/apple/login`, `POST/GET /api/v1/auth/apple/callback`
- Générer client_secret (JWT signé) à partir de `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY`
- Échanger code, vérifier id_token (iss, aud), extraire `sub`/email
- Même logique de liaison/création que Google

#### C. Dépendances et sécurité
- Ajouter Authlib (ou équivalent) pour OAuth/OIDC
- Cookies: `httpOnly`, `SameSite=Lax` (ou `None` si cross-site), `Secure` en production, `COOKIE_DOMAIN` configuré
- Rate limiting déjà en place (slowapi)

#### D. API et docs
- Conserver les endpoints locaux (fallback)
- Ajouter documentation OpenAPI (schémas/flows), descriptions des redirections et des cookies

### 1.4 Variables d'Environnement

```bash
# JWT & sessions
JWT_SECRET_KEY=<from-secrets>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
COOKIE_NAME_REFRESH=refresh_token
COOKIE_SECURE=true            # en production
COOKIE_SAMESITE=lax           # ou none si cross-site avec HTTPS
COOKIE_DOMAIN=app.yourdomain.com

# CORS / Frontend
CORS_ORIGINS=https://app.yourdomain.com
FRONTEND_URL=https://app.yourdomain.com

# Google OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/google/callback

# Apple OAuth
APPLE_CLIENT_ID=...
APPLE_TEAM_ID=...
APPLE_KEY_ID=...
APPLE_PRIVATE_KEY=<base64_or_ssm_reference>
APPLE_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/apple/callback
```

### 1.5 Critères d'Acceptation
- [ ] Connexion via Google fonctionnelle (profil minimal récupéré, session établie)
- [ ] Connexion via Apple fonctionnelle
- [ ] Fallback local (register/login/refresh/logout) opérationnel
- [ ] Cookies httpOnly + Secure (prod), rotation du refresh à chaque `/refresh`
- [ ] Les routes sensibles retournent 401 sans access token valide
- [ ] CORS respecte `CORS_ORIGINS`

### 1.6 Tests
- **Unitaires** :
  - Création/validation JWT, rotation refresh, cookies
  - Normalisation user (auth_provider/provider_id)
- **Intégration** :
  - Mocks Google/Apple (id_token valides/invalides, lien de compte, premier login)
- **E2E** :
  - Parcours complet depuis le frontend (login social -> retour -> `/me` -> accès route protégée)

### 1.7 Risques et Mitigations
- **Risque** : Exigence HTTPS et domaine pour cookies Secure/OAuth callbacks
  - **Mitigation** : Domaines/ACM prévus en Chantier 7, sandbox local avec callbacks localhost
- **Risque** : Account takeover via collision email
  - **Mitigation** : Vérification stricte d’email vérifié par provider + stratégie de lien de comptes
- **Risque** : Complexité Apple (JWT client secret)
  - **Mitigation** : Scripts de génération et rotation, stockage secret sécurisé (SSM/Secrets Manager)

### 1.8 Livrables
- [ ] Endpoints Google/Apple (`/auth/google/*`, `/auth/apple/*`)
- [ ] Ajout Authlib, configuration OIDC
- [ ] Intégration cookies et rotation refresh
- [ ] Documentation OpenAPI + guide d’auth (docs/AUTHENTICATION_SETUP.md)
- [ ] Tests unitaires/intégration

### 1.9 Spotify OAuth (Link Account) — Readiness Checklist
- Configuration
  - [ ] SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET / SPOTIFY_REDIRECT_URI définis (dev/staging/prod)
  - [ ] Redirect URI whitelistee dans le dashboard Spotify pour chaque environnement
- Sécurité
  - [ ] Cookies: Secure=true en prod ; SameSite adapté (None si front ≠ domaine, sur HTTPS)
  - [ ] Aucun logging de tokens Spotify (access/refresh)
- Observabilité
  - [ ] Logs d’erreurs callback (state_mismatch, token_exchange_failed, profile_fetch_failed, persistence_failed)
- Tests de fumée (staging)
  - [ ] Utilisateur connecté → /api/v1/auth/spotify/login → consentement → /api/v1/auth/spotify/callback → redirection succès
  - [ ] Inspection DB: champs spotify_* peuplés sur l’utilisateur
  - [ ] Cas erreur: state mismatch redirige bien vers error

---

## Front-end — Auth pattern recommandé (à implémenter)

Vue condensée
- Modèle: access token court en mémoire + refresh cookie httpOnly (30 jours absolus)
- À l’auth (register/login/social): le serveur pose refresh_token en cookie httpOnly; le front stocke l’access_token en mémoire uniquement (pas de localStorage)
- Intercepteur HTTP:
  - Ajoute Authorization: Bearer <access_token en mémoire>
  - Sur 401/expired → POST /api/v1/auth/refresh (le cookie est envoyé automatiquement), met à jour l’access_token, rejoue la requête
  - Sur 401 de /refresh → redirige vers la page de login
- Sécurité prod: COOKIE_SECURE=true, SameSite=None si front≠API (HTTPS), COOKIE_DOMAIN configuré; CORS_ORIGINS sur le domaine front

Optimisations courantes
- Proactif: rafraîchir T-2 minutes avant exp (décodage exp du JWT côté front)
- Multi-onglets: synchroniser un refresh unique via BroadcastChannel/Storage events
- Backoff: en cas d’échecs réseau, retry limité puis signout
- Tracing: ajouter un header X-Client-Request-Id pour corréler les retries

Tâches front à planifier
- [ ] Intercepteur HTTP pour auto-refresh et rejouer la requête initiale
- [ ] Gestion multi-onglets (BroadcastChannel)
- [ ] Gestion proactive du refresh (timer avant exp)
- [ ] Page de login + gestion 401 /refresh → redirection
- [ ] Configuration CORS/SameSite/COOKIE_SECURE alignée prod

---

## Chantier 2: Monétisation en minutes (Stripe)

### 2.1 Objectif
Basculer vers un modèle “minutes” avec abonnements (S/M/L) et packs one-shot. Créditer un pool de minutes, débiter au réel, gérer rollover 1 mois, et piloter le tout via Stripe (checkout + webhooks) et des “minute buckets”.

### 2.2 État Actuel
- Code actuel orienté “crédits” (endpoints /credits/*, modèles CreditTransaction, etc.).
- Intégration Stripe en place pour l’achat de crédits (à remplacer par abonnements + packs minutes).

### 2.3 Changements à Réaliser

#### A. Endpoints Billing (API)
- POST /api/v1/billing/subscriptions/checkout { tier: S|M|L }
- POST /api/v1/billing/packs/checkout { minutes: 100|300|600|1200 }
- POST /api/v1/billing/customer-portal
- GET  /api/v1/billing/me (statut abonnement, buckets, prochain cycle)
- GET  /api/v1/billing/history (abonnements + packs)
- POST /api/v1/payments/webhook (conservé): traite les événements Stripe suivants:
  - checkout.session.completed (mode=payment|subscription)
  - invoice.payment_succeeded (création bucket d’abonnement pour la période)
  - customer.subscription.created/updated/deleted (sync statut)

#### B. Produits/Prices Stripe
- Abonnements (prices mensuels): STRIPE_PRICE_ID_SUB_S / SUB_M / SUB_L
- Packs minutes: STRIPE_PRICE_ID_PACK_100 / 300 / 600 / 1200
- URLs de succès/annulation: STRIPE_SUCCESS_URL / STRIPE_CANCEL_URL

#### C. Minute Buckets et usage
- minute_buckets: enregistre les minutes disponibles (source=subscription|pack|rollover|migration, minutes_total, minutes_remaining, expires_at)
- minute_usage: holds/finalize par job (status=held/finalized/released/expired)
- Rollover: fin de période -> créer un bucket “rollover” (expiration = fin du mois suivant)
- Ordre de consommation: rollover → abonnement courant → packs par expiration
- Débit au réel: minutes = ceil(durée_secondes / 60)

#### D. Dépréciation de l’ancien système
- Supprimer /credits/* et la logique CreditTransaction après migration one-shot (1 crédit = 1 minute)
- Supprimer /payments/intent|confirm|refund (paiement packs via Checkout + webhooks)

#### E. Réservations “soft” (follows) et prévision
- Mettre en place des réservations non bloquantes par podcast suivi pour estimer la consommation mensuelle.
- Règles de prévision: 4/3/2/<1 mois selon l’horizon; recalcul mensuel automatique.
- Exposer la prévision dans /billing/me (prévision totale et par source) sans empêcher les soumissions.

#### F. Intégration workers et états
- À la soumission d’un épisode: place_hold(job_id, estimate) via MinutePoolService.
- Après le download (durée réelle connue): finalize(actual) pour débiter les minutes réelles; release_hold en cas d’échec.
- Si le pool est insuffisant à la soumission: marquer le job en WAITING_FOR_MINUTES (sans échec), et le reprendre automatiquement lorsque des minutes deviennent disponibles (achat, rollover, renouvellement).

### 2.4 Variables d'Environnement
```bash
STRIPE_API_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
# Abonnements
STRIPE_PRICE_ID_SUB_S=price_xxx
STRIPE_PRICE_ID_SUB_M=price_xxx
STRIPE_PRICE_ID_SUB_L=price_xxx
# Packs minutes
STRIPE_PRICE_ID_PACK_100=price_xxx
STRIPE_PRICE_ID_PACK_300=price_xxx
STRIPE_PRICE_ID_PACK_600=price_xxx
STRIPE_PRICE_ID_PACK_1200=price_xxx
# Redirections
STRIPE_SUCCESS_URL=https://app.yourdomain.com/payment-success
STRIPE_CANCEL_URL=https://app.yourdomain.com/payment-cancel
```

### 2.5 Critères d'Acceptation
- [ ] Checkout abonnement/pack opérationnel
- [ ] Webhooks idempotents (stripe_events) et sécurisés (signature)
- [ ] Buckets minutes créés correctement aux événements (packs et factures d’abonnement)
- [ ] Rollover mensuel effectif
- [ ] Dashboard /billing/me exact (minutes libres/réservées, prévision totale)

### 2.6 Tests
- **Unitaires** : services Stripe V2, minute pool (allocation, holds, finalize, release)
- **Intégration** : Stripe CLI pour webhooks (subscription + payment)
- **E2E** : souscription, achat pack, soumission épisode, débit au réel, rollover

### 2.7 Risques et Mitigations
- **Risque** : double crédit sur retry webhook
  - **Mitigation** : table d’idempotence existante (stripe_events)
- **Risque** : conflits de débit concurrent
  - **Mitigation** : ConditionExpression DynamoDB lors des débits/retours de minutes

### 2.8 Livrables
- [ ] Endpoints billing (subscriptions/packs/me/history)
- [ ] Webhooks V2 (subscriptions + packs)
- [ ] MinutePoolService et tables minute_buckets/minute_usage
- [ ] Migration crédits→minutes (script)
- [ ] Documentation mise à jour (PAYMENT_SYSTEM)

---



## Chantier 3: Alignement Modèle de Données / Infrastructure

### 3.1 Objectif
Aligner parfaitement les ressources AWS (DynamoDB, S3, SQS) avec les attentes du code.

### 3.2 État Actuel

**Code attend** (`media_summarizer/utils/database_async.py`) :
- Tables : `users`, `processing_jobs`, `subscriptions`, `minute_buckets`, `minute_usage`, `follows`, `stripe_events`
- GSIs : `email-index`, `user-index`, `status-index`, `expiry-index`, `job-index`

**Terraform a** (`infrastructure/terraform/scaling.tf`) :
- Tables avec noms différents et attributs incomplets
- Pas de configuration DLQ
- Buckets S3 sans nommage unique

### 3.3 Changements à Réaliser

#### A. Corriger Terraform

**Modifier** : `infrastructure/terraform/dynamodb.tf`
```hcl
resource "aws_dynamodb_table" "users" {
  name = "users"  # Exactement ce nom
  billing_mode = "PAY_PER_REQUEST"
  hash_key = "id"

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "email"
    type = "S"
  }

  global_secondary_index {
    name = "email-index"  # Exactement ce nom
    hash_key = "email"
    projection_type = "ALL"
  }
}

# Idem pour processing_jobs et credit_transactions
```

#### B. SQS avec DLQ

**Modifier** : `infrastructure/terraform/sqs.tf`
```hcl
resource "aws_sqs_queue" "audio_download_dlq" {
  name = "audio-download-dlq"
}

resource "aws_sqs_queue" "audio_download" {
  name = "audio-download-queue"  # Exactement ce nom
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.audio_download_dlq.arn
    maxReceiveCount = 3
  })
}

# Idem pour les autres queues
```

#### C. S3 avec noms uniques

**Modifier** : `infrastructure/terraform/s3.tf`
```hcl
resource "aws_s3_bucket" "audio" {
  bucket = "media-summarizer-audio-${data.aws_caller_identity.current.account_id}-${var.environment}"
  # Exporter le nom dans les outputs
}

output "audio_bucket_name" {
  value = aws_s3_bucket.audio.id
}
```

### 3.4 Variables d'Environnement

```bash
# Injectées depuis Terraform outputs
AUDIO_BUCKET=${audio_bucket_name}
TRANSCRIPT_BUCKET=${transcript_bucket_name}
SUMMARY_BUCKET=${summary_bucket_name}
```

### 3.5 Critères d'Acceptation
- [ ] Tables DynamoDB avec les bons noms et GSIs
- [ ] Queues SQS avec DLQ configurées
- [ ] Buckets S3 avec noms uniques
- [ ] Variables d'env alignées avec Terraform outputs

### 3.6 Tests
- **Terraform** : `terraform apply` crée tout correctement
- **Application** : Connexion réussie à toutes les ressources

### 3.7 Risques et Mitigations
- **Risque** : Migration de données existantes
  - **Mitigation** : Script de migration si données en prod

### 3.8 Livrables
- [ ] Terraform corrigé et testé
- [ ] Script de migration données (si nécessaire)
- [ ] Documentation mapping ressources

---

## Chantier 4: Durcissement API et Productisation

### 4.1 Objectif
Sécuriser l'API, implémenter rate limiting, gérer les remboursements automatiques, et valider strictement les entrées.

### 4.2 État Actuel
- `submit_episode_for_processing` sans auth, crée users automatiquement
- Pas de rate limiting malgré RATE_LIMIT_PER_MINUTE dans env
- Pas de remboursement auto en cas d'échec
- Validation URL basique (juste http/https)

### 4.3 Changements à Réaliser

#### A. Sécuriser submit_episode

**Modifier** : `media_summarizer/api/endpoints/podcast_search.py`
```python
@router.post("/submit-episode")
async def submit_episode_for_processing(
    request: EpisodeSelectionRequest,
    current_user: AuthUser = Depends(get_current_user),  # AJOUT
    db=Depends(get_db)
):
    # Utiliser current_user au lieu de créer/chercher par email
```

#### B. Rate Limiting

**Installer** : `slowapi`
**Modifier** : `media_summarizer/api/main.py`
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[os.getenv("RATE_LIMIT_PER_MINUTE", "60/minute")]
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

#### C. Libération automatique des minutes en cas d'échec

Adapter le traitement d’échec des jobs pour libérer les minutes placées en hold.

**Modifier** : `media_summarizer/workers/base_worker.py`
```python
# Remplacer refund_credits_on_failure() par release_hold_on_failure()
# Appeler MinutePoolService.release_hold(job_id) si le job échoue définitivement
```

#### D. Validation stricte

**Créer** : `media_summarizer/core/validators.py`
```python
def validate_audio_url(url: str) -> bool:
    # - HTTPS only en prod
    # - Whitelist domaines connus
    # - Taille max via HEAD request
    # - Timeout strict
```

### 4.4 Variables d'Environnement

```bash
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=500
ALLOWED_AUDIO_DOMAINS=*.podbean.com,*.spotify.com,*.apple.com
MAX_AUDIO_SIZE_MB=500
DOWNLOAD_TIMEOUT_SECONDS=60
```

### 4.5 Critères d'Acceptation
- [ ] submit_episode nécessite authentification
- [ ] Rate limiting fonctionnel (429 après limite)
- [ ] Remboursement auto en cas d'échec job
- [ ] URLs audio validées strictement
- [ ] Timeouts sur tous les appels externes

### 4.6 Tests
- **Rate limiting** : Bombarder l'API, vérifier 429
- **Remboursement** : Simuler échec, vérifier crédit rendu
- **Validation** : Tester URLs malveillantes

### 4.7 Risques et Mitigations
- **Risque** : SSRF via URL audio
  - **Mitigation** : Whitelist domaines, sandbox download

### 4.8 Livrables
- [ ] Rate limiting configuré
- [ ] Système de remboursement auto
- [ ] Validateurs stricts
- [ ] Tests de sécurité

---

## Chantier 5: Détails Intégration OpenAI

### 5.1 Objectif
Paramétrer le modèle LLM, gérer les erreurs, logger les coûts sans exposer les secrets.

### 5.2 État Actuel
- `media_summarizer/workers/summarization/summarization_worker.py`
- Modèle "gpt-4" hardcodé
- Pas de retry sophistiqué
- Pas de logging des coûts

### 5.3 Changements à Réaliser

#### A. Paramétrer le modèle

**Modifier** : `media_summarizer/workers/summarization/summarization_worker.py`
```python
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4-turbo-preview")
MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "2000"))

payload = {
    "model": LLM_MODEL,
    "max_tokens": MAX_TOKENS,
    "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.7"))
}
```

#### B. Logging des coûts

```python
# Après réponse OpenAI
usage = result.get("usage", {})
logger.info(f"OpenAI usage for job {job_id}: "
           f"prompt_tokens={usage.get('prompt_tokens')}, "
           f"completion_tokens={usage.get('completion_tokens')}, "
           f"estimated_cost=${calculate_cost(usage)}")
```

#### C. Gestion d'erreur améliorée

```python
# Fallback si parsing JSON échoue
if not isinstance(summary_data, dict):
    summary_data = {
        "summary": content,
        "main_topics": ["Résumé non structuré"],
        "key_points": [],
        "conclusion": "Voir résumé complet ci-dessus"
    }
```

### 5.4 Variables d'Environnement

```bash
LLM_MODEL=gpt-4-turbo-preview
LLM_MAX_TOKENS=2000
LLM_TEMPERATURE=0.7
LLM_TIMEOUT_SECONDS=120
LLM_MAX_RETRIES=3
```

### 5.5 Critères d'Acceptation
- [ ] Modèle configurable via env
- [ ] Coûts loggés sans exposer la clé API
- [ ] Fallback si réponse non-JSON
- [ ] Timeout et retry configurables

### 5.6 Tests
- **Mock OpenAI** : Tester différentes réponses
- **Timeout** : Simuler lenteur, vérifier retry

### 5.7 Risques et Mitigations
- **Risque** : Coûts OpenAI explosent
  - **Mitigation** : Limites de tokens, alertes sur usage

### 5.8 Livrables
- [ ] Configuration LLM flexible
- [ ] Logging des coûts
- [ ] Gestion d'erreur robuste

---

## Chantier 6: Observabilité et CI/CD

### 6.1 Objectif
Mettre en place CI/CD complet, monitoring, alerting, et logging centralisé.

### 6.2 État Actuel
- Tests CI : `.github/workflows/integration-tests.yml`
- Pas de build/push images
- Logs basiques Python
- Pas de métriques

### 6.3 Changements à Réaliser

#### A. CI/CD Pipeline

**Créer** : `.github/workflows/build-and-push.yml`
```yaml
name: Build and Push to ECR
on:
  push:
    tags:
      - 'v*'
jobs:
  build:
    steps:
      - name: Configure AWS credentials
      - name: Login to ECR
      - name: Build and push API image
      - name: Build and push Worker image
      - name: Build and push Whisper image
      - name: Update ECS task definitions
      - name: Deploy to ECS
```

#### B. Monitoring CloudWatch

**Créer** : `infrastructure/terraform/monitoring.tf`
```hcl
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name = "media-summarizer-api-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods = "2"
  metric_name = "5XXError"
  namespace = "AWS/ApplicationELB"
  period = "60"
  statistic = "Sum"
  threshold = "10"
}

resource "aws_cloudwatch_metric_alarm" "queue_age" {
  alarm_name = "media-summarizer-queue-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods = "2"
  metric_name = "ApproximateAgeOfOldestMessage"
  namespace = "AWS/SQS"
  period = "300"
  statistic = "Maximum"
  threshold = "3600"  # 1 heure
}
```

#### C. Logging structuré

**Modifier** : Tous les workers et API
```python
import json
logger.info(json.dumps({
    "event": "job_processed",
    "job_id": job_id,
    "duration": duration,
    "status": "success"
}))
```

#### D. Intégration Sentry (Optionnel)

**Modifier** : `media_summarizer/api/main.py`
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[FastApiIntegration()],
        environment=os.getenv("ENVIRONMENT")
    )
```

### 6.4 Variables d'Environnement

```bash
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
CLOUDWATCH_LOGS_ENABLED=true
METRICS_NAMESPACE=MediaSummarizer
ALARM_SNS_TOPIC_ARN=arn:aws:sns:eu-west-1:xxx:alerts
```

### 6.5 Critères d'Acceptation
- [ ] Images construites et poussées automatiquement
- [ ] Déploiement automatique sur tag
- [ ] Alertes CloudWatch configurées
- [ ] Logs structurés JSON
- [ ] Dashboard CloudWatch créé

### 6.6 Tests
- **CI/CD** : Push tag, vérifier déploiement
- **Alertes** : Simuler erreurs, vérifier notifications

### 6.7 Risques et Mitigations
- **Risque** : Déploiement casse la prod
  - **Mitigation** : Blue/green deployment, rollback auto

### 6.8 Livrables
- [ ] Pipelines GitHub Actions
- [ ] Configuration monitoring Terraform
- [ ] Dashboard CloudWatch
- [ ] Runbook alertes

---

## Chantier 7: Configuration de Déploiement Production

### 7.1 Objectif
Déployer sur AWS ECS Fargate avec ALB HTTPS, CloudWatch, et gestion des secrets.

### 7.2 État Actuel
- **Dockerfiles prêts** : `infrastructure/docker/` (api, worker, whisper)
- **Terraform incomplet** : `infrastructure/terraform/scaling.tf`
  - Manque : ECR, Task Definitions, Services ECS, ALB, Route53
- **Pas de** : `docker-compose.prod.yml`

### 7.3 Changements à Réaliser (Option B: ECS Fargate - Recommandée)

#### A. Compléter Terraform

**Créer** : `infrastructure/terraform/main.tf`
```hcl
# Modules à ajouter :
# - ECR repositories (api, worker, whisper)
# - VPC et subnets (ou utiliser default)
# - ALB avec HTTPS listener (ACM certificate)
# - ECS Task Definitions (1 API, 4 workers)
# - ECS Services avec auto-scaling
# - Route53 hosted zone et records
# - Secrets Manager pour les secrets
```

**Créer** : `infrastructure/terraform/variables.tf`
```hcl
variable "domain_name" {}
variable "environment" {}
variable "openai_api_key" { sensitive = true }
variable "stripe_api_key" { sensitive = true }
# etc...
```

#### B. GitHub Actions pour CI/CD

**Créer** : `.github/workflows/deploy.yml`
```yaml
# Steps :
# 1. Build et push images vers ECR
# 2. Update ECS task definitions
# 3. Force new deployment
```

#### C. Configuration des services ECS

**Task Definition API** :
```json
{
  "family": "media-summarizer-api",
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [{
    "name": "api",
    "image": "xxx.dkr.ecr.eu-west-1.amazonaws.com/media-summarizer-api:latest",
    "portMappings": [{"containerPort": 8000}],
    "environment": [...],
    "secrets": [...],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/media-summarizer-api",
        "awslogs-region": "eu-west-1",
        "awslogs-stream-prefix": "api"
      }
    },
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/health || exit 1"],
      "interval": 30,
      "timeout": 5,
      "retries": 3
    }
  }]
}
```

### 7.4 Variables d'Environnement

```bash
# Secrets dans AWS Secrets Manager
/media-summarizer/prod/openai-api-key
/media-summarizer/prod/stripe-api-key
/media-summarizer/prod/stripe-webhook-secret
/media-summarizer/prod/jwt-secret

# Variables dans Task Definition
AWS_REGION=eu-west-1
ENVIRONMENT=production
WHISPER_MODEL_SIZE=large
# Pas de AWS_ENDPOINT_URL en prod
```

### 7.5 Critères d'Acceptation
- [ ] Infrastructure créée via Terraform
- [ ] API accessible via HTTPS sur le domaine
- [ ] Health check ALB passe
- [ ] Logs visibles dans CloudWatch
- [ ] Auto-scaling fonctionnel (2-10 tasks)
- [ ] Secrets chargés depuis Secrets Manager

### 7.6 Tests
- **Infrastructure** : `terraform plan` sans erreurs
- **Déploiement** : GitHub Actions déploie sur push tag
- **Santé** : Monitoring ALB et ECS health checks

### 7.7 Risques et Mitigations
- **Risque** : Coûts AWS élevés
  - **Mitigation** : Alertes budget, auto-scaling conservateur
- **Risque** : Secrets exposés
  - **Mitigation** : Secrets Manager, IAM roles stricts

### 7.8 Livrables
- [ ] `infrastructure/terraform/` complet
- [ ] `.github/workflows/deploy.yml`
- [ ] Documentation déploiement
- [ ] Runbook incidents

### 7.9 Décisions validées (pour reprise ultérieure)
- Région: eu-west-1
- Pattern workers retenu (Pattern 2):
  - API en service ECS Fargate allumé en continu derrière un ALB (site toujours up)
  - Workers Fargate « éphémères » pour Download, Transcription (Whisper), Summarization, Email
- Mise en œuvre des workers éphémères:
  - Services ECS par type de worker avec autoscaling basé sur la profondeur SQS (min=0, max initial faible), capacity provider FARGATE_SPOT (fallback FARGATE si nécessaire)
  - La Lambda de scaling existante dans le repo reste optionnelle et non prioritaire (peut être réévaluée plus tard)
- Réseau (option budget):
  - VPC sans NAT, uniquement des subnets publics + Internet Gateway; toutes les tâches ECS avec assignPublicIp=true
  - Sécurité SG stricte: ALB (HTTP/80) depuis 0.0.0.0/0; API (8000) uniquement depuis le SG de l’ALB; Workers: aucun inbound, egress autorisé
  - VPC Gateway Endpoints S3 et DynamoDB activés (gratuits)
- Domaine/HTTPS:
  - Différé. Utilisation temporaire du DNS de l’ALB en HTTP (port 80)
  - Plus tard: Route53 + ACM et listener HTTPS 443 avec redirection HTTP→HTTPS
- CI/CD:
  - GitHub Actions avec OIDC (pas de clés AWS longues). Deux workflows: build/push vers ECR, puis déploiement (terraform plan/apply avec approbation)
  - Rôles IAM dédiés pour OIDC (push ECR et déploiement Terraform/ECS)
- ECR: noms validés — `media-summarizer-api` et `media-summarizer-ephemeral-worker`
- Data plane (S3/DynamoDB/SQS):
  - Création reportée jusqu’à stabilisation du modèle (paiements, schéma). Si besoin d’E2E avant, créer un set -v1 et prévoir bascule vers -v2
- Secrets/config:
  - Stockage initial dans SSM Parameter Store (SecureString) et injection via ECS task definitions; migration possible vers Secrets Manager ultérieurement
- Maîtrise des coûts:
  - Ne provisionner ALB et service API (desiredCount > 0) qu’au moment opportun; workers min=0; ajouter un Budget AWS pour alerte de dépense

### 7.10 Terraform en Production — Principes et Exigences

Objectif
- Définir un mode opératoire “production-grade” pour provisionner et faire évoluer l’infrastructure AWS via Terraform, distinct du flux de développement local (LocalStack + docker-compose).

Principes directeurs (DOIT)
- Exécution Terraform pilotée par la CI/CD (et non par l’application ni un service docker au runtime)
  - Terraform peut s’exécuter dans un conteneur, mais au sein d’un job CI (GitHub Actions, GitLab CI, CircleCI, Jenkins, Terraform Cloud/Enterprise).
  - Séparer le cycle “provision infra” du cycle “déploiement applicatif”.
- État distant et verrouillage
  - Backend S3 pour le state, avec chiffrement et versionning
  - Table DynamoDB pour le lock (évite les apply concurrents)
  - Accès restreint: seul le rôle CI dédié peut lire/écrire l’état.
- Identité et accès sans secrets en clair
  - Authentification basée sur OIDC/STS (assume-role) depuis la CI vers AWS, pas de clés longues durées.
  - Rôle IAM Terraform minimalement privilégié (least-privilege), borné aux ressources nécessaires.
- Flux d’approbation et contrôles
  - Pull Request: terraform fmt/validate + plan (artifact) + revue humaine
  - Branche principale / release: apply protégé par approbation manuelle (environment protection)
  - Linting/sécurité: tflint, checkov/OPA, policy-as-code (ex: Sentinel/Terraform Cloud) si disponible
- Séparation des environnements
  - Environnements distincts (dev, staging, prod) avec états distants séparés (chemins S3 différents, ou comptes AWS différents)
  - Variables/paramètres dédiés par environnement; optionnellement workspaces ou répertoires/projets Terraform séparés
- Gestion des secrets et de la config
  - Secrets en Secrets Manager ou SSM Parameter Store
  - Ne pas committer de secrets; préférer data sources/refs plutôt que définir en clair
- Détection de dérive et observabilité
  - Job plan programmé (ex: quotidien) avec -detailed-exitcode; alerte en cas de dérive
  - Taggage systématique des ressources (Project, Environment, Owner) et exposition des métriques/logs
- Stratégie de changements risqués
  - Fractionner les changements destructifs (ex: recréation de file d’attente, index DynamoDB), planifier fenêtres de maintenance si nécessaire
  - Préférer des patterns blue/green ou duplications temporaires pour ressources critiques

À faire (prod)
1. Créer une racine Terraform “production” dédiée (ou un dossier par env) avec:
   - backend S3 + verrou DynamoDB
   - providers et variables paramétrées par environnement
   - séparation claire des modules/ressources nécessaires à la prod
2. Créer un rôle IAM Terraform (prod) et une politique minimale:
   - Autoriser uniquement les actions/services gérés par ce Terraform
   - Ajouter le trust OIDC nécessaire à la CI
3. Mettre en place le pipeline CI/CD “terraform-prod”:
   - Sur PR touchant l’infra: fmt, validate, tflint, checkov (si utilisé), plan (artifact)
   - Sur déclenchement manuel (ou merge vers main): init + apply, soumis à approbation manuelle
   - Configurer l’auth AWS via OIDC/STS (aucune clé en clair)
4. Définir la stratégie de variables et de sensibilités:
   - tfvars par environnement; marquer les variables sensibles
   - Secrets en Secrets Manager/SSM et référencés par Terraform/les workloads
5. Mettre en place la détection de dérive et les notifications:
   - Job plan périodique avec alerte si écart
6. Documenter le runbook de déploiement infra:
   - Comment exécuter un plan, comment approuver et appliquer
   - Comment faire un rollback (revert PR + apply)
   - Où consulter l’état et les logs

Critères d'acceptation (prod)
- Un dossier Terraform “prod” (ou équivalent) avec backend distant opérationnel (S3 + DynamoDB)
- Un rôle IAM Terraform dédié avec trust OIDC et politique least-privilege
- Un workflow CI complet:
  - PR: fmt/validate/lint/sécurité + plan publié comme artefact
  - Prod: apply déclenché manuellement et protégé
- Variables/secret mgmt et tagging standardisés
- Documentation du runbook (plan/apply/rollback) et de la stratégie de dérive

Distinction DEV local vs PROD
- DEV: docker-compose démarre LocalStack + un service Terraform pour provisionner une infra éphémère locale.
- PROD: Terraform n’est pas exécuté par docker-compose ni par l’app; il est exécuté par la CI avec état distant, contrôle d’accès, approbations et journaux centralisés.

Notes de mise en œuvre
- Le “Terraform en Docker” reste pertinent… mais comme image de job CI, pas comme service de runtime.
- Pour préparer l’adoption multi-comptes (org AWS), prévoir des rôles par environnement et, si possible, des SCP (Service Control Policies) en complément.
- Prévoir les politiques de rotation et de rétention pour les artefacts de plan et les logs CI.

Portée (hors de ce jalon)
- Pas de création de squelette prod (tfstate backend, workflows CI) dans ce chantier; ils seront implémentés lors du dernier jalon du plan.

---

## Chantier 8: Industrialisation Email (SES)

### 8.1 Objectif
Configurer SES production avec domaine vérifié, SPF/DKIM/DMARC, et gestion des bounces.

### 8.2 État Actuel
- Worker email : `media_summarizer/workers/notification/email_worker.py`
- LocalStack simule SES en dev
- Variables FROM_EMAIL et SUPPORT_EMAIL dans `.env`

### 8.3 Changements à Réaliser

#### A. Configuration SES

**Actions AWS Console** :
```
1. Vérifier domaine yourdomain.com
2. Configurer DKIM (3 CNAME records)
3. Configurer SPF : "v=spf1 include:amazonses.com ~all"
4. Configurer DMARC : "v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com"
5. Sortir du sandbox (ticket support AWS)
6. Configurer configuration set pour tracking
```

#### B. Gestion des bounces/complaints

**Créer** : SNS topics pour bounces/complaints
**Créer** : Lambda ou endpoint pour traiter les notifications

### 8.4 Variables d'Environnement

```bash
FROM_EMAIL=noreply@yourdomain.com
SUPPORT_EMAIL=support@yourdomain.com
SES_CONFIGURATION_SET=media-summarizer-prod
```

### 8.5 Critères d'Acceptation
- [ ] Domaine vérifié dans SES
- [ ] SPF/DKIM/DMARC configurés
- [ ] Emails arrivent en inbox (pas spam)
- [ ] Sandbox SES levé
- [ ] Bounces/complaints trackés

### 8.6 Tests
- **Envoi test** : mail-tester.com score > 8/10
- **Délivrabilité** : Tester Gmail, Outlook, Yahoo

### 8.7 Risques et Mitigations
- **Risque** : Réputation email dégradée
  - **Mitigation** : Warm-up progressif, monitoring bounces

### 8.8 Livrables
- [ ] Configuration DNS complète
- [ ] Documentation SES
- [ ] Dashboard CloudWatch pour métriques email

---

## Chantier 9: Spotify « Tosum Sync »

### 9.1 Objectif
Automatiser l’ingestion des épisodes Spotify écoutés au-delà d’un seuil configurable (playlist utilisateur « Tosum ») et les envoyer dans le workflow existant (download → whisper → summarize), via résolution feed/épisode avec PodcastIndex.

### 9.2 Décisions (V1)
- V1 on-demand seulement (pas de scheduler). L’endpoint est interne (pas accessible aux utilisateurs finaux); pas de rate limit requis.
- Matching naïf: normalize (minuscules, retrait ponctuation, espaces) + égalité stricte → substring → token-overlap pour sélectionner d’abord le feed (titre), puis l’épisode (titre) côté PodcastIndex.
- Cap par exécution: 5 épisodes maximum (configurable via SPOTIFY_SYNC_MAX, défaut 5).
- Limite récupération épisodes par feed: 250 (PodcastIndex) pour limiter la charge.
- Pas d’évitement « in-run » via set mémoire (Spotify ne permet pas de dupliquer un épisode dans une playlist). L’évitement inter-run est, lui, critique (voir 9.4 Idempotence).
- Critère d’écoute: remplacer l’usage actuel de fully_played par un seuil configurable calculé depuis resume_point.resume_position_ms / duration_ms. Considérer un épisode « écouté » si (resume_point.resume_position_ms / duration_ms) × 100 ≥ SPOTIFY_LISTEN_THRESHOLD_PERCENT (défaut 80). Si resume_point ou duration_ms est absent, ignorer l’épisode (pas de fallback).

Mise à jour (implémentée) — V1 on-demand
- Endpoint interne POST /api/v1/spotify/sync-tosum (auth requis: require_verified_email)
- Service: core/services/tosum_sync.py (résolution PodcastIndex et soumission via service partagé)
- Utilitaires Spotify: utils/spotify.py (refresh token + accès playlist + items épisodes)
- Variables env: SPOTIFY_TOSUM_PLAYLIST_NAME, SPOTIFY_SYNC_MAX, SPOTIFY_LISTEN_THRESHOLD_PERCENT
- Source marquée "spotify" dans submit_episode_for_user pour lier watchers à la politique de notification
- Idempotence globale + watchers: si épisode en cours → watcher créé (source=spotify), hold minutes placé, notification fan-out à complétion (from_cache=True)

### 9.3 Rappel planification (future)
- Rappel: configurer un CloudWatch Event quotidien (cron) pour déclencher le sync automatiquement (Lambda/ECS/Batch). L’appel devra être sécurisé (token interne/service account) et instrumenté (métriques processed/queued/skipped).

### 9.4 Idempotence / Caching unifié des épisodes
- Introduire une base unifiée d’idempotence (DynamoDB) pour marquer les épisodes déjà traités par utilisateur, partagée par toutes les sources (soumission UI, sync Spotify, etc.).
- Clés d’unification (ordre de préférence):
  1) PodcastIndex episode GUID (si disponible)
  2) Hash de l’audio_url (fallback universel)
  3) spotify_episode_id (convenance source Spotify)
- Sémantique: réservation conditionnelle à la création du job (status=reserved via ConditionExpression attribute_not_exists) → status=processed en fin de workflow. Empêche les doublons inter-run et cross-sources.
- Helpers à exposer: already_processed(user_id, keys…), reserve_or_skip(user_id, keys…), mark_processed(job_id, keys…).

Mise à jour (implémentée) — Idempotence globale par GUID + Watchers (fan-out):
- Idempotence désormais globale par GUID (partition key = episode_guid), indépendante de l’utilisateur.
- Si GUID déjà « processed », on facture l’utilisateur demandeur et on envoie un email avec le résumé en cache (from_cache=True), sans retraitement.
- Si GUID « reserved/in-progress », on enregistre un watcher (table episode_watchers (PK=guid, SK=user_id)) pour l’utilisateur demandeur, on place un hold minute estimatif immédiatement, et on attend l’événement de complétion.
- À la complétion canonique, le worker fan-out (episode-completed-events) finalise l’usage pour chaque watcher, envoie les emails (from_cache=True), et marque le watcher « emailed » (ou « failed » si minutes insuffisantes).
- Politique « minutes insuffisantes »: watchers source=spotify → email d’information; source=manual → pas d’email (notification côté UI), watcher marqué « failed ».

### 9.5 Variables d’environnement
- SPOTIFY_SYNC_MAX=5 (défaut 5, configurable par les développeurs)
- SPOTIFY_LISTEN_THRESHOLD_PERCENT=80 (seuil d’écoute en pourcentage; utilisé avec resume_point.resume_position_ms / duration_ms)
- (Variables Spotify existantes: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI)

---

## Plan d'Exécution Phasé

### Phase 1: Fondations (Semaine 1-2)
1. **Chantier 3** : Alignement infrastructure (2 jours)
2. **Chantier 1** : Authentification (3 jours)
3. **Chantier 4** : Durcissement API partie 1 (2 jours)

### Phase 2: Monétisation (Semaine 3)
4. **Chantier 2** : Monétisation minutes (Stripe V2: abonnements + packs + webhooks) (3-5 jours)
5. **Chantier 4** : Libération auto des minutes en cas d’échec (1 jour)
6. Tests end-to-end monétisation (1 jour)

### Phase 3: Infrastructure Prod (Semaine 4)
7. [Reporté] **Chantier 7** : Déploiement ECS — déplacé en Phase 5
8. **Chantier 6** : CI/CD de base (1 jour)

### Phase 4: Optimisations (Semaine 5)
9. **Chantier 5** : OpenAI tuning (1 jour)
10. **Chantier 6** : Monitoring complet (2 jours)
11. **Chantier 9** : Spotify « Tosum Sync » V1 on-demand (endpoint interne), cap par run via SPOTIFY_SYNC_MAX=5, matching naïf, critère d’écoute ≥ SPOTIFY_LISTEN_THRESHOLD_PERCENT basé sur resume_point.resume_position_ms/duration_ms (remplace fully_played), pas de rate limit (process non accessible aux utilisateurs).
12. Tests de charge et optimisations (2 jours)

### Phase 5: Go Live (Semaine 6)
12. **Chantier 7** : Déploiement ECS (3 jours) — API ECS always-on + ALB HTTP (domaine/HTTPS ultérieur)
13. **Chantier 8** : Industrialisation Email (SES) (1 jour)
14. **Chantier 9** : Planification CloudWatch quotidienne du « Tosum Sync » (déclenchement automatique sécurisé). Instrumentation (logs/metrics) et runbook d’exploitation.
15. **Chantier 9** : Idempotence/caching unifié des épisodes (DynamoDB) — helpers already_processed / reserve_or_skip / mark_processed et intégration dans tous les points d’entrée.
16. Migration données si nécessaire
17. Tests finaux
18. Bascule DNS
19. Monitoring intensif post-launch

---

## Checklists de Validation

### Checklist Pré-Production
- [ ] Tous les tests passent (unit, integration, E2E)
- [ ] Authentification fonctionne (Google/Apple OAuth + fallback local)
- [ ] Abonnements & packs (Stripe) testés (sandbox et live) avec webhooks
- [ ] Infrastructure Terraform appliquée
- [ ] Secrets dans Secrets Manager
- [ ] Domaine vérifié dans SES
- [ ] SSL/TLS configuré sur ALB
- [ ] Health checks passent
- [ ] Logs visibles dans CloudWatch
- [ ] Alertes configurées
- [ ] Backup DynamoDB activé
- [ ] Documentation à jour
- [ ] Runbook incidents prêt

### Checklist Go-Live
- [ ] DNS pointé vers ALB
- [ ] Mode production activé (variables env)
- [ ] Monitoring dashboard ouvert
- [ ] Équipe en standby
- [ ] Communication clients prête
- [ ] Rollback plan testé

### Checklist Post-Launch (J+1)
- [ ] Métriques dans les normes
- [ ] Pas d'erreurs critiques
- [ ] Emails délivrés correctement
- [ ] Paiements processés
- [ ] Temps de réponse < 2s
- [ ] Utilisation ressources normale

---

## Annexe: Mapping Variables d'Environnement

### Variables Communes (Tous Services)
```bash
ENVIRONMENT=production
AWS_REGION=eu-west-1
LOG_LEVEL=INFO
```

### Variables API
```bash
# JWT & sessions
JWT_SECRET_KEY=<from-secrets-manager>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
COOKIE_NAME_REFRESH=refresh_token
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
COOKIE_DOMAIN=app.yourdomain.com

# CORS / Frontend
CORS_ORIGINS=https://app.yourdomain.com
RATE_LIMIT_PER_MINUTE=60
FRONTEND_URL=https://app.yourdomain.com

# Google OAuth
GOOGLE_CLIENT_ID=<from-secrets-manager>
GOOGLE_CLIENT_SECRET=<from-secrets-manager>
GOOGLE_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/google/callback

# Apple OAuth
APPLE_CLIENT_ID=<from-secrets-manager>
APPLE_TEAM_ID=<from-secrets-manager>
APPLE_KEY_ID=<from-secrets-manager>
APPLE_PRIVATE_KEY=<from-secrets-manager>
APPLE_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/apple/callback
```

### Variables Workers
```bash
WHISPER_MODEL_SIZE=large
LLM_MODEL=gpt-4-turbo-preview
LLM_MAX_TOKENS=2000
OPENAI_API_KEY=<from-secrets-manager>
```

### Variables Infrastructure
```bash
# Injectées depuis Terraform outputs
AUDIO_BUCKET=media-summarizer-audio-xxx-prod
TRANSCRIPT_BUCKET=media-summarizer-transcriptions-xxx-prod
SUMMARY_BUCKET=media-summarizer-summaries-xxx-prod
USERS_TABLE=users
PROCESSING_JOBS_TABLE=processing_jobs
SUBSCRIPTIONS_TABLE=subscriptions
MINUTE_BUCKETS_TABLE=minute_buckets
MINUTE_USAGE_TABLE=minute_usage
FOLLOWS_TABLE=follows
STRIPE_EVENTS_TABLE=stripe_events
```

### Variables Stripe
```bash
STRIPE_API_KEY=<from-secrets-manager>
STRIPE_WEBHOOK_SECRET=<from-secrets-manager>
# Abonnements
STRIPE_PRICE_ID_SUB_S=price_xxx
STRIPE_PRICE_ID_SUB_M=price_xxx
STRIPE_PRICE_ID_SUB_L=price_xxx
# Packs minutes
STRIPE_PRICE_ID_PACK_100=price_xxx
STRIPE_PRICE_ID_PACK_300=price_xxx
STRIPE_PRICE_ID_PACK_600=price_xxx
STRIPE_PRICE_ID_PACK_1200=price_xxx
# Redirections
STRIPE_SUCCESS_URL=https://app.yourdomain.com/payment-success
STRIPE_CANCEL_URL=https://app.yourdomain.com/payment-cancel
```

### Variables Email
```bash
FROM_EMAIL=noreply@yourdomain.com
SUPPORT_EMAIL=support@yourdomain.com
SES_CONFIGURATION_SET=media-summarizer-prod
```

### Variables Monitoring
```bash
SENTRY_DSN=<optionnel>
CLOUDWATCH_LOGS_ENABLED=true
METRICS_NAMESPACE=MediaSummarizer
```

---

## Conclusion

Ce plan couvre les 8 chantiers critiques pour une mise en production réussie. L'ordre d'exécution proposé minimise les risques en construisant d'abord les fondations (auth, infrastructure), puis la monétisation (Stripe), et enfin les optimisations.

**Durée estimée totale** : 5-6 semaines avec 1-2 développeurs

**Prochaines étapes** :
1. Valider les décisions stratégiques
2. Provisionner les comptes AWS et Stripe
3. Acheter le domaine
4. Commencer par le Chantier 3 (alignement infra)

**Points d'attention** :
- Tester extensivement les paiements avant go-live
- Prévoir une période de soft launch avec utilisateurs beta
- Monitorer de près les premiers jours post-launch
- Avoir un plan de rollback prêt

---

## Chantier 10: Emails Quiz Interactifs (AMP + iOS/Samsung + Fallback)

Objectif
- Intégrer un quiz interactif généré par LLM dans l’email de complétion: quiz en premier, puis un bouton « Reveal Summary » qui dévoile le résumé dans le même email.
- Maximiser la compatibilité: AMP4Email (Gmail), HTML interactif (iOS/Apple/Samsung Mail), fallback HTML statique + texte pour les autres (Outlook/Yahoo...).

Décisions
- Génération: nouveau worker `media_summarizer/workers/quiz/worker.py` qui consomme `QUIZ_QUEUE`, prend `transcript_s3_key` en entrée, produit un JSON `quiz` et envoie sur `email-notification-queue` (pas d’enregistrement de réponses, pas de webhooks).
- Email: le `email_worker` rend 4 variantes (AMP, HTML interactif, HTML fallback, texte) via Jinja et envoie un MIME `multipart/alternative` (text/plain, text/x-amp-html, text/html) via `send_raw_email`.
- AMP (Gmail): feedback correct/incorrect immédiat; score final calculé via amp-bind, affiché en fin d’email; « Reveal Summary » avec `amp-accordion`.
- iOS/Apple/Samsung: pattern inputs+labels (sans position absolue) + feedback immédiat par option; page finale sans score agrégé (limitation CSS-only). « Reveal Summary » via checkbox CSS.
- Fallback: HTML statique listant les bonnes réponses; texte brut équivalent.
- Limites: pas de persistance des réponses; pas de hook/analytics pour l’instant.
- i18n: la langue du quiz est passée au worker (défaut EN). Plus tard, un champ `user.preferred_language` guidera la langue; valeur par défaut à définir via i18n (à implémenter).

Implémentation (V1)
- Modèles: `media_summarizer/core/models/quiz.py` (Quiz, Question, Choice) avec cap 15 questions, validation simple.
- Templates Jinja (repo):
  - `media_summarizer/email_templates/quiz/quiz_amp.html.j2`
  - `media_summarizer/email_templates/quiz/quiz_interactive.html.j2`
  - `media_summarizer/email_templates/quiz/quiz_fallback.html.j2`
  - `media_summarizer/email_templates/quiz/quiz.txt.j2`
- MIME builder: `media_summarizer/utils/mime_builder.py` (construction multipart/alternative AMP pour SES).
- Pipeline feature-flag: `ENABLE_QUIZ_EMAIL=true` fait dévier le `summarization_worker` vers `QUIZ_QUEUE`; sinon, l’email de complétion legacy reste inchangé.
- Aucune position absolue dans le template iOS/Samsung; si un jour nécessaire, ajouter CSS ciblé Samsung (`#MessageViewBody`) pour forcer le fallback (selon Email on Acid).
- Contrainte viewport: « 1 question + 4 options » doit tenir sans scroll; on limite la longueur des prompts/choices dans le prompting LLM et on tronque au rendu si besoin.
- Taille email: viser < 100KB; pas de webfonts; images optionnelles.

AMP Gmail — readiness
- Tant que le domaine d’envoi n’est pas approuvé pour AMP, Gmail affichera la partie HTML classique. Étapes à planifier:
  - SPF/DKIM/DMARC alignés; TLS; volume d’envoi raisonnable.
  - Demande d’approbation Gmail Dynamic Email (adresse/domaine).
  - Valider le document avec `amphtml-validator` (local ou via playground AMP) avant les tests.

Tests (manuels pour V1)
- Envoi réel de mails de test via SES (sandbox) vers boîtes Gmail, iOS Mail, Samsung Mail, Outlook, Yahoo.
- Idéalement, utiliser Email on Acid / Litmus si disponible pour prévisualisations cross-clients.
- Le copier/coller du code dans un email ne suffit pas pour AMP; préférer l’envoi réel.

Variables d’environnement
- `ENABLE_QUIZ_EMAIL=true|false` (défaut false)
- `QUIZ_QUEUE=quiz-queue`
- `TRANSCRIPT_BUCKET` (existant)
- `DEFAULT_QUIZ_LANGUAGE=EN`
- `LLM_API_URL`, `OPENAI_API_KEY`, `LLM_TIMEOUT_SECONDS`

Points ouverts / prochaines étapes
- i18n complète: introduire `user.preferred_language` (DB + API) et une valeur par défaut déterminée via i18n; alimenter worker quiz et templates.
- R&D (timebox) sur un score agrégé CSS-only pour iOS/Samsung; si non concluant, proposer un lien « Voir mon score en ligne » (page web stateless).
- Onboarding AMP: préparer les DNS et la demande d’approbation.

---

## Statut d’avancement (2025-10-02)

Cette section suit l’état réel du code et liste les TODO par phase. Les cases cochées indiquent ce qui est en place. Les éléments restants sont listés en TODO.

Références clés dans le repo (non exhaustif):
- Auth: `media_summarizer/api/endpoints/auth.py`, `media_summarizer/api/endpoints/auth_social.py`, `media_summarizer/api/dependencies/auth.py`
- Durcissement API / Rate limiting / Validators: `media_summarizer/api/rate_limit.py`, `media_summarizer/core/validators.py`, `media_summarizer/api/endpoints/podcast_search.py`
- Monétisation minutes: `media_summarizer/api/endpoints/billing.py`, `media_summarizer/core/services/stripe_service_v2.py`, `media_summarizer/core/services/minute_pool.py`
- Workers: `media_summarizer/workers/base_worker.py`, `media_summarizer/workers/summarization/summarization_worker.py`
- Terraform (DynamoDB/SQS/S3/LocalStack): `infrastructure/terraform/*`
- CI: `.github/workflows/*.yml`

### Phase 1 — Fondations
- [x] Chantier 3 — Alignement infra (DynamoDB tables + GSI, SQS avec DLQ, S3)
  - Terraform: `dynamodb_core_tables.tf`, `dynamodb_minutes_tables.tf`, `dynamodb_stripe_events.tf`, ressources SQS/S3 dans `scaling.tf` et LocalStack dans `localstack/main.tf`.
  - Note: prévoir des outputs explicites S3 (audio/transcripts/summaries) pour consommation applicative.
- [x] Chantier 1 — Auth (OAuth social Google/Apple + fallback local + cookies httpOnly 30j + CORS)
  - Implémenté + tests d’intégration pour Google/Apple.
  - [x] Documentation d’auth (guide ajouté: docs/AUTHENTICATION_SETUP.md). OpenAPI auto via /docs.
- [x] Chantier 4 (partie 1) — Durcissement API
  - Rate limiting global et par endpoint (slowapi), validation stricte URL audio, release automatique des minutes sur échec job.

### Phase 2 — Monétisation (minutes) et tests
- [x] Endpoints minutes V2 (`/billing/subscriptions/checkout`, `/billing/packs/checkout`, `/billing/me`) et webhooks `/payments/webhook` v2.
- [x] StripeService V2 (abonnements + packs + idempotence) et MinutePool (hold/finalize/release).
- [x] Tables minutes (subscriptions, minute_buckets, minute_usage, follows) + `stripe_events`.
- [x] Rollover mensuel automatique (créé à l’arrivée de la nouvelle facture: leftover -> bucket « rollover » avec expiry = fin de période courante).
- [x] Endpoint `/billing/history` (implémenté) avec agrégation via minute_buckets/subscriptions.
- [x] Migration crédits→minutes — N/A (site non publié). Remplacé complètement par le système minutes; endpoints `/payments/*` neutralisés; tests « crédits » désactivés.
- [x] E2E « minutes » (abonnement + pack + webhooks + consommation réelle) ajoutés et passants.

### Phase 3 — CI/CD de base
- [x] CI tests (intégration, E2E, coverage): `.github/workflows/integration-tests.yml`, `.github/workflows/e2e-tests.yml`, `.github/workflows/test-coverage.yml`.
- [ ] Pipeline build/push images (API, workers, whisper) vers ECR (sur tag `v*`).
- [ ] Déploiement automatique (mise à jour task definitions / services ECS) et/ou job Terraform avec approbation.

### Phase 4 — Optimisations & Front Auth
- [ ] Front: intercepteur HTTP (auto-refresh + replay), multi-onglets (BroadcastChannel), refresh proactif T-2min, backoff
- [ ] Vérifier prod: CORS_ORIGINS, COOKIE_SECURE, SameSite=None, COOKIE_DOMAIN
- [ ] OpenAI/LLM tuning dans `summarization_worker.py`:
  - Rendre le modèle configurable via env (LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_MAX_RETRIES) et ne plus hardcoder "gpt-4"; gérer timeouts/retries paramétrables.
  - Logger l’usage/coûts (sans exposer la clé).
  - Fallback JSON robuste (déjà partiellement présent, à aligner avec le plan).
- [ ] Observabilité/Monitoring:
  - Terraform CloudWatch (alarms 5xx ALB/API, âge plus ancien message SQS, CPU/Mem ECS), logs structurés JSON, Sentry (optionnel).
- [ ] Tests de charge et optimisations (script/outillage, runbook perfs).

### Phase 5 — Go Live
- [ ] Terraform Prod ECS Fargate (Option B): ECR, TaskDefinition API, Service ECS API always-on derrière ALB, ALB (HTTP puis HTTPS/ACM ultérieur), Route53, Secrets Manager/SSM.
- [ ] Workflows GitHub Actions de déploiement (OIDC, build/push ECR, update ECS, Terraform plan/apply avec approbation).
- [ ] SES production: domaine vérifié, SPF/DKIM/DMARC, sortie sandbox, bounces/complaints (SNS + traitement).
- [ ] Exécuter les checklists pré-prod/go-live/post-launch (SSL/TLS ALB, health checks, backups DynamoDB, alertes, secrets, runbooks, monitoring dashboard, rollback).

---

### TODO par phase (concret)

Phase 2
- [x] Migration crédits→minutes — N/A (site non publié). Remplacement direct par minutes; endpoints `/payments/*` neutralisés; tests crédits désactivés.
- [x] Écrire E2E complets « minutes »: abonnement/packs/webhooks/consommation sur soumission d’épisode.

Phase 3
- [ ] Ajouter `.github/workflows/build-and-push.yml` (build & push images API/worker/whisper vers ECR sur tag `v*`).
- [ ] Ajouter `.github/workflows/deploy.yml` (update task definitions/services ECS et/ou Terraform apply avec approbation, via OIDC).

Phase 4
- [ ] Paramétrage LLM via env (LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_MAX_RETRIES) + logging coûts + retries/timeout.
- [ ] Ajout Terraform monitoring (CloudWatch alarms), formatage logs JSON, intégration Sentry (optionnel).
- [ ] Préparer et lancer des tests de charge; documenter un runbook de perfs.
- [ ] Implémenter le seuil d’écoute Spotify (resume_point.resume_position_ms / duration_ms) et rendre SPOTIFY_LISTEN_THRESHOLD_PERCENT configurable.

Phase 5
- [ ] Compléter Terraform Prod (ECR, ECS API/Workers, ALB, Route53, Secrets Manager/SSM, autoscaling, budgets).
- [ ] Mettre en place les workflows de déploiement (build/push + déploiement ECS/Terraform avec approvals).
- [ ] Configurer SES en production (domaine, SPF/DKIM/DMARC, sortie sandbox, bounces/complaints).
- [ ] Exécuter les checklists et bascule DNS le moment venu.
