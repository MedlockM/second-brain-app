# staging environment root — A BLUEPRINT, NOT A LIVE ENVIRONMENT.
#
# staging was destroyed by task-248 and promoted into prod (the environment token
# is ForceNew on nearly every resource, so promoting an environment is a destroy
# plus an apply elsewhere, never a rename). `env/staging/terraform.tfstate` is an
# empty state; nothing named "-staging" exists on AWS.
#
# The directory is kept on purpose: `terraform apply` here builds a full,
# disposable third copy of the platform for an afternoon of testing before a
# risky migration, and the teardown path has now been walked end to end for real.
#
# READ THIS BEFORE APPLYING IT AGAIN:
#   * It lands in the DEV account (125313707865) — see the backend and the absence
#     of `allowed_account_ids` below. It is therefore the one remaining case where
#     `scripts/tf_plan_guard.sh staging tfplan dev` does real work, because two
#     environments would then share one account. Run it.
#   * Its runtime secret shell will be empty, and the previous
#     media-summarizer-runtime-staging was force-deleted, so the name is free.
#   * Deleting it again means repeating the destroy dance: lift
#     `deletion_protection_enabled` on every table by hand first, and force-delete
#     the secret, or the name stays blocked for 30 days.
#
# The two literals below are the entire isolation mechanism WITHIN an account: the
# backend key is a compile-time constant of this directory, and `environment`
# drives every physical resource name inside the module. A plan run here can only
# propose changes to resources present in THIS state, and can only name resources
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

  # The three metered extras stay off in this blueprint. When staging existed they
  # cost, measured on Cost Explorer, ~$7.60/month for an environment with zero
  # users — it took the whole account from $0.233/day to $0.295/day (+27%) on an
  # account that billed $8.11 in July.
  #
  #   enable_alarms         43 alarms          ~$3.30/mo
  #   enable_dashboard      1 dashboard        ~$3.00/mo
  #   enable_worker_polling 14 SQS mappings    ~$0.90/mo
  #
  # A short-lived rehearsal environment needs none of them: you are watching it by
  # hand for a few hours. `enable_worker_polling` is the one to consider flipping,
  # and only if the rehearsal actually needs queues to drain by themselves.
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
