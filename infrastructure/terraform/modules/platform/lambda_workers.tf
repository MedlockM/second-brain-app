# Lambda functions for all SQS-triggered workers.
# Each worker is a container image from the shared ECR repository with a
# per-function CMD override pointing to the appropriate handler module.

variable "worker_image_tag" {
  description = "Bootstrap tag for the shared worker image; CI deploys immutable image digests afterwards."
  type        = string
  default     = "worker-latest"
}

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
      timeout     = 60
      queue_arn   = aws_sqs_queue.youtube_ingestion.arn
      handler     = "media_summarizer.workers.lambda_handlers.youtube_ingestion_handler"
    }
    instagram_ingestion = {
      memory_size = 512
      timeout     = 60
      queue_arn   = aws_sqs_queue.instagram_ingestion.arn
      handler     = "media_summarizer.workers.lambda_handlers.instagram_ingestion_handler"
    }
    tiktok_ingestion = {
      memory_size = 512
      timeout     = 60
      queue_arn   = aws_sqs_queue.tiktok_ingestion.arn
      handler     = "media_summarizer.workers.lambda_handlers.tiktok_ingestion_handler"
    }
    deepgram_transcription = {
      memory_size = 512
      timeout     = 600
      queue_arn   = aws_sqs_queue.deepgram_transcription.arn
      handler     = "media_summarizer.workers.lambda_handlers.deepgram_transcription_handler"
    }
    artifact_generator = {
      memory_size = 512
      timeout     = 300
      queue_arn   = aws_sqs_queue.artifact_generator.arn
      handler     = "media_summarizer.workers.lambda_handlers.artifact_generator_handler"
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
    transcript_translation = {
      memory_size = 512
      timeout     = 300
      queue_arn   = aws_sqs_queue.transcript_translation.arn
      handler     = "media_summarizer.workers.lambda_handlers.transcript_translation_handler"
    }
  }
}

# CloudWatch Log Groups for workers
resource "aws_cloudwatch_log_group" "lambda_worker" {
  for_each = local.workers

  name              = "/aws/lambda/${var.project_name}-worker-${each.key}${local.suffix}"
  retention_in_days = 14

  tags = {
    Name = "${var.project_name}-worker-${each.key}${local.suffix}-logs"
  }
}

# Lambda Functions
resource "aws_lambda_function" "worker" {
  for_each = local.workers

  function_name = "${var.project_name}-worker-${each.key}${local.suffix}"
  role          = aws_iam_role.lambda_worker.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repository_url}:${var.worker_image_tag}"
  timeout       = each.value.timeout
  memory_size   = each.value.memory_size
  architectures = ["arm64"]

  image_config {
    command = [each.value.handler]
  }

  # Every table, queue and bucket name this environment owns. The application
  # code no longer carries hardcoded defaults, so this block is the only source
  # of resource names at runtime (see runtime_env.tf).
  environment {
    variables = contains(
      ["instagram_ingestion", "tiktok_ingestion", "youtube_ingestion"],
      each.key,
      ) ? merge(local.lambda_environment, {
        APIFY_WEBHOOK_URL = "${aws_apigatewayv2_api.main.api_endpoint}/api/webhooks/apify"
    }) : local.lambda_environment
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_worker
  ]

  # image_uri is owned by deploy-lambda.yml (it pushes :worker-<sha> per commit
  # and runs aws lambda update-function-code on every worker function).
  # Terraform only seeds :worker-latest at first creation; afterwards the CI is
  # the source of truth, so don't let `terraform apply` revert deployed images.
  lifecycle {
    ignore_changes = [image_uri]
  }

  tags = {
    Name = "${var.project_name}-worker-${each.key}${local.suffix}"
  }
}

# SQS Event Source Mappings
resource "aws_lambda_event_source_mapping" "worker" {
  for_each = local.workers

  event_source_arn = each.value.queue_arn
  function_name    = aws_lambda_function.worker[each.key].arn
  batch_size       = 1

  # Disabling the mapping stops the long-poll without deleting it: an idle
  # environment's 14 mappings issue ~74k SQS Tier-1 requests a day against
  # queues that never receive anything (~$0.90/mo). Re-enabling is a one-line
  # apply, so a mothballed environment stays one command from usable.
  enabled = var.enable_worker_polling

  # Scale up slowly to avoid throttling
  scaling_config {
    maximum_concurrency = 10
  }
}

output "worker_bootstrap_image_uri" {
  description = "Shared worker image URI used by Terraform when creating worker Lambdas."
  value       = "${var.ecr_repository_url}:${var.worker_image_tag}"
}

output "worker_function_names" {
  description = "Names of this environment's worker Lambda functions."
  value       = [for w in aws_lambda_function.worker : w.function_name]
}
