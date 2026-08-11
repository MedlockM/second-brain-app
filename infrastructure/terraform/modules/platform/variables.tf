# =============================================================================
# Platform module inputs
# =============================================================================

variable "environment" {
  description = "Environment name. Drives local.suffix, which is appended to every physical resource name."
  type        = string

  # No default on purpose: an apply without an explicit environment used to
  # target the token "production", which no resource has ever used.
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod (note: 'prod', not 'production' — the Lambda name budget is 64 chars)."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3"
}

variable "project_name" {
  description = "Project name used as prefix for all resources"
  type        = string
  default     = "media-summarizer"
}

variable "enable_alarms" {
  description = "Provision CloudWatch alarms + SNS topics. Off in dev to save ~$4.20/mo (42 alarms × $0.10). Enable for staging/prod."
  type        = bool
  default     = false
}

variable "ecr_repository_url" {
  description = "URL of the shared Lambda ECR repository, owned by ../../shared and passed in from the environment root."
  type        = string
}
