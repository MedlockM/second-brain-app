FROM python:3.11-slim

# Installation des dépendances système nécessaires
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Installation uv
RUN pip install uv

WORKDIR /app

# Copie des fichiers de projet
COPY pyproject.toml ./

# Installation des dépendances
RUN uv pip install --system -e .

# Copie du code source
COPY . .

# Variables d'environnement par défaut
ENV PYTHONPATH=/app
ENV EPHEMERAL_MODE=true
ENV MAX_PROCESSING_TIME=3600
ENV HEARTBEAT_INTERVAL=60
ENV VISIBILITY_TIMEOUT=300

# Healthcheck pour Fargate
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Point d'entrée pour le worker éphémère
ENTRYPOINT ["python", "-m", "media_summarizer.workers.ephemeral_worker"]
