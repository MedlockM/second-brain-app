# Lambda functions for all SQS-triggered workers.
# Each worker is a container image from the shared ECR repository with a
# per-function CMD override pointing to the appropriate handler module.

locals {
  workers = {
    podcastindex_resolution = {
      memory_size = 256
      timeout     = 60
      queue_arn   = aws_sqs_queue.rss_resolution.arn
      handler     = "media_summarizer.workers.lambda_handlers.podcastindex_resolution_handler"
    }
    article_extraction = {
      memory_size = 512
      timeout     = 60
      queue_arn   = aws_sqs_queue.article_extraction.arn
      handler     = "media_summarizer.workers.lambda_handlers.article_extraction_handler"
    }
    x_ingestion = {
      memory_size = 256
      timeout     = 60
      queue_arn   = aws_sqs_queue.x_ingestion.arn
      handler     = "media_summarizer.workers.lambda_handlers.x_ingestion_handler"
    }
    youtube_ingestion = {
      memory_size = 512
      timeout     = 120
      queue_arn   = aws_sqs_queue.youtube_ingestion.arn
      handler     = "media_summarizer.workers.lambda_handlers.youtube_ingestion_handler"
    }
    tiktok_ingestion = {
      memory_size = 512
      timeout     = 120
      queue_arn   = aws_sqs_queue.tiktok_ingestion.arn
      handler     = "media_summarizer.workers.lambda_handlers.tiktok_ingestion_handler"
    }
    deepgram_transcription = {
      memory_size = 512
      timeout     = 600
      queue_arn   = aws_sqs_queue.deepgram_transcription.arn
      handler     = "media_summarizer.workers.lambda_handlers.deepgram_transcription_handler"
    }
    summarization = {
      memory_size = 512
      timeout     = 300
      queue_arn   = aws_sqs_queue.summarization.arn
      handler     = "media_summarizer.workers.lambda_handlers.summarization_handler"
    }
    document_parsing = {
      memory_size = 512
      timeout     = 600
      queue_arn   = aws_sqs_queue.document_parsing.arn
      handler     = "media_summarizer.workers.lambda_handlers.document_parsing_handler"
    }
    search_indexing = {
      memory_size = 256
      timeout     = 60
      queue_arn   = aws_sqs_queue.search_indexing.arn
      handler     = "media_summarizer.workers.lambda_handlers.search_indexing_handler"
    }
    rss_feed_poll = {
      memory_size = 512
      timeout     = 120
      queue_arn   = aws_sqs_queue.rss_feed_poll.arn
      handler     = "media_summarizer.workers.lambda_handlers.rss_feed_poll_handler"
    }
    media_completed_events = {
      memory_size = 256
      timeout     = 60
      queue_arn   = aws_sqs_queue.media_completed_events.arn
      handler     = "media_summarizer.workers.lambda_handlers.media_completed_events_handler"
    }
    flashcards = {
      memory_size = 512
      timeout     = 300
      queue_arn   = aws_sqs_queue.flashcards.arn
      handler     = "media_summarizer.workers.lambda_handlers.flashcards_handler"
    }
    notes = {
      memory_size = 512
      timeout     = 300
      queue_arn   = aws_sqs_queue.notes.arn
      handler     = "media_summarizer.workers.lambda_handlers.notes_handler"
    }
  }
}

# CloudWatch Log Groups for workers
resource "aws_cloudwatch_log_group" "lambda_worker" {
  for_each = local.workers

  name              = "/aws/lambda/${var.project_name}-worker-${each.key}"
  retention_in_days = 14

  tags = {
    Name        = "${var.project_name}-worker-${each.key}-logs"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Lambda Functions
resource "aws_lambda_function" "worker" {
  for_each = local.workers

  function_name = "${var.project_name}-worker-${each.key}"
  role          = aws_iam_role.lambda_worker.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.lambda.repository_url}:worker-latest"
  timeout       = each.value.timeout
  memory_size   = each.value.memory_size
  architectures = ["arm64"]

  image_config {
    command = [each.value.handler]
  }

  environment {
    variables = {
      ENVIRONMENT         = var.environment
      RUNTIME_SECRET_NAME = aws_secretsmanager_secret.runtime.name
      # AWS_DEFAULT_REGION is reserved by Lambda runtime; boto3 reads it automatically
      # from the execution context. See:
      # https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html#configuration-envvars-runtime
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_worker
  ]

  tags = {
    Name        = "${var.project_name}-worker-${each.key}"
    Environment = var.environment
    Project     = var.project_name
  }
}

# SQS Event Source Mappings
resource "aws_lambda_event_source_mapping" "worker" {
  for_each = local.workers

  event_source_arn = each.value.queue_arn
  function_name    = aws_lambda_function.worker[each.key].arn
  batch_size       = 1
  enabled          = true

  # Scale up slowly to avoid throttling
  scaling_config {
    maximum_concurrency = 10
  }
}
