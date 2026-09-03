# Consolidated Secrets Manager entry for all runtime secrets the application
# reads via os.getenv(). One JSON secret per environment (dev, staging, prod).
# The Lambda cold-start hook (media_summarizer/workers/lambda_handlers.py and
# media_summarizer/api/lambda_handler.py) reads RUNTIME_SECRET_NAME and calls
# os.environ.setdefault() for each key, so Terraform-injected variables always
# win over secret keys of the same name.
#
# Terraform creates the secret SHELL ONLY and never writes its value
# (task-221 §7.3): `secret_string` is stored in PLAINTEXT inside the Terraform
# state, and with three environments that would mean three plaintext copies of
# every third-party credential in the state bucket.
#
# Populate or rotate a secret out-of-band, then redeploy the consumers so the
# cold start picks up the new values:
#
#   aws secretsmanager put-secret-value \
#     --secret-id media-summarizer-runtime-<env> \
#     --secret-string file://runtime-secrets.json   # then delete the local file
#
# The two secrets are SEPARATE AWS objects in separate accounts: copying a value
# from dev to prod creates no live link, and changing dev's copy later does not
# touch prod. So a per-environment value is only warranted when SHARING the value
# is what couples the environments. That is the case for exactly three keys, and
# prod holds its own (task-252): JWT_SECRET_KEY and PRICING_ADMIN_SECRET, because
# a shared signing secret means a token minted by dev is accepted by prod; and
# REVENUCAT_WEBHOOK_SECRET, because each RevenueCat webhook integration carries
# its own Authorization header (dev's is filtered to sandbox purchases, prod's to
# production purchases).
#
# Everything else is copied from dev, deliberately. Third-party quotas that are
# shared (Apify credits are per user, OpenAI rate limits and Deepgram credits are
# per project) stay shared whether or not the keys differ — a fresh key repairs
# nothing there, only a second account or project would. task-252 lists the
# accepted consequences key by key.
#
# Algolia needs no index variable: the code derives it as
# media_items_{ENVIRONMENT} (utils/algolia_client.py), so the environments write
# to separate indices structurally. The Admin key is nonetheless account-wide;
# scoping each environment's key to its own index is an open item on task-252.

resource "aws_secretsmanager_secret" "runtime" {
  name        = "${var.project_name}-runtime${local.suffix}"
  description = "Consolidated runtime secrets for ${var.project_name} ${var.environment}. Value is managed out-of-band, never by Terraform."

  tags = {
    Name = "${var.project_name}-runtime${local.suffix}"
  }
}

# Empty initial version so the secret exists and is readable before the first
# out-of-band `put-secret-value`. ignore_changes means Terraform never proposes
# to overwrite whatever the owner has populated.
resource "aws_secretsmanager_secret_version" "runtime" {
  secret_id     = aws_secretsmanager_secret.runtime.id
  secret_string = jsonencode({})

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# IAM policy granting GetSecretValue on the runtime secret. Attach it to any
# role that needs to read secrets (Lambda execution roles).
resource "aws_iam_policy" "runtime_secret_read" {
  name        = "${var.project_name}-runtime-secret-read${local.suffix}"
  description = "Allows reading the consolidated runtime secret."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.runtime.arn
      }
    ]
  })
}

# Outputs so other modules / Lambda definitions can wire the secret into their
# `environment` or `secrets` blocks without re-declaring it.
output "runtime_secret_arn" {
  description = "ARN of the consolidated runtime secret."
  value       = aws_secretsmanager_secret.runtime.arn
}

output "runtime_secret_name" {
  description = "Name of the consolidated runtime secret (for AWS CLI lookups)."
  value       = aws_secretsmanager_secret.runtime.name
}
