# S3 Buckets for media pipeline storage.
# Every bucket used by the workers follows the convention:
#   ${project_name}-${role}-${account_id}-${environment}
# Bucket names are injected as plain Lambda env vars (NOT via Secrets Manager).

resource "aws_s3_bucket" "audio" {
  bucket = "${var.project_name}-audio-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-audio${local.suffix}"
  }

  # Buckets hold the only copy of every transcript, summary and uploaded
  # document. prevent_destroy errors at PLAN time, so "I destroyed the
  # wrong environment" becomes "the plan refused to run".
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "transcripts" {
  bucket = "${var.project_name}-transcripts-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-transcripts${local.suffix}"
  }

  # Buckets hold the only copy of every transcript, summary and uploaded
  # document. prevent_destroy errors at PLAN time, so "I destroyed the
  # wrong environment" becomes "the plan refused to run".
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "summaries" {
  bucket = "${var.project_name}-summaries-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-summaries${local.suffix}"
  }

  # Buckets hold the only copy of every transcript, summary and uploaded
  # document. prevent_destroy errors at PLAN time, so "I destroyed the
  # wrong environment" becomes "the plan refused to run".
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "summary_short" {
  bucket = "${var.project_name}-summary-short-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-summary-short${local.suffix}"
  }

  # Buckets hold the only copy of every transcript, summary and uploaded
  # document. prevent_destroy errors at PLAN time, so "I destroyed the
  # wrong environment" becomes "the plan refused to run".
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "summary_detailed" {
  bucket = "${var.project_name}-summary-detailed-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-summary-detailed${local.suffix}"
  }

  # Buckets hold the only copy of every transcript, summary and uploaded
  # document. prevent_destroy errors at PLAN time, so "I destroyed the
  # wrong environment" becomes "the plan refused to run".
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "notes" {
  bucket = "${var.project_name}-notes-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-notes${local.suffix}"
  }

  # Buckets hold the only copy of every transcript, summary and uploaded
  # document. prevent_destroy errors at PLAN time, so "I destroyed the
  # wrong environment" becomes "the plan refused to run".
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "flashcards" {
  bucket = "${var.project_name}-flashcards-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-flashcards${local.suffix}"
  }

  # Buckets hold the only copy of every transcript, summary and uploaded
  # document. prevent_destroy errors at PLAN time, so "I destroyed the
  # wrong environment" becomes "the plan refused to run".
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "quiz" {
  bucket = "${var.project_name}-quiz-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-quiz${local.suffix}"
  }

  # Buckets hold the only copy of every transcript, summary and uploaded
  # document. prevent_destroy errors at PLAN time, so "I destroyed the
  # wrong environment" becomes "the plan refused to run".
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "review_blurb" {
  bucket = "${var.project_name}-review-blurb-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-review-blurb${local.suffix}"
  }

  # Internal artifact type (task-323), stored in its own bucket like the five
  # requestable ones: the artifact layout is one bucket per type, and sharing one
  # would make a per-type lifecycle rule or a per-type restore impossible.
  #
  # Buckets hold the only copy of every transcript, summary and uploaded
  # document. prevent_destroy errors at PLAN time, so "I destroyed the
  # wrong environment" becomes "the plan refused to run".
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "documents" {
  bucket = "${var.project_name}-documents-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-documents${local.suffix}"
  }

  # Buckets hold the only copy of every transcript, summary and uploaded
  # document. prevent_destroy errors at PLAN time, so "I destroyed the
  # wrong environment" becomes "the plan refused to run".
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "covers" {
  bucket = "${var.project_name}-covers-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name = "${var.project_name}-covers${local.suffix}"
  }

  # Re-hosted cover thumbnails for the sources whose CDN URL is signed and
  # expires (Instagram, TikTok) or private (camera and gallery photos) --
  # task-302 §5. Unlike the other buckets this one holds no original content:
  # every object is a 640x360 derivative that a re-ingestion would rebuild.
  # prevent_destroy is kept anyway, so a wrong -target still fails at plan time.
  lifecycle {
    prevent_destroy = true
  }
}

# Covers are served through presigned URLs (task-302 §5.5): the bucket stays
# private, and the user's own photos are never reachable without a signature.
resource "aws_s3_bucket_public_access_block" "covers" {
  bucket = aws_s3_bucket.covers.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
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

output "review_blurb_bucket_name" {
  description = "Name of the S3 bucket for review blurbs (internal artifact type)"
  value       = aws_s3_bucket.review_blurb.bucket
}

output "documents_bucket_name" {
  description = "Name of the S3 bucket for documents"
  value       = aws_s3_bucket.documents.bucket
}

output "archives_bucket_name" {
  description = "Name of the S3 bucket for archives"
  value       = aws_s3_bucket.archives.bucket
}

output "covers_bucket_name" {
  description = "Name of the S3 bucket for re-hosted media cover thumbnails"
  value       = aws_s3_bucket.covers.bucket
}
