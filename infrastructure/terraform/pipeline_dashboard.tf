# =============================================================================
# Pipeline Observability Dashboard
# Covers: Ingestion -> Resolver -> Transcription -> Artifact Generation
#
# All metrics are derived from structured JSON log events via CloudWatch
# Metric Filters on the Lambda worker and API log groups.
# =============================================================================

# =============================================================================
# METRIC FILTERS — Stage 1: Ingestion
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "ingest_started" {
  name           = "ingest-started"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.event = \"media.ingest.started\" }"

  metric_transformation {
    name      = "IngestStarted"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "ingest_created" {
  name           = "ingest-created"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.event = \"media.ingest.created\" }"

  metric_transformation {
    name      = "IngestCreated"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "ingest_failed" {
  name           = "ingest-failed"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.event = \"media.ingest.failed\" }"

  metric_transformation {
    name      = "IngestFailed"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

# =============================================================================
# METRIC FILTERS — Stage 2: Resolver Success/Failure (per worker type)
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "resolver_success" {
  for_each = toset(["podcastindex_resolution", "youtube_ingestion", "tiktok_ingestion", "deepgram_transcription", "summarization"])

  name           = "${each.key}-resolver-success"
  log_group_name = aws_cloudwatch_log_group.lambda_worker[each.key].name
  pattern        = "{ $.event = \"worker.message_completed\" }"

  metric_transformation {
    name      = "ResolverSuccess"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
    dimensions = {
      WorkerType = each.key
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "resolver_failed" {
  for_each = toset(["podcastindex_resolution", "youtube_ingestion", "tiktok_ingestion", "deepgram_transcription", "summarization"])

  name           = "${each.key}-resolver-failed"
  log_group_name = aws_cloudwatch_log_group.lambda_worker[each.key].name
  pattern        = "{ $.event = \"worker.failed\" }"

  metric_transformation {
    name      = "ResolverFailed"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
    dimensions = {
      WorkerType = each.key
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "resolver_retry" {
  for_each = toset(["podcastindex_resolution", "youtube_ingestion", "tiktok_ingestion", "deepgram_transcription", "summarization"])

  name           = "${each.key}-resolver-retry"
  log_group_name = aws_cloudwatch_log_group.lambda_worker[each.key].name
  pattern        = "{ $.event = \"worker.retry_scheduled\" }"

  metric_transformation {
    name      = "ResolverRetry"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
    dimensions = {
      WorkerType = each.key
    }
  }
}

# =============================================================================
# METRIC FILTERS — Stage 3: Transcription
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "transcription_started" {
  name           = "transcription-started"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["deepgram_transcription"].name
  pattern        = "{ $.event = \"worker.transcription.started\" }"

  metric_transformation {
    name      = "TranscriptionStarted"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "transcription_completed" {
  name           = "transcription-completed"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["deepgram_transcription"].name
  pattern        = "{ $.event = \"worker.transcription.completed\" }"

  metric_transformation {
    name      = "TranscriptionCompleted"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "transcription_failed" {
  name           = "transcription-failed"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["deepgram_transcription"].name
  pattern        = "{ $.event = \"worker.transcription.failed\" }"

  metric_transformation {
    name      = "TranscriptionFailed"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "transcription_duration" {
  name           = "transcription-duration"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["deepgram_transcription"].name
  pattern        = "{ $.event = \"worker.transcription.completed\" && $.duration_ms = * }"

  metric_transformation {
    name      = "TranscriptionDurationMs"
    namespace = "MediaSummarizer/Pipeline"
    value     = "$.duration_ms"
  }
}

# =============================================================================
# METRIC FILTERS — Stage 4: Artifact Generation
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "artifact_generation_completed" {
  name           = "artifact-generation-completed"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["summarization"].name
  pattern        = "{ $.event = \"artifact.generation.completed\" }"

  metric_transformation {
    name      = "ArtifactGenerationCompleted"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "artifact_generation_failed" {
  name           = "artifact-generation-failed"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["summarization"].name
  pattern        = "{ $.event = \"artifact.generation.failed\" }"

  metric_transformation {
    name      = "ArtifactGenerationFailed"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "artifact_generation_duration" {
  name           = "artifact-generation-duration"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["summarization"].name
  pattern        = "{ $.event = \"artifact.generation.completed\" && $.duration_ms = * }"

  metric_transformation {
    name      = "ArtifactGenerationDurationMs"
    namespace = "MediaSummarizer/Pipeline"
    value     = "$.duration_ms"
  }
}

# =============================================================================
# CLOUDWATCH DASHBOARD — Full Pipeline View
# =============================================================================

resource "aws_cloudwatch_dashboard" "pipeline_observability" {
  dashboard_name = "${var.project_name}-pipeline-observability"

  dashboard_body = jsonencode({
    widgets = [
      # -----------------------------------------------------------------------
      # Row 0: Pipeline Overview
      # -----------------------------------------------------------------------
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "# Share-First Pipeline Observability\nIngestion -> Resolver -> Transcription -> Artifact Generation | [Runbook](https://github.com/your-org/media-summarizer/blob/main/infrastructure/observability/runbooks/pipeline-alerts.md)"
        }
      },

      # -----------------------------------------------------------------------
      # Row 1: Stage 1 - Ingestion
      # -----------------------------------------------------------------------
      {
        type   = "text"
        x      = 0
        y      = 1
        width  = 24
        height = 1
        properties = {
          markdown = "## Stage 1: Ingestion (POST /api/media/ingest-url) | SLO: 99.5% success"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["MediaSummarizer/Pipeline", "IngestCreated", { "stat" : "Sum", "label" : "Created (success)", "color" : "#2ca02c" }],
            ["MediaSummarizer/Pipeline", "IngestFailed", { "stat" : "Sum", "label" : "Failed", "color" : "#d62728" }],
            ["MediaSummarizer/Pipeline", "IngestStarted", { "stat" : "Sum", "label" : "Started (total)", "color" : "#1f77b4" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Ingestion Volume"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 2
        width  = 8
        height = 6
        properties = {
          metrics = [
            [{ "expression" : "100 * m1 / m2", "label" : "Success Rate %", "id" : "e1" }],
            ["MediaSummarizer/Pipeline", "IngestCreated", { "stat" : "Sum", "id" : "m1", "visible" : false }],
            ["MediaSummarizer/Pipeline", "IngestStarted", { "stat" : "Sum", "id" : "m2", "visible" : false }]
          ]
          view    = "timeSeries"
          region  = var.aws_region
          title   = "Ingestion Success Rate (SLO: 99.5%)"
          period  = 300
          yAxis   = { left = { min = 90, max = 100 } }
          annotations = {
            horizontal = [
              { label = "SLO Target", value = 99.5, color = "#ff7f0e" }
            ]
          }
        }
      },
      {
        type   = "log"
        x      = 16
        y      = 2
        width  = 8
        height = 6
        properties = {
          query   = "SOURCE '/aws/lambda/${var.project_name}-api' | fields @timestamp, user_id, source_platform, error_code | filter event = 'media.ingest.failed' | sort @timestamp desc | limit 10"
          region  = var.aws_region
          title   = "Recent Ingestion Failures"
          view    = "table"
        }
      },

      # -----------------------------------------------------------------------
      # Row 2: Stage 2 - Resolvers
      # -----------------------------------------------------------------------
      {
        type   = "text"
        x      = 0
        y      = 8
        width  = 24
        height = 1
        properties = {
          markdown = "## Stage 2: Resolvers (YouTube, TikTok, Podcast, Article) | SLO: 97% success per platform"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 9
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["MediaSummarizer/Pipeline", "ResolverSuccess", "WorkerType", "youtube_ingestion", { "stat" : "Sum", "label" : "YouTube OK" }],
            ["...", "tiktok_ingestion", { "stat" : "Sum", "label" : "TikTok OK" }],
            ["...", "podcastindex_resolution", { "stat" : "Sum", "label" : "Podcast OK" }],
            ["MediaSummarizer/Pipeline", "ResolverFailed", "WorkerType", "youtube_ingestion", { "stat" : "Sum", "label" : "YouTube FAIL", "color" : "#d62728" }],
            ["...", "tiktok_ingestion", { "stat" : "Sum", "label" : "TikTok FAIL", "color" : "#ff7f0e" }],
            ["...", "podcastindex_resolution", { "stat" : "Sum", "label" : "Podcast FAIL", "color" : "#9467bd" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Resolver Outcomes by Platform"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 9
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["MediaSummarizer/Pipeline", "ResolverRetry", "WorkerType", "youtube_ingestion", { "stat" : "Sum", "label" : "YouTube" }],
            ["...", "tiktok_ingestion", { "stat" : "Sum", "label" : "TikTok" }],
            ["...", "podcastindex_resolution", { "stat" : "Sum", "label" : "Podcast" }],
            ["...", "deepgram_transcription", { "stat" : "Sum", "label" : "Deepgram" }]
          ]
          view    = "timeSeries"
          stacked = true
          region  = var.aws_region
          title   = "Retries by Platform (leading indicator)"
          period  = 300
        }
      },

      # -----------------------------------------------------------------------
      # Row 3: Stage 3 - Transcription (Deepgram)
      # -----------------------------------------------------------------------
      {
        type   = "text"
        x      = 0
        y      = 15
        width  = 24
        height = 1
        properties = {
          markdown = "## Stage 3: Transcription (Deepgram) | SLO: 98% success, p95 < 120s"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 16
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["MediaSummarizer/Pipeline", "TranscriptionCompleted", { "stat" : "Sum", "label" : "Completed", "color" : "#2ca02c" }],
            ["MediaSummarizer/Pipeline", "TranscriptionFailed", { "stat" : "Sum", "label" : "Failed", "color" : "#d62728" }],
            ["MediaSummarizer/Pipeline", "TranscriptionStarted", { "stat" : "Sum", "label" : "Started", "color" : "#1f77b4" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Transcription Volume"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 16
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["MediaSummarizer/Pipeline", "TranscriptionDurationMs", { "stat" : "p95", "label" : "p95 Latency (ms)", "color" : "#d62728" }],
            ["MediaSummarizer/Pipeline", "TranscriptionDurationMs", { "stat" : "p50", "label" : "p50 Latency (ms)", "color" : "#2ca02c" }],
            ["MediaSummarizer/Pipeline", "TranscriptionDurationMs", { "stat" : "Average", "label" : "Average (ms)", "color" : "#1f77b4" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Transcription Latency (SLO p95 < 120s)"
          period  = 300
          annotations = {
            horizontal = [
              { label = "SLO p95 Target", value = 120000, color = "#ff7f0e" }
            ]
          }
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 16
        width  = 8
        height = 6
        properties = {
          metrics = [
            [{ "expression" : "100 * m1 / (m1 + m2)", "label" : "Success Rate %", "id" : "e1" }],
            ["MediaSummarizer/Pipeline", "TranscriptionCompleted", { "stat" : "Sum", "id" : "m1", "visible" : false }],
            ["MediaSummarizer/Pipeline", "TranscriptionFailed", { "stat" : "Sum", "id" : "m2", "visible" : false }]
          ]
          view    = "timeSeries"
          region  = var.aws_region
          title   = "Transcription Success Rate (SLO: 98%)"
          period  = 300
          yAxis   = { left = { min = 85, max = 100 } }
          annotations = {
            horizontal = [
              { label = "SLO Target", value = 98, color = "#ff7f0e" }
            ]
          }
        }
      },

      # -----------------------------------------------------------------------
      # Row 4: Stage 4 - Artifact Generation
      # -----------------------------------------------------------------------
      {
        type   = "text"
        x      = 0
        y      = 22
        width  = 24
        height = 1
        properties = {
          markdown = "## Stage 4: Artifact Generation (LLM) | SLO: 95% success, p95 < 30s"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 23
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["MediaSummarizer/Pipeline", "ArtifactGenerationCompleted", { "stat" : "Sum", "label" : "Completed", "color" : "#2ca02c" }],
            ["MediaSummarizer/Pipeline", "ArtifactGenerationFailed", { "stat" : "Sum", "label" : "Failed", "color" : "#d62728" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Artifact Generation Volume"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 23
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["MediaSummarizer/Pipeline", "ArtifactGenerationDurationMs", { "stat" : "p95", "label" : "p95 (ms)", "color" : "#d62728" }],
            ["MediaSummarizer/Pipeline", "ArtifactGenerationDurationMs", { "stat" : "p50", "label" : "p50 (ms)", "color" : "#2ca02c" }],
            ["MediaSummarizer/Pipeline", "ArtifactGenerationDurationMs", { "stat" : "Average", "label" : "Average (ms)", "color" : "#1f77b4" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Artifact Generation Latency (SLO p95 < 30s)"
          period  = 300
          annotations = {
            horizontal = [
              { label = "SLO p95 Target", value = 30000, color = "#ff7f0e" }
            ]
          }
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 23
        width  = 8
        height = 6
        properties = {
          metrics = [
            [{ "expression" : "100 * m1 / (m1 + m2)", "label" : "Success Rate %", "id" : "e1" }],
            ["MediaSummarizer/Pipeline", "ArtifactGenerationCompleted", { "stat" : "Sum", "id" : "m1", "visible" : false }],
            ["MediaSummarizer/Pipeline", "ArtifactGenerationFailed", { "stat" : "Sum", "id" : "m2", "visible" : false }]
          ]
          view    = "timeSeries"
          region  = var.aws_region
          title   = "Artifact Success Rate (SLO: 95%)"
          period  = 300
          yAxis   = { left = { min = 80, max = 100 } }
          annotations = {
            horizontal = [
              { label = "SLO Target", value = 95, color = "#ff7f0e" }
            ]
          }
        }
      },

      # -----------------------------------------------------------------------
      # Row 5: Queue Health (infrastructure)
      # -----------------------------------------------------------------------
      {
        type   = "text"
        x      = 0
        y      = 29
        width  = 24
        height = 1
        properties = {
          markdown = "## Infrastructure: Queue Depth and DLQ"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 30
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfVisibleMessages", "QueueName", "podcastindex-resolution-queue", { "stat" : "Average", "period" : 60 }],
            ["...", "youtube-ingestion-queue", { "stat" : "Average", "period" : 60 }],
            ["...", "tiktok-ingestion-queue", { "stat" : "Average", "period" : 60 }],
            ["...", "deepgram-transcription-queue", { "stat" : "Average", "period" : 60 }],
            ["...", "summarization-queue", { "stat" : "Average", "period" : 60 }],
            ["...", "article-extraction-queue", { "stat" : "Average", "period" : 60 }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Queue Backlog (Visible Messages)"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 30
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfVisibleMessages", "QueueName", "deepgram-transcription-dlq", { "stat" : "Sum", "period" : 300, "label" : "Deepgram DLQ" }],
            ["...", "summarization-dlq", { "stat" : "Sum", "period" : 300, "label" : "Summarization DLQ" }],
            ["...", "youtube-ingestion-dlq", { "stat" : "Sum", "period" : 300, "label" : "YouTube DLQ" }],
            ["...", "tiktok-ingestion-dlq", { "stat" : "Sum", "period" : 300, "label" : "TikTok DLQ" }],
            ["...", "audio-download-dlq", { "stat" : "Sum", "period" : 300, "label" : "Download DLQ" }],
            ["...", "article-extraction-dlq", { "stat" : "Sum", "period" : 300, "label" : "Article DLQ" }]
          ]
          view    = "timeSeries"
          stacked = true
          region  = var.aws_region
          title   = "Dead Letter Queue Depth (poison messages)"
        }
      },

      # -----------------------------------------------------------------------
      # Row 6: Diagnostic Queries
      # -----------------------------------------------------------------------
      {
        type   = "text"
        x      = 0
        y      = 36
        width  = 24
        height = 1
        properties = {
          markdown = "## Diagnostic Queries"
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 37
        width  = 12
        height = 6
        properties = {
          query   = "SOURCE '/aws/lambda/${var.project_name}-worker-deepgram_transcription' | SOURCE '/aws/lambda/${var.project_name}-worker-summarization' | SOURCE '/aws/lambda/${var.project_name}-worker-youtube_ingestion' | SOURCE '/aws/lambda/${var.project_name}-worker-tiktok_ingestion' | SOURCE '/aws/lambda/${var.project_name}-worker-podcastindex_resolution' | fields @timestamp, event, job_id, error_type, error_code | filter level = 'ERROR' | sort @timestamp desc | limit 20"
          region  = var.aws_region
          title   = "All Worker Errors (last 20)"
          view    = "table"
        }
      },
      {
        type   = "log"
        x      = 12
        y      = 37
        width  = 12
        height = 6
        properties = {
          query   = "SOURCE '/aws/lambda/${var.project_name}-worker-deepgram_transcription' | stats avg(duration_ms) as avg_ms, pct(duration_ms, 95) as p95_ms, count(*) as total by bin(5m) | filter event = 'worker.transcription.completed' | sort bin desc | limit 24"
          region  = var.aws_region
          title   = "Transcription Latency Distribution (5min buckets)"
          view    = "table"
        }
      }
    ]
  })
}
