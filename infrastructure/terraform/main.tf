# Root Terraform configuration for Media Summarizer infrastructure.
# Provider and shared variables used across all .tf files in this directory.

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state (S3) + concurrent-apply lock (DynamoDB).
  # Bucket/table provisioned out-of-band via AWS CLI (chicken-and-egg with the
  # backend itself). Migrated from local state on 2026-06-12 — secret_string
  # values now live in the encrypted bucket instead of a local file.
  backend "s3" {
    bucket         = "media-summarizer-tfstate-125313707865"
    key            = "infrastructure/terraform.tfstate"
    region         = "eu-west-3"
    encrypt        = true
    dynamodb_table = "media-summarizer-tfstate-lock"
  }
}

provider "aws" {
  region = var.aws_region
}

# =============================================================================
# Shared Variables
# =============================================================================

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "production"
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

# =============================================================================
# Data Sources
# =============================================================================

data "aws_caller_identity" "current" {}
