# =============================================================================
# Pipeline Alerting Rules
# Covers sustained failures and latency degradations for all pipeline stages.
#
# Alert naming convention: {project}-{stage}-{condition}
# All alerts route to the ops_alerts SNS topic defined in monitoring.tf.
#
# Runbook: infrastructure/observability/runbooks/pipeline-alerts.md
# =============================================================================

# =============================================================================
# Stage 1: Ingestion Alerts
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "ingestion_sustained_failures" {
  alarm_name          = "${var.project_name}-ingestion-sustained-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  threshold           = "3"
  alarm_description   = "Ingestion failures exceeded 3 in 3 consecutive 5-minute periods. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#ingestion-failures"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_name = "IngestFailed"
  namespace   = "MediaSummarizer/Pipeline"
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name        = "${var.project_name}-ingestion-sustained-failures"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "ingestion"
    Severity    = "high"
  }
}

resource "aws_cloudwatch_metric_alarm" "ingestion_success_rate_breach" {
  alarm_name          = "${var.project_name}-ingestion-success-rate-breach"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  threshold           = "99.5"
  alarm_description   = "Ingestion success rate dropped below 99.5% SLO for 15 minutes. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#ingestion-failures"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "100 * m1 / m2"
    label       = "Ingestion Success Rate"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "IngestCreated"
      namespace   = "MediaSummarizer/Pipeline"
      period      = "300"
      stat        = "Sum"
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "IngestStarted"
      namespace   = "MediaSummarizer/Pipeline"
      period      = "300"
      stat        = "Sum"
    }
  }

  tags = {
    Name        = "${var.project_name}-ingestion-success-rate-breach"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "ingestion"
    Severity    = "high"
  }
}

# =============================================================================
# Stage 2: Resolver Alerts (per worker type)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "resolver_sustained_failures" {
  for_each = toset(["rss", "youtube", "tiktok"])

  alarm_name          = "${var.project_name}-${each.key}-resolver-sustained-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  threshold           = "3"
  alarm_description   = "${each.key} resolver failures exceeded 3 in 3 consecutive 5-min periods. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#resolver-failures"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_name = "ResolverFailed"
  namespace   = "MediaSummarizer/Pipeline"
  period      = "300"
  statistic   = "Sum"

  dimensions = {
    WorkerType = each.key
  }

  tags = {
    Name        = "${var.project_name}-${each.key}-resolver-sustained-failures"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "resolver"
    Severity    = "high"
  }
}

resource "aws_cloudwatch_metric_alarm" "resolver_high_retry_rate" {
  for_each = toset(["rss", "youtube", "tiktok"])

  alarm_name          = "${var.project_name}-${each.key}-resolver-high-retry-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  threshold           = "10"
  alarm_description   = "${each.key} resolver retries exceeded 10 in 2 consecutive 5-min periods. Possible upstream degradation. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#resolver-retries"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_name = "ResolverRetry"
  namespace   = "MediaSummarizer/Pipeline"
  period      = "300"
  statistic   = "Sum"

  dimensions = {
    WorkerType = each.key
  }

  tags = {
    Name        = "${var.project_name}-${each.key}-resolver-high-retry-rate"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "resolver"
    Severity    = "medium"
  }
}

# =============================================================================
# Stage 3: Transcription Alerts
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "transcription_sustained_failures" {
  alarm_name          = "${var.project_name}-transcription-sustained-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  threshold           = "2"
  alarm_description   = "Transcription failures exceeded 2 in 3 consecutive 5-min periods. Possible Deepgram outage. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#transcription-failures"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_name = "TranscriptionFailed"
  namespace   = "MediaSummarizer/Pipeline"
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name        = "${var.project_name}-transcription-sustained-failures"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "transcription"
    Severity    = "critical"
  }
}

resource "aws_cloudwatch_metric_alarm" "transcription_latency_degradation" {
  alarm_name          = "${var.project_name}-transcription-latency-p95-breach"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  threshold           = "120000"
  alarm_description   = "Transcription p95 latency exceeded 120s SLO for 15 minutes. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#transcription-latency"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_name = "TranscriptionDurationMs"
  namespace   = "MediaSummarizer/Pipeline"
  period      = "300"
  statistic   = "p95"

  tags = {
    Name        = "${var.project_name}-transcription-latency-p95-breach"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "transcription"
    Severity    = "high"
  }
}

resource "aws_cloudwatch_metric_alarm" "transcription_success_rate_breach" {
  alarm_name          = "${var.project_name}-transcription-success-rate-breach"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  threshold           = "98"
  alarm_description   = "Transcription success rate dropped below 98% SLO for 15 minutes. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#transcription-failures"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "100 * m1 / (m1 + m2)"
    label       = "Transcription Success Rate"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "TranscriptionCompleted"
      namespace   = "MediaSummarizer/Pipeline"
      period      = "300"
      stat        = "Sum"
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "TranscriptionFailed"
      namespace   = "MediaSummarizer/Pipeline"
      period      = "300"
      stat        = "Sum"
    }
  }

  tags = {
    Name        = "${var.project_name}-transcription-success-rate-breach"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "transcription"
    Severity    = "critical"
  }
}

# =============================================================================
# Stage 4: Artifact Generation Alerts
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "artifact_generation_sustained_failures" {
  alarm_name          = "${var.project_name}-artifact-generation-sustained-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  threshold           = "3"
  alarm_description   = "Artifact generation failures exceeded 3 in 3 consecutive 5-min periods. Possible LLM API issue. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#artifact-generation-failures"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_name = "ArtifactGenerationFailed"
  namespace   = "MediaSummarizer/Pipeline"
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name        = "${var.project_name}-artifact-generation-sustained-failures"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "artifact_generation"
    Severity    = "high"
  }
}

resource "aws_cloudwatch_metric_alarm" "artifact_generation_latency_degradation" {
  alarm_name          = "${var.project_name}-artifact-generation-latency-p95-breach"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  threshold           = "30000"
  alarm_description   = "Artifact generation p95 latency exceeded 30s SLO for 15 minutes. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#artifact-generation-latency"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_name = "ArtifactGenerationDurationMs"
  namespace   = "MediaSummarizer/Pipeline"
  period      = "300"
  statistic   = "p95"

  tags = {
    Name        = "${var.project_name}-artifact-generation-latency-p95-breach"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "artifact_generation"
    Severity    = "high"
  }
}

resource "aws_cloudwatch_metric_alarm" "artifact_generation_success_rate_breach" {
  alarm_name          = "${var.project_name}-artifact-generation-success-rate-breach"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  threshold           = "95"
  alarm_description   = "Artifact generation success rate dropped below 95% SLO for 15 minutes. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#artifact-generation-failures"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "100 * m1 / (m1 + m2)"
    label       = "Artifact Generation Success Rate"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "ArtifactGenerationCompleted"
      namespace   = "MediaSummarizer/Pipeline"
      period      = "300"
      stat        = "Sum"
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "ArtifactGenerationFailed"
      namespace   = "MediaSummarizer/Pipeline"
      period      = "300"
      stat        = "Sum"
    }
  }

  tags = {
    Name        = "${var.project_name}-artifact-generation-success-rate-breach"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "artifact_generation"
    Severity    = "high"
  }
}

# =============================================================================
# Cross-Stage: DLQ Alerts
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "dlq_messages_present" {
  for_each = {
    "deepgram"             = aws_sqs_queue.deepgram_transcription_dlq.name
    "summarization"        = aws_sqs_queue.summarization_dlq.name
    "youtube"              = aws_sqs_queue.youtube_ingestion_dlq.name
    "tiktok"               = aws_sqs_queue.tiktok_ingestion_dlq.name
    "audio-download"       = aws_sqs_queue.audio_download_dlq.name
    "article-extraction"   = aws_sqs_queue.article_extraction_dlq.name
    "document-parsing"     = aws_sqs_queue.document_parsing_dlq.name
  }

  alarm_name          = "${var.project_name}-${each.key}-dlq-non-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "${each.key} Dead Letter Queue has messages. Poison messages require manual investigation. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#dlq-messages"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_name = "ApproximateNumberOfVisibleMessages"
  namespace   = "AWS/SQS"
  period      = "300"
  statistic   = "Sum"

  dimensions = {
    QueueName = each.value
  }

  tags = {
    Name        = "${var.project_name}-${each.key}-dlq-alarm"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "infrastructure"
    Severity    = "medium"
  }
}

# =============================================================================
# Cross-Stage: Queue Starvation (no messages processed in extended period)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "pipeline_stalled" {
  alarm_name          = "${var.project_name}-pipeline-stalled"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = "6"
  threshold           = "0"
  alarm_description   = "No transcriptions completed in 30 minutes despite ingestion activity. Pipeline may be stalled. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#pipeline-stalled"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "breaching"

  metric_name = "TranscriptionCompleted"
  namespace   = "MediaSummarizer/Pipeline"
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name        = "${var.project_name}-pipeline-stalled"
    Environment = var.environment
    Project     = var.project_name
    Stage       = "end_to_end"
    Severity    = "critical"
  }
}
