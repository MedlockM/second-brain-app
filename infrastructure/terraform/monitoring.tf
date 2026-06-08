# =============================================================================
# Monitoring Configuration for Media Summarizer (Lambda Architecture)
# Aligned with V1 Phase 8 (task-114). ECS references removed.
#
# This file provides:
# - CloudWatch Log Groups for Lambda functions
# - Basic job failure metric filters (legacy, retained for continuity)
# - The ops_alerts SNS topic (retained for backward compatibility)
#
# The primary alerting is now in pipeline_alerts.tf (pipeline_alerts topic).
# =============================================================================

# SNS Topic for Ops Alerts (legacy -- retained for backward compatibility)
resource "aws_sns_topic" "ops_alerts" {
  count = var.enable_alarms ? 1 : 0
  name  = "${var.project_name}-ops-alerts"

  tags = {
    Name        = "${var.project_name}-ops-alerts"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sns_topic_subscription" "ops_email" {
  count     = var.enable_alarms ? 1 : 0
  topic_arn = aws_sns_topic.ops_alerts[0].arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# -----------------------------------------------------------------------------
# CloudWatch Log Groups for Lambda Workers
# These log groups are created automatically by AWS Lambda on first invocation,
# but we declare them here to control retention and enable metric filters.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "lambda_workers" {
  for_each = toset(local.lambda_workers)

  name              = "/aws/lambda/${var.project_name}-${each.key}"
  retention_in_days = 14

  tags = {
    Name        = "${var.project_name}-${each.key}-logs"
    Environment = var.environment
    Project     = var.project_name
  }
}
