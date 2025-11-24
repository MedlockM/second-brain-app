terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "localstack_endpoint" {
  description = "Base endpoint for LocalStack services"
  type        = string
  default     = "http://localhost:4566"
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  s3_use_path_style           = true

  endpoints {
    dynamodb = var.localstack_endpoint
    s3       = var.localstack_endpoint
    sqs      = var.localstack_endpoint
    ses      = var.localstack_endpoint
  }
}

locals {
  project     = "media-summarizer"
  environment = "local"
}

# -------------------- DynamoDB Tables --------------------
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
  attribute {
    name = "status"
    type = "S"
  }
  attribute {
    name = "stripe_subscription_id"
    type = "S"
  }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "stripe-index"
    hash_key        = "stripe_subscription_id"
    projection_type = "ALL"
  }

  tags = { Name = "subscriptions", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "minute_buckets" {
  name         = "minute_buckets"
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
    name = "expires_at"
    type = "S"
  }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "expiry-index"
    hash_key        = "expires_at"
    projection_type = "ALL"
  }

  tags = { Name = "minute_buckets", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "minute_usage" {
  name         = "minute_usage"
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
    name = "job_id"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "job-index"
    hash_key        = "job_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    projection_type = "ALL"
  }

  tags = { Name = "minute_usage", Environment = local.environment, Project = local.project }
}

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

  tags = { Name = "follows", Environment = local.environment, Project = local.project }
}

# Episode watchers table
resource "aws_dynamodb_table" "episode_watchers" {
  name         = "episode_watchers"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "episode_guid"
  range_key    = "user_id"

  attribute {
    name = "episode_guid"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }

  tags = { Name = "episode_watchers", Environment = local.environment, Project = local.project }
}

# Spotify playlist follows
resource "aws_dynamodb_table" "spotify_playlist_follows" {
  name         = "spotify_playlist_follows"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "playlist_id"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "playlist_id"
    type = "S"
  }

  tags = { Name = "spotify_playlist_follows", Environment = local.environment, Project = local.project }
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

  tags = { Name = "feed_forecasts", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "users" {
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

  tags = { Name = "users", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "processing_jobs" {
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

  tags = { Name = "processing_jobs", Environment = local.environment, Project = local.project }
}

# Episode idempotence: per-user, per-episode GUID reservation table
resource "aws_dynamodb_table" "episode_idempotence" {
  name         = "episode_idempotence"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "episode_guid"

  attribute {
    name = "episode_guid"
    type = "S"
  }

  tags = { Name = "episode_idempotence", Environment = local.environment, Project = local.project }
}

# User episode submissions table: prevent per-user re-submissions
resource "aws_dynamodb_table" "user_episode_submissions" {
  name         = "user_episode_submissions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "episode_guid"

  attribute {
    name = "user_id"
    type  = "S"
  }
  attribute {
    name = "episode_guid"
    type  = "S"
  }

  tags = { Name = "user_episode_submissions", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "credit_transactions" {
  name         = "credit_transactions"
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

  tags = { Name = "credit_transactions", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "auth_tokens" {
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

  tags = { Name = "auth_tokens", Environment = local.environment, Project = local.project }
}

resource "aws_dynamodb_table" "stripe_events" {
  name         = "stripe_events"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = { Name = "stripe_events", Environment = local.environment, Project = local.project }
}

# -------------------- S3 Buckets --------------------
resource "aws_s3_bucket" "audio" {
  bucket        = "media-summarizer-audio"
  force_destroy = true
  tags          = { Name = "audio", Environment = local.environment, Project = local.project }
}

resource "aws_s3_bucket" "transcripts" {
  bucket        = "media-summarizer-transcriptions"
  force_destroy = true
  tags          = { Name = "transcripts", Environment = local.environment, Project = local.project }
}

resource "aws_s3_bucket" "summaries" {
  bucket        = "media-summarizer-summaries"
  force_destroy = true
  tags          = { Name = "summaries", Environment = local.environment, Project = local.project }
}

resource "aws_s3_bucket" "quizzes" {
  bucket        = "media-summarizer-quizzes"
  force_destroy = true
  tags          = { Name = "quizzes", Environment = local.environment, Project = local.project }
}

# -------------------- SQS Queues (+ DLQs) --------------------
resource "aws_sqs_queue" "audio_download_dlq" {
  name = "audio-download-dlq"
}

resource "aws_sqs_queue" "audio_download" {
  name = "audio-download-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.audio_download_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "transcription_dlq" { name = "transcription-dlq" }
resource "aws_sqs_queue" "transcription" {
  name = "transcription-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.transcription_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "summarization_dlq" { name = "summarization-dlq" }
resource "aws_sqs_queue" "summarization" {
  name = "summarization-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.summarization_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue" "email_notification_dlq" { name = "email-notification-dlq" }
resource "aws_sqs_queue" "email_notification" {
  name = "email-notification-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.email_notification_dlq.arn
    maxReceiveCount     = 3
  })
}

# Quiz generation queue
resource "aws_sqs_queue" "quiz_dlq" { name = "quiz-dlq" }
resource "aws_sqs_queue" "quiz" {
  name = "quiz-queue"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.quiz_dlq.arn
    maxReceiveCount     = 3
  })
}

# Episode completed events (fan-out to watchers)
resource "aws_sqs_queue" "episode_completed_dlq" { name = "episode-completed-dlq" }
resource "aws_sqs_queue" "episode_completed" {
  name = "episode-completed-events"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.episode_completed_dlq.arn
    maxReceiveCount     = 3
  })
}

# -------------------- SES Email Identities --------------------
resource "aws_ses_email_identity" "noreply_prod" {
  email = "noreply@media-summarizer.com"
}

resource "aws_ses_email_identity" "noreply_example" {
  email = "noreply@example.com"
}

resource "aws_ses_email_identity" "test_example" {
  email = "test@example.com"
}

# -------------------- Outputs --------------------
output "dynamodb_tables" {
  value = [
    aws_dynamodb_table.users.name,
    aws_dynamodb_table.processing_jobs.name,
    aws_dynamodb_table.credit_transactions.name,
    aws_dynamodb_table.auth_tokens.name,
    aws_dynamodb_table.stripe_events.name,
    aws_dynamodb_table.subscriptions.name,
    aws_dynamodb_table.minute_buckets.name,
    aws_dynamodb_table.minute_usage.name,
    aws_dynamodb_table.follows.name,
    aws_dynamodb_table.spotify_playlist_follows.name,
    aws_dynamodb_table.feed_forecasts.name,
    aws_dynamodb_table.episode_idempotence.name,
    aws_dynamodb_table.episode_watchers.name,
    aws_dynamodb_table.user_episode_submissions.name,
  ]
}

output "sqs_queues" {
  value = [
    aws_sqs_queue.audio_download.name,
    aws_sqs_queue.transcription.name,
    aws_sqs_queue.summarization.name,
    aws_sqs_queue.email_notification.name,
    aws_sqs_queue.quiz.name,
    aws_sqs_queue.episode_completed.name,
  ]
}

output "s3_buckets" {
  value = [
    aws_s3_bucket.audio.id,
    aws_s3_bucket.transcripts.id,
    aws_s3_bucket.summaries.id,
    aws_s3_bucket.quizzes.id,
  ]
}

