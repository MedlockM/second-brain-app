# =============================================================================
# Digest notification scheduler (task-369, per the delivery path validated in
# docs/research/task-368-push-delivery/README.md).
#
# One Lambda, two schedules:
#
#   1. The Digest sweep. Daily Digests go out at 18:30 and weekly ones on Monday
#      at 09:30 — in the *user's* local time, so there is no single UTC instant to
#      fire at. This rule fires often enough that every local send instant falls
#      inside one of its passes, and the worker decides per account who is due.
#
#   2. A daily purge of push tokens no device has claimed in ninety days. Same
#      function because it is the same concern at the same cadence, routed on the
#      event's `source` — a second container image for one Scan is not worth the
#      deploy surface.
#
# Declared outside local.workers for the same reason as lambda_media_lifecycle:
# that map is SQS-shaped and the dashboard reads it as "the pipeline". This
# function is a *producer* of the push notification queue. CI still deploys its
# image — the workflow discovers Lambdas by the Environment tag plus the
# `media-summarizer-worker-` name prefix, which this one carries.
#
# Handler: media_summarizer/workers/digest/scheduler.py
# Consumer: media_summarizer/workers/push_notification_worker.py
# =============================================================================

variable "digest_notification_sweep_schedule" {
  description = <<-EOT
    When the Digest notification sweep runs. Every 15 minutes of every hour.

    A 15-minute grid is coarser than it looks. Across the 498 zones of the IANA
    database, 18:30 local and Monday 09:30 local only ever land on UTC minutes
    :00, :30 and :45 — no zone has an offset that puts them on :15 — so
    `cron(0,30,45 * * * ? *)` would already be exhaustive today, at 72 fires a
    day. The fourth fire is there because the exhaustiveness is a property of the
    current tz database, not of arithmetic: India moving from +05:30 to +05:45,
    or a new zone at a quarter-hour offset, would silence those users under the
    tighter grid. 96 fires a day of a 256MB function is under five cents a month.

    The worker is idempotent per (account, period) through a conditional write on
    published_at, so a denser grid cannot produce a duplicate notification — only
    more passes that find the period already claimed.
  EOT
  type        = string
  default     = "cron(0,15,30,45 * * * ? *)"
}

variable "push_token_purge_schedule" {
  description = "When stale push tokens are swept. Off-peak UTC: it scans user_push_tokens end to end."
  type        = string
  default     = "cron(15 4 * * ? *)"
}

locals {
  digest_scheduler_function_name = "${var.project_name}-worker-digest-scheduler${local.suffix}"
}

resource "aws_cloudwatch_log_group" "digest_scheduler" {
  name              = "/aws/lambda/${local.digest_scheduler_function_name}"
  retention_in_days = 14

  tags = {
    Name = "${local.digest_scheduler_function_name}-logs"
  }
}

resource "aws_lambda_function" "digest_scheduler" {
  function_name = local.digest_scheduler_function_name
  role          = aws_iam_role.lambda_worker.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repository_url}:${var.worker_image_tag}"

  # A sweep scans the users table, then reads settings and assembles a digest for
  # each account that is due. Most passes find nobody due and return in under a
  # second; the 18:30 and 09:30 passes do the real work.
  timeout       = 300
  memory_size   = 512
  architectures = ["arm64"]

  image_config {
    command = ["media_summarizer.workers.lambda_handlers.digest_scheduler_handler"]
  }

  environment {
    variables = local.lambda_environment
  }

  depends_on = [aws_cloudwatch_log_group.digest_scheduler]

  # See lambda_workers.tf: image_uri is owned by deploy-lambda.yml.
  lifecycle {
    ignore_changes = [image_uri]
  }

  tags = {
    Name = local.digest_scheduler_function_name
  }
}

# -----------------------------------------------------------------------------
# Trigger 1: the Digest notification sweep.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "digest_notification_sweep" {
  name                = "${var.project_name}-digest-notification-sweep${local.suffix}"
  description         = "Digest notification sweep: whose local 18:30 or Monday 09:30 just passed (task-369)"
  schedule_expression = var.digest_notification_sweep_schedule
  state               = "ENABLED"

  tags = {
    Name = "${var.project_name}-digest-notification-sweep${local.suffix}"
  }
}

resource "aws_cloudwatch_event_target" "digest_notification_sweep" {
  rule      = aws_cloudwatch_event_rule.digest_notification_sweep.name
  target_id = "${local.digest_scheduler_function_name}-sweep"
  arn       = aws_lambda_function.digest_scheduler.arn

  # The worker routes on this source. Anything that is not the purge source is
  # a sweep, so the sweep is the default and this input is documentation.
  input = jsonencode({
    source = "media-summarizer.digest-notification-sweep"
  })
}

resource "aws_lambda_permission" "digest_notification_sweep" {
  statement_id  = "AllowEventBridgeDigestNotificationSweep"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.digest_scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.digest_notification_sweep.arn
}

# -----------------------------------------------------------------------------
# Trigger 2: the stale push token purge.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "push_token_purge" {
  name                = "${var.project_name}-push-token-purge${local.suffix}"
  description         = "Delete push tokens unseen for 90 days (task-369)"
  schedule_expression = var.push_token_purge_schedule
  state               = "ENABLED"

  tags = {
    Name = "${var.project_name}-push-token-purge${local.suffix}"
  }
}

resource "aws_cloudwatch_event_target" "push_token_purge" {
  rule      = aws_cloudwatch_event_rule.push_token_purge.name
  target_id = "${local.digest_scheduler_function_name}-purge"
  arn       = aws_lambda_function.digest_scheduler.arn

  # This exact string is PURGE_EVENT_SOURCE in workers/digest/scheduler.py. The
  # two must agree: a mismatch silently runs a sweep instead of a purge.
  input = jsonencode({
    source = "media-summarizer.push-token-purge"
  })
}

resource "aws_lambda_permission" "push_token_purge" {
  statement_id  = "AllowEventBridgePushTokenPurge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.digest_scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.push_token_purge.arn
}

output "digest_scheduler_function_name" {
  description = "Name of the Digest notification scheduler Lambda (sweep + push token purge)."
  value       = aws_lambda_function.digest_scheduler.function_name
}
