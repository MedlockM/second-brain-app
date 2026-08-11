
# Media Summarizer platform module.
#
# Every AWS resource of the application lives here, parameterised by
# var.environment. This module deliberately declares NO backend and NO provider
# block: it can only be consumed from one of the environment roots in
# ../../envs/<env>/, each of which pins a literal backend key and a literal
# environment. Running `terraform plan` directly inside this directory fails,
# which is the intended guard rail.

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    # Generates the job-archiver placeholder package (see archiving.tf).
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

# =============================================================================
# Data Sources
# =============================================================================

data "aws_caller_identity" "current" {}
