# DynamoDB table for RevenueCat webhook event idempotency
# Stores processed event IDs to prevent duplicate processing.
# TTL enabled: events automatically expire after 30 days.

resource "aws_dynamodb_table" "revenucat_events" {
  name         = "revenucat_events${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "event_id"

  attribute {
    name = "event_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name = "revenucat_events${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

output "revenucat_events_table_name" { value = aws_dynamodb_table.revenucat_events.name }
