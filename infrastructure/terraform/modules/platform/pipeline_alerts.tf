# =============================================================================
# Pipeline Alerting Rules (Lambda Architecture)
# Aligned with V1 Phase 8 monitoring requirements (task-114).
# All ECS references removed post Lambda migration (task-106).
#
# Alert naming convention: {project}-{condition}
# All alerts route to the pipeline_alerts SNS topic.
#
# Runbook: infrastructure/observability/runbooks/pipeline-alerts.md
# =============================================================================

# =============================================================================
# SNS Topic for Pipeline Alerts
# =============================================================================

resource "aws_sns_topic" "pipeline_alerts" {
  count = var.enable_alarms ? 1 : 0
  name  = "${var.project_name}-pipeline-alerts${local.suffix}"

  tags = {
    Name = "${var.project_name}-pipeline-alerts${local.suffix}"
  }
}

# Only created when an address is supplied. No address is committed to the
# repository: subscribe out-of-band, or pass -var alert_email=... on the apply
# that creates the topic.
resource "aws_sns_topic_subscription" "pipeline_alerts_email" {
  count     = var.enable_alarms && var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.pipeline_alerts[0].arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# =============================================================================
# Alarm: API Latency p95 > threshold for 5 min
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "api_latency_p95" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-api-latency-p95-breach${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = var.api_slow_request_threshold_ms
  alarm_description   = "API Gateway p95 latency exceeded ${var.api_slow_request_threshold_ms}ms for 5 minutes. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#api-latency"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name        = "Latency"
  namespace          = "AWS/ApiGateway"
  period             = "300"
  extended_statistic = "p95"

  dimensions = {
    ApiId = local.api_gateway_id
  }

  tags = {
    Name     = "${var.project_name}-api-latency-p95-breach${local.suffix}"
    Severity = "high"
  }
}

# =============================================================================
# Alarm: API 5xx Rate > 1% over 5 min
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "api_5xx_rate" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-api-5xx-rate-breach${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "1"
  alarm_description   = "API Gateway 5xx error rate exceeded 1% over 5 minutes. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#api-5xx-rate"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "IF(m2 > 0, 100 * m1 / m2, 0)"
    label       = "5xx Error Rate %"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "5xx"
      namespace   = "AWS/ApiGateway"
      period      = "300"
      stat        = "Sum"
      dimensions = {
        ApiId = local.api_gateway_id
      }
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "Count"
      namespace   = "AWS/ApiGateway"
      period      = "300"
      stat        = "Sum"
      dimensions = {
        ApiId = local.api_gateway_id
      }
    }
  }

  tags = {
    Name     = "${var.project_name}-api-5xx-rate-breach${local.suffix}"
    Severity = "critical"
  }
}

# =============================================================================
# Alarm: DLQ Depth > 0 for 5 min (per DLQ)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  for_each = var.enable_alarms ? local.queue_dlq_map : {}

  alarm_name          = "${var.project_name}-dlq-${replace(each.key, "_", "-")}-non-empty${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "DLQ ${each.value.dlq} has messages (source queue: ${each.value.queue}). Poison messages require investigation. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#dlq-messages"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "ApproximateNumberOfMessagesVisible"
  namespace   = "AWS/SQS"
  period      = "300"
  statistic   = "Sum"

  dimensions = {
    QueueName = each.value.dlq
  }

  tags = {
    Name     = "${var.project_name}-dlq-${replace(each.key, "_", "-")}-non-empty${local.suffix}"
    Severity = "medium"
  }
}

# =============================================================================
# Alarm: Lambda Error Rate > 5% over 10 min (per function)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "lambda_error_rate" {
  for_each = var.enable_alarms ? toset(local.lambda_workers) : toset([])

  alarm_name          = "${var.project_name}-${each.key}-lambda-error-rate${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  threshold           = "5"
  alarm_description   = "Lambda ${each.key} error rate exceeded 5% over 10 minutes. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#lambda-errors"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "IF(m2 > 0, 100 * m1 / m2, 0)"
    label       = "Error Rate %"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "Errors"
      namespace   = "AWS/Lambda"
      period      = "300"
      stat        = "Sum"
      dimensions = {
        FunctionName = local.worker_function_names[each.key]
      }
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = "300"
      stat        = "Sum"
      dimensions = {
        FunctionName = local.worker_function_names[each.key]
      }
    }
  }

  tags = {
    Name     = "${var.project_name}-${each.key}-lambda-error-rate${local.suffix}"
    Severity = "high"
  }
}

# =============================================================================
# Alarm: Lambda Throttles > 0 over 5 min
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  for_each = var.enable_alarms ? toset(local.lambda_workers) : toset([])

  alarm_name          = "${var.project_name}-${each.key}-lambda-throttled${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "Lambda ${each.key} was throttled in the last 5 minutes. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#lambda-throttles"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "Throttles"
  namespace   = "AWS/Lambda"
  period      = "300"
  statistic   = "Sum"

  dimensions = {
    FunctionName = local.worker_function_names[each.key]
  }

  tags = {
    Name     = "${var.project_name}-${each.key}-lambda-throttled${local.suffix}"
    Severity = "high"
  }
}

# =============================================================================
# Alarm: Deepgram Error Rate > 5% over 15 min
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "deepgram_error_rate" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-deepgram-error-rate-breach${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "5"
  alarm_description   = "Deepgram transcription error rate exceeded 5% over 15 minutes. Possible Deepgram outage or quota exhaustion. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#deepgram-error-rate"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "IF(m2 > 0, 100 * m1 / m2, 0)"
    label       = "Deepgram Error Rate %"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "DeepgramErrors"
      namespace   = local.metrics_namespace
      period      = "900"
      stat        = "Sum"
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "DeepgramCallsTotal"
      namespace   = local.metrics_namespace
      period      = "900"
      stat        = "Sum"
    }
  }

  tags = {
    Name     = "${var.project_name}-deepgram-error-rate-breach${local.suffix}"
    Severity = "high"
  }
}

# =============================================================================
# Alarm: LlamaParse -> Unstructured Fallback > N times/hour
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "llamaparse_fallback_rate" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-llamaparse-fallback-rate-breach${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = var.llamaparse_fallback_threshold_per_hour
  alarm_description   = "Unstructured fallback triggered more than ${var.llamaparse_fallback_threshold_per_hour} times in 1 hour. LlamaParse quota may be exhausted. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#llamaparse-fallback"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "UnstructuredFallbackTriggered"
  namespace   = local.metrics_namespace
  period      = "3600"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-llamaparse-fallback-rate-breach${local.suffix}"
    Severity = "medium"
  }
}

# =============================================================================
# Job archiver silent failure (task-242)
# =============================================================================
# The §1.5 incident: the archiver Lambda was invoked 144 times by the
# processing_jobs stream and never wrote a single object. Nothing noticed,
# because "the Lambda ran without error" was the only thing being watched.
# With the TTL re-enabled the rows now really disappear, so the guardrail has to
# answer the outcome question: were the deletions we saw actually archived?
#
# That is a comparison between what the archiver received and what it produced,
# so it needs two metrics and two alarms:
#
#   job_archiver_archive_gap    -- the handler ran and dropped deletions
#                                  (remove_records - archived > 0).
#   job_archiver_silent_failure -- composite: the Lambda was invoked at all
#                                  (AWS/Lambda Invocations, a metric the
#                                  application cannot fail to emit) while
#                                  nothing was archived. This is the case a
#                                  log-derived metric alone cannot see: a
#                                  regression back to a no-op handler logs
#                                  nothing, so its metrics are simply absent.
#
# Both metrics come from the one JSON summary line emitted per invocation by
# media_summarizer/workers/cleanup/job_archiver.py, per the module convention
# (metrics are derived from log metric filters; the application never calls
# put_metric_data). Metric filters are free, so they stay ungated; the alarms
# follow var.enable_alarms like every other alarm here.
#
# Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#archiver-failure

# REMOVE records handed to the archiver by the stream event source mapping.
resource "aws_cloudwatch_log_metric_filter" "job_archiver_remove_records" {
  name           = "job-archiver-remove-records${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_archiver.name
  pattern        = "{ $.event = \"job_archiver.batch_completed\" }"

  metric_transformation {
    name          = "JobArchiverRemoveRecords"
    namespace     = local.metrics_namespace
    value         = "$.remove_records"
    default_value = "0"
  }
}

# Objects the archiver actually wrote to the archives bucket. The denominator of
# the metric above: read alone, either number means nothing.
resource "aws_cloudwatch_log_metric_filter" "job_archiver_objects_archived" {
  name           = "job-archiver-objects-archived${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_archiver.name
  pattern        = "{ $.event = \"job_archiver.batch_completed\" }"

  metric_transformation {
    name          = "JobArchiverObjectsArchived"
    namespace     = local.metrics_namespace
    value         = "$.archived"
    default_value = "0"
  }
}

# -----------------------------------------------------------------------------
# Alarm: deletions seen but not archived.
#
# Threshold 0, not a rate: an unarchived deletion is a job row that is gone with
# no audit trail, and there is no acceptable background level of it.
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "job_archiver_archive_gap" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-job-archiver-archive-gap${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "The job archiver received REMOVE events it did not archive: deleted processing_jobs rows are being lost with no audit trail. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#archiver-failure"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "m1 - m2"
    label       = "REMOVE records not archived"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "JobArchiverRemoveRecords"
      namespace   = local.metrics_namespace
      period      = "300"
      stat        = "Sum"
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "JobArchiverObjectsArchived"
      namespace   = local.metrics_namespace
      period      = "300"
      stat        = "Sum"
    }
  }

  tags = {
    Name     = "${var.project_name}-job-archiver-archive-gap${local.suffix}"
    Severity = "critical"
  }
}

# -----------------------------------------------------------------------------
# Child alarm: the archiver Lambda ran. AWS/Lambda Invocations is emitted by the
# platform, not by the function, so this side of the comparison survives any
# regression in the handler -- including the no-op placeholder of §1.5.
# No actions: it is only read by the composite alarm below.
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "job_archiver_invoked" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-job-archiver-invoked${local.suffix}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = "1"
  threshold           = "1"
  alarm_description   = "Support alarm (no actions): the job archiver Lambda was invoked during the period. Read by ${var.project_name}-job-archiver-silent-failure${local.suffix}."
  treat_missing_data  = "notBreaching"

  metric_name = "Invocations"
  namespace   = "AWS/Lambda"
  period      = "300"
  statistic   = "Sum"

  dimensions = {
    FunctionName = aws_lambda_function.job_archiver.function_name
  }

  tags = {
    Name     = "${var.project_name}-job-archiver-invoked${local.suffix}"
    Severity = "none"
  }
}

# -----------------------------------------------------------------------------
# Child alarm: nothing was archived. treat_missing_data = "breaching" is the
# whole point -- a handler that writes nothing and logs nothing produces no
# datapoint at all, and "no data" is precisely the symptom to catch. On its own
# this alarm is in ALARM whenever the archiver is idle, which is why it carries
# no actions and is only meaningful ANDed with job_archiver_invoked.
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "job_archiver_nothing_archived" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-job-archiver-nothing-archived${local.suffix}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  threshold           = "1"
  alarm_description   = "Support alarm (no actions): no object was archived during the period. Read by ${var.project_name}-job-archiver-silent-failure${local.suffix}."
  treat_missing_data  = "breaching"

  metric_name = "JobArchiverObjectsArchived"
  namespace   = local.metrics_namespace
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-job-archiver-nothing-archived${local.suffix}"
    Severity = "none"
  }
}

# -----------------------------------------------------------------------------
# The tripwire itself: invoked AND nothing archived. This is the exact shape of
# the §1.5 failure, and unlike the metric alarm it replaces it does not depend
# on any code path inside the archiver to raise its hand.
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_composite_alarm" "job_archiver_silent_failure" {
  count             = var.enable_alarms ? 1 : 0
  alarm_name        = "${var.project_name}-job-archiver-silent-failure${local.suffix}"
  alarm_description = "The job archiver Lambda was invoked but archived nothing: deletions of processing_jobs rows are being discarded silently, as in the task-218 §1.5 incident. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#archiver-failure"
  alarm_actions     = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions        = [aws_sns_topic.pipeline_alerts[0].arn]

  alarm_rule = join(" AND ", [
    "ALARM(${aws_cloudwatch_metric_alarm.job_archiver_invoked[0].alarm_name})",
    "ALARM(${aws_cloudwatch_metric_alarm.job_archiver_nothing_archived[0].alarm_name})",
  ])

  tags = {
    Name     = "${var.project_name}-job-archiver-silent-failure${local.suffix}"
    Severity = "critical"
  }
}
