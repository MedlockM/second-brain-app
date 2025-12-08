#!/bin/bash
# Build Spotify Sync Lambda packages for LocalStack deployment
# This builds both the worker (SQS-triggered) and dispatcher (EventBridge-triggered) lambdas

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔨 Building Spotify Sync Lambda packages..."

# Build main worker lambda (using existing script)
echo ""
echo "📦 Building spotify-sync-worker..."
"$PROJECT_ROOT/.venv/bin/python" "$SCRIPT_DIR/build_lambda_package.py" \
    --output "$PROJECT_ROOT/infrastructure/terraform/localstack/spotify_sync_worker.zip" \
    --module media_summarizer.workers.spotify_sync.worker \
    -v

# Build dispatcher lambda (same package, different handler)
echo ""
echo "📦 Building spotify-sync-dispatcher..."
"$PROJECT_ROOT/.venv/bin/python" "$SCRIPT_DIR/build_lambda_package.py" \
    --output "$PROJECT_ROOT/infrastructure/terraform/localstack/spotify_sync_dispatcher.zip" \
    --module media_summarizer.workers.spotify_sync.dispatcher \
    -v

echo ""
echo "✅ Lambda packages built successfully!"
echo ""
echo "Packages created:"
ls -lh "$PROJECT_ROOT/infrastructure/terraform/localstack/"*.zip 2>/dev/null || echo "  (no zip files found)"

echo ""
echo "Next steps:"
echo "1. Restart LocalStack: docker-compose -f docker-compose.dev.yml restart localstack"
echo "2. Apply Terraform: cd infrastructure/terraform/localstack && terraform apply"
