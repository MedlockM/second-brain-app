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

# =============================================================================
# The deletion lifecycle (task-243, §6.2 + §6.5)
#
# Until task-243 the only alarm on the TTL was "any TTL deletion at all", which
# was correct while no deletion use case existed and became meaningless the
# moment one shipped. It is replaced below by three questions that stay
# meaningful forever:
#
#   1. Did a row expire that nobody deleted?          -> unexplained_purge
#   2. Did a row expire without its content going?    -> ttl_without_cascade,
#                                                        purge_cascade_failed
#   3. Is the watchdog that answers 1 and 2 running?  -> reconciliation_stopped
# =============================================================================

# The user's deletion request. Emitted by the API
# (core/services/media_deletion_service.py); the failure side is what gets
# alarmed, and the success side is its denominator.
resource "aws_cloudwatch_log_metric_filter" "user_media_soft_deleted" {
  name           = "user-media-soft-deleted${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.event = \"user_media.soft_deleted\" }"

  metric_transformation {
    name          = "UserMediaSoftDeleted"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "user_media_delete_failed" {
  name           = "user-media-delete-failed${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.event = \"user_media.delete_failed\" }"

  metric_transformation {
    name          = "UserMediaDeleteFailed"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

# The purge cascade, 30 days later, on the lifecycle worker's log group.
resource "aws_cloudwatch_log_metric_filter" "user_media_purge_completed" {
  name           = "user-media-purge-completed${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.media_lifecycle.name
  pattern        = "{ $.event = \"user_media.purge_cascade_completed\" }"

  metric_transformation {
    name          = "UserMediaPurgeCompleted"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "user_media_purge_failed" {
  name           = "user-media-purge-failed${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.media_lifecycle.name
  pattern        = "{ $.event = \"user_media.purge_cascade_failed\" }"

  metric_transformation {
    name          = "UserMediaPurgeFailed"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "user_media_unexplained_purge" {
  name           = "user-media-unexplained-purge${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.media_lifecycle.name
  pattern        = "{ $.event = \"user_media.unexplained_purge\" }"

  metric_transformation {
    name          = "UserMediaUnexplainedPurge"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

# The daily reconciliation publishes its gauges as fields of a single log event,
# so each one is a metric filter reading a JSON field rather than counting lines.
resource "aws_cloudwatch_log_metric_filter" "user_media_reconciliation_ran" {
  name           = "user-media-reconciliation-ran${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.media_lifecycle.name
  pattern        = "{ $.event = \"user_media.reconciliation_completed\" }"

  metric_transformation {
    name          = "UserMediaReconciliationRuns"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "user_media_orphan_artifacts_recent" {
  name           = "user-media-orphan-artifacts-recent${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.media_lifecycle.name
  pattern        = "{ $.event = \"user_media.reconciliation_completed\" }"

  metric_transformation {
    name      = "UserMediaOrphanArtifactsRecent"
    namespace = local.metrics_namespace
    value     = "$.artifact_rows_orphaned_recent"
  }
}

# Total drift is a gauge, never an alarm: dev carries a permanent standing drift
# from the task-241 backfill (quarantined artifact rows whose owner could not be
# established), so an alarm on it would be permanently breaching and therefore
# ignored. The *recent* orphan count above is the actionable half.
resource "aws_cloudwatch_log_metric_filter" "user_media_orphan_artifacts_total" {
  name           = "user-media-orphan-artifacts-total${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.media_lifecycle.name
  pattern        = "{ $.event = \"user_media.reconciliation_completed\" }"

  metric_transformation {
    name      = "UserMediaOrphanArtifactsTotal"
    namespace = local.metrics_namespace
    value     = "$.artifact_rows_orphaned"
  }
}

resource "aws_cloudwatch_log_metric_filter" "user_media_rows_overdue_purge" {
  name           = "user-media-rows-overdue-purge${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.media_lifecycle.name
  pattern        = "{ $.event = \"user_media.reconciliation_completed\" }"

  metric_transformation {
    name      = "UserMediaRowsOverduePurge"
    namespace = local.metrics_namespace
    value     = "$.library_rows_overdue_purge"
  }
}

# Per-user library size (§6.5). No alarm: it is the number that tells us whether
# a library is growing as expected, and the one that would have made the task-218
# incident visible in a glance.
resource "aws_cloudwatch_log_metric_filter" "user_media_max_rows_per_user" {
  name           = "user-media-max-rows-per-user${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.media_lifecycle.name
  pattern        = "{ $.event = \"user_media.reconciliation_completed\" }"

  metric_transformation {
    name      = "UserMediaMaxRowsPerUser"
    namespace = local.metrics_namespace
    value     = "$.library_max_rows_per_user"
  }
}

# -----------------------------------------------------------------------------
# Alarm: a user's deletion request failed.
#
# The user asked for the item to go and it did not. Threshold 0: there is no
# acceptable background level of a deletion that silently does not happen.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "user_media_delete_failed" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-user-media-delete-failed${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "A user-initiated media deletion failed to write its soft delete. The item is still in the user's library. Runbook: infrastructure/observability/runbooks/durable-media.md#deletion-failed"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "UserMediaDeleteFailed"
  namespace   = local.metrics_namespace
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-user-media-delete-failed${local.suffix}"
    Severity = "critical"
  }
}

# -----------------------------------------------------------------------------
# Alarm: a row expired that nobody deleted (invariant I2 tripwire).
#
# This is what the old "any TTL deletion" alarm was really watching for. A
# TTL-swept row with no deleted_at means something other than the deletion use
# case wrote purge_at — the exact shape of the incident this table exists to
# prevent. The worker deliberately does NOT cascade those, so the content is
# still recoverable when this fires.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "user_media_unexplained_purge" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-user-media-unexplained-purge${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "A user_media row was swept by TTL without ever being deleted by its owner: purge_at was written by something other than the deletion use case (invariant I2). Restore from PITR before the 35-day window closes. Runbook: infrastructure/observability/runbooks/durable-media.md#unexplained-ttl"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "UserMediaUnexplainedPurge"
  namespace   = local.metrics_namespace
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-user-media-unexplained-purge${local.suffix}"
    Severity = "critical"
  }
}

# -----------------------------------------------------------------------------
# Alarm: the purge cascade failed.
#
# The row is gone and a cascade step that had no remaining content reference
# failed, leaving artifacts, objects or search records behind.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "user_media_purge_cascade_failed" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-user-media-purge-cascade-failed${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "The purge cascade failed after a user_media TTL sweep: artifacts, S3 objects or search records may survive after the final applicable library reference. Runbook: infrastructure/observability/runbooks/durable-media.md#purge-cascade-failed"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "UserMediaPurgeFailed"
  namespace   = local.metrics_namespace
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-user-media-purge-cascade-failed${local.suffix}"
    Severity = "critical"
  }
}

# -----------------------------------------------------------------------------
# Alarm: rows were swept by TTL and the cascade never even ran.
#
# The outcome metric that covers the failure modes no log line can report,
# because in those the code never executes: the event source mapping disabled,
# the stream permissions revoked, records aged out of the 24h retention. Compares
# DynamoDB's own sweep counter against the number of records the worker accounted
# for (cascaded + flagged as unexplained).
#
# Two consecutive breaching days are required: a sweep at 23:59 whose cascade
# lands at 00:01 straddles the daily boundary and would otherwise false-alarm.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "user_media_ttl_without_cascade" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-user-media-ttl-without-cascade${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  datapoints_to_alarm = "2"
  threshold           = "0"
  alarm_description   = "user_media rows were swept by TTL without the purge cascade accounting for them: the stream consumer is disabled, unauthorized, or falling behind its 24h record retention. Runbook: infrastructure/observability/runbooks/durable-media.md#ttl-without-cascade"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "unaccounted"
    expression  = "IF(swept - (cascaded + flagged) > 0, swept - (cascaded + flagged), 0)"
    label       = "TTL sweeps the cascade never accounted for"
    return_data = true
  }

  metric_query {
    id = "swept"
    metric {
      metric_name = "TimeToLiveDeletedItemCount"
      namespace   = "AWS/DynamoDB"
      period      = "86400"
      stat        = "Sum"
      dimensions = {
        TableName = aws_dynamodb_table.user_media_v1.name
      }
    }
  }

  metric_query {
    id = "cascaded"
    metric {
      metric_name = "UserMediaPurgeCompleted"
      namespace   = local.metrics_namespace
      period      = "86400"
      stat        = "Sum"
    }
  }

  metric_query {
    id = "flagged"
    metric {
      metric_name = "UserMediaUnexplainedPurge"
      namespace   = local.metrics_namespace
      period      = "86400"
      stat        = "Sum"
    }
  }

  tags = {
    Name     = "${var.project_name}-user-media-ttl-without-cascade${local.suffix}"
    Severity = "critical"
  }
}

# -----------------------------------------------------------------------------
# Alarm: a purge is overdue.
#
# purge_at passed more than 48h ago (DynamoDB's own best-effort window) and the
# row is still there. Most likely cause, and the reason this alarm exists at all:
# a PITR restore produces a NEW table with the TTL setting NOT carried over, so
# every scheduled purge silently stops. See the restore runbook.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "user_media_purge_overdue" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-user-media-purge-overdue${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "user_media rows are past their purge_at by more than 48h and still present: the TTL is disabled on the table (a PITR restore does not carry it over) or the sweeper is stalled. Runbook: infrastructure/observability/runbooks/durable-media.md#purge-overdue"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "UserMediaRowsOverduePurge"
  namespace   = local.metrics_namespace
  period      = "86400"
  statistic   = "Maximum"

  tags = {
    Name     = "${var.project_name}-user-media-purge-overdue${local.suffix}"
    Severity = "warning"
  }
}

# -----------------------------------------------------------------------------
# Alarm: artifacts are being written for a library row that does not exist.
#
# Recent orphans only (48h window, computed in the worker): a live write path
# creating artifacts for a missing library row is a bug now, whereas the
# historical drift is a known backfill residue.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "user_media_recent_orphan_artifacts" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-user-media-recent-orphan-artifacts${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "Artifacts created in the last 48h point at a media_item_id with no user_media row: either a save is writing artifacts without a library row, or a purge deleted the row and left the artifacts. Runbook: infrastructure/observability/runbooks/durable-media.md#orphan-artifacts"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "UserMediaOrphanArtifactsRecent"
  namespace   = local.metrics_namespace
  period      = "86400"
  statistic   = "Maximum"

  tags = {
    Name     = "${var.project_name}-user-media-recent-orphan-artifacts${local.suffix}"
    Severity = "warning"
  }
}

# -----------------------------------------------------------------------------
# Alarm: the reconciliation itself stopped running.
#
# Every alarm above that reads a gauge depends on this job running daily, so a
# silent watchdog would look exactly like a healthy system — which is precisely
# how the task-218 incident stayed invisible. treat_missing_data = breaching:
# "no data" is the failure being detected, not the absence of one.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "user_media_reconciliation_stopped" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-user-media-reconciliation-stopped${local.suffix}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  threshold           = "1"
  alarm_description   = "The daily user_media reconciliation has not reported for 48h. Every drift gauge and purge-overdue alarm depends on it, so they are all blind until it runs again. Runbook: infrastructure/observability/runbooks/durable-media.md#reconciliation-stopped"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "breaching"

  metric_name = "UserMediaReconciliationRuns"
  namespace   = local.metrics_namespace
  period      = "172800"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-user-media-reconciliation-stopped${local.suffix}"
    Severity = "warning"
  }
}
