FROM python:3.11-slim

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
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

# Copie du code source
COPY . .

# La commande sera spécifiée dans docker-compose