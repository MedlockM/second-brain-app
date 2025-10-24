#!/bin/bash

# Script de démarrage pour le développement frontend + backend
# Usage: ./start-dev.sh [frontend|backend|all]

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/front"

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Fonction pour vérifier si un port est utilisé
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Fonction pour démarrer le backend
start_backend() {
    log_info "Démarrage du backend API..."

    cd "$PROJECT_ROOT"

    if check_port 8000; then
        log_warn "Le port 8000 est déjà utilisé. Le backend est peut-être déjà en cours d'exécution."
        log_info "Vérification de l'état de l'API..."

        if curl -s http://localhost:8000/api/v1/health/ > /dev/null 2>&1; then
            log_success "L'API est déjà en cours d'exécution et répond correctement"
            log_info "API disponible sur http://localhost:8000"
            log_info "Documentation API: http://localhost:8000/docs"
            return 0
        else
            log_warn "Le port 8000 est utilisé mais l'API ne répond pas correctement"
            log_info "Pour arrêter le backend existant: docker compose -f docker-compose.dev.yml --profile api down"
            return 1
        fi
    else
        log_info "Lancement des conteneurs Docker (localstack, terraform, api)..."
        log_info "Cela peut prendre quelques minutes lors du premier lancement..."

        docker compose -f docker-compose.dev.yml --profile api up -d

        if [ $? -ne 0 ]; then
            log_error "Échec du démarrage des conteneurs Docker"
            log_info "Consultez les logs avec: docker compose -f docker-compose.dev.yml --profile api logs"
            exit 1
        fi

        log_info "Attente de l'initialisation des services..."
        log_info "- LocalStack (AWS local)"
        log_info "- Terraform (infrastructure)"
        log_info "- API FastAPI"

        # Attendre que le conteneur api soit complètement démarré
        log_info "Attente du démarrage du conteneur API..."
        local container_wait=0
        while [ $container_wait -lt 30 ]; do
            if docker ps | grep -q "media-summarizer-project-api-1"; then
                local status=$(docker inspect --format='{{.State.Status}}' media-summarizer-project-api-1 2>/dev/null)
                if [ "$status" = "running" ]; then
                    log_info "Conteneur API en cours d'exécution"
                    break
                fi
            fi
            sleep 2
            container_wait=$((container_wait + 2))
            echo -n "."
        done
        echo ""

        # Attendre que l'API réponde aux requêtes health check
        log_info "Attente de la disponibilité de l'API..."
        local max_wait=60
        local waited=0

        while [ $waited -lt $max_wait ]; do
            if curl -sf http://localhost:8000/api/v1/health/ > /dev/null 2>&1; then
                log_success "Backend API démarré avec succès!"
                log_info "API disponible sur http://localhost:8000"
                log_info "Documentation API: http://localhost:8000/docs"
                return 0
            fi
            sleep 2
            waited=$((waited + 2))
            echo -n "."
        done

        echo ""
        log_error "Le backend n'a pas démarré dans les temps (timeout après ${max_wait}s)"
        log_info "Vérifiez les logs avec: docker compose -f docker-compose.dev.yml --profile api logs api"
        exit 1
    fi
}

# Fonction pour démarrer le frontend
start_frontend() {
    log_info "Démarrage du frontend..."

    cd "$FRONTEND_DIR"

    # Vérifier si node_modules existe
    if [ ! -d "node_modules" ]; then
        log_info "node_modules non trouvé. Installation des dépendances..."
        npm install
    fi

    # Vérifier si .env.development existe
    if [ ! -f ".env.development" ]; then
        log_warn ".env.development non trouvé. Copie depuis .env.example..."
        if [ -f ".env.example" ]; then
            cp .env.example .env.development
            log_success "Fichier .env.development créé"
        else
            log_error "Fichier .env.example non trouvé!"
            exit 1
        fi
    fi

    log_info "Lancement du serveur de développement Vite..."
    npm run dev
}

# Fonction pour arrêter les services
stop_services() {
    log_info "Arrêt des services..."

    cd "$PROJECT_ROOT"

    log_info "Arrêt du backend..."
    docker compose -f docker-compose.dev.yml --profile api down

    log_success "Services arrêtés"
}

# Fonction pour afficher les logs
show_logs() {
    cd "$PROJECT_ROOT"
    docker compose -f docker-compose.dev.yml --profile api logs -f
}

# Fonction pour tout démarrer
start_all() {
    log_info "Démarrage du backend et du frontend..."
    echo ""

    # Démarrer le backend
    start_backend

    local backend_status=$?

    if [ $backend_status -ne 0 ]; then
        log_error "Le backend n'a pas démarré correctement. Arrêt."
        exit 1
    fi

    echo ""
    log_info "Backend prêt! Démarrage du frontend..."
    sleep 2

    # Démarrer le frontend
    start_frontend
}

# Fonction pour afficher l'aide
show_help() {
    cat << 'EOF'
Usage: ./start-dev.sh [OPTIONS]

Options:
  frontend, front, f    Démarrer uniquement le frontend
  backend, back, b, api Démarrer uniquement le backend
  all, a                Démarrer le backend et le frontend (défaut)
  stop, down            Arrêter tous les services backend
  logs, log, l          Afficher les logs du backend
  help, h, -h, --help   Afficher cette aide

Exemples:
  ./start-dev.sh                # Démarre tout (backend + frontend)
  ./start-dev.sh frontend       # Démarre uniquement le frontend
  ./start-dev.sh backend        # Démarre uniquement le backend
  ./start-dev.sh stop           # Arrête le backend
  ./start-dev.sh logs           # Affiche les logs du backend

Services backend:
  - LocalStack (AWS local) : http://localhost:4566
  - API FastAPI           : http://localhost:8000
  - API Documentation     : http://localhost:8000/docs

Services frontend:
  - Vite dev server       : http://localhost:5173

Pour arrêter les services:
  Backend:  ./start-dev.sh stop  OU  docker compose -f docker-compose.dev.yml --profile api down
  Frontend: Ctrl+C dans le terminal

Configuration:
  Variables d'environnement dans front/.env.development:
    VITE_API_URL=http://localhost:8000
EOF
}

# Point d'entrée principal
main() {
    local command="${1:-all}"

    case "$command" in
        frontend|front|f)
            start_frontend
            ;;
        backend|back|b|api)
            start_backend
            ;;
        all|a)
            start_all
            ;;
        stop|down)
            stop_services
            ;;
        logs|log|l)
            show_logs
            ;;
        help|h|-h|--help)
            show_help
            ;;
        *)
            log_error "Option inconnue: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Vérifier les prérequis
check_prerequisites() {
    local missing=0

    if ! command -v docker &> /dev/null; then
        log_error "Docker n'est pas installé. Veuillez installer Docker pour continuer."
        missing=1
    fi

    if ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose n'est pas disponible. Veuillez installer Docker Compose pour continuer."
        missing=1
    fi

    if ! command -v npm &> /dev/null; then
        log_error "npm n'est pas installé. Veuillez installer Node.js et npm pour continuer."
        missing=1
    fi

    if ! command -v curl &> /dev/null; then
        log_warn "curl n'est pas installé. Certaines vérifications seront désactivées."
    fi

    if [ $missing -eq 1 ]; then
        exit 1
    fi
}

# Vérifier les prérequis avant d'exécuter
check_prerequisites

# Exécuter le script
main "$@"
