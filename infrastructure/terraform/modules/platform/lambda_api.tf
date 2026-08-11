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

variable "api_image_tag" {
  description = "Bootstrap tag for the dedicated API image; CI deploys immutable image digests afterwards."
  type        = string
  default     = "api-latest"
}

variable "api_reserved_concurrency" {
  description = "Optional API reservation override. Defaults to -1 in dev and 10 in staging/production."
  type        = number
  default     = null
  nullable    = true

  validation {
    condition = (
      var.api_reserved_concurrency == null ||
      var.api_reserved_concurrency == -1 ||
      try(var.api_reserved_concurrency >= 1, false)
    )
    error_message = "api_reserved_concurrency must be -1 or at least 1."
  }
}

locals {
  effective_api_reserved_concurrency = (
    var.api_reserved_concurrency != null
    ? var.api_reserved_concurrency
    : (var.environment == "dev" ? -1 : 10)
  )
}

variable "api_warmup_enabled" {
  description = "Invoke and validate the API health route on a low-cost EventBridge schedule."
  type        = bool
  default     = true
}

variable "api_warmup_schedule_expression" {
  description = "EventBridge schedule used for API warm-up and health validation."
  type        = string
  default     = "rate(15 minutes)"

  validation {
    condition = (
      startswith(var.api_warmup_schedule_expression, "rate(") ||
      startswith(var.api_warmup_schedule_expression, "cron(")
    )
    error_message = "api_warmup_schedule_expression must be an EventBridge rate() or cron() expression."
  }
}

# =============================================================================
# CloudWatch Log Group
# =============================================================================

resource "aws_cloudwatch_log_group" "lambda_api" {
  name              = "/aws/lambda/${var.project_name}-api${local.suffix}"
  retention_in_days = 14

  tags = {
    Name = "${var.project_name}-api${local.suffix}-logs"
  }
}

# =============================================================================
# Lambda Function
# =============================================================================

resource "aws_lambda_function" "api" {
  function_name                  = "${var.project_name}-api${local.suffix}"
  role                           = aws_iam_role.lambda_api.arn
  package_type                   = "Image"
  image_uri                      = "${var.ecr_repository_url}:${var.api_image_tag}"
  timeout                        = 30
  memory_size                    = 1024
  architectures                  = ["arm64"]
  reserved_concurrent_executions = local.effective_api_reserved_concurrency

  image_config {
    command = ["media_summarizer.api.lambda_handler.handler"]
  }

  # Every table, queue and bucket name this environment owns. The application
  # code no longer carries hardcoded defaults, so this block is the only source
  # of resource names at runtime (see runtime_env.tf).
  environment {
    variables = merge(local.lambda_environment, {
      # Disable the S3 preflight check on Lambda (infra is guaranteed by Terraform)
      PRESTART_INFRA_CHECK = "0"
    })
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_api
  ]

  # image_uri is owned by deploy-lambda.yml (it pushes :api-<sha> per commit
  # and runs aws lambda update-function-code). Terraform only seeds :api-latest
  # at first creation; afterwards the CI is the source of truth, so don't let
  # `terraform apply` revert deployed images back to whatever :latest points at.
  lifecycle {
    ignore_changes = [image_uri]
  }

  tags = {
    Name = "${var.project_name}-api${local.suffix}"
  }
}

# =============================================================================
# API Gateway HTTP API
# =============================================================================

resource "aws_apigatewayv2_api" "main" {
  # NOT ForceNew in the AWS provider: renaming the API updates it in place and
  # preserves its ID and its execute-api URL, so mobile clients and OAuth
  # redirect URIs keep working across the task-237 rename.
  name          = "${var.project_name}-api${local.suffix}"
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
    Name = "${var.project_name}-api${local.suffix}"
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
      requestId               = "$context.requestId"
      ip                      = "$context.identity.sourceIp"
      requestTime             = "$context.requestTime"
      httpMethod              = "$context.httpMethod"
      routeKey                = "$context.routeKey"
      status                  = "$context.status"
      protocol                = "$context.protocol"
      responseLength          = "$context.responseLength"
      integrationLatency      = "$context.integrationLatency"
      integrationErrorMessage = "$context.integrationErrorMessage"
      errorMessage            = "$context.error.message"
      errorResponseType       = "$context.error.responseType"
    })
  }

  tags = {
    Name = "${var.project_name}-api${local.suffix}-default-stage"
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

# A scheduled direct invocation keeps the on-demand execution environment warm
# and exercises the canonical health route through the same Mangum adapter. The
# wrapper raises on non-200/unhealthy responses so Lambda Errors exposes failures.
resource "aws_cloudwatch_event_rule" "api_warmup" {
  count = var.api_warmup_enabled ? 1 : 0

  name                = "${var.project_name}-api-warmup${local.suffix}"
  description         = "Low-cost scheduled warm-up and health validation for the interactive API"
  schedule_expression = var.api_warmup_schedule_expression
  state               = "ENABLED"

  tags = {
    Name = "${var.project_name}-api-warmup${local.suffix}"
  }
}

resource "aws_cloudwatch_event_target" "api_warmup" {
  count = var.api_warmup_enabled ? 1 : 0

  rule      = aws_cloudwatch_event_rule.api_warmup[0].name
  target_id = "${var.project_name}-api${local.suffix}"
  arn       = aws_lambda_function.api.arn
  input = jsonencode({
    source = "media-summarizer.api-warmup"
  })
}

resource "aws_lambda_permission" "api_warmup" {
  count = var.api_warmup_enabled ? 1 : 0

  statement_id  = "AllowEventBridgeApiWarmup"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.api_warmup[0].arn
}

# =============================================================================
# Custom Domain (optional, only created when api_custom_domain is set)
# =============================================================================

resource "aws_acm_certificate" "api" {
  count             = var.api_custom_domain != "" ? 1 : 0
  domain_name       = var.api_custom_domain
  validation_method = "DNS"

  tags = {
    Name = "${var.project_name}-api${local.suffix}-cert"
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
    Name = "${var.project_name}-api${local.suffix}-domain"
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

output "api_gateway_id" {
  description = "API Gateway HTTP API ID. Stable across the task-237 rename, and the only safe way for CI to resolve an environment's endpoint (API names are not unique)."
  value       = aws_apigatewayv2_api.main.id
}

output "api_bootstrap_image_uri" {
  description = "Dedicated API image URI used by Terraform when creating the Lambda."
  value       = aws_lambda_function.api.image_uri
}
