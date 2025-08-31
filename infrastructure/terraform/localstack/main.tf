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
  ]
}

output "sqs_queues" {
  value = [
    aws_sqs_queue.audio_download.name,
    aws_sqs_queue.transcription.name,
    aws_sqs_queue.summarization.name,
    aws_sqs_queue.email_notification.name,
  ]
}

output "s3_buckets" {
  value = [
    aws_s3_bucket.audio.id,
    aws_s3_bucket.transcripts.id,
    aws_s3_bucket.summaries.id,
  ]
}

