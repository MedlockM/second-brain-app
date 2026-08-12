# staging environment root.
#
# The two literals below are the entire isolation mechanism: the backend key is
# a compile-time constant of this directory, and `environment` drives every
# physical resource name inside the module. A plan run here can only propose
# changes to resources present in THIS state, and can only name resources
# ending in "-staging".

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
    key            = "env/staging/terraform.tfstate" # literal #1
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
      Environment = "staging"
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

  environment        = "staging" # literal #2
  ecr_repository_url = data.terraform_remote_state.shared.outputs.lambda_ecr_repository_url

  # staging rehearses prod: alarms on, reserved concurrency defaulted to 10.
  enable_alarms = true
  alert_email   = var.alert_email

  # No secret_payload on purpose (task-221 §7.3): Terraform creates the empty
  # secret shell and the owner populates it once out-of-band with
  #   aws secretsmanager put-secret-value --secret-id media-summarizer-runtime-staging ...
  # so no third-party credential is ever written to the Terraform state.
}

variable "alert_email" {
  description = "Address subscribed to the pipeline alerts SNS topic. Empty by default so no personal address lives in the repository: pass -var alert_email=... or subscribe out-of-band."
  type        = string
  default     = ""
}
