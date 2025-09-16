# Media Summarizer Makefile
# Simplified commands for development and testing

# Ensure bash is used for recipes (needed for sourcing .env.dev)
SHELL := bash

.PHONY: help install dev test test-unit test-integration test-e2e test-all clean setup-dev setup-e2e coverage lint format docker-build docker-up docker-down

# Default target
help: ## Show this help message
	@echo "Media Summarizer Development Commands"
	@echo "====================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation and setup
install: ## Install dependencies
	uv pip install -e ".[dev]"

setup-dev: ## Setup development environment
	@echo "🔧 Setting up development environment..."
	cp .env.example .env || echo "⚠️ .env.example not found, please create .env manually"
	uv pip install -e ".[dev]"
	@echo "✅ Development environment ready!"
	@echo "📝 Don't forget to configure your .env file with API keys"

setup-e2e: ## Setup E2E testing environment
	@echo "🧪 Setting up E2E testing environment..."
	docker-compose -f docker-compose.dev.yml --profile infrastructure up -d
	@echo "⏳ Waiting for LocalStack to be ready..."
	@timeout 120 bash -c 'until curl -s http://localhost:4566/health | grep -q "running"; do sleep 3; echo "Waiting..."; done' || echo "⚠️ LocalStack may not be ready"
	@echo "✅ E2E environment ready!"

# Testing commands
test: test-unit ## Run unit tests (default)

test-unit: ## Run unit tests only
	@echo "🧪 Running unit tests..."
	pytest -m "not integration and not e2e" -v --tb=short

test-integration: ## Run integration tests
	@echo "🔗 Running integration tests..."

	bash -lc 'set -a; source .env.dev 2>/dev/null || true; set +a; uv run pytest -m integration -v --tb=short --no-cov'
test-e2e: ## Run E2E tests (assumes LocalStack already running)
	@echo "🧪 Running E2E tests..."
	@echo "⚠️ Make sure LocalStack is running: 'make setup-e2e'"
	pytest media_summarizer/tests/end_to_end/ -m e2e -v -s --tb=short

test-all: ## Run all tests (unit + integration)
	@echo "🎯 Running all tests..."
	$(MAKE) test-unit
	$(MAKE) test-integration

test-fast: ## Run fast tests only
	@echo "⚡ Running fast tests..."
	pytest -m "fast or (not slow and not e2e)" -v --tb=short

test-with-coverage: ## Run tests with coverage report
	@echo "📊 Running tests with coverage..."
	pytest --cov=media_summarizer --cov-report=html --cov-report=term-missing --cov-fail-under=80

# Code quality
lint: ## Run linting
	@echo "🔍 Running linters..."
	ruff check media_summarizer/
	mypy media_summarizer/ || echo "⚠️ MyPy issues found"

format: ## Format code
	@echo "🎨 Formatting code..."
	ruff format media_summarizer/
	ruff check --fix media_summarizer/

# Coverage
coverage: ## Generate coverage report
	@echo "📊 Generating coverage report..."
	pytest --cov=media_summarizer --cov-report=html --cov-report=term-missing
	@echo "📖 Coverage report generated in htmlcov/index.html"

coverage-e2e: ## Generate E2E coverage report (assumes LocalStack running)
	@echo "📊 Generating E2E coverage report..."
	pytest media_summarizer/tests/end_to_end/ -m e2e --cov=media_summarizer --cov-report=html:htmlcov-e2e --cov-report=term-missing
	@echo "📖 E2E coverage report generated in htmlcov-e2e/index.html"

# Docker commands
docker-build: ## Build Docker images
	@echo "🐳 Building Docker images..."
	docker-compose -f docker-compose.dev.yml build

docker-up: ## Start all services with Docker
	@echo "🚀 Starting all services..."
	docker-compose -f docker-compose.dev.yml --profile full up -d

docker-up-infra: ## Start infrastructure services only
	@echo "🏗️ Starting infrastructure services..."
	docker-compose -f docker-compose.dev.yml --profile infrastructure up -d

docker-up-api: ## Start API and infrastructure
	@echo "🔗 Starting API services..."
	docker-compose -f docker-compose.dev.yml --profile api up -d

docker-down: ## Stop all Docker services
	@echo "🛑 Stopping Docker services..."
	docker-compose -f docker-compose.dev.yml down -v --remove-orphans

docker-logs: ## Show Docker logs
	docker-compose -f docker-compose.dev.yml logs -f

docker-status: ## Show Docker services status
	@echo "📊 Docker services status:"
	docker-compose -f docker-compose.dev.yml ps

# Development utilities
dev: ## Start development environment
	@echo "🚀 Starting development environment..."
	$(MAKE) docker-up-infra
	@echo "✅ Development environment started!"
	@echo "🔗 LocalStack: http://localhost:4566"
	@echo "📝 Configure .env file and start API with: uvicorn media_summarizer.api.main:app --reload"

dev-full: ## Start full development stack
	@echo "🚀 Starting full development stack..."
	$(MAKE) docker-up
	@echo "✅ Full stack started!"
	@echo "🔗 API: http://localhost:8000"
	@echo "🔗 LocalStack: http://localhost:4566"

init-db: ## Initialize database tables
	@echo "🗃️ Initializing database..."
	python scripts/init_db.py init
	@echo "✅ Database initialized!"

health-check: ## Check services health
	@echo "🏥 Checking services health..."
	@echo "LocalStack:"
	@curl -s http://localhost:4566/health | jq . || echo "❌ LocalStack not responding"
	@echo
	@echo "API:"
	@curl -s http://localhost:8000/health | jq . || echo "❌ API not responding"

# Cleanup
clean: ## Clean up temporary files and Docker resources
	@echo "🧹 Cleaning up..."
	$(MAKE) docker-down
	docker system prune -f
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf htmlcov-e2e/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf *.xml
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleanup completed!"

clean-data: ## Clean up all data (including volumes)
	@echo "🗑️ Cleaning up all data..."
	$(MAKE) docker-down
	docker volume prune -f
	@echo "✅ All data cleaned!"

# CI/CD helpers
ci-setup: ## Setup CI environment
	@echo "⚙️ Setting up CI environment..."
	uv pip install -e ".[dev]"

ci-test-unit: ## Run unit tests for CI
	pytest -m "not integration and not e2e" --tb=short --strict-markers

ci-test-integration: ## Run integration tests for CI
	pytest -m integration --tb=short --strict-markers

ci-test-e2e: ## Run E2E tests for CI (with full setup/teardown)
	$(MAKE) setup-e2e
	pytest -m e2e --tb=short --strict-markers
	$(MAKE) docker-down

# Quick development commands
quick-test: ## Quick test run (unit tests only)
	pytest -x -q -m "not integration and not e2e"

watch-test: ## Watch files and run tests on changes
	@echo "👀 Watching files for changes..."
	pytest-watch -- -m "not integration and not e2e" -x

# Documentation
docs: ## Generate documentation
	@echo "📚 Generating documentation..."
	@echo "E2E Tests documentation: media_summarizer/tests/end_to_end/README.md"
	@echo "Project documentation: README.md"

# Environment validation
validate-env: ## Validate environment setup
	@echo "✅ Validating environment..."
	@python -c "import media_summarizer; print('✅ Package imports correctly')"
	@python -c "import pytest; print('✅ Pytest available')"
	@docker --version > /dev/null && echo "✅ Docker available" || echo "❌ Docker not available"
	@curl --version > /dev/null && echo "✅ Curl available" || echo "❌ Curl not available"
	@test -f .env && echo "✅ .env file exists" || echo "⚠️ .env file missing"

# Example workflows


# Development workflow shortcuts
dev-e2e: ## Start infrastructure for E2E testing
	@echo "🔄 Starting E2E development environment..."
	$(MAKE) setup-e2e
	@echo "✅ Infrastructure ready! Now run 'make test-e2e' for testing"
	@echo "🛑 Run 'make docker-down' when done"

# Development shortcuts
start: dev ## Alias for dev
stop: docker-down ## Alias for docker-down
restart: ## Restart development environment
	$(MAKE) docker-down
	$(MAKE) dev

# Help for specific test types
help-testing: ## Show testing help
	@echo "Testing Commands Help"
	@echo "===================="
	@echo "make test-unit          - Fast unit tests only"
	@echo "make test-integration   - Integration tests with LocalStack"
	@echo "make test-e2e          - E2E tests (assumes LocalStack running)"
	@echo "make test-all          - All tests (unit + integration)"
	@echo "make test-fast         - Only fast tests"
	@echo ""
	@echo "E2E Development workflow:"
	@echo "make dev-e2e           - Start infrastructure for E2E testing"
	@echo "make test-e2e          - Run E2E tests (multiple times, fast)"
	@echo "make docker-down       - Stop infrastructure when done"
	@echo ""
	@echo "For CI/CD, tests are automatically run via GitHub Actions:"
	@echo "- .github/workflows/test-coverage.yml   - Unit & integration tests"
	@echo "- .github/workflows/integration-tests.yml - Component & workflow tests"
	@echo "- .github/workflows/e2e-tests.yml       - E2E tests"

# Default Python and environment settings
PYTHON := python
UV := uv
PYTEST := pytest
DOCKER_COMPOSE := docker-compose -f docker-compose.dev.yml
