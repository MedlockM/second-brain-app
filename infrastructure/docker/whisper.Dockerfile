FROM python:3.11-slim

# Installation des dépendances système pour Whisper
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Installation uv
RUN pip install uv
ENV UV_HTTP_TIMEOUT=180 PIP_DEFAULT_TIMEOUT=180

WORKDIR /app

# Copie des fichiers de projet
COPY pyproject.toml ./

# Installation des dépendances
RUN uv pip install --system -e .

# Pré-téléchargement du modèle Whisper
ARG WHISPER_MODEL_SIZE=tiny
ENV WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE}
RUN python -c "import whisper; import os; whisper.load_model(os.environ.get('WHISPER_MODEL_SIZE', 'tiny'))"

# Copie du code source
COPY . .

# Commande par défaut (peut être surchargée)
# Mode SQS worker par défaut, HTTP server si WHISPER_MODE=http
CMD ["sh", "-c", "if [ \"$WHISPER_MODE\" = \"http\" ]; then python -m media_summarizer.workers.transcription.http_server; else python -m media_summarizer.workers.transcription.worker; fi"]
