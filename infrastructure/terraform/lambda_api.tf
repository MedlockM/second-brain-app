# Lambda function for the FastAPI API + API Gateway HTTP API front door.

# =============================================================================
# Variables
# =============================================================================

variable "api_custom_domain" {
  description = "Custom domain for the API (e.g. api.media-summarizer.app)"
  type        = string
  default     = ""
}

variable "api_zone_id" {
  description = "Route53 hosted zone ID for the API domain"
  type        = string
  default     = ""
}

# =============================================================================
# CloudWatch Log Group
# =============================================================================

resource "aws_cloudwatch_log_group" "lambda_api" {
  name              = "/aws/lambda/${var.project_name}-api"
  retention_in_days = 14

  tags = {
    Name        = "${var.project_name}-api-logs"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# Lambda Function
# =============================================================================

resource "aws_lambda_function" "api" {
  function_name = "${var.project_name}-api"
  role          = aws_iam_role.lambda_api.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.lambda.repository_url}:api-latest"
  timeout       = 30
  memory_size   = 1024
  architectures = ["arm64"]

  image_config {
    command = ["media_summarizer.api.lambda_handler.handler"]
  }

  environment {
    variables = {
      ENVIRONMENT         = var.environment
      RUNTIME_SECRET_NAME = aws_secretsmanager_secret.runtime.name
      # AWS_DEFAULT_REGION is reserved by Lambda runtime; boto3 reads it automatically
      # from the execution context. See:
      # https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html#configuration-envvars-runtime
      # Disable the S3 preflight check on Lambda (infra is guaranteed by Terraform)
      PRESTART_INFRA_CHECK = "0"

      # S3 bucket names — injected by Terraform, NOT via Secrets Manager.
      AUDIO_BUCKET            = aws_s3_bucket.audio.bucket
      TRANSCRIPT_BUCKET       = aws_s3_bucket.transcripts.bucket
      SUMMARY_BUCKET          = aws_s3_bucket.summaries.bucket
      SUMMARY_SHORT_BUCKET    = aws_s3_bucket.summary_short.bucket
      SUMMARY_DETAILED_BUCKET = aws_s3_bucket.summary_detailed.bucket
      NOTES_BUCKET            = aws_s3_bucket.notes.bucket
      FLASHCARDS_BUCKET       = aws_s3_bucket.flashcards.bucket
      QUIZ_BUCKET             = aws_s3_bucket.quiz.bucket
      DOCUMENT_BUCKET         = aws_s3_bucket.documents.bucket
      ARCHIVE_BUCKET          = aws_s3_bucket.archives.bucket
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_api
  ]

  tags = {
    Name        = "${var.project_name}-api"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# API Gateway HTTP API
# =============================================================================

resource "aws_apigatewayv2_api" "main" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers     = ["*"]
    expose_headers    = ["X-Request-ID"]
    max_age           = 3600
    allow_credentials = false
  }

  tags = {
    Name        = "${var.project_name}-api"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 1000
    throttling_rate_limit  = 500
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.lambda_api.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      integrationLatency = "$context.integrationLatency"
    })
  }

  tags = {
    Name        = "${var.project_name}-api-default-stage"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_apigatewayv2_integration" "lambda_api" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_api.id}"
}

# Permission for API Gateway to invoke the Lambda
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# =============================================================================
# Custom Domain (optional, only created when api_custom_domain is set)
# =============================================================================

resource "aws_acm_certificate" "api" {
  count             = var.api_custom_domain != "" ? 1 : 0
  domain_name       = var.api_custom_domain
  validation_method = "DNS"

  tags = {
    Name        = "${var.project_name}-api-cert"
    Environment = var.environment
    Project     = var.project_name
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_apigatewayv2_domain_name" "api" {
  count       = var.api_custom_domain != "" ? 1 : 0
  domain_name = var.api_custom_domain

  domain_name_configuration {
    certificate_arn = aws_acm_certificate.api[0].arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }

  tags = {
    Name        = "${var.project_name}-api-domain"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_apigatewayv2_api_mapping" "api" {
  count       = var.api_custom_domain != "" ? 1 : 0
  api_id      = aws_apigatewayv2_api.main.id
  domain_name = aws_apigatewayv2_domain_name.api[0].id
  stage       = aws_apigatewayv2_stage.default.id
}

resource "aws_route53_record" "api" {
  count   = var.api_custom_domain != "" && var.api_zone_id != "" ? 1 : 0
  zone_id = var.api_zone_id
  name    = var.api_custom_domain
  type    = "A"

  alias {
    name                   = aws_apigatewayv2_domain_name.api[0].domain_name_configuration[0].target_domain_name
    zone_id                = aws_apigatewayv2_domain_name.api[0].domain_name_configuration[0].hosted_zone_id
    evaluate_target_health = false
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "api_function_name" {
  description = "Name of the API Lambda function"
  value       = aws_lambda_function.api.function_name
}
