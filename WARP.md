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
- Policy (local): ignore coverage until the end of the project. Focus on tests passing.
  - To bypass coverage options defined in pytest.ini, override addopts:
    - Unit only: `uv run pytest media_summarizer/tests/unit -q --override-ini "addopts="`
    - Integration: `uv run pytest media_summarizer/tests/integration -q --override-ini "addopts="`
    - E2E: `uv run pytest media_summarizer/tests/end_to_end -q -m e2e --override-ini "addopts="`
- All tests (with coverage via pytest.ini): pytest
- Run by folder
  - Unit: pytest media_summarizer/tests/unit -v
  - Integration: pytest media_summarizer/tests/integration -v
  - E2E: pytest media_summarizer/tests/end_to_end -v -m e2e
- Markers (defined in pytest.ini): unit, integration, component, workflow, e2e, requires_workers, requires_localstack, requires_database, requires_stripe, requires_whisper, requires_all_services, slow, fast, api, worker, adapter, core, database, ci_only, local_only, nightly, smoke, forecast
  - Example: pytest -m "unit and not slow"
- Single test
  - File: pytest media_summarizer/tests/unit/api/endpoints/test_health.py -q
  - Specific test: pytest media_summarizer/tests/unit/api/endpoints/test_health.py::TestBasicHealthCheck::test_health_check_success -q
- Parallel tests (pytest-xdist): pytest -n auto
- E2E helper script: bash scripts/run_e2e_tests.sh
- Integration infra checks:
  - python scripts/verify_integration_tests.py
  - python scripts/demo_integration_tests.py

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

Testing architecture (high level)
- SQS in tests: to avoid flakiness when peeking into queues, always delete messages after receiving them, prefer per-test unique queues (monkeypatch get_queue_url to map logical names like "transcription-queue" to the test queue), and widen retry windows when necessary. Ensure AWS creds are set in the test environment for aiobotocore/boto3 (AWS_ACCESS_KEY_ID/SECRET, AWS_REGION, AWS_ENDPOINT_URL).
- pytest.ini routes tests to media_summarizer/tests and enables asyncio, coverage, and rich markers
- Integration tests emphasize real services: LocalStack for AWS, real Whisper docker service, httpx async server for RSS/audio
- E2E tests require API + workers + LocalStack up; helper script validates services and runs -m e2e

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

