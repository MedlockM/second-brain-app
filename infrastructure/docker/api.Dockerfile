FROM python:3.11-slim

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    build-essential \
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

# Exposition du port
EXPOSE 8000

# Commande par défaut
CMD ["uvicorn", "media_summarizer.api.main:app", "--host", "0.0.0.0", "--port", "8000"]