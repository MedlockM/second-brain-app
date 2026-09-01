---
id: task-330
title: Make artifact-generation and LLM-provider failures visible to the alarm layer
status: To Do
assignee: []
created_date: '2026-09-01 16:42'
labels:
  - observability
  - artifacts
  - terraform
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Observed

On 2026-09-01 the backend stopped producing any artifact for an entire test session — the OpenAI credit was exhausted — and **no automated signal could have fired**. Two distinct reasons, the second being the more troubling:

### 1. No alarm covers artifact-generation failure or an LLM-provider refusal

The 19 `aws_cloudwatch_metric_alarm` blocks in the `platform` module cover API p95 latency, the 5xx rate, DLQ depth, Lambda errors and throttles, Deepgram, the LlamaParse fallback, the job archiver, the `user_media` lifecycle and the RevenueCat tier. Nothing covers "the LLM refuses to answer".

### 2. `lambda_error_rate` gives false assurance on exactly these workers

That alarm computes `100 * Errors / Invocations` on `AWS/Lambda` (`infrastructure/terraform/modules/platform/pipeline_alerts.tf:153-201`) for every worker in `local.lambda_workers`, `artifact_generator` and `transcript_translation` included. But `media_summarizer/workers/lambda_handlers.py:83` reports failures through `batchItemFailures` **without raising**, and the translation worker even catches its own failure internally. So `Errors` stayed at **0** while 3 artifact generations and 25 translation invocations were failing. The DLQs stayed empty for the same reason.

An error rate built on `Errors` structurally cannot see these outages. A reader looking at the alarm list would conclude the pipeline was covered.

## Scope

What is missing is an **application metric the alarm layer can observe**, not one more alarm on a blind one. Emit it from the two workers that call the LLM, alarm on it the way the module already alarms on everything else, and leave a note next to `lambda_error_rate` so nobody trusts it for these workers again.

`enable_alarms = false` in dev is a deliberate cost decision (confirmed by the owner) — this task does not change it.

## Owner note

`enable_alarms = false` holds for `staging` (`infrastructure/terraform/envs/staging/main.tf:86`) and `prod` (`infrastructure/terraform/envs/prod/main.tf:91`) too, so none of the module's alarms is deployed anywhere. Flipping prod to `true` and subscribing an address to the SNS topic is a launch prerequisite, out of scope here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The artifact generation worker emits a CloudWatch application metric when generation fails, distinguishing an LLM-provider refusal (quota, authentication, rate limit) from a failure of any other nature
- [ ] #2 The transcript translation worker emits the same family of metric on its own failure path
- [ ] #3 The namespace, metric name and dimensions are documented where the repo already documents the pipeline alarms
- [ ] #4 An aws_cloudwatch_metric_alarm covers those metrics, gated by var.enable_alarms like every other alarm in the module, with an alarm_description pointing at a runbook as the existing ones do, and a name that keeps the environment suffix the alarm-naming check requires
- [ ] #5 A comment next to lambda_error_rate records that it cannot detect a failure reported through batchItemFailures, so the next reader does not rely on it for the worker Lambdas
- [ ] #6 enable_alarms stays false in the dev, staging and prod envs
- [ ] #7 terraform validate passes on the platform module and on the dev env; ruff and mypy pass on the changed Python modules
<!-- AC:END -->
