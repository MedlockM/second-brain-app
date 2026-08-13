# prod environment root — lives in its OWN AWS account.
#
# Since task-248 prod is AWS Organizations member account 866874944541, while dev
# stays in the management account 125313707865 that carries the whole history.
# This is the only hard isolation AWS offers: an IAM policy in dev cannot name a
# prod resource, a `terraform destroy` run with the dev profile cannot reach prod,
# and the bill splits per account for free. "Resource Groups" would not have done
# any of that — they are tag-based views with no permission or billing boundary.
#
# Credentials: no second key pair. `[profile prod]` in ~/.aws/config assumes into
# this account from the dev keys, so `AWS_PROFILE=prod terraform ...` just works.
# That profile is tracked at infrastructure/aws/config.example (it holds no
# secret); see infrastructure/terraform/README.md, "Two accounts, one set of keys".
#
# The two literals below are the isolation mechanism WITHIN an account: the
# backend key is a compile-time constant of this directory, and `environment`
# drives every physical resource name inside the module. Across accounts the
# provider block does the same job at a stronger level.
#
# The environment token is "prod", not "production": the longest Lambda name is
# media-summarizer-worker-podcastindex_resolution-prod (52 of the 64 characters
# AWS allows), and "-production" would leave almost no headroom.

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Prod's state lives in prod's own account, with prod's own lock table.
  # media-summarizer-tfstate-lock in 125313707865 is shared by envs/dev and
  # shared/, and is not reachable with the prod profile — sharing it would have
  # meant granting cross-account write access to the one resource whose entire
  # job is to be trustworthy. Bootstrapped by scripts/bootstrap_tf_backend.sh.
  backend "s3" {
    bucket         = "media-summarizer-tfstate-866874944541"
    key            = "env/prod/terraform.tfstate" # literal #1
    region         = "eu-west-3"
    encrypt        = true
    dynamodb_table = "media-summarizer-tfstate-lock"
  }
}

provider "aws" {
  region = "eu-west-3"

  # Refuse to do anything if the ambient credentials are not prod's. Without
  # this, forgetting AWS_PROFILE=prod would build a second copy of prod inside
  # the dev account — the backend would still be prod's, so the mistake would be
  # invisible in the state.
  allowed_account_ids = ["866874944541"]

  default_tags {
    tags = {
      Project     = "media-summarizer"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}

module "platform" {
  source = "../../modules/platform"

  environment        = "prod" # literal #2
  ecr_repository_url = var.shared_ecr_repository_url

  # MOTHBALLED until launch — owner decision of 2026-08-12, applied by task-248.
  #
  # This comment replaces an earlier one that forbade mothballing prod outright.
  # That instruction predates the decision and is not being bypassed silently:
  # the rule it encoded is still right, it is just narrower than it looked. A
  # production serving real users without alarms is a fault. A production with
  # zero users, zero rows and zero objects, waiting for a launch that is blocked
  # on App Store products and a domain that does not resolve yet, is not — it is
  # ~$7.20/mo of CloudWatch billed to watch nothing happen.
  #
  #   enable_alarms         1 SNS topic + 43 alarms  ~$3.30/mo
  #   enable_dashboard      1 dashboard              ~$3.00/mo
  #   enable_worker_polling 14 SQS event mappings    ~$0.90/mo
  #
  # THE MOTHBALLING IS TEMPORARY AND ENDS AT LAUNCH. Flipping these three
  # booleans back to true is a plan + apply and nothing else: no data move, no
  # recreation, and the event source mappings stay in the state the whole time.
  # Waking prod up is a prerequisite of taking the first paying user, not a
  # follow-up to it — the day a real account exists in prod, an unwatched prod is
  # once again the fault the original comment described.
  enable_alarms         = false
  enable_dashboard      = false
  enable_worker_polling = false
  alert_email           = var.alert_email

  # NO API reservation yet, and this one is NOT a cost decision — it is an AWS
  # quota wall discovered during the first apply.
  #
  # The module defaults every non-dev environment to a reservation of 10, which
  # is the right value: it guarantees the interactive API a slice of concurrency
  # that a worker burst cannot eat. But a BRAND NEW AWS account gets a Lambda
  # "Concurrent executions" quota of 10 instead of the usual 1000, and AWS
  # refuses any reservation that would leave fewer than 10 unreserved. So in this
  # account a reservation of 10 is arithmetically impossible:
  #
  #   PutFunctionConcurrency: InvalidParameterValueException: Specified
  #   ReservedConcurrentExecutions for function decreases account's
  #   UnreservedConcurrentExecution below its minimum value of [10].
  #
  # An increase to 1000 has been requested (Service Quotas L-B99A9384, PENDING at
  # the time of writing; find the request id with `aws service-quotas
  # list-requested-service-quota-change-history --service-code lambda` under the
  # prod profile — it is not recorded here because this repository is public).
  # LAUNCH PREREQUISITE: once it is granted, delete this line so the
  # module default of 10 applies again, then plan and apply. Until then prod
  # serves zero users, so an unreserved API changes nothing observable — but a
  # launched prod whose API competes with 14 workers over 10 total concurrent
  # executions would throttle under the first real load.
  api_reserved_concurrency = -1

  # No secret_payload on purpose (task-221 §7.3): Terraform creates the empty
  # secret shell and the owner populates it once out-of-band with
  #   aws secretsmanager put-secret-value --secret-id media-summarizer-runtime-prod ...
  # so no third-party credential is ever written to the Terraform state. Prod's
  # 37 credentials are task-252, owner-only: they must be distinct from dev's
  # (RevenueCat live, its own JWT_SECRET_KEY, its own Algolia index).
}

variable "shared_ecr_repository_url" {
  description = "URL of the ONE shared Lambda ECR repository. A literal, not a terraform_remote_state read: the registry stays in account 125313707865 (see shared/ecr.tf) whose state bucket the prod profile cannot read, and an environment root must never need two sets of credentials to plan."
  type        = string
  default     = "125313707865.dkr.ecr.eu-west-3.amazonaws.com/media-summarizer-lambda"
}

variable "alert_email" {
  description = "Address subscribed to the pipeline alerts SNS topic. Empty by default so no personal address lives in the repository: pass -var alert_email=... or subscribe out-of-band. Unused while enable_alarms = false."
  type        = string
  default     = ""
}
