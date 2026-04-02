# Lambda Zip Builder Dockerfile - Optimized with caching
# Key optimization: Use multi-stage build to cache pip install layer
#
# The zip file is output to /output/lambda_package.zip

FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Stage 1: Install dependencies (cached unless requirements change)
# This layer is cached and reused across builds
RUN pip install --no-cache-dir --target /deps \
    aioboto3>=12.0.0 \
    boto3>=1.34.0 \
    httpx>=0.25.0 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    python-dotenv>=1.0.0 \
    tenacity>=8.2.0

# Clean up dependencies (do this once in cached layer)
RUN cd /deps && \
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true && \
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true && \
    find . -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find . -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find . -type d -name "examples" -exec rm -rf {} + 2>/dev/null || true && \
    rm -rf pydantic/v1 2>/dev/null || true

# Prune unused botocore service models (reduces ~17MB to ~3MB)
RUN if [ -d "/deps/botocore/data" ]; then \
    cd /deps/botocore/data && \
    for dir in */; do \
        service="${dir%/}"; \
        case "$service" in \
            dynamodb|sqs|sts|iam|lambda|events|logs|endpoints|partitions|_retry|sdk-default-configuration) ;; \
            *) rm -rf "$service" 2>/dev/null || true ;; \
        esac; \
    done; \
    fi

# Stage 2: Final assembly (only this runs when code changes)
FROM python:3.11-slim AS assembler

RUN apt-get update && apt-get install -y --no-install-recommends \
    zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy pre-built, cleaned dependencies from builder stage (cached)
COPY --from=builder /deps /build/

# Script to assemble final zip (runs at container start)
COPY <<'EOF' /assemble.sh
#!/bin/bash
set -e

echo "📦 Assembling Lambda zip package..."

# Copy application code from mounted volume
if [ -d "/app/media_summarizer" ]; then
    cp -r /app/media_summarizer /build/
    # Clean pycache from app code
    find /build/media_summarizer -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
else
    echo "⚠️  Warning: /app/media_summarizer not found"
fi

# Create the zip
cd /build
zip -q -r /output/lambda_package.zip .

# Show results
ZIP_SIZE=$(du -h /output/lambda_package.zip | cut -f1)
echo ""
echo "✅ Lambda package built successfully!"
echo "📊 Package size: $ZIP_SIZE"
echo "📍 Output: /output/lambda_package.zip"
EOF

RUN chmod +x /assemble.sh

ENTRYPOINT ["/assemble.sh"]
