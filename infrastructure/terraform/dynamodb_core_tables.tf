# Core DynamoDB tables aligned with application code expectations

# Users table
resource "aws_dynamodb_table" "users_v2" {
  name         = "users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "email"
    type = "S"
  }

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

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "job_status"
    type = "S"
  }

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

  # TTL FROZEN (task-239, Phase 0 of the task-218 benchmark §5.1).
  # Every library read path resolves through this table, so expiring a job also
  # destroyed the user's media entry, folder membership and tags. The TTL stays
  # disabled until the durable `user_media` record owns the library; it is
  # re-enabled in Phase 4 once nothing user-facing reads processing_jobs.
  # DO NOT flip this back to `true` before that phase.
  ttl {
    attribute_name = "expire_at"
    enabled        = false
  }

  # Enable Streams for archiving (job_archiver Lambda)
  stream_enabled   = true
  stream_view_type = "OLD_IMAGE"

  # 35-day continuous restore window (task-239). No recovery net existed before:
  # PITR was off and the deployed job-archiver Lambda is a no-op placeholder.
  point_in_time_recovery {
    enabled = true
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

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "token"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "token_type"
    type = "S"
  }

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

# Media idempotence table (global media key reservation)
resource "aws_dynamodb_table" "media_idempotence_v1" {
  name         = "media_idempotence"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "media_key"

  attribute {
    name = "media_key"
    type = "S"
  }

  tags = {
    Name        = "media_idempotence"
    Environment = var.environment
    Project     = var.project_name
  }
}

# User media submissions table (per-user dedup of submissions)
resource "aws_dynamodb_table" "user_media_submissions_v1" {
  name         = "user_media_submissions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "media_key"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "media_key"
    type = "S"
  }

  # 35-day continuous restore window (task-239) — backfill source for the
  # durable library record, must survive.
  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name        = "user_media_submissions"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Media artifacts table (canonical artifact records + request pointers)
resource "aws_dynamodb_table" "media_artifacts_v1" {
  name         = "media_artifacts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "artifact_id"

  attribute {
    name = "artifact_id"
    type = "S"
  }
  attribute {
    name = "media_item_id"
    type = "S"
  }
  attribute {
    name = "request_fingerprint"
    type = "S"
  }
  attribute {
    name = "generation_fingerprint"
    type = "S"
  }

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

  # 35-day continuous restore window (task-239) — the artifact rows are the
  # richest surviving proof of media whose job was deleted.
  point_in_time_recovery {
    enabled = true
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

  attribute {
    name = "generation_fingerprint"
    type = "S"
  }

  tags = {
    Name        = "artifact_idempotence"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Translation idempotence table (state machine for transcript translations)
# Prevents thundering herd: only the first caller reserves the translation slot,
# subsequent /raw-content polls read the state without re-enqueuing (task-203).
resource "aws_dynamodb_table" "translation_idempotence_v1" {
  name         = "translation_idempotence"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "translation_fingerprint"

  attribute {
    name = "translation_fingerprint"
    type = "S"
  }

  tags = {
    Name        = "translation_idempotence"
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

output "translation_idempotence_table_name" {
  value       = aws_dynamodb_table.translation_idempotence_v1.name
  description = "Translation idempotence table name (task-203)"
}

output "processing_jobs_table_name" {
  value       = aws_dynamodb_table.processing_jobs_v1.name
  description = "Processing jobs table name"
}


output "auth_tokens_table_name" {
  value       = aws_dynamodb_table.auth_tokens_v1.name
  description = "Auth tokens table name"
}

# Media watchers table (pending notifications fan-out)
# Renamed from legacy "episode_watchers" (episode_guid PK) to align with
# media_summarizer/utils/media_watchers.py which uses media_key as the
# canonical identity key for all media types (podcasts, docs, videos, etc.).
resource "aws_dynamodb_table" "media_watchers_v1" {
  name         = "media_watchers"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "media_key"
  range_key    = "user_id"

  attribute {
    name = "media_key"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }

  tags = {
    Name        = "media_watchers"
    Environment = var.environment
    Project     = var.project_name
  }
}

output "media_idempotence_table_name" {
  value       = aws_dynamodb_table.media_idempotence_v1.name
  description = "Media idempotence table name"
}

output "media_watchers_table_name" {
  value       = aws_dynamodb_table.media_watchers_v1.name
  description = "Media watchers table name"
}

# User tags table (private per-user tags for media labeling)
resource "aws_dynamodb_table" "user_tags_v1" {
  name         = "user_tags"
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

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  # 35-day continuous restore window (task-239) — user-owned organization data.
  point_in_time_recovery {
    enabled = true
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

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  # 35-day continuous restore window (task-239) — user-owned organization data.
  point_in_time_recovery {
    enabled = true
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

  attribute {
    name = "config_key"
    type = "S"
  }

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
