# S3 Buckets for media pipeline storage.
# All 10 buckets used by workers follow the convention:
#   ${project_name}-${role}-${account_id}-${environment}
# Bucket names are injected as plain Lambda env vars (NOT via Secrets Manager).

resource "aws_s3_bucket" "audio" {
  bucket = "${var.project_name}-audio-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name        = "${var.project_name}-audio"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket" "transcripts" {
  bucket = "${var.project_name}-transcripts-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name        = "${var.project_name}-transcripts"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket" "summaries" {
  bucket = "${var.project_name}-summaries-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name        = "${var.project_name}-summaries"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket" "summary_short" {
  bucket = "${var.project_name}-summary-short-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name        = "${var.project_name}-summary-short"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket" "summary_detailed" {
  bucket = "${var.project_name}-summary-detailed-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name        = "${var.project_name}-summary-detailed"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket" "notes" {
  bucket = "${var.project_name}-notes-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name        = "${var.project_name}-notes"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket" "flashcards" {
  bucket = "${var.project_name}-flashcards-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name        = "${var.project_name}-flashcards"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket" "quiz" {
  bucket = "${var.project_name}-quiz-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name        = "${var.project_name}-quiz"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket" "documents" {
  bucket = "${var.project_name}-documents-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name        = "${var.project_name}-documents"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Outputs

output "audio_bucket_name" {
  description = "Name of the S3 bucket for audio files"
  value       = aws_s3_bucket.audio.bucket
}

output "transcripts_bucket_name" {
  description = "Name of the S3 bucket for transcripts"
  value       = aws_s3_bucket.transcripts.bucket
}

output "summaries_bucket_name" {
  description = "Name of the S3 bucket for summaries"
  value       = aws_s3_bucket.summaries.bucket
}

output "summary_short_bucket_name" {
  description = "Name of the S3 bucket for short summaries"
  value       = aws_s3_bucket.summary_short.bucket
}

output "summary_detailed_bucket_name" {
  description = "Name of the S3 bucket for detailed summaries"
  value       = aws_s3_bucket.summary_detailed.bucket
}

output "notes_bucket_name" {
  description = "Name of the S3 bucket for notes"
  value       = aws_s3_bucket.notes.bucket
}

output "flashcards_bucket_name" {
  description = "Name of the S3 bucket for flashcards"
  value       = aws_s3_bucket.flashcards.bucket
}

output "quiz_bucket_name" {
  description = "Name of the S3 bucket for quizzes"
  value       = aws_s3_bucket.quiz.bucket
}

output "documents_bucket_name" {
  description = "Name of the S3 bucket for documents"
  value       = aws_s3_bucket.documents.bucket
}

output "archives_bucket_name" {
  description = "Name of the S3 bucket for archives"
  value       = aws_s3_bucket.archives.bucket
}
