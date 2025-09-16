# DynamoDB tables for minutes-based monetization (subscriptions, minute buckets, minute usage, follows)

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Subscriptions table
resource "aws_dynamodb_table" "subscriptions" {
  name         = "subscriptions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute { name = "id"                     type = "S" }
  attribute { name = "user_id"                type = "S" }
  attribute { name = "stripe_subscription_id" type = "S" }

  # GSI: user-index
  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  # GSI: stripe-index
  global_secondary_index {
    name            = "stripe-index"
    hash_key        = "stripe_subscription_id"
    projection_type = "ALL"
  }

  tags = {
    Name        = "subscriptions"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Minute buckets table
resource "aws_dynamodb_table" "minute_buckets" {
  name         = "minute_buckets"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute { name = "id"        type = "S" }
  attribute { name = "user_id"   type = "S" }
  attribute { name = "expires_at" type = "S" }

  # GSI: user-index
  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  # GSI: expiry-index (TTL queries)
  global_secondary_index {
    name            = "expiry-index"
    hash_key        = "expires_at"
    projection_type = "ALL"
  }

  tags = {
    Name        = "minute_buckets"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Minute usage (holds/finalize/release)
resource "aws_dynamodb_table" "minute_usage" {
  name         = "minute_usage"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute { name = "id"      type = "S" }
  attribute { name = "user_id" type = "S" }
  attribute { name = "job_id"  type = "S" }

  # GSI: user-index
  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  # GSI: job-index
  global_secondary_index {
    name            = "job-index"
    hash_key        = "job_id"
    projection_type = "ALL"
  }

  tags = {
    Name        = "minute_usage"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Follows (forecast/reservations)
resource "aws_dynamodb_table" "follows" {
  name         = "follows"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "feed_id"

  attribute { name = "user_id" type = "S" }
  attribute { name = "feed_id" type = "S" }

  tags = {
    Name        = "follows"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Outputs
output "subscriptions_table_name" { value = aws_dynamodb_table.subscriptions.name }
output "minute_buckets_table_name" { value = aws_dynamodb_table.minute_buckets.name }
output "minute_usage_table_name" { value = aws_dynamodb_table.minute_usage.name }
output "follows_table_name" { value = aws_dynamodb_table.follows.name }

