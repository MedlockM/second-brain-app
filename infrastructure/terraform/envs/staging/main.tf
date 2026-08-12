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

  # MOTHBALLED 2026-08-12 — owner decision: staging must not cost money until
  # Phase 9 of docs/V1_LAUNCH_PLAN.md actually uses it. Every table, bucket,
  # queue and Lambda stays in place (all empty: 0 rows, 0 objects); only the
  # metered extras are switched off. Measured on Cost Explorer: creating staging
  # took the whole account from $0.233/day to $0.295/day (+27%), i.e. ~$7.60/mo
  # for an environment with no users, on an account that billed $8.11 in July.
  #
  #   enable_alarms         43 alarms          ~$3.30/mo
  #   enable_dashboard      1 dashboard        ~$3.00/mo
  #   enable_worker_polling 14 SQS mappings    ~$0.90/mo
  #
  # Flip all three back to true to wake staging up — that is the whole of
  # Phase 9 step 1. Deliberately NOT a destroy: the environment is a validated
  # prod rehearsal and rebuilding it costs far more than $7.60.
  enable_alarms         = false
  enable_dashboard      = false
  enable_worker_polling = false
  alert_email           = var.alert_email

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
