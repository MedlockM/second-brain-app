# Media Summarizer

Service de résumé automatique de podcasts utilisant l'IA.

[![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/user/gistid/raw/media-summarizer-coverage.json)](https://github.com/user/media-summarizer/actions/workflows/test-coverage.yml)

## Description

Media Summarizer est un service qui génère automatiquement des résumés de podcasts à partir de liens vers des épisodes. Le système accepte des liens de diverses plateformes (Spotify, Apple Podcasts, Google Podcasts, etc.), résout le flux RSS correspondant, télécharge l'audio, le transcrit avec Whisper Large, et génère un résumé structuré via un LLM.

## Fonctionnalités

- Soumission de liens de podcast depuis n'importe quelle plateforme
- Résolution automatique des flux RSS
- Téléchargement et traitement audio
- Transcription haute qualité avec Whisper Large
- Résumés structurés générés par IA
- Livraison des résumés par email
- Système de paiement basé sur des crédits

## Architecture

Le projet utilise une architecture microservices avec:
- Backend: Python avec FastAPI
- Base de données: PostgreSQL
- File d'attente: Amazon SQS
- Stockage: Amazon S3
- Conteneurisation: Docker avec AWS Fargate
- Modèles IA: Whisper Large (transcription), GPT-4 (résumé)

## Installation

### Prérequis

- Docker et Docker Compose
- Python 3.10+
- uv (gestionnaire de packages Python)

### Installation des dépendances

```bash
# Installation avec uv
uv pip install -e .

# Installation des dépendances de développement
uv pip install -e ".[dev]"
```

### Démarrage de l'environnement local

```bash
# Démarrer l'environnement de développement
docker-compose -f docker-compose.dev.yml up
```

## Tests

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

## Couverture de Code

Le projet utilise pytest-cov pour générer des rapports de couverture de code. Les rapports sont disponibles dans les formats suivants:

- HTML: `htmlcov/index.html`
- XML: `coverage.xml`
- JSON: `coverage.json`

Le seuil minimal de couverture est fixé à 80%. Les rapports de couverture sont générés automatiquement lors de l'exécution des tests dans le pipeline CI/CD.

## Licence

Tous droits réservés.