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
  description = "Provision CloudWatch alarms + SNS topics. Measured cost when on: ~$3.30/mo (43 alarms × $0.10 - free tier). Enable for an environment that is actually being watched."
  type        = bool
  default     = false
}

variable "enable_dashboard" {
  description = "Provision the CloudWatch dashboard. Billed per dashboard beyond the 3-dashboard free tier: measured at ~$3.00/mo, which is the single largest line item of an idle environment. Independent of enable_alarms on purpose — an environment can be worth a dashboard without being worth 43 alarms, and vice versa."
  type        = bool
  default     = true
}

variable "enable_worker_polling" {
  description = "Whether the SQS event source mappings are enabled. When false the mappings still exist but the workers stop long-polling their queues. An idle environment's 14 mappings bill ~$0.90/mo in Tier-1 SQS requests polling queues that are always empty. Set false to mothball an environment without destroying anything."
  type        = bool
  default     = true
}

variable "durable_media_enabled" {
  description = "Whether every user save also writes the durable user_media library record (task-240, Phase 1 of the task-218 benchmark). The table is additive and orphan rows are harmless, so the rollback for the whole phase is flipping this to false. Reads still resolve through processing_jobs until task-220 flips them."
  type        = bool
  default     = true
}

variable "ecr_repository_url" {
  description = "URL of the shared Lambda ECR repository, owned by ../../shared and passed in from the environment root."
  type        = string
}
