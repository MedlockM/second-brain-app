# DynamoDB tables for quota enforcement (user usage counters)

# Monthly usage counters per user (hard caps enforcement)
resource "aws_dynamodb_table" "user_usage_monthly" {
  name         = "user_usage_monthly${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "period"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "period"
    type = "S" # format: YYYY-MM
  }

  tags = {
    Name = "user_usage_monthly${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# Daily usage counters per user (rate limits enforcement)
resource "aws_dynamodb_table" "user_usage_daily" {
  name         = "user_usage_daily${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "date"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "date"
    type = "S" # format: YYYY-MM-DD
  }

  ttl {
    attribute_name = "ttl_epoch"
    enabled        = true
  }

  tags = {
    Name = "user_usage_daily${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# Outputs
output "user_usage_monthly_table_name" {
  value       = aws_dynamodb_table.user_usage_monthly.name
  description = "User usage monthly counters table name"
}

output "user_usage_daily_table_name" {
  value       = aws_dynamodb_table.user_usage_daily.name
  description = "User usage daily counters table name"
}
