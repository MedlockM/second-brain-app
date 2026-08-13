FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv to resolve from the lockfile rather than the pyproject ranges —
# resolving at build time makes every build a different image (see the comment
# in lambda-api.Dockerfile: an unpinned fastapi took dev down).
RUN pip install --no-cache-dir uv

# Copy the manifest and its lockfile, then install the locked dev set.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --extra dev --no-emit-project --format requirements-txt \
      -o /tmp/requirements.txt \
    && uv pip install --system -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# E2E-runner-only dependencies. These are not in pyproject.toml, so they are
# not in the lock either; pin them here so this image stays reproducible too.
RUN uv pip install --system \
    docker==7.1.0 \
    pytest-xdist==3.6.1 \
    pytest-html==4.1.1 \
    pytest-json-report==1.5.0

# Copy application code
COPY . .

# Create directories for test artifacts
RUN mkdir -p /app/test-results /app/test-logs

# Set environment variables
ENV PYTHONPATH=/app
ENV TEST_MODE=e2e

# Default command (can be overridden)
CMD ["python", "-m", "pytest", "tests/e2e/", "-v", "--tb=short", "--html=/app/test-results/report.html", "--json-report", "--json-report-file=/app/test-results/report.json"]