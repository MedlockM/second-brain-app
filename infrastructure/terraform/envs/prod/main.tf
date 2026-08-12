# prod environment root — NEVER APPLIED YET.
#
# task-237 delivers dev and staging only; creating production is Phase 10 of
# docs/V1_LAUNCH_PLAN.md, after staging has been validated. This directory
# exists so the layout is complete and reviewable, and so the prod bring-up is a
# plan + apply rather than a design exercise. Running `apply` here creates a
# third environment: do it deliberately.
#
# The two literals below are the entire isolation mechanism: the backend key is
# a compile-time constant of this directory, and `environment` drives every
# physical resource name inside the module.
#
# The environment token is "prod", not "production": the longest Lambda name is
# media-summarizer-worker-podcastindex_resolution-prod (52 of the 64 characters
# AWS allows), and "-production" would leave almost no headroom.
#
# When prod moves to its own AWS account, only the backend bucket and the
# provider block in THIS directory change — dev and staging are unaffected.

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "media-summarizer-tfstate-125313707865"
    key            = "env/prod/terraform.tfstate" # literal #1
    region         = "eu-west-3"
    encrypt        = true
    dynamodb_table = "media-summarizer-tfstate-lock"
  }
}

provider "aws" {
  region = "eu-west-3"

  default_tags {
    tags = {
      Project     = "media-summarizer"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}

data "terraform_remote_state" "shared" {
  backend = "s3"
  config = {
    bucket = "media-summarizer-tfstate-125313707865"
    key    = "env/shared/terraform.tfstate"
    region = "eu-west-3"
  }
}

module "platform" {
  source = "../../modules/platform"

  environment        = "prod" # literal #2
  ecr_repository_url = data.terraform_remote_state.shared.outputs.lambda_ecr_repository_url

  enable_alarms = true
  alert_email   = var.alert_email

  # No secret_payload on purpose (task-221 §7.3): Terraform creates the empty
  # secret shell and the owner populates it once out-of-band with
  #   aws secretsmanager put-secret-value --secret-id media-summarizer-runtime-prod ...
  # so no third-party credential is ever written to the Terraform state.
}

variable "alert_email" {
  description = "Address subscribed to the pipeline alerts SNS topic. Empty by default so no personal address lives in the repository: pass -var alert_email=... or subscribe out-of-band."
  type        = string
  default     = ""
}
