# Optimized Worker Dockerfile
# Key optimizations:
# 1. Multi-stage build for better layer caching
# 2. uv native pyproject.toml support (fast, no duplication)
# 3. No editable install (useless in containers)

# Stage 1: Base image with system dependencies
FROM python:3.11-slim AS base

# Install system dependencies (rarely changes - good cache layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv package manager
RUN pip install --no-cache-dir uv
ENV UV_HTTP_TIMEOUT=180 PIP_DEFAULT_TIMEOUT=180

WORKDIR /app

# Stage 2: Dependencies (cached unless pyproject.toml changes)
FROM base AS dependencies

# Copy the manifest and its lockfile first (better cache)
COPY pyproject.toml uv.lock ./

# Install the locked versions, never the pyproject ranges — resolving at build
# time makes every build a different image (see the comment in
# lambda-api.Dockerfile: an unpinned fastapi took dev down). The worker extra
# carries the article-extraction stack.
# --no-emit-project: the project itself is the source tree copied below.
RUN uv export --frozen --no-dev --extra worker --no-emit-project \
      --format requirements-txt -o /tmp/requirements.txt \
    && uv pip install --system -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Stage 3: Final image with source code
FROM dependencies AS final

WORKDIR /app

# Copy source code (changes frequently, but deps are cached above)
COPY media_summarizer/ ./media_summarizer/

# Set Python path so the module is importable
ENV PYTHONPATH=/app

# No default command - specified in docker-compose
