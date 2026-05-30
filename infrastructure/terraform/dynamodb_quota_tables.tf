# DynamoDB tables for quota enforcement (user usage counters)

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Monthly usage counters per user (hard caps enforcement)
resource "aws_dynamodb_table" "user_usage_monthly" {
  name         = "user_usage_monthly"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "period"

  attribute { name = "user_id" type = "S" }
  attribute { name = "period"  type = "S" }  # format: YYYY-MM

  tags = {
    Name        = "user_usage_monthly"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Daily usage counters per user (rate limits enforcement)
resource "aws_dynamodb_table" "user_usage_daily" {
  name         = "user_usage_daily"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "date"

  attribute { name = "user_id" type = "S" }
  attribute { name = "date"    type = "S" }  # format: YYYY-MM-DD

  ttl {
    attribute_name = "ttl_epoch"
    enabled        = true
  }

  tags = {
    Name        = "user_usage_daily"
    Environment = var.environment
    Project     = var.project_name
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
