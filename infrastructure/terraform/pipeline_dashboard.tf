# =============================================================================
# Pipeline Observability Dashboard (Lambda Architecture)
# Covers: API Gateway -> Lambda Workers -> SQS Queues -> External Providers
#
# Aligned with V1 Phase 8 monitoring requirements (task-114).
# All ECS references have been removed post Lambda migration (task-106).
# =============================================================================

# -----------------------------------------------------------------------------
# Variables for monitoring
# -----------------------------------------------------------------------------
variable "alert_email" {
  description = "Email address for pipeline alert notifications"
  type        = string
  default     = "ops@media-summarizer.com"
}

variable "api_slow_request_threshold_ms" {
  description = "Threshold in ms for API p95 latency alarm"
  type        = number
  default     = 3000
}

variable "llamaparse_fallback_threshold_per_hour" {
  description = "Max Unstructured fallback invocations per hour before alarm fires"
  type        = number
  default     = 20
}

# -----------------------------------------------------------------------------
# Locals: Lambda function names and queue definitions
# -----------------------------------------------------------------------------
locals {
  # Lambda worker function names (matching the Lambda architecture)
  lambda_workers = [
    "podcastindex-resolution",
    "youtube-ingestion",
    "tiktok-ingestion",
    "x-ingestion",
    "audio-download",
    "deepgram-transcription",
    "article-extraction",
    "document-parsing",
    "summarization",
    "flashcards",
    "search-indexing",
    "episode-completed",
    "push-notification",
  ]

  # API Lambda function name
  lambda_api = "${var.project_name}-api"

  # API Gateway name
  api_gateway_name = "${var.project_name}-http-api"

  # All queues and their DLQs (name -> DLQ name)
  queue_dlq_map = {
    "podcastindex-resolution-queue"  = "podcastindex-resolution-dlq"
    "youtube-ingestion-queue"        = "youtube-ingestion-dlq"
    "tiktok-ingestion-queue"         = "tiktok-ingestion-dlq"
    "x-ingestion-queue"              = "x-ingestion-dlq"
    "audio-download-queue"           = "audio-download-dlq"
    "deepgram-transcription-queue"   = "deepgram-transcription-dlq"
    "article-extraction-queue"       = "article-extraction-dlq"
    "summarization-queue"            = "summarization-dlq"
    "flashcards-queue"               = "flashcards-dlq"
    "episode-completed-events"       = "episode-completed-dlq"
    "push-notification-queue"        = "push-notification-dlq"
    "spotify-sync-queue"             = "spotify-sync-dlq"
  }

  # Log group names for Lambda functions
  api_log_group    = "/aws/lambda/${local.lambda_api}"
  worker_log_groups = { for w in local.lambda_workers : w => "/aws/lambda/${var.project_name}-${w}" }
}

# =============================================================================
# LOG METRIC FILTERS -- Source Platform Counters
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "source_platform_counter" {
  for_each = toset(["youtube", "tiktok", "instagram", "x", "podcast", "article", "document"])

  name           = "source-platform-${each.key}"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.source_platform = \"${each.key}\" && $.event = \"media.ingest.created\" }"

  metric_transformation {
    name      = "IngestByPlatform"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
    dimensions = {
      SourcePlatform = "$.source_platform"
    }
  }
}

# =============================================================================
# LOG METRIC FILTERS -- Parser Usage (LlamaParse vs Unstructured)
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "parser_llamaparse" {
  name           = "parser-llamaparse-calls"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["document_parsing"].name
  pattern        = "{ $.event = \"document_parsing.primary_success\" && $.provider = \"llamaparse\" }"

  metric_transformation {
    name      = "ParserCalls"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
    dimensions = {
      Parser = "$.provider"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "parser_unstructured_fallback" {
  name           = "parser-unstructured-fallback"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["document_parsing"].name
  pattern        = "{ $.event = \"document_parsing.fallback_success\" && $.provider = \"unstructured\" }"

  metric_transformation {
    name      = "ParserCalls"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
    dimensions = {
      Parser = "$.provider"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "unstructured_fallback_triggered" {
  name           = "unstructured-fallback-triggered"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["document_parsing"].name
  pattern        = "{ $.event = \"document_parsing.primary_failed\" }"

  metric_transformation {
    name      = "UnstructuredFallbackTriggered"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

# =============================================================================
# LOG METRIC FILTERS -- Apify Provider Calls
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "apify_calls" {
  name           = "apify-provider-calls"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["tiktok_ingestion"].name
  pattern        = "{ $.provider = \"apify\" }"

  metric_transformation {
    name      = "ApifyCalls"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

# =============================================================================
# LOG METRIC FILTERS -- Deepgram Error Rate
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "deepgram_calls_total" {
  name           = "deepgram-calls-total"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["deepgram_transcription"].name
  pattern        = "{ $.transcript_source = \"deepgram\" && ($.event = \"worker.transcription.completed\" || $.event = \"worker.transcription.failed\") }"

  metric_transformation {
    name      = "DeepgramCallsTotal"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "deepgram_errors" {
  name           = "deepgram-errors"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["deepgram_transcription"].name
  pattern        = "{ $.transcript_source = \"deepgram\" && $.event = \"worker.transcription.failed\" }"

  metric_transformation {
    name      = "DeepgramErrors"
    namespace = "MediaSummarizer/Pipeline"
    value     = "1"
  }
}

# =============================================================================
# CLOUDWATCH DASHBOARD
# =============================================================================

resource "aws_cloudwatch_dashboard" "pipeline_observability" {
  dashboard_name = "${var.project_name}-pipeline-observability"

  dashboard_body = jsonencode({
    widgets = concat(
      # -----------------------------------------------------------------------
      # Row 0: Header
      # -----------------------------------------------------------------------
      [
        {
          type   = "text"
          x      = 0
          y      = 0
          width  = 24
          height = 1
          properties = {
            markdown = "# Media Summarizer Pipeline (Lambda)\nAPI Gateway -> Lambda Workers -> SQS -> External Providers | [Runbook](https://github.com/your-org/media-summarizer/blob/main/infrastructure/observability/runbooks/pipeline-alerts.md)"
          }
        }
      ],

      # -----------------------------------------------------------------------
      # Row 1: API Gateway HTTP API
      # -----------------------------------------------------------------------
      [
        {
          type   = "text"
          x      = 0
          y      = 1
          width  = 24
          height = 1
          properties = {
            markdown = "## API Gateway HTTP API - Latency & Errors"
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
              ["AWS/ApiGateway", "Latency", "ApiId", local.api_gateway_name, { "stat" : "p50", "label" : "p50" }],
              ["AWS/ApiGateway", "Latency", "ApiId", local.api_gateway_name, { "stat" : "p95", "label" : "p95", "color" : "#ff7f0e" }],
              ["AWS/ApiGateway", "Latency", "ApiId", local.api_gateway_name, { "stat" : "p99", "label" : "p99", "color" : "#d62728" }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "API Latency (p50 / p95 / p99)"
            period = 300
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
              ["AWS/ApiGateway", "4xx", "ApiId", local.api_gateway_name, { "stat" : "Sum", "label" : "4xx", "color" : "#ff7f0e" }],
              ["AWS/ApiGateway", "5xx", "ApiId", local.api_gateway_name, { "stat" : "Sum", "label" : "5xx", "color" : "#d62728" }],
              ["AWS/ApiGateway", "Count", "ApiId", local.api_gateway_name, { "stat" : "Sum", "label" : "Total", "color" : "#1f77b4" }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "API Request Count (4xx / 5xx / Total)"
            period = 300
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 2
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ApiGateway", "Count", "ApiId", local.api_gateway_name, "Resource", "/api/media/ingest-url", "Method", "POST", { "stat" : "Sum", "label" : "POST /ingest-url" }],
              ["AWS/ApiGateway", "Count", "ApiId", local.api_gateway_name, "Resource", "/api/media/ingest-shared-content", "Method", "POST", { "stat" : "Sum", "label" : "POST /ingest-shared-content" }],
              ["AWS/ApiGateway", "Count", "ApiId", local.api_gateway_name, "Resource", "/api/media/{id}", "Method", "GET", { "stat" : "Sum", "label" : "GET /media/{id}" }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "Requests by Route"
            period = 300
          }
        }
      ],

      # -----------------------------------------------------------------------
      # Row 2: Lambda Workers - Invocations, Errors, Duration, Throttles
      # -----------------------------------------------------------------------
      [
        {
          type   = "text"
          x      = 0
          y      = 8
          width  = 24
          height = 1
          properties = {
            markdown = "## Lambda Workers - Invocations / Errors / Duration p95 / Throttles"
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
              for w in local.lambda_workers :
              ["AWS/Lambda", "Invocations", "FunctionName", "${var.project_name}-${w}", { "stat" : "Sum", "label" : w }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "Lambda Invocations (per function)"
            period = 300
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
              for w in local.lambda_workers :
              ["AWS/Lambda", "Errors", "FunctionName", "${var.project_name}-${w}", { "stat" : "Sum", "label" : w }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "Lambda Errors (per function)"
            period = 300
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 15
          width  = 12
          height = 6
          properties = {
            metrics = [
              for w in local.lambda_workers :
              ["AWS/Lambda", "Duration", "FunctionName", "${var.project_name}-${w}", { "stat" : "p95", "label" : w }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "Lambda Duration p95 (per function)"
            period = 300
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 15
          width  = 12
          height = 6
          properties = {
            metrics = concat(
              [
                for w in local.lambda_workers :
                ["AWS/Lambda", "Throttles", "FunctionName", "${var.project_name}-${w}", { "stat" : "Sum", "label" : w }]
              ],
              [
                for w in local.lambda_workers :
                ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", "${var.project_name}-${w}", { "stat" : "Maximum", "label" : "${w} (concurrency)", "yAxis" : "right" }]
              ]
            )
            view   = "timeSeries"
            region = var.aws_region
            title  = "Lambda Throttles & Concurrent Executions"
            period = 300
          }
        }
      ],

      # -----------------------------------------------------------------------
      # Row 3: SQS Queue Depth (main queues + DLQs)
      # -----------------------------------------------------------------------
      [
        {
          type   = "text"
          x      = 0
          y      = 21
          width  = 24
          height = 1
          properties = {
            markdown = "## SQS Queue Depth - Main Queues & Dead Letter Queues"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 22
          width  = 12
          height = 6
          properties = {
            metrics = [
              for q_name, _ in local.queue_dlq_map :
              ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", q_name, { "stat" : "Average", "period" : 60, "label" : q_name }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "Queue Backlog (Visible Messages)"
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 22
          width  = 12
          height = 6
          properties = {
            metrics = [
              for _, dlq_name in local.queue_dlq_map :
              ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", dlq_name, { "stat" : "Sum", "period" : 300, "label" : dlq_name }]
            ]
            view    = "timeSeries"
            stacked = true
            region  = var.aws_region
            title   = "Dead Letter Queue Depth"
          }
        }
      ],

      # -----------------------------------------------------------------------
      # Row 4: Ingestion by Source Platform (stacked area)
      # -----------------------------------------------------------------------
      [
        {
          type   = "text"
          x      = 0
          y      = 28
          width  = 24
          height = 1
          properties = {
            markdown = "## Ingestion by Source Platform & Provider Quotas"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 29
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["MediaSummarizer/Pipeline", "IngestByPlatform", "SourcePlatform", "youtube", { "stat" : "Sum", "label" : "YouTube" }],
              ["MediaSummarizer/Pipeline", "IngestByPlatform", "SourcePlatform", "tiktok", { "stat" : "Sum", "label" : "TikTok" }],
              ["MediaSummarizer/Pipeline", "IngestByPlatform", "SourcePlatform", "instagram", { "stat" : "Sum", "label" : "Instagram" }],
              ["MediaSummarizer/Pipeline", "IngestByPlatform", "SourcePlatform", "x", { "stat" : "Sum", "label" : "X (Twitter)" }],
              ["MediaSummarizer/Pipeline", "IngestByPlatform", "SourcePlatform", "podcast", { "stat" : "Sum", "label" : "Podcast" }],
              ["MediaSummarizer/Pipeline", "IngestByPlatform", "SourcePlatform", "article", { "stat" : "Sum", "label" : "Article" }],
              ["MediaSummarizer/Pipeline", "IngestByPlatform", "SourcePlatform", "document", { "stat" : "Sum", "label" : "Document" }]
            ]
            view    = "timeSeries"
            stacked = true
            region  = var.aws_region
            title   = "Ingestion Volume by Platform (5min)"
            period  = 300
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 29
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["MediaSummarizer/Pipeline", "ParserCalls", "Parser", "llamaparse", { "stat" : "Sum", "label" : "LlamaParse" }],
              ["MediaSummarizer/Pipeline", "ParserCalls", "Parser", "unstructured", { "stat" : "Sum", "label" : "Unstructured (fallback)" }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "Document Parser Usage (LlamaParse vs Unstructured)"
            period = 300
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 29
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["MediaSummarizer/Pipeline", "ApifyCalls", { "stat" : "Sum", "label" : "Apify Calls" }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "Apify Provider Calls (TikTok/Instagram)"
            period = 300
          }
        }
      ],

      # -----------------------------------------------------------------------
      # Row 5: Deepgram & Transcription Metrics
      # -----------------------------------------------------------------------
      [
        {
          type   = "text"
          x      = 0
          y      = 35
          width  = 24
          height = 1
          properties = {
            markdown = "## Transcription (Deepgram) & Error Rates"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 36
          width  = 12
          height = 6
          properties = {
            metrics = [
              ["MediaSummarizer/Pipeline", "DeepgramCallsTotal", { "stat" : "Sum", "label" : "Total Calls", "color" : "#1f77b4" }],
              ["MediaSummarizer/Pipeline", "DeepgramErrors", { "stat" : "Sum", "label" : "Errors", "color" : "#d62728" }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "Deepgram Calls vs Errors"
            period = 300
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 36
          width  = 12
          height = 6
          properties = {
            metrics = [
              [{ "expression" : "IF(m2 > 0, 100 * m1 / m2, 0)", "label" : "Deepgram Error Rate %", "id" : "e1" }],
              ["MediaSummarizer/Pipeline", "DeepgramErrors", { "stat" : "Sum", "id" : "m1", "visible" : false }],
              ["MediaSummarizer/Pipeline", "DeepgramCallsTotal", { "stat" : "Sum", "id" : "m2", "visible" : false }]
            ]
            view   = "timeSeries"
            region = var.aws_region
            title  = "Deepgram Error Rate % (alarm > 5%)"
            period = 900
            annotations = {
              horizontal = [
                { label = "Alarm Threshold", value = 5, color = "#d62728" }
              ]
            }
          }
        }
      ]
    )
  })
}
