---
id: task-217
title: Isolate the interactive API runtime from shared Lambda worker dependencies
status: To Do
assignee: []
created_date: '2026-07-27 20:59'
labels:
  - infra
  - lambda
  - performance
  - cost-optimization
  - release
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The FastAPI Lambda currently uses the same 406 MB container image as every asynchronous worker. After a long idle period, reactivation produced two API Gateway 500 responses followed by a 25.7-second first invocation, placing the interactive API close to its 30-second integration timeout. Implement the owner-approved production shape: keep the API on Lambda ARM64/on-demand but give it a minimal dedicated runtime; retain a shared image for asynchronous workers; protect interactive capacity without enabling paid provisioned concurrency by default; and add a low-cost warm-up plus release checks that detect an unavailable or unhealthy API. The outcome should reduce cold-start latency and deployment blast radius while preserving the Lambda-only architecture and near-zero idle cost. Provisioned concurrency remains an opt-in operational control to enable later only when production metrics justify it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The FastAPI Lambda is deployed from a dedicated minimal container image that excludes worker-only runtime dependencies.
- [ ] #2 All asynchronous SQS workers continue to run from a shared worker image and retain their existing handler mappings.
- [ ] #3 The deployment pipeline builds immutable versioned API and worker images and updates each Lambda group with the correct image without forcing unrelated functions onto the other runtime.
- [ ] #4 Terraform represents the distinct API and worker deployment artifacts while preserving ARM64 and the existing Lambda-only architecture.
- [ ] #5 The API has configurable reserved concurrency that protects interactive traffic from worker concurrency exhaustion without enabling paid provisioned concurrency by default.
- [ ] #6 A low-cost scheduled warm invocation prevents multi-week inactivity and verifies the canonical health endpoint without introducing permanent provisioned capacity.
- [ ] #7 Release validation waits for the Lambda to be Active and fails unless the public API health endpoint returns a successful healthy response.
- [ ] #8 API Gateway access logs capture the integration error message needed to diagnose failures occurring before Lambda invocation.
- [ ] #9 Before-and-after measurements document compressed image sizes, cold initialization duration, first-request latency, and warm-request latency in AWS dev.
- [ ] #10 The production configuration keeps provisioned concurrency disabled by default and documents the measured threshold and explicit procedure for enabling it later.
<!-- AC:END -->
