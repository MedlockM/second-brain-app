# =============================================================================
# RevenueCat webhook observability (task-262, task-334)
#
# Two ways a subscription event can be received and still leave the row wrong,
# both emitted at ERROR by media_summarizer/api/endpoints/revenucat_webhook.py
# and alarmed here: the tier no entitlement resolves (task-262), and the event
# describing a subscription none of the user's rows match (task-334).
#
# Until task-262 the webhook resolved the subscription tier from a hardcoded map
# of store product IDs, and a product the map did not know was dropped at
# WARNING with no metric behind it: the user was charged, no subscription row was
# written, and nothing surfaced anywhere. Tier resolution now reads the event's
# entitlement identifiers, and the residual failure mode -- a store product that
# reached a store without being attached to one of the tier entitlements -- is
# emitted at ERROR as revenucat.tier_unresolved and alarmed here.
#
# Same shape as durable_media_alerts.tf: a metric filter over the structured JSON
# log events (the application never calls put_metric_data), an outcome metric,
# and an alarm gated on var.enable_alarms so dev stays at ~$0.23/day. The webhook
# only ever runs in the API Lambda, so the API log group is the only source.
#
# Fixing an occurrence is a dashboard operation, no deploy: attach the product
# named by revenucat_product_id to its tier entitlement in RevenueCat project
# proj879a771a. Layout reference: docs/REVENUECAT_ENTITLEMENTS.md
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "revenucat_tier_unresolved" {
  name           = "revenucat-tier-unresolved${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.event = \"revenucat.tier_unresolved\" }"

  metric_transformation {
    name          = "RevenueCatTierUnresolved"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

# Threshold 0, not a rate. A subscription event whose tier cannot be resolved is
# a payment the backend ignores; there is no acceptable background level of it.
resource "aws_cloudwatch_metric_alarm" "revenucat_tier_unresolved" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-revenucat-tier-unresolved${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "A RevenueCat subscription event carried no known tier entitlement: the purchase or product change was dropped and the user is paying for access they do not have. Attach the product in the ERROR log's revenucat_product_id field to its tier entitlement in RevenueCat project proj879a771a. See docs/REVENUECAT_ENTITLEMENTS.md"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "RevenueCatTierUnresolved"
  namespace   = local.metrics_namespace
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-revenucat-tier-unresolved${local.suffix}"
    Severity = "critical"
  }
}

# -----------------------------------------------------------------------------
# An event that matches no subscription row of its user (task-334)
#
# Until task-334 every handler acted on the user's *first* row, so this case
# could not be detected: a renewal, a cancellation or an expiry always found
# something to write to, even a row belonging to the other store. Handlers now
# match the row on the store's subscription identifier or on the (platform,
# product) pair, and a miss is a real anomaly — the store is reporting on a
# subscription the backend never recorded, or recorded under another product.
#
# Diagnosis is entirely in the log line: revenucat_event_type,
# revenucat_product_id, revenucat_store, app_user_id and the number of rows the
# user has. Zero rows means the INITIAL_PURCHASE never landed (look for a
# tier_unresolved before it); rows present means the product on them differs from
# the one the store is talking about.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_metric_filter" "revenucat_subscription_unmatched" {
  name           = "revenucat-subscription-unmatched${local.suffix}"
  log_group_name = aws_cloudwatch_log_group.lambda_api.name
  pattern        = "{ $.event = \"revenucat.subscription_unmatched\" }"

  metric_transformation {
    name          = "RevenueCatSubscriptionUnmatched"
    namespace     = local.metrics_namespace
    value         = "1"
    default_value = "0"
  }
}

# Threshold 0, same reasoning as above: a subscription event the backend cannot
# attach to a row is a divergence between what the store bills and what the app
# grants, and there is no acceptable background level of it.
resource "aws_cloudwatch_metric_alarm" "revenucat_subscription_unmatched" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-revenucat-subscription-unmatched${local.suffix}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "0"
  alarm_description   = "A RevenueCat subscription event matched no subscription row of its user: the renewal, cancellation or expiry it reports was not applied anywhere. The ERROR log carries revenucat_event_type, revenucat_product_id, revenucat_store, app_user_id and the user's row count. See docs/REVENUECAT_ENTITLEMENTS.md"
  alarm_actions       = [aws_sns_topic.pipeline_alerts[0].arn]
  ok_actions          = [aws_sns_topic.pipeline_alerts[0].arn]
  treat_missing_data  = "notBreaching"

  metric_name = "RevenueCatSubscriptionUnmatched"
  namespace   = local.metrics_namespace
  period      = "300"
  statistic   = "Sum"

  tags = {
    Name     = "${var.project_name}-revenucat-subscription-unmatched${local.suffix}"
    Severity = "critical"
  }
}
