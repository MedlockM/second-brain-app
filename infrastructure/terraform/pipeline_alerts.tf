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
  name  = "${var.project_name}-pipeline-alerts-${var.environment}"

  tags = {
    Name        = "${var.project_name}-pipeline-alerts"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sns_topic_subscription" "pipeline_alerts_email" {
  count     = var.enable_alarms ? 1 : 0
  topic_arn = aws_sns_topic.pipeline_alerts[0].arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# =============================================================================
# Alarm: API Latency p95 > threshold for 5 min
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "api_latency_p95" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-api-latency-p95-breach"
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
    ApiId = local.api_gateway_name
  }

  tags = {
    Name        = "${var.project_name}-api-latency-p95-breach"
    Environment = var.environment
    Project     = var.project_name
    Severity    = "high"
  }
}

# =============================================================================
# Alarm: API 5xx Rate > 1% over 5 min
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "api_5xx_rate" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-api-5xx-rate-breach"
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
        ApiId = local.api_gateway_name
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
        ApiId = local.api_gateway_name
      }
    }
  }

  tags = {
    Name        = "${var.project_name}-api-5xx-rate-breach"
    Environment = var.environment
    Project     = var.project_name
    Severity    = "critical"
  }
}

# =============================================================================
# Alarm: DLQ Depth > 0 for 5 min (per DLQ)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  for_each = var.enable_alarms ? local.queue_dlq_map : {}

  alarm_name          = "${var.project_name}-dlq-${each.value}-non-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "DLQ ${each.value} has messages (source queue: ${each.key}). Poison messages require investigation. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#dlq-messages"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "ApproximateNumberOfMessagesVisible"
  namespace   = "AWS/SQS"
  period      = "300"
  statistic   = "Sum"

  dimensions = {
    QueueName = each.value
  }

  tags = {
    Name        = "${var.project_name}-dlq-${each.value}-alarm"
    Environment = var.environment
    Project     = var.project_name
    Severity    = "medium"
  }
}

# =============================================================================
# Alarm: Lambda Error Rate > 5% over 10 min (per function)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "lambda_error_rate" {
  for_each = var.enable_alarms ? toset(local.lambda_workers) : toset([])

  alarm_name          = "${var.project_name}-${each.key}-lambda-error-rate"
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
        FunctionName = "${var.project_name}-${each.key}"
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
        FunctionName = "${var.project_name}-${each.key}"
      }
    }
  }

  tags = {
    Name        = "${var.project_name}-${each.key}-lambda-error-rate"
    Environment = var.environment
    Project     = var.project_name
    Severity    = "high"
  }
}

# =============================================================================
# Alarm: Lambda Throttles > 0 over 5 min
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  for_each = var.enable_alarms ? toset(local.lambda_workers) : toset([])

  alarm_name          = "${var.project_name}-${each.key}-lambda-throttled"
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
    FunctionName = "${var.project_name}-${each.key}"
  }

  tags = {
    Name        = "${var.project_name}-${each.key}-lambda-throttled"
    Environment = var.environment
    Project     = var.project_name
    Severity    = "high"
  }
}

# =============================================================================
# Alarm: Deepgram Error Rate > 5% over 15 min
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "deepgram_error_rate" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-deepgram-error-rate-breach"
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
      namespace   = "MediaSummarizer/Pipeline"
      period      = "900"
      stat        = "Sum"
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "DeepgramCallsTotal"
      namespace   = "MediaSummarizer/Pipeline"
      period      = "900"
      stat        = "Sum"
    }
  }

  tags = {
    Name        = "${var.project_name}-deepgram-error-rate-breach"
    Environment = var.environment
    Project     = var.project_name
    Severity    = "high"
  }
}

# =============================================================================
# Alarm: LlamaParse -> Unstructured Fallback > N times/hour
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "llamaparse_fallback_rate" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-llamaparse-fallback-rate-breach"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = var.llamaparse_fallback_threshold_per_hour
  alarm_description   = "Unstructured fallback triggered more than ${var.llamaparse_fallback_threshold_per_hour} times in 1 hour. LlamaParse quota may be exhausted. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#llamaparse-fallback"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "UnstructuredFallbackTriggered"
  namespace   = "MediaSummarizer/Pipeline"
  period      = "3600"
  statistic   = "Sum"

  tags = {
    Name        = "${var.project_name}-llamaparse-fallback-rate-breach"
    Environment = var.environment
    Project     = var.project_name
    Severity    = "medium"
  }
}
