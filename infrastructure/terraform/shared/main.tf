# Account-scoped singletons shared by every environment.
#
# Currently: the single Lambda ECR repository. Its URL is consumed by each
# environment root through a terraform_remote_state data source — the only
# cross-state reference in the whole configuration.

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      # Pinned to 6.x for this root only: IMMUTABLE_WITH_EXCLUSION support on
      # aws_ecr_repository landed in provider 6.6. The environment roots stay on
      # 5.x — each root resolves its own provider, and this state holds exactly
      # two resources, so the blast radius of the newer provider is minimal.
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket         = "media-summarizer-tfstate-125313707865"
    key            = "env/shared/terraform.tfstate"
    region         = "eu-west-3"
    encrypt        = true
    dynamodb_table = "media-summarizer-tfstate-lock"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "media-summarizer"
      Environment = "shared"
      ManagedBy   = "terraform"
    }
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

data "aws_caller_identity" "current" {}

variable "consumer_account_ids" {
  description = "AWS accounts OUTSIDE this one whose Lambdas pull from the shared repository. Since task-248 prod lives in Organizations member account 866874944541 while the registry stays here; without this the prod Lambdas fail their cold start on an image-pull denial."
  type        = list(string)
  default     = ["866874944541"]

  validation {
    condition     = alltrue([for account in var.consumer_account_ids : can(regex("^[0-9]{12}$", account))])
    error_message = "consumer_account_ids must be 12-digit AWS account ids."
  }
}

variable "image_retention_count" {
  description = "Number of images kept per tag prefix (api-, worker-). Must cover the rollback target of every environment at once."
  type        = number
  default     = 15

  validation {
    condition     = var.image_retention_count >= 15
    error_message = "image_retention_count must be at least 15: with three environments, a smaller value expires a prod rollback candidate after a couple of dev pushes."
  }
}

output "lambda_ecr_repository_url" {
  description = "URL of the ECR repository for Lambda container images"
  value       = aws_ecr_repository.lambda.repository_url
}

output "lambda_ecr_repository_name" {
  description = "Name of the ECR repository for Lambda container images"
  value       = aws_ecr_repository.lambda.name
}
