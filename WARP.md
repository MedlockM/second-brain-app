# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project: Media Summarizer — FastAPI service plus background workers that process podcast links into AI-generated summaries using AWS-like services (LocalStack in dev, AWS in prod).

Contents
- Common commands (install, run, test, lint/format)
- How to run subsets (single test, markers, E2E)
- Big-picture architecture (API, workers, queues, storage, DB)
- Pointers to important repo docs

Common commands

Setup (Python 3.10+, uv, Docker, Docker Compose)
- Create/activate venv and install deps
  - source .venv/bin/activate
  - uv pip install -e .
  - uv pip install -e ".[dev]"
- Environment: copy or prepare .env from example (if present)
  - cp .env.example .env

Services (dev, via compose profiles)
- Full stack (API + workers + LocalStack)
  - docker-compose -f docker-compose.dev.yml --profile full up -d
- API only
  - docker-compose -f docker-compose.dev.yml --profile api up -d
- Workers only
  - docker-compose -f docker-compose.dev.yml --profile workers up -d
- Infrastructure only (LocalStack)
  - docker-compose -f docker-compose.dev.yml --profile infrastructure up -d
- Stop everything
  - docker-compose -f docker-compose.dev.yml down
- Logs
  - docker-compose -f docker-compose.dev.yml logs api
  - docker-compose -f docker-compose.dev.yml logs download-worker

API (local)
- Uvicorn (hot reload): uvicorn media_summarizer.api.main:app --reload --port 8000
- Health check: curl http://localhost:8000/health or http://localhost:8000/api/v1/health
- API docs: http://localhost:8000/docs

Database (DynamoDB via LocalStack)
- Status: python scripts/init_db.py status
- Health: python scripts/init_db.py health
- Initialize (verify required tables exist): python scripts/init_db.py init

Testing
- No automated tests in V1. Validation is done via local manual runs and mobile Maestro flows (mobile/.maestro/).

Linting and formatting
- Lint (Ruff): ruff check .
- Lint (auto-fix): ruff check . --fix
- Format (Black): black .
- Format check: black . --check

Development helpers
- One-shot environment bootstrap with health checks: python scripts/start_dev_environment.py --profile full
- Ephemeral worker scaling test: python scripts/test_ephemeral_local.py --build

Big-picture architecture

Overview
- API: FastAPI app defined in media_summarizer/api/main.py, with versioned routes under /api/v1
  - Endpoints include health, users, credits, podcast-search, jobs
- Workers: Background processes consuming SQS queues and producing outputs to S3 and notifications via SES
  - Download Worker: Fetches audio from episode URL -> stores in S3 -> enqueues transcription job
  - Transcription Worker: Pulls audio from S3 -> Whisper transcription -> stores transcript in S3 -> enqueues summarization job
  - Summarization Worker: Pulls transcript from S3 -> calls LLM (OpenAI API) -> stores summary JSON in S3 -> enqueues email notification
  - Email Worker: Sends SES emails to users (completion/error)
- Messaging: Amazon SQS queues (LocalStack in dev). Defaults in docker-compose.dev.yml
  - audio-download-queue, transcription-queue, summarization-queue, email-notification-queue
- Storage: Amazon S3 buckets (LocalStack in dev)
  - media-summarizer-audio, media-summarizer-transcriptions, media-summarizer-summaries
- Database: DynamoDB tables (LocalStack in dev)
  - users, processing_jobs, credit_transactions (+ optional podcasts, episodes)
- Payments/Credits: Stripe for payments; credits tracked in DynamoDB; API exposes credit endpoints
- Composition: docker-compose.dev.yml orchestrates LocalStack, API, and all workers with environment variables for buckets/tables/queues

Key flows (end-to-end)
1) Submit/search/select episode via API
2) API writes job metadata (DynamoDB) and enqueues processing
3) Download -> Transcription (Whisper) -> Summarization (LLM) via SQS chain
4) Summary stored to S3; email notification sent via SES; job status tracked in DynamoDB

Important references
- README.md: Quickstart, services, environments, and test overview
- docs/whisper-hybrid-approach.md: Async wrapper pattern used to integrate synchronous Whisper within async worker code
- scripts/*: Environment setup, DB CLI, E2E runner, integration infra verifiers, ephemeral scaling tester

Notes for Agent usage
- Always use uv at repo root for Python env and commands. Do NOT use pip directly in this repo.
  - Install deps: `uv pip install -e .` then `uv pip install -e ".[dev]"`
  - Run tools/tests: `uv run pytest ...`, `uv run ruff check .`, etc.
- No CLAUDE.md, Cursor rules, or Copilot instruction files were found
- Secret variables are expected via .env (e.g., OPENAI_API_KEY, STRIPE_TEST_API_KEY, PODCASTINDEXORG_API_KEY/SECRET, AWS_ENDPOINT_URL, AWS_REGION, etc.). Do not print or log secret values.

