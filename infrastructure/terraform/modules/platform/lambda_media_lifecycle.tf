# =============================================================================
# user_media lifecycle worker (task-243, §6.2 + §6.5)
#
# One Lambda, two triggers:
#
#   1. The user_media DynamoDB stream. A REMOVE means the TTL swept a row the
#      user deleted 30 days earlier, and the cascade destroys the artifacts, the
#      S3 objects and the search records that row owned. Filtered to REMOVE only
#      so the ~all-INSERT/MODIFY traffic of a normal save never invokes it.
#
#   2. A daily schedule for the reconciliation of §6.5 (artifacts whose library
#      row is gone, purges that never happened, dangling job pointers, per-user
#      library size). This is the outcome metric the task-218 incident lacked:
#      the archiver reported zero errors for two months while the data it was
#      meant to protect disappeared.
#
# Declared here rather than in local.workers because that map is SQS-shaped
# (every entry has a queue_arn and an event source mapping, and the dashboard
# reads it as "the pipeline"). CI still deploys this function's image: the
# workflow discovers Lambdas by the Environment tag plus the
# `media-summarizer-worker-` name prefix, which this one carries.
#
# Handler: media_summarizer/workers/cleanup/media_lifecycle.py
# Runbook: infrastructure/observability/runbooks/durable-media.md
# =============================================================================

variable "media_lifecycle_reconciliation_schedule" {
  description = "When the daily user_media reconciliation runs. Off-peak UTC on purpose: it scans user_media and media_artifacts end to end."
  type        = string
  default     = "cron(30 3 * * ? *)"
}

locals {
  media_lifecycle_function_name = "${var.project_name}-worker-media-lifecycle${local.suffix}"
}

resource "aws_cloudwatch_log_group" "media_lifecycle" {
  name              = "/aws/lambda/${local.media_lifecycle_function_name}"
  retention_in_days = 14

  tags = {
    Name = "${local.media_lifecycle_function_name}-logs"
  }
}

resource "aws_lambda_function" "media_lifecycle" {
  function_name = local.media_lifecycle_function_name
  role          = aws_iam_role.lambda_worker.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repository_url}:${var.worker_image_tag}"

  # The reconciliation scans two tables and then samples job pointers; 300s and
  # 512MB is the same envelope as the heavier pipeline workers.
  timeout       = 300
  memory_size   = 512
  architectures = ["arm64"]

  image_config {
    command = ["media_summarizer.workers.lambda_handlers.media_lifecycle_handler"]
  }

  environment {
    variables = local.lambda_environment
  }

  depends_on = [aws_cloudwatch_log_group.media_lifecycle]

  # See lambda_workers.tf: image_uri is owned by deploy-lambda.yml.
  lifecycle {
    ignore_changes = [image_uri]
  }

  tags = {
    Name = local.media_lifecycle_function_name
  }
}

# -----------------------------------------------------------------------------
# Trigger 1: the purge cascade, driven by the table's own stream.
# -----------------------------------------------------------------------------

resource "aws_lambda_event_source_mapping" "media_lifecycle_stream" {
  event_source_arn  = aws_dynamodb_table.user_media_v1.stream_arn
  function_name     = aws_lambda_function.media_lifecycle.arn
  starting_position = "LATEST"
  batch_size        = 10

  # A record whose cascade keeps failing must not block the shard: the worker
  # returns batchItemFailures, the failure is alarmed as
  # user_media.purge_cascade_failed, and the daily reconciliation surfaces
  # whatever the retries never managed to delete.
  function_response_types        = ["ReportBatchItemFailures"]
  bisect_batch_on_function_error = true
  maximum_retry_attempts         = 5
  maximum_record_age_in_seconds  = 86400

  # REMOVE only. A stream filter cannot test for the absence of an attribute, so
  # "was this row actually deleted by its owner" is decided in the worker, which
  # reads deleted_at off the OldImage.
  filter_criteria {
    filter {
      pattern = jsonencode({
        eventName = ["REMOVE"]
      })
    }
  }
}

# -----------------------------------------------------------------------------
# Trigger 2: the daily reconciliation.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "media_lifecycle_reconciliation" {
  name                = "${var.project_name}-media-lifecycle-reconciliation${local.suffix}"
  description         = "Daily user_media <-> media_artifacts reconciliation (task-243 §6.5)"
  schedule_expression = var.media_lifecycle_reconciliation_schedule
  state               = "ENABLED"

  tags = {
    Name = "${var.project_name}-media-lifecycle-reconciliation${local.suffix}"
  }
}

resource "aws_cloudwatch_event_target" "media_lifecycle_reconciliation" {
  rule      = aws_cloudwatch_event_rule.media_lifecycle_reconciliation.name
  target_id = local.media_lifecycle_function_name
  arn       = aws_lambda_function.media_lifecycle.arn

  # No Records key: that is how the worker tells a scheduled tick from a stream
  # batch.
  input = jsonencode({
    source = "media-summarizer.media-lifecycle-reconciliation"
  })
}

resource "aws_lambda_permission" "media_lifecycle_reconciliation" {
  statement_id  = "AllowEventBridgeMediaLifecycleReconciliation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.media_lifecycle.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.media_lifecycle_reconciliation.arn
}

# -----------------------------------------------------------------------------
# Stream read permissions.
#
# A separate policy from lambda_worker: that one is 6144 bytes from its quota
# and shared by 13 functions that have no business reading a stream.
# -----------------------------------------------------------------------------

resource "aws_iam_policy" "media_lifecycle_stream" {
  name        = "${var.project_name}-media-lifecycle-stream-policy${local.suffix}"
  description = "Read the user_media stream to drive the purge cascade (task-243)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator",
          "dynamodb:DescribeStream",
          "dynamodb:ListStreams"
        ]
        Resource = aws_dynamodb_table.user_media_v1.stream_arn
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-media-lifecycle-stream-policy${local.suffix}"
  }
}

resource "aws_iam_role_policy_attachment" "media_lifecycle_stream" {
  role       = aws_iam_role.lambda_worker.name
  policy_arn = aws_iam_policy.media_lifecycle_stream.arn
}

output "media_lifecycle_function_name" {
  description = "Name of the user_media lifecycle Lambda (purge cascade + reconciliation)."
  value       = aws_lambda_function.media_lifecycle.function_name
}
