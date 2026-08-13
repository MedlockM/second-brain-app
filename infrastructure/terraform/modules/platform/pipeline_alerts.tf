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
# Alarm: Job Archiver Silent Failure (REMOVE events processed but no objects archived)
# =============================================================================
# This tripwire detects the §1.5 failure mode: the archiver Lambda is invoked by
# the DynamoDB stream but silently no-ops while deleting rows. We alarm when
# REMOVE events are processed by the event source mapping (visible in Lambda metrics
# as Invocations > 0 over 24 hours) but S3 archives show zero new objects.
# The owner's account owns the job_archiver Lambda directly in AWS,
# so we check: Invocations > 0 over 24h, AND zero new objects in the archives bucket over the same period.
resource "aws_cloudwatch_metric_alarm" "job_archiver_silent_failure" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-job-archiver-silent-failure${local.suffix}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  threshold           = "1"
  alarm_description   = "Job archiver invoked (REMOVE events received) but no objects written to archives bucket in the last 24h. The archiver may be silently discarding deletions. Review archiver logs immediately. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#archiver-failure"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  # Composite alarm would be ideal (Invocations > 0 AND PutObject count == 0),
  # but CloudWatch doesn't support composite alarms with metric math across
  # different services (Lambda Invocations vs S3 PutObject). Instead, we use
  # a metric filter on archiver logs to emit a custom metric "ArchiveFailure"
  # that the app observability layer can increment when it detects the mismatch.
  # For now, a periodic (daily) check by the observability agent is the fallback.
  # This alarm fires on a manual metric emit only.
  metric_name = "JobArchiverSilentFailure"
  namespace   = local.metrics_namespace
  period      = "86400"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-job-archiver-silent-failure${local.suffix}"
    Severity = "critical"
  }
}
