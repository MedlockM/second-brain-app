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
  default     = "us-east-1"
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

# =============================================================================
# Data Sources
# =============================================================================

data "aws_caller_identity" "current" {}
