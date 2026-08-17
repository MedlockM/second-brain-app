# Core DynamoDB tables aligned with application code expectations

# Users table
resource "aws_dynamodb_table" "users_v2" {
  name         = "users${local.suffix}"
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
    Name = "users${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# Processing jobs table
resource "aws_dynamodb_table" "processing_jobs_v1" {
  name         = "processing_jobs${local.suffix}"
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

  # TTL RE-ENABLED (task-242, Phase 4 of the task-218 benchmark §5.5).
  # Phase 3 (task-220) has migrated all library reads to the durable user_media table,
  # so processing_jobs can now safely expire. The TTL is re-enabled with a configurable
  # window (30-90 days, default 90) to preserve job records for debugging while removing
  # stale records. The real job_archiver now writes deletions to S3.
  # The TTL attribute (expire_at) is set by job workers on every status transition:
  # media_summarizer/core/models/processing_job.py:250 and :361.
  ttl {
    attribute_name = "expire_at"
    enabled        = true
  }

  # TTL window is parameterized per the owner's decision (task-242 AC #3 pending owner choice)
  # Default: 90 days (conservative, prioritizes debugging trail over cleanup aggressiveness)
  # To override: terraform apply -var processing_jobs_ttl_days=60 (or 30)

  # Enable Streams for archiving (job_archiver Lambda)
  stream_enabled   = true
  stream_view_type = "OLD_IMAGE"

  tags = {
    Name = "processing_jobs${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}


# Auth tokens table used for refresh/email verification tokens
resource "aws_dynamodb_table" "auth_tokens_v1" {
  name         = "auth_tokens${local.suffix}"
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
    Name = "auth_tokens${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# Media idempotence table (global media key reservation)
resource "aws_dynamodb_table" "media_idempotence_v1" {
  name         = "media_idempotence${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "media_key"

  attribute {
    name = "media_key"
    type = "S"
  }

  tags = {
    Name = "media_idempotence${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# user_media_submissions is gone (task-220). Its rows only ever held per-user
# (user_id, media_key, job_id) pointers, half of them dangling; the durable
# user_media table now carries that ownership fact properly, and the task-241
# backfill already consumed the last of them.
#
# Dropped from state rather than destroyed: the table was created with
# deletion_protection_enabled and prevent_destroy, so a plain resource removal
# would fail the plan. This leaves the physical table untouched in AWS for the
# owner to delete by hand, and stops Terraform from managing it.
removed {
  from = aws_dynamodb_table.user_media_submissions_v1

  lifecycle {
    destroy = false
  }
}

# AI artifacts table — an append-only history, one entry per generation
# (task-269/270). One index replaced three: the old GSIs were hash-only, so they
# could not sort, and a history has to come back newest-first. `scope-index`
# carries `created_at` as its range key, which gives that ordering from DynamoDB
# with ScanIndexForward=false — no application sort, no broken pagination.
#
# The projection is INCLUDE, not ALL, on purpose: the listing renders exactly
# these attributes, so a page costs one query with no read of the base table and
# no S3 access. `sources` (the snapshot, up to ~5 kB at the 25-source ceiling) is
# deliberately left out — it is only needed when one entry is opened, and
# projecting it would double the write cost of the largest attribute.
#
# The index is sparse: rows written before this change carry no `scope_key`, so
# they never enter it and become invisible to every read path without a purge
# script.
resource "aws_dynamodb_table" "media_artifacts_v1" {
  name         = "media_artifacts${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "artifact_id"

  attribute {
    name = "artifact_id"
    type = "S"
  }
  attribute {
    name = "scope_key"
    type = "S"
  }
  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "scope-index"
    hash_key        = "scope_key"
    range_key       = "created_at"
    projection_type = "INCLUDE"
    non_key_attributes = [
      "artifact_type",
      "status",
      "title",
      "source_count",
      "completed_at",
      "error_code",
    ]
  }

  tags = {
    Name = "media_artifacts${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# The artifact_idempotence table is gone (task-270). Its only job was to stop a
# second identical generation — the exact opposite of what an append-only history
# needs. Short-window deduplication is now the deterministic `artifact_id` plus a
# conditional write, so no auxiliary table is involved.

# Translation idempotence table (state machine for transcript translations)
# Prevents thundering herd: only the first caller reserves the translation slot,
# subsequent /raw-content polls read the state without re-enqueuing (task-203).
resource "aws_dynamodb_table" "translation_idempotence_v1" {
  name         = "translation_idempotence${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "translation_fingerprint"

  attribute {
    name = "translation_fingerprint"
    type = "S"
  }

  tags = {
    Name = "translation_idempotence${local.suffix}"
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
output "users_table_name" {
  value       = aws_dynamodb_table.users_v2.name
  description = "Users table name"
}

output "media_artifacts_table_name" {
  value       = aws_dynamodb_table.media_artifacts_v1.name
  description = "Media artifacts table name"
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
  name         = "media_watchers${local.suffix}"
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
    Name = "media_watchers${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
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
  name         = "user_tags${local.suffix}"
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

  tags = {
    Name = "user_tags${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

output "user_tags_table_name" {
  value       = aws_dynamodb_table.user_tags_v1.name
  description = "User tags table name"
}

# User folders table (hierarchical media organization)
resource "aws_dynamodb_table" "user_folders_v1" {
  name         = "user_folders${local.suffix}"
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

  tags = {
    Name = "user_folders${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

output "user_folders_table_name" {
  value       = aws_dynamodb_table.user_folders_v1.name
  description = "User folders table name"
}

# Pricing configuration table (dynamic pricing/quota parameters, no redeploy needed)
resource "aws_dynamodb_table" "pricing_config_v1" {
  name         = "pricing_config${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "config_key"

  attribute {
    name = "config_key"
    type = "S"
  }

  tags = {
    Name = "pricing_config${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

output "pricing_config_table_name" {
  value       = aws_dynamodb_table.pricing_config_v1.name
  description = "Pricing configuration table name"
}
