# =============================================================================
# Naming convention (task-221 / task-237)
# =============================================================================
#
# Every physical resource name created by this module ends with local.suffix, so
# a plan run from envs/staging can never name a resource that belongs to
# envs/dev. S3 buckets, the runtime secret and the SNS topic were already
# suffixed before task-237 and keep their existing pattern.

locals {
  suffix = "-${var.environment}"
  prefix = "${var.project_name}-${var.environment}"
}
