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
- Système de paiement basé sur des crédits

## Architecture

Le projet utilise une architecture microservices avec:
- Backend: Python avec FastAPI
- Base de données: DynamoDB (LocalStack en dev, AWS en prod)
- File d'attente: Amazon SQS
- Stockage: Amazon S3
- Conteneurisation: Docker avec LocalStack pour le développement
- Modèles IA: Whisper tiny/large (transcription), GPT-4 (résumé)

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

# 5. Initialiser la base de données DynamoDB
python scripts/init_db.py init
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

- `users`: Informations utilisateur et crédits
- `processing_jobs`: Suivi des tâches de traitement
- `credit_transactions`: Historique des transactions de crédits
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