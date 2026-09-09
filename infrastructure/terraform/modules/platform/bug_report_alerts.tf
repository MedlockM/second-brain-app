# =============================================================================
# Bug Report Observability (task-382)
#
# A user-submitted bug report is always worth attention. This module watches for
# the structured log event emitted by the API when a report arrives and routes
# the alert to the pipeline SNS topic.
#
# The event carries report_id, user_id, source_platform, source_app_version, and
# when present, media_item_id and error_code (introduced in task-381). Threshold 0:
# one report, one mail. There is no background level of bug reports that is
# acceptable to ignore.
#
# Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#bug-reports
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "bug_report_created" {
  name           = "bug-report-created${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.event = \"bug_report.created\" }"

  metric_transformation {
    name          = "BugReportCreated"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

# Threshold 0: one report is always actionable and worth escalating immediately.
resource "aws_cloudwatch_metric_alarm" "bug_report_created" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-bug-report-created${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "A new bug report was submitted. The event carries report_id, user_id, source_platform, source_app_version, and when present media_item_id and error_code. Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#bug-reports"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "BugReportCreated"
  namespace   = local.metrics_namespace
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-bug-report-created${local.suffix}"
    Severity = "critical"
  }
}