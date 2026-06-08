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

# Episode idempotence table (global episode GUID reservation)
resource "aws_dynamodb_table" "episode_idempotence_v1" {
  name         = "episode_idempotence"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "episode_guid"

  attribute { name = "episode_guid" type = "S" }

  tags = {
    Name        = "episode_idempotence"
    Environment = var.environment
    Project     = var.project_name
  }
}

# User episode submissions table (per-user dedup of submissions)
resource "aws_dynamodb_table" "user_episode_submissions_v1" {
  name         = "user_episode_submissions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "episode_guid"

  attribute { name = "user_id"     type = "S" }
  attribute { name = "episode_guid" type = "S" }

  tags = {
    Name        = "user_episode_submissions"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Media artifacts table (canonical artifact records + request pointers)
resource "aws_dynamodb_table" "media_artifacts_v1" {
  name         = "media_artifacts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "artifact_id"

  attribute { name = "artifact_id"             type = "S" }
  attribute { name = "media_item_id"           type = "S" }
  attribute { name = "request_fingerprint"     type = "S" }
  attribute { name = "generation_fingerprint"  type = "S" }

  global_secondary_index {
    name            = "media-item-index"
    hash_key        = "media_item_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "request-fingerprint-index"
    hash_key        = "request_fingerprint"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "generation-fingerprint-index"
    hash_key        = "generation_fingerprint"
    projection_type = "ALL"
  }

  tags = {
    Name        = "media_artifacts"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Artifact idempotence table (generation locks for deduplication)
resource "aws_dynamodb_table" "artifact_idempotence_v1" {
  name         = "artifact_idempotence"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "generation_fingerprint"

  attribute { name = "generation_fingerprint" type = "S" }

  tags = {
    Name        = "artifact_idempotence"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Outputs
output "users_table_name" {
  value       = aws_dynamodb_table.users_v2.name
  description = "Users table name"
}

output "media_artifacts_table_name" {
  value       = aws_dynamodb_table.media_artifacts_v1.name
  description = "Media artifacts table name"
}

output "artifact_idempotence_table_name" {
  value       = aws_dynamodb_table.artifact_idempotence_v1.name
  description = "Artifact idempotence table name"
}

output "processing_jobs_table_name" {
  value       = aws_dynamodb_table.processing_jobs_v1.name
  description = "Processing jobs table name"
}


output "auth_tokens_table_name" {
  value       = aws_dynamodb_table.auth_tokens_v1.name
  description = "Auth tokens table name"
}

# Episode watchers table (pending notifications fan-out)
resource "aws_dynamodb_table" "episode_watchers_v1" {
  name         = "episode_watchers"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "episode_guid"
  range_key    = "user_id"

  attribute { name = "episode_guid" type = "S" }
  attribute { name = "user_id"      type = "S" }

  tags = {
    Name        = "episode_watchers"
    Environment = var.environment
    Project     = var.project_name
  }
}

output "episode_idempotence_table_name" {
  value       = aws_dynamodb_table.episode_idempotence_v1.name
description = "Episode idempotence table name"
}

output "episode_watchers_table_name" {
  value       = aws_dynamodb_table.episode_watchers_v1.name
  description = "Episode watchers table name"
}

# User tags table (private per-user tags for media labeling)
resource "aws_dynamodb_table" "user_tags_v1" {
  name         = "user_tags"
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
    Name        = "user_tags"
    Environment = var.environment
    Project     = var.project_name
  }
}

output "user_tags_table_name" {
  value       = aws_dynamodb_table.user_tags_v1.name
  description = "User tags table name"
}

# User folders table (hierarchical media organization)
resource "aws_dynamodb_table" "user_folders_v1" {
  name         = "user_folders"
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
    Name        = "user_folders"
    Environment = var.environment
    Project     = var.project_name
  }
}

output "user_folders_table_name" {
  value       = aws_dynamodb_table.user_folders_v1.name
  description = "User folders table name"
}

# Pricing configuration table (dynamic pricing/quota parameters, no redeploy needed)
resource "aws_dynamodb_table" "pricing_config_v1" {
  name         = "pricing_config"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "config_key"

  attribute { name = "config_key" type = "S" }

  tags = {
    Name        = "pricing_config"
    Environment = var.environment
    Project     = var.project_name
  }
}

output "pricing_config_table_name" {
  value       = aws_dynamodb_table.pricing_config_v1.name
  description = "Pricing configuration table name"
}
