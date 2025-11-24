#!/bin/bash
# Verification script for Spotify Playlists Manager deployment

set -e

echo "🔍 Vérification du déploiement Spotify Playlists Manager"
echo "=========================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# AWS LocalStack credentials
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_REGION=us-east-1
AWS_ENDPOINT="http://localhost:4566"

# Check functions
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Check DynamoDB table
echo "1️⃣  Vérification de la table DynamoDB..."
if aws --endpoint-url=$AWS_ENDPOINT dynamodb describe-table --table-name spotify_playlist_follows &>/dev/null; then
    check_pass "Table spotify_playlist_follows existe"
    
    # Check keys
    KEYS=$(aws --endpoint-url=$AWS_ENDPOINT dynamodb describe-table --table-name spotify_playlist_follows --query 'Table.KeySchema' --output json)
    if echo "$KEYS" | grep -q "user_id" && echo "$KEYS" | grep -q "playlist_id"; then
        check_pass "Clés de partition correctes (user_id + playlist_id)"
    else
        check_fail "Structure de clés incorrecte"
    fi
else
    check_fail "Table spotify_playlist_follows n'existe pas"
    echo "   → Exécutez: docker-compose -f docker-compose.dev.yml down && docker-compose -f docker-compose.dev.yml --profile infrastructure up -d"
fi
echo ""

# 2. Check API endpoints
echo "2️⃣  Vérification des endpoints API..."
API_URL="http://localhost:8000"

if curl -s "$API_URL/openapi.json" | grep -q "/api/v1/spotify/playlists"; then
    check_pass "Endpoint /api/v1/spotify/playlists disponible"
else
    check_fail "Endpoint /api/v1/spotify/playlists manquant"
fi

if curl -s "$API_URL/openapi.json" | grep -q "/api/v1/spotify/playlists/{playlist_id}/subscription"; then
    check_pass "Endpoint /api/v1/spotify/playlists/{id}/subscription disponible"
else
    check_fail "Endpoint subscription manquant"
fi

if curl -s "$API_URL/openapi.json" | grep -q "/api/v1/spotify/playlists/{playlist_id}/sync"; then
    check_pass "Endpoint /api/v1/spotify/playlists/{id}/sync disponible"
else
    check_fail "Endpoint sync manquant"
fi

if curl -s "$API_URL/openapi.json" | grep -q "/api/v1/spotify/subscriptions"; then
    check_pass "Endpoint /api/v1/spotify/subscriptions disponible"
else
    check_fail "Endpoint subscriptions manquant"
fi
echo ""

# 3. Check Frontend files
echo "3️⃣  Vérification des fichiers Frontend..."
if [ -f "front/src/components/SpotifyPlaylists.tsx" ]; then
    check_pass "Composant SpotifyPlaylists.tsx existe"
else
    check_fail "SpotifyPlaylists.tsx manquant"
fi

if grep -q "getPlaylists" front/src/services/spotifyService.ts; then
    check_pass "Service spotifyService.ts mis à jour"
else
    check_fail "spotifyService.ts non mis à jour"
fi

if grep -q "SpotifyPlaylists" front/src/components/Dashboard.tsx; then
    check_pass "Dashboard.tsx intègre SpotifyPlaylists"
else
    check_fail "Dashboard.tsx non mis à jour"
fi
echo ""

# 4. Check Backend files
echo "4️⃣  Vérification des fichiers Backend..."
if [ -f "media_summarizer/core/models/spotify.py" ]; then
    check_pass "Modèle spotify.py existe"
else
    check_fail "Modèle spotify.py manquant"
fi

if [ -f "media_summarizer/utils/spotify_follows_db.py" ]; then
    check_pass "Helper spotify_follows_db.py existe"
else
    check_fail "Helper spotify_follows_db.py manquant"
fi

if [ -f "media_summarizer/core/services/playlist_sync.py" ]; then
    check_pass "Service playlist_sync.py existe"
else
    check_fail "Service playlist_sync.py manquant"
fi

if [ -f "media_summarizer/api/endpoints/spotify_playlists.py" ]; then
    check_pass "Endpoints spotify_playlists.py existe"
else
    check_fail "Endpoints spotify_playlists.py manquant"
fi
echo ""

# 5. Check services status
echo "5️⃣  Vérification des services..."
if docker-compose -f docker-compose.dev.yml ps | grep -q "api.*Up"; then
    check_pass "API container est en cours d'exécution"
else
    check_warn "API container n'est pas en cours d'exécution"
fi

if docker-compose -f docker-compose.dev.yml ps | grep -q "localstack.*Up.*healthy"; then
    check_pass "LocalStack est en cours d'exécution et healthy"
else
    check_warn "LocalStack n'est pas healthy"
fi

if curl -s http://localhost:5173 | grep -q "vite"; then
    check_pass "Frontend Vite dev server est accessible"
else
    check_warn "Frontend Vite dev server n'est pas accessible sur le port 5173"
fi
echo ""

# Summary
echo "=========================================================="
echo "✅ Vérification terminée !"
echo ""
echo "📖 Prochaines étapes:"
echo "   1. Ouvrir http://localhost:5173 dans le navigateur"
echo "   2. Se connecter avec un compte utilisateur"
echo "   3. Cliquer sur l'icône Spotify sur le dashboard"
echo "   4. Autoriser l'application Spotify"
echo "   5. Vérifier l'affichage de la page playlists"
echo ""
echo "📝 Guide de tests manuels complet:"
echo "   scripts/test_spotify_playlists_manual.md"
echo ""
