# Gestion des Environnements - Media Summarizer

## Vue d'ensemble

Media Summarizer utilise différents modèles Whisper selon l'environnement pour optimiser les performances et les coûts :

- **Développement** : Modèle `tiny` (rapide, moins précis)
- **Production** : Modèle `large` (lent, haute précision)

## 📁 Structure des fichiers de configuration

```
media-summarizer-project/
├── .env.example          # Template de configuration
├── .env.dev              # Configuration développement
├── .env.prod             # Configuration production
├── .env                  # Fichier actuel (copié depuis .env.dev/.env.prod)
├── docker-compose.dev.yml    # Services développement
├── docker-compose.prod.yml   # Services production
└── scripts/
    └── setup_environment.py # Script de gestion d'environnement
```

## 🚀 Configuration rapide

### Méthode 1 : Script automatique (Recommandé)

```bash
# Lister les environnements disponibles
python scripts/setup_environment.py list

# Configurer l'environnement de développement
python scripts/setup_environment.py setup development

# Configurer l'environnement de production
python scripts/setup_environment.py setup production

# Vérifier les prérequis
python scripts/setup_environment.py check development

# Basculer rapidement d'environnement
python scripts/setup_environment.py switch production
```

### Méthode 2 : Configuration manuelle

```bash
# Pour le développement
cp .env.dev .env

# Pour la production
cp .env.prod .env
```

## 🔧 Configuration détaillée par environnement

### Développement

**Caractéristiques :**
- Modèle Whisper : `tiny`
- AWS : LocalStack
- Base de données : DynamoDB LocalStack
- Temps de transcription : ~5-10 secondes
- Qualité : Basique (suffisant pour les tests)

**Démarrage :**
```bash
# Configuration
python scripts/setup_environment.py setup development

# Démarrage des services
docker-compose -f docker-compose.dev.yml --profile full up -d

# Ou par étapes
docker-compose -f docker-compose.dev.yml --profile infrastructure up -d
docker-compose -f docker-compose.dev.yml --profile api up -d
docker-compose -f docker-compose.dev.yml --profile workers up -d
```

**Variables d'environnement clés :**
```bash
ENVIRONMENT=development
WHISPER_MODEL_SIZE=tiny
AWS_ENDPOINT_URL=http://localhost:4566
USE_LOCALSTACK=1
DEBUG=true
```

### Production

**Caractéristiques :**
- Modèle Whisper : `large`
- AWS : Services réels
- Base de données : DynamoDB production
- Temps de transcription : ~30-60 secondes
- Qualité : Haute précision

**Démarrage :**
```bash
# Configuration
python scripts/setup_environment.py setup production

# Vérification des prérequis
python scripts/setup_environment.py check production

# Démarrage des services
docker-compose -f docker-compose.prod.yml up -d
```

**Variables d'environnement critiques :**
```bash
ENVIRONMENT=production
WHISPER_MODEL_SIZE=large
OPENAI_API_KEY=sk-...
STRIPE_API_KEY=sk_live_...
# Pas d'AWS_ENDPOINT_URL (utilise AWS réel)
USE_LOCALSTACK=0
DEBUG=false
```

## 📊 Comparaison des modèles Whisper

| Modèle | Taille | Vitesse | Précision | Usage recommandé |
|--------|--------|---------|-----------|------------------|
| `tiny` | 39 MB | ⚡⚡⚡⚡⚡ | ⭐⭐ | Développement, tests |
| `large` | 1550 MB | ⚡ | ⭐⭐⭐⭐⭐ | Production |

## 🔄 Gestion du changement d'environnement

### Détection automatique

Le système détecte automatiquement l'environnement grâce à la variable `ENVIRONMENT` :

```python
# Dans le worker de transcription
environment = os.environ.get("ENVIRONMENT", "development")

if environment == "production":
    default_model = "large"
else:  # development, testing
    default_model = "tiny"

whisper_model_size = os.environ.get("WHISPER_MODEL_SIZE", default_model)
```

### Fallback automatique

En cas d'échec du chargement du modèle spécifié, le système bascule automatiquement sur le modèle `tiny` :

```python
try:
    model = whisper.load_model(whisper_model_size)
except Exception as e:
    if whisper_model_size != "tiny":
        logger.warning("Falling back to 'tiny' model due to loading error")
        model = whisper.load_model("tiny")
```

## 🐳 Configuration Docker

### Développement

```yaml
# docker-compose.dev.yml
whisper:
  build:
    args:
      - WHISPER_MODEL_SIZE=tiny
  environment:
    - WHISPER_MODEL_SIZE=tiny
```

### Production

```yaml
# docker-compose.prod.yml
whisper:
  build:
    args:
      - WHISPER_MODEL_SIZE=large
  environment:
    - WHISPER_MODEL_SIZE=large
  deploy:
    resources:
      limits:
        memory: 8G
        cpus: '4.0'
```

## 🧪 Tests et validation

### Validation du modèle chargé

```bash
# Vérifier quel modèle est utilisé
docker-compose logs whisper | grep "Loading Whisper model"

# Test de transcription rapide
python -c "
import os
os.environ['WHISPER_MODEL_SIZE'] = 'tiny'
from media_summarizer.workers.transcription.worker import model
print(f'Modèle chargé: {type(model).__name__}')
"
```

### Tests d'intégration

```bash
# Tests avec modèle tiny (rapide)
WHISPER_MODEL_SIZE=tiny pytest media_summarizer/tests/integration/

# Tests avec modèle real (plus long)
WHISPER_MODEL_SIZE=base pytest media_summarizer/tests/integration/ -m "requires_whisper"
```

## 🚨 Dépannage

### Problèmes courants

**1. Modèle Whisper ne se charge pas**
```bash
# Vérifier l'espace disque
df -h

# Vérifier la RAM disponible
free -h

# Forcer le re-téléchargement
docker-compose build --no-cache whisper
```

**2. Mauvaises performances**
```bash
# Vérifier le modèle utilisé
echo $WHISPER_MODEL_SIZE

# Vérifier les logs du worker
docker-compose logs -f whisper
```

**3. Erreurs de configuration**
```bash
# Vérifier la configuration actuelle
python scripts/setup_environment.py check development

# Reconfigurer l'environnement
python scripts/setup_environment.py setup development --force
```

### Logs et monitoring

```bash
# Suivre les logs en temps réel
docker-compose logs -f whisper

# Vérifier les métriques de performance
docker stats whisper

# Vérifier l'utilisation du modèle
grep "Whisper model" /var/log/media-summarizer/*.log
```

## 🔒 Sécurité et bonnes pratiques

### Variables d'environnement sensibles

```bash
# Ne jamais commiter les vraies clés
cp .env.example .env
# Éditer .env avec vos vraies valeurs

# Utiliser des secrets Docker en production
docker secret create openai_key ./openai_key.txt
```

### Ressources système

```yaml
# Production : allouer suffisamment de ressources
deploy:
  resources:
    limits:
      memory: 8G      # Minimum pour le modèle large
      cpus: '4.0'     # Recommandé pour performance optimale
    reservations:
      memory: 4G
      cpus: '2.0'
```

## 📈 Optimisation des performances

### Développement
- Utilisez `tiny` pour des itérations rapides
- Activez le cache des modèles : `docker volume create whisper_cache`
- Parallélisez les tests : `pytest -n auto`

### Production
- Pré-chargez le modèle `large` dans l'image Docker
- Utilisez des instances avec GPU si disponible
- Configurez l'auto-scaling basé sur la charge CPU

## 📚 Références

- [Documentation Whisper OpenAI](https://github.com/openai/whisper)
- [Guide Docker Compose](https://docs.docker.com/compose/)
- [Configuration AWS LocalStack](https://docs.localstack.cloud/)
- [Monitoring des performances](docs/monitoring.md)