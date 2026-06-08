# Terraform configuration for Media Summarizer horizontal scaling infrastructure

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "media-summarizer"
}

variable "max_parallel_workers" {
  description = "Maximum number of parallel workers"
  type        = number
  default     = 15
}

variable "vpc_id" {
  description = "VPC ID for the infrastructure"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for Fargate tasks"
  type        = list(string)
}

variable "openai_api_key" {
  description = "OpenAI API key for summarization"
  type        = string
  sensitive   = true
}

variable "deepgram_api_key" {
  description = "Deepgram API key for transcription"
  type        = string
  sensitive   = true
}

# Data sources
data "aws_caller_identity" "current" {}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${var.project_name}-cluster"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Security Group for Fargate tasks
resource "aws_security_group" "fargate_tasks" {
  name        = "${var.project_name}-fargate-tasks"
  description = "Security group for Media Summarizer Fargate tasks"
  vpc_id      = var.vpc_id

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-fargate-tasks"
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-ecs-task-execution"
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Policy for ECS Task Execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM Role for ECS Tasks
resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-ecs-task"
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Policy for ECS Tasks
resource "aws_iam_policy" "ecs_task_policy" {
  name        = "${var.project_name}-ecs-task-policy"
  description = "Policy for Media Summarizer ECS tasks"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:SendMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = [
          aws_sqs_queue.rss_resolution.arn,
          aws_sqs_queue.audio_download.arn,
          aws_sqs_queue.youtube_ingestion.arn,
          aws_sqs_queue.tiktok_ingestion.arn,
          aws_sqs_queue.deepgram_transcription.arn,
          aws_sqs_queue.transcription.arn,
          aws_sqs_queue.summarization.arn,
          aws_sqs_queue.notes.arn,
          aws_sqs_queue.flashcards.arn,
          aws_sqs_queue.quiz.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.audio.arn}/*",
          "${aws_s3_bucket.transcripts.arn}/*",
          "${aws_s3_bucket.summaries.arn}/*",
          "${aws_s3_bucket.notes.arn}/*",
          "${aws_s3_bucket.flashcards.arn}/*",
          "${aws_s3_bucket.quizzes.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.audio.arn,
          aws_s3_bucket.transcripts.arn,
          aws_s3_bucket.summaries.arn,
          aws_s3_bucket.notes.arn,
          aws_s3_bucket.flashcards.arn,
          aws_s3_bucket.quizzes.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.processing_jobs.arn,
          aws_dynamodb_table.users.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-ecs-task-policy"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_policy" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_task_policy.arn
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "workers" {
  for_each = toset(["rss", "x", "youtube", "tiktok", "download", "deepgram", "whisper", "summarization"])

  name              = "/ecs/${var.project_name}-${each.key}-worker"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-${each.key}-worker-logs"
    Environment = var.environment
    Project     = var.project_name
  }
}

# SQS Queues
resource "aws_sqs_queue" "rss_resolution" {
  name                      = "podcastindex-resolution-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds = 1209600 # 14 days
  max_receive_count         = 3

  tags = {
    Name        = "podcastindex-resolution-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Dead-letter queue for audio download
resource "aws_sqs_queue" "audio_download_dlq" {
  name = "audio-download-dlq"

  tags = {
    Name        = "audio-download-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "audio_download" {
  name                       = "audio-download-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.audio_download_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "audio-download-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Dead-letter queue for transcription
resource "aws_sqs_queue" "transcription_dlq" {
  name = "transcription-dlq"

  tags = {
    Name        = "transcription-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "transcription" {
  name                       = "transcription-queue"
  visibility_timeout_seconds = 1800 # 30 minutes for long transcriptions
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.transcription_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "transcription-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Dead-letter queue for Deepgram transcription
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
  visibility_timeout_seconds = 1800
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

# Dead-letter queue for X ingestion
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

# Dead-letter queue for YouTube ingestion
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
  visibility_timeout_seconds = 300
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

# Dead-letter queue for TikTok ingestion
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
  visibility_timeout_seconds = 300
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

# Dead-letter queue for summarization
resource "aws_sqs_queue" "summarization_dlq" {
  name = "summarization-dlq"

  tags = {
    Name        = "summarization-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_sqs_queue" "summarization" {
  name                       = "summarization-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.summarization_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name        = "summarization-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Dead-letter queue for notes artifact generation
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
  visibility_timeout_seconds = 300
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

# Dead-letter queue for flashcards artifact generation
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
  visibility_timeout_seconds = 300
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

# Dead-letter queue for quiz artifact generation
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
  visibility_timeout_seconds = 300
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

# S3 Buckets for media storage (prod): unique names per account/env
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

resource "aws_s3_bucket" "quizzes" {
  bucket = "${var.project_name}-quizzes-${data.aws_caller_identity.current.account_id}-${var.environment}"
  tags = {
    Name        = "${var.project_name}-quizzes"
    Environment = var.environment
    Project     = var.project_name
  }
}

# DynamoDB Tables (aligned with application expectations)
resource "aws_dynamodb_table" "processing_jobs" {
  name         = "processing_jobs"          # EXACT application name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute { name = "id"         type = "S" }
  attribute { name = "user_id"    type = "S" }
  attribute { name = "job_status" type = "S" }

  # GSI: user-index (query jobs by user)
  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  # GSI: status-index (query by status)
  global_secondary_index {
    name            = "status-index"
    hash_key        = "job_status"
    projection_type = "ALL"
  }

  # TTL configuration for auto-deletion
  ttl {
    attribute_name = "expire_at"
    enabled        = true
  }

  # Enable Streams for archiving
  stream_enabled   = true
  stream_view_type = "OLD_IMAGE" # We need the deleted item to archive it

  tags = {
    Name        = "processing_jobs"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_dynamodb_table" "users" {
  name         = "users"                     # EXACT application name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute { name = "id"    type = "S" }
  attribute { name = "email" type = "S" }

  # GSI: email-index (lookup by email)
  global_secondary_index {
    name            = "email-index"
    hash_key        = "email"
    projection_type = "ALL"
  }

  tags = {
    Name        = "users"
    Environment = var.environment
    Project     = var.project_name
  }
}

# ECS Task Definitions
resource "aws_ecs_task_definition" "ephemeral_worker" {
  for_each = {
    rss           = { cpu = 256, memory = 512 }
    x             = { cpu = 256, memory = 512 }
    youtube       = { cpu = 512, memory = 1024 }
    tiktok        = { cpu = 512, memory = 1024 }
    download      = { cpu = 512, memory = 1024 }
    deepgram      = { cpu = 1024, memory = 2048 }
    whisper       = { cpu = 1024, memory = 2048 }
    summarization = { cpu = 512, memory = 1024 }
  }

  family                   = "${var.project_name}-${each.key}-worker"
  network_mode             = "awsvpc"
  requires_compatibility   = ["FARGATE"]
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "${var.project_name}-${each.key}"
      image = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.project_name}-ephemeral-worker:latest"

      environment = [
        {
          name  = "WORKER_TYPE"
          value = each.key
        },
        {
          name  = "AWS_DEFAULT_REGION"
          value = var.aws_region
        },
        {
          name  = "EPHEMERAL_MODE"
          value = "true"
        },
        {
          name  = "MAX_PROCESSING_TIME"
          value = contains(["whisper", "deepgram"], each.key) ? "3600" : "900"
        },
        {
          name  = "HEARTBEAT_INTERVAL"
          value = "60"
        },
        {
          name  = "VISIBILITY_TIMEOUT"
          value = contains(["whisper", "deepgram"], each.key) ? "1800" : "300"
        }
      ]

      secrets = each.key == "summarization" ? [
        {
          name      = "OPENAI_API_KEY"
          valueFrom = aws_secretsmanager_secret.openai_api_key.arn
        }
      ] : each.key == "deepgram" ? [
        {
          name      = "DEEPGRAM_API_KEY"
          valueFrom = aws_secretsmanager_secret.deepgram_api_key.arn
        }
      ] : []

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.workers[each.key].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      essential = true
    }
  ])

  tags = {
    Name        = "${var.project_name}-${each.key}-worker"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Secrets Manager for OpenAI API Key
resource "aws_secretsmanager_secret" "openai_api_key" {
  name        = "${var.project_name}-openai-api-key"
  description = "OpenAI API key for Media Summarizer"

  tags = {
    Name        = "${var.project_name}-openai-api-key"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key
}

# Secrets Manager for Deepgram API Key
resource "aws_secretsmanager_secret" "deepgram_api_key" {
  name        = "${var.project_name}-deepgram-api-key"
  description = "Deepgram API key for Media Summarizer"

  tags = {
    Name        = "${var.project_name}-deepgram-api-key"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "deepgram_api_key" {
  secret_id     = aws_secretsmanager_secret.deepgram_api_key.id
  secret_string = var.deepgram_api_key
}

# IAM Role for Lambda Scaling Controller
resource "aws_iam_role" "lambda_scaling" {
  name = "${var.project_name}-lambda-scaling"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-lambda-scaling"
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Policy for Lambda Scaling Controller
resource "aws_iam_policy" "lambda_scaling" {
  name        = "${var.project_name}-lambda-scaling-policy"
  description = "Policy for Lambda scaling controller"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:ListTasks",
          "ecs:DescribeTasks"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = [
          aws_sqs_queue.rss_resolution.arn,
          aws_sqs_queue.audio_download.arn,
          aws_sqs_queue.x_ingestion.arn,
          aws_sqs_queue.youtube_ingestion.arn,
          aws_sqs_queue.tiktok_ingestion.arn,
          aws_sqs_queue.deepgram_transcription.arn,
          aws_sqs_queue.transcription.arn,
          aws_sqs_queue.summarization.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_task_execution.arn,
          aws_iam_role.ecs_task.arn
        ]
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-lambda-scaling-policy"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "lambda_scaling" {
  role       = aws_iam_role.lambda_scaling.name
  policy_arn = aws_iam_policy.lambda_scaling.arn
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_scaling.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda function for scaling control
resource "aws_lambda_function" "scaling_controller" {
  filename         = "scaling_controller.zip"
  function_name    = "${var.project_name}-scaling-controller"
  role            = aws_iam_role.lambda_scaling.arn
  handler         = "scaling_controller.lambda_handler"
  runtime         = "python3.11"
  timeout         = 300
  memory_size     = 256

  environment {
    variables = {
      CLUSTER_NAME                    = aws_ecs_cluster.main.name
      RSS_TASK_DEFINITION_ARN         = aws_ecs_task_definition.ephemeral_worker["rss"].arn
      X_TASK_DEFINITION_ARN           = aws_ecs_task_definition.ephemeral_worker["x"].arn
      YOUTUBE_TASK_DEFINITION_ARN     = aws_ecs_task_definition.ephemeral_worker["youtube"].arn
      TIKTOK_TASK_DEFINITION_ARN      = aws_ecs_task_definition.ephemeral_worker["tiktok"].arn
      DOWNLOAD_TASK_DEFINITION_ARN    = aws_ecs_task_definition.ephemeral_worker["download"].arn
      DEEPGRAM_TASK_DEFINITION_ARN    = aws_ecs_task_definition.ephemeral_worker["deepgram"].arn
      WHISPER_TASK_DEFINITION_ARN     = aws_ecs_task_definition.ephemeral_worker["whisper"].arn
      SUMMARIZATION_TASK_DEFINITION_ARN = aws_ecs_task_definition.ephemeral_worker["summarization"].arn
      SUBNET_IDS                      = join(",", var.subnet_ids)
      SECURITY_GROUP_IDS              = aws_security_group.fargate_tasks.id
      MAX_PARALLEL_WORKERS            = var.max_parallel_workers
      AWS_DEFAULT_REGION              = var.aws_region
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_scaling,
    aws_cloudwatch_log_group.lambda_scaling
  ]

  tags = {
    Name        = "${var.project_name}-scaling-controller"
    Environment = var.environment
    Project     = var.project_name
  }
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_scaling" {
  name              = "/aws/lambda/${var.project_name}-scaling-controller"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-scaling-controller-logs"
    Environment = var.environment
    Project     = var.project_name
  }
}

# CloudWatch Alarms for queue monitoring
resource "aws_cloudwatch_metric_alarm" "queue_messages" {
  for_each = {
    "podcastindex-resolution" = aws_sqs_queue.rss_resolution.name
    "x-ingestion"             = aws_sqs_queue.x_ingestion.name
    "youtube-ingestion"       = aws_sqs_queue.youtube_ingestion.name
    "tiktok-ingestion"        = aws_sqs_queue.tiktok_ingestion.name
    "deepgram-transcription"  = aws_sqs_queue.deepgram_transcription.name
    "summarization"           = aws_sqs_queue.summarization.name
  }

  alarm_name          = "${var.project_name}-${each.key}-queue-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateNumberOfVisibleMessages"
  namespace           = "AWS/SQS"
  period              = "60"
  statistic           = "Average"
  threshold           = "0"
  alarm_description   = "This metric monitors ${each.key} queue message count"
  alarm_actions       = [aws_sns_topic.scaling_alerts.arn]
  ok_actions          = []

  dimensions = {
    QueueName = each.value
  }

  tags = {
    Name        = "${var.project_name}-${each.key}-queue-alarm"
    Environment = var.environment
    Project     = var.project_name
  }
}

# SNS Topic for scaling alerts
resource "aws_sns_topic" "scaling_alerts" {
  name = "${var.project_name}-scaling-alerts"

  tags = {
    Name        = "${var.project_name}-scaling-alerts"
    Environment = var.environment
    Project     = var.project_name
  }
}

# SNS Topic Subscription for Lambda
resource "aws_sns_topic_subscription" "lambda_scaling" {
  topic_arn = aws_sns_topic.scaling_alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.scaling_controller.arn
}

# Lambda permission for SNS
resource "aws_lambda_permission" "allow_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scaling_controller.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.scaling_alerts.arn
}

# EventBridge rule for periodic scaling check
resource "aws_cloudwatch_event_rule" "scaling_check" {
  name                = "${var.project_name}-scaling-check"
  description         = "Periodic check for scaling needs"
  schedule_expression = "rate(2 minutes)"

  tags = {
    Name        = "${var.project_name}-scaling-check"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_cloudwatch_event_target" "lambda_scaling" {
  rule      = aws_cloudwatch_event_rule.scaling_check.name
  target_id = "ScalingControllerTarget"
  arn       = aws_lambda_function.scaling_controller.arn

  input = jsonencode({
    action = "scale"
    source = "eventbridge.scheduler"
  })
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scaling_controller.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scaling_check.arn
}

# ECR Repository for ephemeral worker
resource "aws_ecr_repository" "ephemeral_worker" {
  name                 = "${var.project_name}-ephemeral-worker"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "${var.project_name}-ephemeral-worker"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Outputs
output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "security_group_id" {
  description = "Security group ID for Fargate tasks"
  value       = aws_security_group.fargate_tasks.id
}

output "lambda_function_name" {
  description = "Name of the scaling controller Lambda function"
  value       = aws_lambda_function.scaling_controller.function_name
}

output "sns_topic_arn" {
  description = "ARN of the scaling alerts SNS topic"
  value       = aws_sns_topic.scaling_alerts.arn
}

output "queue_urls" {
  description = "URLs of the SQS queues"
  value = {
    podcastindex_resolution = aws_sqs_queue.rss_resolution.url
    rss_resolution     = aws_sqs_queue.rss_resolution.url
    audio_download     = aws_sqs_queue.audio_download.url
    transcription      = aws_sqs_queue.transcription.url
    x_ingestion        = aws_sqs_queue.x_ingestion.url
    youtube_ingestion  = aws_sqs_queue.youtube_ingestion.url
    tiktok_ingestion   = aws_sqs_queue.tiktok_ingestion.url
    deepgram_transcription = aws_sqs_queue.deepgram_transcription.url
    summarization      = aws_sqs_queue.summarization.url
    notes              = aws_sqs_queue.notes.url
    flashcards         = aws_sqs_queue.flashcards.url
    quiz               = aws_sqs_queue.quiz.url
  }
}

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

output "dynamodb_table_names" {
  description = "Names of the DynamoDB tables"
  value = {
    processing_jobs = aws_dynamodb_table.processing_jobs.name
    users           = aws_dynamodb_table.users.name
  }
}

# Explicit outputs for app wiring
output "users_table_name" {
  description = "Users table name"
  value       = aws_dynamodb_table.users.name
}

output "processing_jobs_table_name" {
  description = "Processing jobs table name"
  value       = aws_dynamodb_table.processing_jobs.name
}

output "ecr_repository_url" {
  description = "URL of the ECR repository for ephemeral worker"
  value       = aws_ecr_repository.ephemeral_worker.repository_url
}

output "task_definition_arns" {
  description = "ARNs of the ECS task definitions"
  value = {
    for k, v in aws_ecs_task_definition.ephemeral_worker : k => v.arn
  }
}
