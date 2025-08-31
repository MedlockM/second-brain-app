# DynamoDB table for Stripe webhook idempotency events

variable "stripe_events_table_name" {
  description = "DynamoDB table name for storing processed Stripe event IDs"
  type        = string
  default     = "stripe_events"
}

resource "aws_dynamodb_table" "stripe_events" {
  name         = var.stripe_events_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = {
    Name        = var.stripe_events_table_name
    Environment = var.environment
    Project     = var.project_name
  }
}

output "stripe_events_table_name" {
  description = "Name of the Stripe events DynamoDB table"
  value       = aws_dynamodb_table.stripe_events.name
}

