# Monitoring configuration for Media Summarizer (Lambda-only architecture)

variable "ops_alert_email" {
  description = "Email address for operations alerts"
  type        = string
  default     = "ops@media-summarizer.com" # Should be overridden in tfvars
}

# SNS Topic for Ops Alerts (Email)
resource "aws_sns_topic" "ops_alerts" {
  name = "${var.project_name}-ops-alerts"

  tags = {
    Name        = "${var.project_name}-ops-alerts"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sns_topic_subscription" "ops_email" {
  topic_arn = aws_sns_topic.ops_alerts.arn
  protocol  = "email"
  endpoint  = var.ops_alert_email
}

# CloudWatch Metric Filters for Job Failures
# Applied to all worker Lambda log groups
resource "aws_cloudwatch_log_metric_filter" "job_failures" {
  for_each = aws_cloudwatch_log_group.lambda_worker

  name           = "${each.key}-job-failures"
  log_group_name = each.value.name

  # Pattern to match JSON logs where message is "Job processing failed"
  pattern = "{ $.message = \"Job processing failed\" }"

  metric_transformation {
    name      = "JobFailureCount"
    namespace = "MediaSummarizer/Jobs"
    value     = "1"
    dimensions = {
      WorkerType = each.key
    }
  }
}

# CloudWatch Alarm for High Failure Rate per worker
resource "aws_cloudwatch_metric_alarm" "high_job_failure_rate" {
  for_each = aws_cloudwatch_log_group.lambda_worker

  alarm_name          = "${var.project_name}-${each.key}-high-failure-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "JobFailureCount"
  namespace           = "MediaSummarizer/Jobs"
  period              = "300" # 5 minutes
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Alert when ${each.key} worker failure rate is high (> 5 in 5 minutes)"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    WorkerType = each.key
  }

  tags = {
    Name        = "${var.project_name}-${each.key}-high-failure-alarm"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Lambda Error Alarms (invocation errors from AWS Lambda metrics)
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = local.workers

  alarm_name          = "${var.project_name}-${each.key}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "3"
  alarm_description   = "Lambda invocation errors for ${each.key} worker"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.worker[each.key].function_name
  }

  tags = {
    Name        = "${var.project_name}-${each.key}-lambda-errors"
    Environment = var.environment
    Project     = var.project_name
  }
}

# API Lambda Error Alarm
resource "aws_cloudwatch_metric_alarm" "api_lambda_errors" {
  alarm_name          = "${var.project_name}-api-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Lambda invocation errors for API function"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }

  tags = {
    Name        = "${var.project_name}-api-lambda-errors"
    Environment = var.environment
    Project     = var.project_name
  }
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "jobs_monitoring" {
  dashboard_name = "${var.project_name}-jobs-monitoring"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["MediaSummarizer/Jobs", "JobFailureCount", "WorkerType", "podcastindex_resolution", { "stat" : "Sum", "label" : "PodcastIndex Resolution" }],
            ["...", "youtube_ingestion", { "stat" : "Sum", "label" : "YouTube" }],
            ["...", "tiktok_ingestion", { "stat" : "Sum", "label" : "TikTok" }],
            ["...", "deepgram_transcription", { "stat" : "Sum", "label" : "Deepgram" }],
            ["...", "summarization", { "stat" : "Sum", "label" : "Summarization" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Job Failures by Worker Type (5min)"
          period  = 300
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type   = "log"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          query   = "SOURCE '/aws/lambda/${var.project_name}-worker-podcastindex_resolution' | SOURCE '/aws/lambda/${var.project_name}-worker-youtube_ingestion' | SOURCE '/aws/lambda/${var.project_name}-worker-tiktok_ingestion' | SOURCE '/aws/lambda/${var.project_name}-worker-deepgram_transcription' | SOURCE '/aws/lambda/${var.project_name}-worker-summarization' | fields @timestamp, job_id, error_message, error_step | filter message = \"Job processing failed\" | sort @timestamp desc | limit 20"
          region  = var.aws_region
          title   = "Recent Job Failures"
          view    = "table"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 24
        height = 6
        properties = {
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfVisibleMessages", "QueueName", "podcastindex-resolution-queue", { "stat" : "Average", "period" : 60 }],
            ["...", "x-ingestion-queue", { "stat" : "Average", "period" : 60 }],
            ["...", "youtube-ingestion-queue", { "stat" : "Average", "period" : 60 }],
            ["...", "tiktok-ingestion-queue", { "stat" : "Average", "period" : 60 }],
            ["...", "deepgram-transcription-queue", { "stat" : "Average", "period" : 60 }],
            ["...", "summarization-queue", { "stat" : "Average", "period" : 60 }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Queue Backlog (Visible Messages)"
        }
      }
    ]
  })
}
