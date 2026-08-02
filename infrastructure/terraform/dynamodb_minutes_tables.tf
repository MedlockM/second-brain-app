# DynamoDB tables for subscriptions and feed follows/forecasts

# Subscriptions table
resource "aws_dynamodb_table" "subscriptions" {
  name         = "subscriptions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }

  # GSI: user-index
  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  tags = {
    Name        = "subscriptions"
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

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "feed_id"
    type = "S"
  }

  tags = {
    Name        = "follows"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Feed forecasts (shared cache): PK (feed_id, month_key)
resource "aws_dynamodb_table" "feed_forecasts" {
  name         = "feed_forecasts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "feed_id"
  range_key    = "month_key"

  attribute {
    name = "feed_id"
    type = "S"
  }
  attribute {
    name = "month_key"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "feed_forecasts"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Outputs
output "subscriptions_table_name" { value = aws_dynamodb_table.subscriptions.name }
output "follows_table_name" { value = aws_dynamodb_table.follows.name }
output "feed_forecasts_table_name" { value = aws_dynamodb_table.feed_forecasts.name }
