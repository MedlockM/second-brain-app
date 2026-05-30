# S3 Buckets for media pipeline storage.
# Extracted from the former scaling.tf.

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
