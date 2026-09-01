# =============================================================================
# LLM-backed generation failures (task-330)
#
# On 2026-09-01 the OpenAI credit ran out and the backend produced no artifact
# for a whole test session while every alarm in this module stayed OK. Nothing
# here covered "the LLM refuses to answer", and the one alarm that looked like it
# did -- lambda_error_rate in pipeline_alerts.tf -- cannot see these two workers'
# failures at all: they report a failed record through batchItemFailures (and the
# translation worker swallows its own failure entirely), so AWS/Lambda Errors
# stayed at 0 and the DLQs stayed empty while 3 artifact generations and 25
# translations were failing.
#
# Same shape as revenucat_alerts.tf and durable_media_alerts.tf: a metric filter
# over the structured JSON log events (the application never calls
# put_metric_data), an outcome metric, and alarms gated on var.enable_alarms.
#
# The application contract is media_summarizer/utils/llm_failures.py: both LLM
# workers emit one llm.generation_failed event per failed generation, carrying
# failure_kind = provider_refused | other. Renaming the event or a kind there
# without changing this file silently blinds both alarms.
#
# Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#llm-generation-failures
# =============================================================================

locals {
  # The workers that call the LLM, and therefore the only log groups that can
  # emit llm.generation_failed. Not derived from local.workers on purpose: a new
  # worker starting to call the LLM must be added here consciously, otherwise its
  # failures are invisible for exactly the reason this file exists.
  llm_worker_keys = ["artifact_generator", "transcript_translation"]

  # One alarm per failure_kind. Kept as data because the two kinds answer two
  # different questions and deserve two thresholds:
  #
  #   provider_refused -- quota, credentials or rate limit. The provider is
  #     turning us away, so every generation in the pipeline is failing and no
  #     retry can help. Threshold 0: there is no acceptable background level.
  #   other -- validation failures, a corpus over the ceiling, an S3 read that
  #     died. One hopeless artifact burns its 3 SQS deliveries and emits 3
  #     events, so >3 in 15 minutes is the first count that means more than a
  #     single unlucky generation.
  llm_generation_failure_alarms = {
    provider_refused = {
      alarm_slug  = "llm-provider-refused"
      severity    = "critical"
      period      = 300
      threshold   = 0
      description = "The LLM provider refused the call (quota exhausted, credentials rejected or rate limited): artifact generation and transcript translation are both producing nothing. Read refusal_reason in the llm.generation_failed events to know whether to top up the OpenAI account, rotate OPENAI_API_KEY in the runtime secret, or wait out a throttle. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#llm-generation-failures"
    }
    other = {
      alarm_slug  = "llm-generation-failures"
      severity    = "high"
      period      = 900
      threshold   = 3
      description = "More than 3 LLM-backed generations failed in 15 minutes for a reason other than a provider refusal. These failures are reported through batchItemFailures, so no Lambda Errors datapoint exists for them: this alarm is the only signal. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#llm-generation-failures"
    }
  }
}

# -----------------------------------------------------------------------------
# The metric. One filter per LLM worker log group, both publishing into the same
# metric so the alarms read one number per failure kind whatever produced it.
# Metric filters are free, so they stay ungated like every other filter here.
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_metric_filter" "llm_generation_failed" {
  for_each = toset(local.llm_worker_keys)

  name           = "llm-generation-failed-${replace(each.key, "_", "-")}${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_worker[each.key].name
  pattern        = "{ $.event = \"llm.generation_failed\" }"

  metric_transformation {
    name      = "LlmGenerationFailures"
    namespace = local.metrics_namespace
    value     = "1"
    # No default_value: CloudWatch rejects one on a dimensioned transformation,
    # which is why both alarms below treat missing data as notBreaching.
    dimensions = {
      FailureKind = "$.failure_kind"
    }
  }
}

# -----------------------------------------------------------------------------
# The alarms. One per failure_kind, because an alarm on a dimensioned metric has
# to pin its dimension value.
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "llm_generation_failures" {
  for_each = var.enable_alarms ? local.llm_generation_failure_alarms : {}

  alarm_name          = "${var.project_name}-${each.value.alarm_slug}${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = each.value.threshold
  alarm_description   = each.value.description
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "LlmGenerationFailures"
  namespace   = local.metrics_namespace
  period      = each.value.period
  statistic   = "Sum"

  dimensions = {
    FailureKind = each.key
  }

  tags = {
    Name     = "${var.project_name}-${each.value.alarm_slug}${local.suffix}"
    Severity = each.value.severity
  }
}
