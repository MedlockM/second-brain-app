# dev environment root.
#
# The two literals below are the entire isolation mechanism: the backend key is
# a compile-time constant of this directory, and `environment` drives every
# physical resource name inside the module. There is no CLI flag, no workspace
# and no wrapper script that can point this directory at another environment.

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
    key            = "env/dev/terraform.tfstate" # literal #1
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
      Environment = "dev"
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

  environment        = "dev" # literal #2
  ecr_repository_url = data.terraform_remote_state.shared.outputs.lambda_ecr_repository_url

  # dev stays cheap: no CloudWatch alarms (43 alarms ≈ $3.30/mo measured) and
  # unreserved API concurrency. The dashboard and the worker SQS polling stay ON
  # — dev is the environment actually being worked in, so its ~$3.00/mo
  # dashboard and live queues are the point. See envs/staging/main.tf for the
  # mothballed counterpart.
  enable_alarms = false

  alert_email = var.alert_email
}

variable "alert_email" {
  description = "Address subscribed to the pipeline alerts SNS topic. Unused while enable_alarms = false."
  type        = string
  default     = ""
}
