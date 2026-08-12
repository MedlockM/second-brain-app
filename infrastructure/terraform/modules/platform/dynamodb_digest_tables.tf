# DynamoDB tables for the in-app digest feature (task-56)

# User digests table: stores assembled daily/weekly digests
resource "aws_dynamodb_table" "user_digests_v1" {
  name         = "user_digests${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "digest_key"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "digest_key"
    type = "S"
  }

  tags = {
    Name = "user_digests${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# User digest settings table: stores per-user digest preferences
resource "aws_dynamodb_table" "user_digest_settings_v1" {
  name         = "user_digest_settings${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  tags = {
    Name = "user_digest_settings${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
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
