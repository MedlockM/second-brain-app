FROM python:3.11-slim

# Installation des dépendances système pour Whisper
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Installation uv
RUN pip install uv

WORKDIR /app

# Copie des fichiers de projet
COPY pyproject.toml ./

# Installation des dépendances
RUN uv pip install --system -e .

# Pré-téléchargement du modèle Whisper Tiny pour les tests
RUN python -c "import whisper; whisper.load_model('tiny')"

# Copie du code source
COPY . .

# Commande par défaut
CMD ["python", "-m", "media_summarizer.workers.transcription.worker"]