FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY pyproject.toml ./
RUN pip install -e .
RUN pip install -e ".[dev]"

# Install additional E2E testing dependencies
RUN pip install \
    docker \
    pytest-xdist \
    pytest-html \
    pytest-json-report

# Copy application code
COPY . .

# Create directories for test artifacts
RUN mkdir -p /app/test-results /app/test-logs

# Set environment variables
ENV PYTHONPATH=/app
ENV TEST_MODE=e2e

# Default command (can be overridden)
CMD ["python", "-m", "pytest", "tests/e2e/", "-v", "--tb=short", "--html=/app/test-results/report.html", "--json-report", "--json-report-file=/app/test-results/report.json"]