# SQS Queues and Dead Letter Queues for all pipeline workers.
# Extracted from the former scaling.tf and expanded for all V1 workers.

# =============================================================================
# Podcastindex Resolution
# =============================================================================

resource "aws_sqs_queue" "rss_resolution" {
  name                       = "podcastindex-resolution-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600 # 14 days

  tags = {
    Name        = "podcastindex-resolution-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Article Extraction
# =============================================================================

resource "aws_sqs_queue" "article_extraction_dlq" {
  name = "article-extraction-dlq"

  tags = {
    Name        = "article-extraction-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "article_extraction" {
  name                       = "article-extraction-queue"
  visibility_timeout_seconds = 360
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.article_extraction_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "article-extraction-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# X Ingestion
# =============================================================================

resource "aws_sqs_queue" "x_ingestion_dlq" {
  name = "x-ingestion-dlq"

  tags = {
    Name        = "x-ingestion-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "x_ingestion" {
  name                       = "x-ingestion-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.x_ingestion_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "x-ingestion-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# YouTube Ingestion
# =============================================================================

resource "aws_sqs_queue" "youtube_ingestion_dlq" {
  name = "youtube-ingestion-dlq"

  tags = {
    Name        = "youtube-ingestion-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "youtube_ingestion" {
  name                       = "youtube-ingestion-queue"
  visibility_timeout_seconds = 720
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.youtube_ingestion_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "youtube-ingestion-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Instagram Ingestion
# =============================================================================

resource "aws_sqs_queue" "instagram_ingestion_dlq" {
  name = "instagram-ingestion-dlq"

  tags = {
    Name        = "instagram-ingestion-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "instagram_ingestion" {
  name                       = "instagram-ingestion-queue"
  visibility_timeout_seconds = 720
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.instagram_ingestion_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "instagram-ingestion-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# TikTok Ingestion
# =============================================================================

resource "aws_sqs_queue" "tiktok_ingestion_dlq" {
  name = "tiktok-ingestion-dlq"

  tags = {
    Name        = "tiktok-ingestion-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "tiktok_ingestion" {
  name                       = "tiktok-ingestion-queue"
  visibility_timeout_seconds = 720
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.tiktok_ingestion_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "tiktok-ingestion-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Deepgram Transcription
# =============================================================================

resource "aws_sqs_queue" "deepgram_transcription_dlq" {
  name = "deepgram-transcription-dlq"

  tags = {
    Name        = "deepgram-transcription-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "deepgram_transcription" {
  name                       = "deepgram-transcription-queue"
  visibility_timeout_seconds = 3600
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.deepgram_transcription_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "deepgram-transcription-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Document Parsing
# =============================================================================

resource "aws_sqs_queue" "document_parsing_dlq" {
  name = "document-parsing-dlq"

  tags = {
    Name        = "document-parsing-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "document_parsing" {
  name                       = "document-parsing-queue"
  visibility_timeout_seconds = 3600
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.document_parsing_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "document-parsing-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Search Indexing
# =============================================================================

resource "aws_sqs_queue" "search_indexing_dlq" {
  name = "search-indexing-dlq"

  tags = {
    Name        = "search-indexing-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "search_indexing" {
  name                       = "search-indexing-queue"
  visibility_timeout_seconds = 360
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.search_indexing_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "search-indexing-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# RSS Feed Poll
# =============================================================================

resource "aws_sqs_queue" "rss_feed_poll_dlq" {
  name = "rss-feed-poll-dlq"

  tags = {
    Name        = "rss-feed-poll-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "rss_feed_poll" {
  name                       = "rss-feed-poll-queue"
  visibility_timeout_seconds = 720
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.rss_feed_poll_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "rss-feed-poll-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Media Completed Events (consumed by media_completed worker)
# =============================================================================

resource "aws_sqs_queue" "media_completed_events_dlq" {
  name = "episode-completed-events-dlq"

  tags = {
    Name        = "episode-completed-events-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "media_completed_events" {
  name                       = "episode-completed-events"
  visibility_timeout_seconds = 360
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.media_completed_events_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "episode-completed-events"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Flashcards
# =============================================================================

resource "aws_sqs_queue" "flashcards_dlq" {
  name = "flashcards-dlq"

  tags = {
    Name        = "flashcards-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "flashcards" {
  name                       = "flashcards-queue"
  visibility_timeout_seconds = 1800
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.flashcards_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "flashcards-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Notes
# =============================================================================

resource "aws_sqs_queue" "notes_dlq" {
  name = "notes-dlq"

  tags = {
    Name        = "notes-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "notes" {
  name                       = "notes-queue"
  visibility_timeout_seconds = 1800
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notes_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "notes-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Quiz
# =============================================================================

resource "aws_sqs_queue" "quiz_dlq" {
  name = "quiz-dlq"

  tags = {
    Name        = "quiz-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "quiz" {
  name                       = "quiz-queue"
  visibility_timeout_seconds = 1800
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.quiz_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "quiz-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "queue_urls" {
  description = "URLs of the SQS queues"
  value = {
    podcastindex_resolution = aws_sqs_queue.rss_resolution.url
    article_extraction      = aws_sqs_queue.article_extraction.url
    x_ingestion             = aws_sqs_queue.x_ingestion.url
    youtube_ingestion       = aws_sqs_queue.youtube_ingestion.url
    instagram_ingestion     = aws_sqs_queue.instagram_ingestion.url
    tiktok_ingestion        = aws_sqs_queue.tiktok_ingestion.url
    deepgram_transcription  = aws_sqs_queue.deepgram_transcription.url
    document_parsing        = aws_sqs_queue.document_parsing.url
    search_indexing         = aws_sqs_queue.search_indexing.url
    rss_feed_poll           = aws_sqs_queue.rss_feed_poll.url
    media_completed_events  = aws_sqs_queue.media_completed_events.url
    flashcards              = aws_sqs_queue.flashcards.url
    notes                   = aws_sqs_queue.notes.url
    quiz                    = aws_sqs_queue.quiz.url
  }
}
