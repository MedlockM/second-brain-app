# SQS Queues and Dead Letter Queues for all pipeline workers.
# Extracted from the former scaling.tf and expanded for all V1 workers.

# =============================================================================
# Podcastindex Resolution
# =============================================================================

resource "aws_sqs_queue" "rss_resolution_dlq" {
  name                      = "podcastindex-resolution-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "podcastindex-resolution-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "rss_resolution" {
  name                       = "podcastindex-resolution-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600 # 14 days

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.rss_resolution_dlq.arn
    maxReceiveCount     = 3
  })

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
  name                      = "article-extraction-dlq"
  message_retention_seconds = 1209600 # 14 days

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
  name                      = "x-ingestion-dlq"
  message_retention_seconds = 1209600 # 14 days

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
  name                      = "youtube-ingestion-dlq"
  message_retention_seconds = 1209600 # 14 days

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
  name                      = "instagram-ingestion-dlq"
  message_retention_seconds = 1209600 # 14 days

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
  name                      = "tiktok-ingestion-dlq"
  message_retention_seconds = 1209600 # 14 days

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
  name                      = "deepgram-transcription-dlq"
  message_retention_seconds = 1209600 # 14 days

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
# Artifact Generator (unified queue for flashcards, notes, quiz, summary_short,
# summary_detailed — consolidation per task-195)
# =============================================================================

resource "aws_sqs_queue" "artifact_generator_dlq" {
  name                      = "artifact-generator-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "artifact-generator-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "artifact_generator" {
  name                       = "artifact-generator-queue"
  visibility_timeout_seconds = 1800
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.artifact_generator_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "artifact-generator-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Document Parsing
# =============================================================================

resource "aws_sqs_queue" "document_parsing_dlq" {
  name                      = "document-parsing-dlq"
  message_retention_seconds = 1209600 # 14 days

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
  name                      = "search-indexing-dlq"
  message_retention_seconds = 1209600 # 14 days

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
  name                      = "rss-feed-poll-dlq"
  message_retention_seconds = 1209600 # 14 days

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
  name                      = "episode-completed-events-dlq"
  message_retention_seconds = 1209600 # 14 days

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
# Transcript Translation (task-200: async translation for /raw-content cache miss)
# =============================================================================

resource "aws_sqs_queue" "transcript_translation_dlq" {
  name                      = "transcript-translation-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "transcript-translation-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "transcript_translation" {
  name                       = "transcript-translation-queue"
  visibility_timeout_seconds = 600
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.transcript_translation_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "transcript-translation-queue"
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
    podcastindex_resolution  = aws_sqs_queue.rss_resolution.url
    article_extraction       = aws_sqs_queue.article_extraction.url
    x_ingestion              = aws_sqs_queue.x_ingestion.url
    youtube_ingestion        = aws_sqs_queue.youtube_ingestion.url
    instagram_ingestion      = aws_sqs_queue.instagram_ingestion.url
    tiktok_ingestion         = aws_sqs_queue.tiktok_ingestion.url
    deepgram_transcription   = aws_sqs_queue.deepgram_transcription.url
    artifact_generator       = aws_sqs_queue.artifact_generator.url
    document_parsing         = aws_sqs_queue.document_parsing.url
    search_indexing          = aws_sqs_queue.search_indexing.url
    rss_feed_poll            = aws_sqs_queue.rss_feed_poll.url
    media_completed_events   = aws_sqs_queue.media_completed_events.url
    transcript_translation   = aws_sqs_queue.transcript_translation.url
  }
}

output "dlq_arns" {
  description = "ARNs of the Dead Letter Queues (for replay tooling)"
  value = {
    podcastindex_resolution  = aws_sqs_queue.rss_resolution_dlq.arn
    article_extraction       = aws_sqs_queue.article_extraction_dlq.arn
    x_ingestion              = aws_sqs_queue.x_ingestion_dlq.arn
    youtube_ingestion        = aws_sqs_queue.youtube_ingestion_dlq.arn
    instagram_ingestion      = aws_sqs_queue.instagram_ingestion_dlq.arn
    tiktok_ingestion         = aws_sqs_queue.tiktok_ingestion_dlq.arn
    deepgram_transcription   = aws_sqs_queue.deepgram_transcription_dlq.arn
    artifact_generator       = aws_sqs_queue.artifact_generator_dlq.arn
    document_parsing         = aws_sqs_queue.document_parsing_dlq.arn
    search_indexing           = aws_sqs_queue.search_indexing_dlq.arn
    rss_feed_poll            = aws_sqs_queue.rss_feed_poll_dlq.arn
    media_completed_events   = aws_sqs_queue.media_completed_events_dlq.arn
    transcript_translation   = aws_sqs_queue.transcript_translation_dlq.arn
  }
}
