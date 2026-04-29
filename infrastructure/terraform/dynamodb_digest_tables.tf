# DynamoDB tables for the in-app digest feature (task-56)

# User digests table: stores assembled daily/weekly digests
resource "aws_dynamodb_table" "user_digests_v1" {
  name         = "user_digests"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "digest_key"

  attribute { name = "user_id"    type = "S" }
  attribute { name = "digest_key" type = "S" }

  tags = {
    Name        = "user_digests"
    Environment = var.environment
    Project     = var.project_name
  }
}

# User digest settings table: stores per-user digest preferences
resource "aws_dynamodb_table" "user_digest_settings_v1" {
  name         = "user_digest_settings"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"

  attribute { name = "user_id" type = "S" }

  tags = {
    Name        = "user_digest_settings"
    Environment = var.environment
    Project     = var.project_name
  }
}

output "user_digests_table_name" {
  value       = aws_dynamodb_table.user_digests_v1.name
  description = "User digests table name"
}

output "user_digest_settings_table_name" {
  value       = aws_dynamodb_table.user_digest_settings_v1.name
  description = "User digest settings table name"
}
