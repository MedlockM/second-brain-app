# =============================================================================
# Backup and archiving of the user-owned library (task-243, §6.4)
#
# Three tiers, three explicit restore windows. They are tiers and not
# redundancy: each one covers a failure the previous one cannot.
#
#   PITR (35 days, on the tables themselves)
#       Recovers from a bad write to the second. This is the tier that would
#       have saved the rows lost in the task-218 incident, and the one
#       processing_jobs and user_folders did not have.
#
#   AWS Backup snapshots (weekly, 90 days, this file)
#       Recovers from something PITR cannot: the table itself being deleted or
#       corrupted beyond its continuous-backup window, and a mistake that is
#       only noticed a month later. Kept in a vault, i.e. outside the table's
#       own lifecycle.
#
#   S3 exports (monthly, 365 days, this file)
#       Recovers from losing the AWS Backup vault, and is the only tier that is
#       readable without DynamoDB at all (DYNAMODB_JSON in the archives bucket,
#       queryable with Athena). It is also the audit trail: a monthly frozen
#       copy of what the library contained.
#
# A restore is NOT transparent, and the runbook says so in more detail:
# DynamoDB restores into a NEW table, and the restored table does NOT carry the
# TTL configuration over. Re-enabling the `purge_at` TTL is a mandatory step of
# every restore — which is exactly what the `purge-overdue` alarm in
# durable_media_alerts.tf detects when it is forgotten.
#
# Runbook: infrastructure/observability/runbooks/durable-media.md#restore
# Retention reference: docs/DATA_RETENTION.md
# =============================================================================

variable "enable_library_backups" {
  description = "Provision the AWS Backup vault/plan and the monthly S3 exports for the user-owned tables. Storage-billed only (~$0.10/GB-month for snapshots, GLACIER_IR for exports), which is cents on tables this size. Set false only for an environment that holds no real user data."
  type        = bool
  default     = true
}

variable "library_backup_schedule" {
  description = "Weekly AWS Backup window for the user-owned tables (UTC)."
  type        = string
  default     = "cron(0 4 ? * SUN *)"
}

variable "library_backup_retention_days" {
  description = "How long a weekly snapshot stays restorable. 90 days per §6.4: long enough that a mistake noticed a month later is still recoverable."
  type        = number
  default     = 90
}

variable "library_export_schedule" {
  description = "Monthly DynamoDB point-in-time export to the archives bucket (UTC)."
  type        = string
  default     = "cron(0 5 1 * ? *)"
}

locals {
  # The user-owned stores. Everything here is data a user created and that no
  # clock but their own may destroy; the operational tables (processing_jobs,
  # idempotence locks, auth tokens) are deliberately absent because losing them
  # costs a re-run, not a library.
  #
  # Keys are used in resource names and S3 prefixes, so they stay hyphenated.
  library_backup_tables = {
    "user-media" = {
      arn  = aws_dynamodb_table.user_media_v1.arn
      name = aws_dynamodb_table.user_media_v1.name
    }
    "user-folders" = {
      arn  = aws_dynamodb_table.user_folders_v1.arn
      name = aws_dynamodb_table.user_folders_v1.name
    }
    "user-tags" = {
      arn  = aws_dynamodb_table.user_tags_v1.arn
      name = aws_dynamodb_table.user_tags_v1.name
    }
    "media-artifacts" = {
      arn  = aws_dynamodb_table.media_artifacts_v1.arn
      name = aws_dynamodb_table.media_artifacts_v1.name
    }
  }

  library_export_prefix = "dynamodb-exports"
}

# -----------------------------------------------------------------------------
# Tier 2: AWS Backup, weekly, 90 days.
# -----------------------------------------------------------------------------

resource "aws_backup_vault" "library" {
  count = var.enable_library_backups ? 1 : 0

  name = "${var.project_name}-library${local.suffix}"

  # No force_destroy on purpose: a vault holding recovery points refuses to be
  # destroyed, which is the cheapest possible guard against `terraform destroy`
  # taking the backups with the tables.

  tags = {
    Name = "${var.project_name}-library${local.suffix}"
  }
}

resource "aws_backup_plan" "library" {
  count = var.enable_library_backups ? 1 : 0

  name = "${var.project_name}-library${local.suffix}"

  rule {
    rule_name         = "weekly"
    target_vault_name = aws_backup_vault.library[0].name
    schedule          = var.library_backup_schedule

    # 1h to start, 8h to finish (AWS requires completion >= start + 60, and both
    # are counted from the scheduled time). Generous because a missed window is a
    # silent gap in the retention, and these tables are small enough that the job
    # takes minutes.
    start_window      = 60
    completion_window = 480

    lifecycle {
      delete_after = var.library_backup_retention_days
    }
  }

  tags = {
    Name = "${var.project_name}-library${local.suffix}"
  }
}

resource "aws_iam_role" "backup_library" {
  count = var.enable_library_backups ? 1 : 0

  name = "${var.project_name}-backup-library${local.suffix}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-backup-library${local.suffix}"
  }
}

resource "aws_iam_role_policy_attachment" "backup_library_backup" {
  count = var.enable_library_backups ? 1 : 0

  role       = aws_iam_role.backup_library[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

# Restores use the same role. Attached now rather than during an incident: a
# restore runbook whose first step is "create an IAM role" is a runbook that has
# never been exercised.
resource "aws_iam_role_policy_attachment" "backup_library_restore" {
  count = var.enable_library_backups ? 1 : 0

  role       = aws_iam_role.backup_library[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
}

resource "aws_backup_selection" "library" {
  count = var.enable_library_backups ? 1 : 0

  name         = "${var.project_name}-library${local.suffix}"
  iam_role_arn = aws_iam_role.backup_library[0].arn
  plan_id      = aws_backup_plan.library[0].id

  # Explicit ARNs, not a tag selector: a table silently dropping out of the
  # backup plan because a tag was edited is exactly the class of invisible
  # failure §6.5 is about.
  resources = [for table in local.library_backup_tables : table.arn]
}

# -----------------------------------------------------------------------------
# Tier 3: monthly ExportTableToPointInTime into the archives bucket.
#
# EventBridge Scheduler calls the DynamoDB API directly (universal target), so
# there is no Lambda to maintain, no image to deploy and nothing to page on
# except the export job's own status.
# -----------------------------------------------------------------------------

resource "aws_iam_role" "library_export" {
  count = var.enable_library_backups ? 1 : 0

  name = "${var.project_name}-library-export${local.suffix}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-library-export${local.suffix}"
  }
}

resource "aws_iam_policy" "library_export" {
  count = var.enable_library_backups ? 1 : 0

  name        = "${var.project_name}-library-export-policy${local.suffix}"
  description = "Export the user-owned tables to the archives bucket (task-243 §6.4)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:ExportTableToPointInTime",
          "dynamodb:DescribeTable",
          "dynamodb:DescribeContinuousBackups"
        ]
        Resource = [for table in local.library_backup_tables : table.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${aws_s3_bucket.archives.arn}/${local.library_export_prefix}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation", "s3:ListBucket"]
        Resource = aws_s3_bucket.archives.arn
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-library-export-policy${local.suffix}"
  }
}

resource "aws_iam_role_policy_attachment" "library_export" {
  count = var.enable_library_backups ? 1 : 0

  role       = aws_iam_role.library_export[0].name
  policy_arn = aws_iam_policy.library_export[0].arn
}

resource "aws_scheduler_schedule" "library_export" {
  for_each = var.enable_library_backups ? local.library_backup_tables : {}

  name                = "${var.project_name}-export-${each.key}${local.suffix}"
  schedule_expression = var.library_export_schedule

  # UTC everywhere, so the archive prefixes line up with the log timestamps of
  # whatever incident is being investigated.
  schedule_expression_timezone = "UTC"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:dynamodb:exportTableToPointInTime"
    role_arn = aws_iam_role.library_export[0].arn

    input = jsonencode({
      TableArn     = each.value.arn
      S3Bucket     = aws_s3_bucket.archives.bucket
      S3Prefix     = "${local.library_export_prefix}/${each.value.name}"
      ExportFormat = "DYNAMODB_JSON"
    })

    retry_policy {
      maximum_retry_attempts = 3
    }
  }
}

output "library_backup_vault_name" {
  description = "AWS Backup vault holding the weekly snapshots of the user-owned tables."
  value       = var.enable_library_backups ? aws_backup_vault.library[0].name : ""
}

output "library_export_prefix" {
  description = "S3 prefix in the archives bucket where the monthly DynamoDB exports land."
  value       = "s3://${aws_s3_bucket.archives.bucket}/${local.library_export_prefix}/"
}
