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
  description = "Address subscribed to the pipeline alerts SNS topic. Empty (the default) creates the topic without an email subscription — subscribe out-of-band so no personal address is committed."
  type        = string
  default     = ""
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
  # Custom metrics emitted by the log metric filters below. The namespace is
  # per-environment: the filters read per-environment log groups, but before
  # task-237 they all published into one shared namespace, so a staging failure
  # would have fired the dev alarm.
  metrics_namespace = "MediaSummarizer/Pipeline/${var.environment}"
}

locals {
  # These three maps used to be hand-maintained string lists that had drifted
  # badly from reality: they still referenced workers and queues that no longer
  # exist (audio-download, push-notification, episode-completed, spotify-sync),
  # used a "-<worker>" naming pattern the functions never had, and pointed the
  # API widgets and alarms at "media-summarizer-http-api", an ApiId that never
  # matched the real API. They are now DERIVED from the resources themselves, so
  # they cannot drift again and they carry the environment suffix for free.

  # Worker Lambda function names, keyed by worker key (see local.workers).
  worker_function_names = {
    for k, fn in aws_lambda_function.worker : k => fn.function_name
  }
  lambda_workers = keys(local.workers)

  # API Gateway dimension value. The AWS/ApiGateway metrics for an HTTP API are
  # dimensioned by API ID, not by name, and API names are not unique across
  # environments.
  api_gateway_id = aws_apigatewayv2_api.main.id

  # Short queue key -> { queue, dlq } physical names, derived from the real SQS
  # resources. The key stays short so alarm names remain readable AND keep the
  # environment suffix at the end (a map keyed by the already-suffixed queue name
  # produced alarms like "…-dlq-media-summarizer-x-dlq-dev-non-empty", which the
  # tf_plan_guard suffix check rightly rejects).
  queue_dlq_map = {
    rss_resolution         = { queue = aws_sqs_queue.rss_resolution.name, dlq = aws_sqs_queue.rss_resolution_dlq.name }
    article_extraction     = { queue = aws_sqs_queue.article_extraction.name, dlq = aws_sqs_queue.article_extraction_dlq.name }
    x_ingestion            = { queue = aws_sqs_queue.x_ingestion.name, dlq = aws_sqs_queue.x_ingestion_dlq.name }
    youtube_ingestion      = { queue = aws_sqs_queue.youtube_ingestion.name, dlq = aws_sqs_queue.youtube_ingestion_dlq.name }
    instagram_ingestion    = { queue = aws_sqs_queue.instagram_ingestion.name, dlq = aws_sqs_queue.instagram_ingestion_dlq.name }
    tiktok_ingestion       = { queue = aws_sqs_queue.tiktok_ingestion.name, dlq = aws_sqs_queue.tiktok_ingestion_dlq.name }
    deepgram_transcription = { queue = aws_sqs_queue.deepgram_transcription.name, dlq = aws_sqs_queue.deepgram_transcription_dlq.name }
    artifact_generator     = { queue = aws_sqs_queue.artifact_generator.name, dlq = aws_sqs_queue.artifact_generator_dlq.name }
    document_parsing       = { queue = aws_sqs_queue.document_parsing.name, dlq = aws_sqs_queue.document_parsing_dlq.name }
    search_indexing        = { queue = aws_sqs_queue.search_indexing.name, dlq = aws_sqs_queue.search_indexing_dlq.name }
    rss_feed_poll          = { queue = aws_sqs_queue.rss_feed_poll.name, dlq = aws_sqs_queue.rss_feed_poll_dlq.name }
    media_completed_events = { queue = aws_sqs_queue.media_completed_events.name, dlq = aws_sqs_queue.media_completed_events_dlq.name }
    transcript_translation = { queue = aws_sqs_queue.transcript_translation.name, dlq = aws_sqs_queue.transcript_translation_dlq.name }
  }
}

# =============================================================================
# LOG METRIC FILTERS -- Source Platform Counters
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "source_platform_counter" {
  for_each = toset(["youtube", "tiktok", "instagram", "x", "podcast", "article", "document"])

  name           = "source-platform-${each.key}${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.source_platform = \"${each.key}\" && $.event = \"media.ingest.created\" }"

  metric_transformation {
    name      = "IngestByPlatform"
    namespace = local.metrics_namespace
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
  name           = "parser-llamaparse-calls${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["document_parsing"].name
  pattern        = "{ $.event = \"document_parsing.primary_success\" && $.provider = \"llamaparse\" }"

  metric_transformation {
    name      = "ParserCalls"
    namespace = local.metrics_namespace
    value     = "1"
    dimensions = {
      Parser = "$.provider"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "parser_unstructured_fallback" {
  name           = "parser-unstructured-fallback${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["document_parsing"].name
  pattern        = "{ $.event = \"document_parsing.fallback_success\" && $.provider = \"unstructured\" }"

  metric_transformation {
    name      = "ParserCalls"
    namespace = local.metrics_namespace
    value     = "1"
    dimensions = {
      Parser = "$.provider"
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "unstructured_fallback_triggered" {
  name           = "unstructured-fallback-triggered${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["document_parsing"].name
  pattern        = "{ $.event = \"document_parsing.primary_failed\" }"

  metric_transformation {
    name      = "UnstructuredFallbackTriggered"
    namespace = local.metrics_namespace
    value     = "1"
  }
}

# =============================================================================
# LOG METRIC FILTERS -- Apify Provider Calls
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "apify_calls" {
  name           = "apify-provider-calls${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["tiktok_ingestion"].name
  pattern        = "{ $.provider = \"apify\" }"

  metric_transformation {
    name      = "ApifyCalls"
    namespace = local.metrics_namespace
    value     = "1"
  }
}

# =============================================================================
# LOG METRIC FILTERS -- Deepgram Error Rate
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "deepgram_calls_total" {
  name           = "deepgram-calls-total${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["deepgram_transcription"].name
  pattern        = "{ $.transcript_source = \"deepgram\" && ($.event = \"worker.transcription.completed\" || $.event = \"worker.transcription.failed\") }"

  metric_transformation {
    name      = "DeepgramCallsTotal"
    namespace = local.metrics_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "deepgram_errors" {
  name           = "deepgram-errors${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_worker["deepgram_transcription"].name
  pattern        = "{ $.transcript_source = \"deepgram\" && $.event = \"worker.transcription.failed\" }"

  metric_transformation {
    name      = "DeepgramErrors"
    namespace = local.metrics_namespace
    value     = "1"
  }
}

# =============================================================================
# CLOUDWATCH DASHBOARD
# =============================================================================

resource "aws_cloudwatch_dashboard" "pipeline_observability" {
  # Gated because this is the most expensive resource in an idle environment:
  # CloudWatch bills per dashboard past the 3-dashboard free tier, measured at
  # ~$3.00/mo — more than the 43 alarms it visualises. It used to be
  # ungated, so a second environment silently doubled the account's
  # CloudWatch bill the day it was created.
  count = var.enable_dashboard ? 1 : 0

  dashboard_name = "${var.project_name}-pipeline-observability${local.suffix}"

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
              ["AWS/ApiGateway", "Latency", "ApiId", local.api_gateway_id, { "stat" : "p50", "label" : "p50" }],
              ["AWS/ApiGateway", "Latency", "ApiId", local.api_gateway_id, { "stat" : "p95", "label" : "p95", "color" : "#ff7f0e" }],
              ["AWS/ApiGateway", "Latency", "ApiId", local.api_gateway_id, { "stat" : "p99", "label" : "p99", "color" : "#d62728" }]
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
              ["AWS/ApiGateway", "4xx", "ApiId", local.api_gateway_id, { "stat" : "Sum", "label" : "4xx", "color" : "#ff7f0e" }],
              ["AWS/ApiGateway", "5xx", "ApiId", local.api_gateway_id, { "stat" : "Sum", "label" : "5xx", "color" : "#d62728" }],
              ["AWS/ApiGateway", "Count", "ApiId", local.api_gateway_id, { "stat" : "Sum", "label" : "Total", "color" : "#1f77b4" }]
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
              ["AWS/ApiGateway", "Count", "ApiId", local.api_gateway_id, "Resource", "/api/media/ingest-url", "Method", "POST", { "stat" : "Sum", "label" : "POST /ingest-url" }],
              ["AWS/ApiGateway", "Count", "ApiId", local.api_gateway_id, "Resource", "/api/media/ingest-shared-content", "Method", "POST", { "stat" : "Sum", "label" : "POST /ingest-shared-content" }],
              ["AWS/ApiGateway", "Count", "ApiId", local.api_gateway_id, "Resource", "/api/media/{id}", "Method", "GET", { "stat" : "Sum", "label" : "GET /media/{id}" }]
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
              ["AWS/Lambda", "Invocations", "FunctionName", local.worker_function_names[w], { "stat" : "Sum", "label" : w }]
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
              ["AWS/Lambda", "Errors", "FunctionName", local.worker_function_names[w], { "stat" : "Sum", "label" : w }]
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
              ["AWS/Lambda", "Duration", "FunctionName", local.worker_function_names[w], { "stat" : "p95", "label" : w }]
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
                ["AWS/Lambda", "Throttles", "FunctionName", local.worker_function_names[w], { "stat" : "Sum", "label" : w }]
              ],
              [
                for w in local.lambda_workers :
                ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", local.worker_function_names[w], { "stat" : "Maximum", "label" : "${w} (concurrency)", "yAxis" : "right" }]
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
              for _, q in local.queue_dlq_map :
              ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", q.queue, { "stat" : "Average", "period" : 60, "label" : q.queue }]
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
              for _, q in local.queue_dlq_map :
              ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", q.dlq, { "stat" : "Sum", "period" : 300, "label" : q.dlq }]
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
              [local.metrics_namespace, "IngestByPlatform", "SourcePlatform", "youtube", { "stat" : "Sum", "label" : "YouTube" }],
              [local.metrics_namespace, "IngestByPlatform", "SourcePlatform", "tiktok", { "stat" : "Sum", "label" : "TikTok" }],
              [local.metrics_namespace, "IngestByPlatform", "SourcePlatform", "instagram", { "stat" : "Sum", "label" : "Instagram" }],
              [local.metrics_namespace, "IngestByPlatform", "SourcePlatform", "x", { "stat" : "Sum", "label" : "X (Twitter)" }],
              [local.metrics_namespace, "IngestByPlatform", "SourcePlatform", "podcast", { "stat" : "Sum", "label" : "Podcast" }],
              [local.metrics_namespace, "IngestByPlatform", "SourcePlatform", "article", { "stat" : "Sum", "label" : "Article" }],
              [local.metrics_namespace, "IngestByPlatform", "SourcePlatform", "document", { "stat" : "Sum", "label" : "Document" }]
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
              [local.metrics_namespace, "ParserCalls", "Parser", "llamaparse", { "stat" : "Sum", "label" : "LlamaParse" }],
              [local.metrics_namespace, "ParserCalls", "Parser", "unstructured", { "stat" : "Sum", "label" : "Unstructured (fallback)" }]
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
              [local.metrics_namespace, "ApifyCalls", { "stat" : "Sum", "label" : "Apify Calls" }]
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
              [local.metrics_namespace, "DeepgramCallsTotal", { "stat" : "Sum", "label" : "Total Calls", "color" : "#1f77b4" }],
              [local.metrics_namespace, "DeepgramErrors", { "stat" : "Sum", "label" : "Errors", "color" : "#d62728" }]
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
              [local.metrics_namespace, "DeepgramErrors", { "stat" : "Sum", "id" : "m1", "visible" : false }],
              [local.metrics_namespace, "DeepgramCallsTotal", { "stat" : "Sum", "id" : "m2", "visible" : false }]
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
