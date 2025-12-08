# Media Summarizer

Service de résumé automatique de podcasts utilisant l'IA.

[![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/user/gistid/raw/media-summarizer-coverage.json)](https://github.com/user/media-summarizer/actions/workflows/test-coverage.yml)

## Description

Media Summarizer est un service qui génère automatiquement des résumés de podcasts à partir de liens vers des épisodes. Le système accepte des liens de diverses plateformes (Spotify, Apple Podcasts, Google Podcasts, etc.), résout le flux RSS correspondant, télécharge l'audio, le transcrit avec Whisper (tiny en dev, large en prod), et génère un résumé structuré via un LLM.

## Fonctionnalités

- Soumission de liens de podcast depuis n'importe quelle plateforme
- Résolution automatique des flux RSS
- Téléchargement et traitement audio
- Transcription adaptative avec Whisper (tiny/large selon l'environnement)
- Résumés structurés générés par IA
- Livraison des résumés par email
- Système de paiement basé sur des crédits (en cours de migration vers un modèle “minutes” — voir section Compatibilité/Migration)
- Authentification locale (email + mot de passe) avec sessions persistantes (30 jours)
- Intégration Stripe pour les paiements
- Tests end-to-end complets

## Compatibilité / Migration vers le modèle “minutes”

Le projet migre du modèle “crédits” vers un modèle “minutes”:
- Abonnements S/M/L créditant un pool de minutes mensuel (S=240, M=840, L=1 980).
- Packs minutes one‑shot (100/300/600/1200) avec validité 6 mois.
- Débit au réel (arrondi à la minute), rollover 1 mois pour les minutes d’abonnement.
- Endpoint /credits/* et /payments/intent|confirm|refund seront retirés au profit de nouveaux endpoints billing (subscriptions/packs) et des webhooks Stripe.
- Une migration one‑shot “1 crédit = 1 minute” sera appliquée: création d’un bucket de minutes “migration” par utilisateur, puis mise à 0 de l’ancien champ credits.

Documentation minute‑based: docs/PAYMENT_SYSTEM_V2.md.

## Architecture

Le projet utilise une architecture microservices avec:
- Backend: Python avec FastAPI
- Base de données: DynamoDB (LocalStack en dev, AWS en prod)
- File d'attente: Amazon SQS
- Stockage: Amazon S3
- Conteneurisation: Docker avec LocalStack pour le développement
- Modèles IA: Whisper tiny/large (transcription), GPT-4 (résumé)
- Paiements: Stripe pour la gestion des crédits
- Authentification: JWT (email/mot de passe) + Social (Google/Apple) avec refresh cookie httpOnly (30 jours)

## 🚀 Démarrage rapide

### Configuration automatique (Recommandé)

```bash
# 1. Cloner le projet
git clone <repo-url>
cd media-summarizer-project

# 2. Copier le fichier d'environnement
cp .env.example .env
# Modifier .env avec vos clés API (OPENAI_API_KEY, PODCASTINDEXORG_API_KEY, etc.)

# 3. Installer les dépendances
source .venv/bin/activate
uv pip install -e ".[dev]"

# 4. Démarrer LocalStack et tous les services
docker-compose -f docker-compose.dev.yml --profile full up -d

# 5. Ou utiliser le Makefile pour une approche simplifiée
make dev-full
```

## 🧪 Tests

### Tests rapides avec Makefile

```bash
# Tests unitaires uniquement
make test-unit

# Tests d'intégration
make test-integration

# Tests E2E complets
make test-e2e

# Tous les tests
make test-all

# Tests avec couverture
make test-with-coverage
```

### Tests manuels avec pytest

```bash
# Tests rapides (unitaires)
pytest -m "not e2e and not integration" -v

# Tests d'intégration
pytest -m integration -v

# Tests E2E spécifiques
pytest media_summarizer/tests/end_to_end/test_auth_payment_e2e.py -m e2e -v -s
```

### Tests End-to-End (E2E)

Le projet inclut des tests E2E complets qui valident l'ensemble du parcours utilisateur :

```bash
# Tests E2E authentification + paiement
make test-e2e-auth

# Tests E2E parcours utilisateur complet
make test-e2e-journey

# Tests E2E existants (podcast processing)
make test-e2e-existing

# Tous les tests E2E
make test-e2e
```

#### Scénarios E2E couverts

1. **Nouvel utilisateur** : Inscription → Authentification → Achat de crédits → Traitement podcast
2. **Utilisateur existant** : Authentification → Traitement direct (avec crédits suffisants)
3. **Crédits insuffisants** : Tentative de traitement → Achat de crédits → Retry
4. **Gestion d'erreurs** : Authentification invalide, paiements échoués, etc.

#### CI/CD et E2E Tests

Les tests E2E sont intégrés dans GitHub Actions :
- **Pipeline automatique** : Chaque PR/push lance les tests E2E
- **Parallélisation** : Tests auth/payment et user journey en parallèle
- **Infrastructure automatisée** : LocalStack et services AWS simulés
- **Rapports de couverture** : Intégration avec Codecov

Voir `media_summarizer/tests/end_to_end/README.md` pour la documentation complète.

# 6. Initialiser la base de données DynamoDB
make init-db
# ou manuellement : python scripts/init_db.py init
```

### 🔧 Configuration manuelle

#### Prérequis

- Docker et Docker Compose
- Python 3.10+
- uv (gestionnaire de packages Python)
- Clés API requises:
  - `OPENAI_API_KEY` (pour les résumés)
  - `PODCASTINDEXORG_API_KEY` et `PODCASTINDEXORG_API_SECRET` (pour la résolution RSS)

#### Installation des dépendances

```bash
# Activer l'environnement virtuel
source .venv/bin/activate

# Installation avec uv
uv pip install -e .

# Installation des dépendances de développement
uv pip install -e ".[dev]"

# Démarrer LocalStack (simule AWS en local)
docker-compose -f docker-compose.dev.yml --profile infrastructure up -d

# Initialiser les tables DynamoDB
python scripts/init_db.py init
```

## 🌟 Gestion des environnements

### Environnements disponibles

| Environnement | Modèle Whisper | Description | Usage |
|---------------|----------------|-------------|-------|
| **Development** | `tiny` | Rapide, LocalStack, DynamoDB local | Tests et développement |
| **Production** | `large` | Haute qualité, AWS prod, DynamoDB | Production |

### Configuration rapide

#### Cookies en production (si front ≠ API)
- COOKIE_SECURE=true
- COOKIE_SAMESITE=None
- COOKIE_DOMAIN=.yourdomain.com

#### Endpoints d’authentification
- Local: POST /api/v1/auth/register, /login, /refresh, /logout, GET /me
- Social: GET /api/v1/auth/google/login, /google/callback, /apple/login, /apple/callback

```bash
# Vérifier le statut des tables DynamoDB
python scripts/init_db.py status

# Vérifier la santé de la connexion
python scripts/init_db.py health

# Créer les tables manquantes
python scripts/init_db.py init
```

### Démarrage par environnement

```bash
# Démarrer l'environnement de développement complet (API + Workers + LocalStack)
 docker-compose -f docker-compose.dev.yml --profile full up -d

# Démarrer seulement l'API et LocalStack
 docker-compose -f docker-compose.dev.yml --profile api up -d

# Démarrer seulement les workers
 docker-compose -f docker-compose.dev.yml --profile workers up -d

# Démarrer seulement l'infrastructure (LocalStack)
 docker-compose -f docker-compose.dev.yml --profile infrastructure up -d
```

### Préflight infrastructure (S3)

- L'API exécute un contrôle de pré-démarrage qui vérifie l'existence des buckets S3 requis.
- Ce contrôle est activé par défaut via `PRESTART_INFRA_CHECK=1` et fait échouer le démarrage si des buckets manquent.
- L'approvisionnement des buckets est géré par le service Terraform inclus dans `docker-compose.dev.yml`.

Commandes utiles:

```bash
# Lancer l’infra complète (incluant Terraform)
docker-compose -f docker-compose.dev.yml --profile full up -d

# Lancer le front
 cd front && npm run dev  

# Vérifier les logs Terraform
docker-compose -f docker-compose.dev.yml logs terraform

# Exécuter manuellement le préflight S3
uv run python -m media_summarizer.utils.infra_check
```

## 📊 Services disponibles

Une fois démarré, les services suivants sont disponibles:

- **API FastAPI**: http://localhost:8000
- **Documentation API**: http://localhost:8000/docs
- **LocalStack Dashboard**: http://localhost:4566
- **DynamoDB Local**: Accessible via AWS CLI avec endpoint `http://localhost:4566`

### Vérification du statut

```bash
# Vérifier que tous les services sont running
docker-compose -f docker-compose.dev.yml ps

# Vérifier les logs d'un service
docker-compose -f docker-compose.dev.yml logs api
docker-compose -f docker-compose.dev.yml logs download-worker

# Tester l'API
curl http://localhost:8000/health
```

## 🧪 Tests

## ⏱️ Rate limiting

The API uses SlowAPI for per-IP rate limiting.

- Global default is controlled by RATE_LIMIT_PER_MINUTE (e.g., 60/minute).
- Sensitive endpoints have dedicated limits; you can override via env:
  - RATE_LIMIT_PAYMENTS_PACKAGES, RATE_LIMIT_PAYMENTS_INTENT, RATE_LIMIT_PAYMENTS_CONFIRM,
    RATE_LIMIT_PAYMENTS_REFUND, RATE_LIMIT_PAYMENTS_CUSTOMER, RATE_LIMIT_PAYMENTS_HISTORY
  - RATE_LIMIT_PODCAST_SEARCH, RATE_LIMIT_PODCAST_EPISODES, RATE_LIMIT_SUBMIT_EPISODE, RATE_LIMIT_PODCAST_TRENDING

See .env.example for sample values.

```bash
# Exécuter tous les tests
pytest

# Exécuter un fichier de test spécifique
pytest tests/test_rss_resolver.py

# Exécuter avec support asyncio
pytest --asyncio-mode=auto

# Exécuter les tests avec couverture
python -m media_summarizer.scripts.run_coverage
```

## 📈 Couverture de Code

Le projet utilise pytest-cov pour générer des rapports de couverture de code. Les rapports sont disponibles dans les formats suivants:

- HTML: `htmlcov/index.html`
- XML: `coverage.xml`
- JSON: `coverage.json`

Le seuil minimal de couverture est fixé à 80%. Les rapports de couverture sont générés automatiquement lors de l'exécution des tests dans le pipeline CI/CD.

## 🔧 Configuration des Workers

Le système utilise plusieurs workers spécialisés:

- **Download Worker**: Télécharge les fichiers audio depuis les URLs de podcast
- **Transcription Worker**: Utilise Whisper pour convertir l'audio en texte
- **Summarization Worker**: Génère des résumés via OpenAI GPT-4
- **Email Worker**: Envoie les notifications par email

Tous les workers utilisent DynamoDB pour le suivi des jobs et S3/SQS via LocalStack en développement.

## 🗄️ Base de données

Le projet utilise DynamoDB avec les tables suivantes:

- `users`: Informations utilisateur (champ credits en cours de décommission)
- `processing_jobs`: Suivi des tâches de traitement
- (Nouveaux) `subscriptions`, `minute_buckets`, `minute_usage`, `follows`, `stripe_events`: tables pour le modèle “minutes”
- `podcasts`: Métadonnées des podcasts (optionnel)
- `episodes`: Métadonnées des épisodes (optionnel)

### Gestion de la base de données

```bash
# Vérifier le statut des tables
python scripts/init_db.py status

# Vérifier la connexion
python scripts/init_db.py health

# Initialiser toutes les tables
python scripts/init_db.py init
```

## 🚀 Déploiement

Pour la production, le système peut être déployé sur AWS avec:
- DynamoDB pour la base de données
- S3 pour le stockage des fichiers
- SQS pour les files d'attente
- ECS/Fargate ou EC2 pour les workers

## 📄 Licence

Tous droits réservés.
