# Media Summarizer Makefile
# Simplified commands for development and testing

# Ensure bash is used for recipes (needed for sourcing .env.dev)
SHELL := bash

# Docker Compose command
DOCKER_PROFILE ?= full
DOCKER_COMPOSE := docker-compose -f docker-compose.dev.yml --env-file .env.dev --profile $(DOCKER_PROFILE)

.PHONY: help install dev test test-unit test-integration test-e2e test-all clean setup-dev setup-e2e coverage lint format docker-build docker-up docker-down docker-logs restart-workers logs-whisper logs-download logs-summarize logs-email logs-quiz logs-episode-events logs-workers logs-all-workers logs-api lambda-build lambda-deploy lambda-redeploy lambda-invoke

# Default target
help: ## Show this help message
	@echo "Media Summarizer Development Commands"
	@echo "====================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Testing commands
test-e2e: ## Run E2E tests (assumes LocalStack already running)
	@echo "🧪 Running E2E tests..."
	@echo "⚠️ Make sure LocalStack is running: 'make setup-e2e'"
	pytest media_summarizer/tests/end_to_end/ -m e2e -v -s --tb=short

# Code quality
lint: ## Run linting
	@echo "🔍 Running linters..."
	ruff check media_summarizer/
	mypy media_summarizer/ || echo "⚠️ MyPy issues found"

format: ## Format code
	@echo "🎨 Formatting code..."
	ruff format media_summarizer/
	ruff check --fix media_summarizer/

docker-up: ## Start all services with Docker
	@echo "🚀 Starting all services..."
	$(DOCKER_COMPOSE) up -d

docker-down: ## Stop all Docker services
	@echo "🛑 Stopping Docker services..."
	@$(DOCKER_COMPOSE) down -v --remove-orphans || true
	@echo "🧹 Stopping any remaining containers for this repo (including LocalStack lambdas)..."
	@docker ps -aq --filter "label=com.docker.compose.project=media-summarizer-project" | \
		xargs -r docker stop || true
	@docker ps -aq --filter "name=media-summarizer-project-localstack-1-lambda-" | \
		xargs -r docker stop || true
	@echo "🧹 Attempting to remove compose network..."
	@docker network rm media-summarizer-project_default 2>/dev/null || true
	@echo "✅ Docker services stopped (removed remaining repo containers and cleaned network)"


docker-logs: ## Show Docker logs (all services)
	$(DOCKER_COMPOSE) logs -f

restart-workers: ## Restart worker services (download, whisper, summarize, email, quiz, episode-events)
	@echo "🔄 Restarting worker services..."
	$(DOCKER_COMPOSE) restart download-worker whisper summarize-worker email-worker quiz-worker episode-events-worker

logs-whisper: ## Follow Whisper transcription service logs
	@echo "📜 Tailing whisper logs..."
	$(DOCKER_COMPOSE) logs -f whisper

logs-download: ## Follow Download worker logs
	@echo "📥 Tailing download-worker logs..."
	$(DOCKER_COMPOSE) logs -f download-worker

logs-summarize: ## Follow Summarize worker logs
	@echo "📝 Tailing summarize-worker logs..."
	$(DOCKER_COMPOSE) logs -f summarize-worker

logs-email: ## Follow Email worker logs
	@echo "✉️ Tailing email-worker logs..."
	$(DOCKER_COMPOSE) logs -f email-worker

logs-quiz: ## Follow Quiz worker logs
	@echo "🧠 Tailing quiz-worker logs..."
	$(DOCKER_COMPOSE) logs -f quiz-worker

logs-episode-events: ## Follow Episode Events worker logs
	@echo "🎬 Tailing episode-events-worker logs..."
	$(DOCKER_COMPOSE) logs -f episode-events-worker

logs-workers: ## Follow logs for all workers at once
	@echo "🔁 Tailing all worker logs (download, whisper, summarize, email, quiz, episode-events)..."
	$(DOCKER_COMPOSE) logs -f download-worker whisper summarize-worker email-worker quiz-worker episode-events-worker

logs-all-workers: ## Alias for logs-workers
	$(MAKE) logs-workers

logs-api: ## Follow API logs
	@echo "🌐 Tailing api logs..."
	$(DOCKER_COMPOSE) logs -f api

# Development shortcuts
start: dev ## Alias for dev
stop: docker-down ## Alias for docker-down
restart: ## Restart development environment
	$(MAKE) docker-down
	$(MAKE) dev

