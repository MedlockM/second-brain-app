# Core DynamoDB tables aligned with application code expectations

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Users table
resource "aws_dynamodb_table" "users_v2" {
  name         = "users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute { name = "id"    type = "S" }
  attribute { name = "email" type = "S" }

  global_secondary_index {
    name            = "email-index"
    hash_key        = "email"
    projection_type = "ALL"
  }

  tags = {
    Name        = "users"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Processing jobs table
resource "aws_dynamodb_table" "processing_jobs_v1" {
  name         = "processing_jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute { name = "id"         type = "S" }
  attribute { name = "user_id"    type = "S" }
  attribute { name = "job_status" type = "S" }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "job_status"
    projection_type = "ALL"
  }

  tags = {
    Name        = "processing_jobs"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Credit transactions table
resource "aws_dynamodb_table" "credit_transactions_v1" {
  name         = "credit_transactions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute { name = "id"      type = "S" }
  attribute { name = "user_id" type = "S" }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  tags = {
    Name        = "credit_transactions"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Auth tokens table used for refresh/email verification tokens
resource "aws_dynamodb_table" "auth_tokens_v1" {
  name         = "auth_tokens"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute { name = "id"         type = "S" }
  attribute { name = "token"      type = "S" }
  attribute { name = "user_id"    type = "S" }
  attribute { name = "token_type" type = "S" }

  global_secondary_index {
    name            = "token-index"
    hash_key        = "token"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "user-type-index"
    hash_key        = "user_id"
    range_key       = "token_type"
    projection_type = "ALL"
  }

  tags = {
    Name        = "auth_tokens"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Outputs
output "users_table_name" {
  value       = aws_dynamodb_table.users_v2.name
  description = "Users table name"
}

output "processing_jobs_table_name" {
  value       = aws_dynamodb_table.processing_jobs_v1.name
  description = "Processing jobs table name"
}

output "credit_transactions_table_name" {
  value       = aws_dynamodb_table.credit_transactions_v1.name
  description = "Credit transactions table name"
}

output "auth_tokens_table_name" {
  value       = aws_dynamodb_table.auth_tokens_v1.name
  description = "Auth tokens table name"
}
