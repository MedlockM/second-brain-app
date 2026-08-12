# =============================================================================
# Durable media library observability (task-240)
#
# §6.5 of docs/research/task-218-durable-media-library-persistence/README.md:
# every signal here is an OUTCOME metric. The data loss investigated in
# task-218 stayed invisible for two months precisely because success metrics
# ("the archiver Lambda reports 0 errors") were watched while outcome metrics
# ("objects actually archived", "rows that actually survived") were not.
#
# Metrics are derived from log metric filters over the structured JSON log
# events, which is the convention already used by pipeline_dashboard.tf: the
# application never calls put_metric_data.
#
# Metric filters are free and therefore ungated. The alarms are gated on
# var.enable_alarms like every other alarm in this module (dev runs with alarms
# off to stay at ~$0.23/day), so in dev the *metric* is the signal and the
# runbook query is the tool.
#
# Runbook: infrastructure/observability/runbooks/durable-media.md
# =============================================================================

# -----------------------------------------------------------------------------
# durable_media.write_failed -- a save whose durable library row did not land.
#
# Emitted at ERROR by media_summarizer/core/services/durable_media_service.py.
# Filtered on the API log group (the save path) and on every worker log group
# (the status/metadata mirror), because both sides write the table.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_metric_filter" "durable_media_write_failed_api" {
  name           = "durable-media-write-failed-api${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.event = \"durable_media.write_failed\" }"

  metric_transformation {
    name          = "DurableMediaWriteFailed"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "durable_media_write_failed_worker" {
  for_each = local.workers

  name           = "durable-media-write-failed-${each.key}${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_worker[each.key].name
  pattern        = "{ $.event = \"durable_media.write_failed\" }"

  metric_transformation {
    name          = "DurableMediaWriteFailed"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

# The saves that did land. Paired with the failure metric on purpose so the
# failure count is read against a denominator instead of in the abstract.
resource "aws_cloudwatch_log_metric_filter" "durable_media_created" {
  name           = "durable-media-created${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.event = \"durable_media.created\" }"

  metric_transformation {
    name          = "DurableMediaCreated"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

# -----------------------------------------------------------------------------
# Alarm: any durable write failure at all.
#
# Threshold 0 and not a rate. A failed library write is a save the user believes
# happened and that does not exist; there is no acceptable background level of
# it. This is the alarm the task-218 incident lacked.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "durable_media_write_failed" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-durable-media-write-failed${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "A durable user_media write failed: a user save may not have been persisted, or a library row has drifted from its processing job. Runbook: infrastructure/observability/runbooks/durable-media.md#write-failed"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "DurableMediaWriteFailed"
  namespace   = local.metrics_namespace
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-durable-media-write-failed${local.suffix}"
    Severity = "critical"
  }
}

# -----------------------------------------------------------------------------
# Alarm: ANY TTL deletion on user_media (invariant I2 tripwire).
#
# The TTL on this table exists solely to sweep rows a user deleted, and no user
# deletion use case ships in Phase 1, so the correct expected value today is
# exactly zero. Once the deletion use case lands, this alarm becomes the
# reconciliation between soft deletes and sweeps; until then any non-zero value
# means something started expiring library rows, which is the regression that
# would silently reintroduce the incident.
#
# Daily period because the TTL sweeper is asynchronous and batchy: a 5-minute
# window would be noise.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "user_media_ttl_deletions" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-user-media-ttl-deletions${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "user_media rows were deleted by TTL. purge_at may only be written by a user-initiated deletion (invariant I2) and no such use case exists yet, so this must be zero. Runbook: infrastructure/observability/runbooks/durable-media.md#unexplained-ttl"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "TimeToLiveDeletedItemCount"
  namespace   = "AWS/DynamoDB"
  period      = "86400"
  statistic   = "Sum"

  dimensions = {
    TableName = aws_dynamodb_table.user_media_v1.name
  }

  tags = {
    Name     = "${var.project_name}-user-media-ttl-deletions${local.suffix}"
    Severity = "critical"
  }
}
