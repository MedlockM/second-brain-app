# Single source of truth for the resource names injected into the Lambda
# runtimes and for the IAM policies that scope access to them.
#
# Before task-237 the Python code carried a hardcoded unsuffixed default for
# every table, queue and bucket name (`os.environ.get("USERS_TABLE", "users")`).
# Those defaults were silently correct for dev and catastrophic for any second
# environment. They are now gone: the code fails fast when a name is missing,
# which means every name the application reads MUST appear in one of the maps
# below.

locals {
  # -------------------------------------------------------------------------
  # DynamoDB tables
  # -------------------------------------------------------------------------
  table_names = {
    USERS_TABLE                   = aws_dynamodb_table.users_v2.name
    PROCESSING_JOBS_TABLE         = aws_dynamodb_table.processing_jobs_v1.name
    AUTH_TOKENS_TABLE             = aws_dynamodb_table.auth_tokens_v1.name
    MEDIA_IDEMPOTENCE_TABLE       = aws_dynamodb_table.media_idempotence_v1.name
    USER_MEDIA_TABLE              = aws_dynamodb_table.user_media_v1.name
    MEDIA_ARTIFACTS_TABLE         = aws_dynamodb_table.media_artifacts_v1.name
    ARTIFACT_IDEMPOTENCE_TABLE    = aws_dynamodb_table.artifact_idempotence_v1.name
    TRANSLATION_IDEMPOTENCE_TABLE = aws_dynamodb_table.translation_idempotence_v1.name
    MEDIA_WATCHERS_TABLE          = aws_dynamodb_table.media_watchers_v1.name
    USER_TAGS_TABLE               = aws_dynamodb_table.user_tags_v1.name
    USER_FOLDERS_TABLE            = aws_dynamodb_table.user_folders_v1.name
    PRICING_CONFIG_TABLE          = aws_dynamodb_table.pricing_config_v1.name
    USER_DIGESTS_TABLE            = aws_dynamodb_table.user_digests_v1.name
    USER_DIGEST_SETTINGS_TABLE    = aws_dynamodb_table.user_digest_settings_v1.name
    SUBSCRIPTIONS_TABLE           = aws_dynamodb_table.subscriptions.name
    FOLLOWS_TABLE                 = aws_dynamodb_table.follows.name
    FEED_FORECASTS_TABLE          = aws_dynamodb_table.feed_forecasts.name
    USER_USAGE_MONTHLY_TABLE      = aws_dynamodb_table.user_usage_monthly.name
    USER_USAGE_DAILY_TABLE        = aws_dynamodb_table.user_usage_daily.name
    REVENUCAT_EVENTS_TABLE        = aws_dynamodb_table.revenucat_events.name
    BUG_REPORTS_TABLE             = aws_dynamodb_table.bug_reports.name
    REVIEW_SCHEDULE_TABLE         = aws_dynamodb_table.review_schedule.name
    USER_REVIEW_SETTINGS_TABLE    = aws_dynamodb_table.user_review_settings.name
    USER_RSS_FEEDS_TABLE          = aws_dynamodb_table.user_rss_feeds.name
  }

  # Every table this environment owns, plus its indexes, matched through the
  # environment suffix that task-237 appends to 100% of the table names. Used to
  # scope the Lambda IAM policies away from the account-wide "table/*" they used
  # to grant.
  #
  # This is a wildcard rather than the 24 explicit ARNs on purpose: enumerating
  # them (48 ARNs with the indexes) pushes the managed policy past the hard
  # 6144-byte quota and the apply fails with `LimitExceeded: Cannot exceed quota
  # for PolicySize: 6144`. The suffix wildcard keeps the property that matters —
  # a dev Lambda cannot address a -staging or -prod table, nor any of the legacy
  # unsuffixed tables — and it survives the next table being added.
  table_arns = [
    "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/*${local.suffix}",
    "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/*${local.suffix}/index/*",
  ]

  # -------------------------------------------------------------------------
  # SQS queues
  # -------------------------------------------------------------------------
  queue_names = {
    PODCASTINDEX_RESOLUTION_QUEUE = aws_sqs_queue.rss_resolution.name
    ARTICLE_EXTRACTION_QUEUE      = aws_sqs_queue.article_extraction.name
    X_INGESTION_QUEUE             = aws_sqs_queue.x_ingestion.name
    YOUTUBE_INGESTION_QUEUE       = aws_sqs_queue.youtube_ingestion.name
    INSTAGRAM_INGESTION_QUEUE     = aws_sqs_queue.instagram_ingestion.name
    TIKTOK_INGESTION_QUEUE        = aws_sqs_queue.tiktok_ingestion.name
    DEEPGRAM_TRANSCRIPTION_QUEUE  = aws_sqs_queue.deepgram_transcription.name
    ARTIFACT_GENERATOR_QUEUE      = aws_sqs_queue.artifact_generator.name
    DOCUMENT_PARSING_QUEUE        = aws_sqs_queue.document_parsing.name
    SEARCH_INDEXING_QUEUE         = aws_sqs_queue.search_indexing.name
    RSS_FEED_POLL_QUEUE           = aws_sqs_queue.rss_feed_poll.name
    TRANSCRIPT_TRANSLATION_QUEUE  = aws_sqs_queue.transcript_translation.name

    # Canonical name settled by task-143: every producer and the single consumer
    # read EPISODE_COMPLETED_EVENTS_QUEUE. Enforced by a guard in
    # .github/workflows/pr.yml.
    EPISODE_COMPLETED_EVENTS_QUEUE = aws_sqs_queue.media_completed_events.name
  }

  # -------------------------------------------------------------------------
  # S3 buckets
  # -------------------------------------------------------------------------
  bucket_names = {
    AUDIO_BUCKET            = aws_s3_bucket.audio.bucket
    TRANSCRIPT_BUCKET       = aws_s3_bucket.transcripts.bucket
    SUMMARY_BUCKET          = aws_s3_bucket.summaries.bucket
    SUMMARY_SHORT_BUCKET    = aws_s3_bucket.summary_short.bucket
    SUMMARY_DETAILED_BUCKET = aws_s3_bucket.summary_detailed.bucket
    NOTES_BUCKET            = aws_s3_bucket.notes.bucket
    FLASHCARDS_BUCKET       = aws_s3_bucket.flashcards.bucket
    QUIZ_BUCKET             = aws_s3_bucket.quiz.bucket
    DOCUMENT_BUCKET         = aws_s3_bucket.documents.bucket
    ARCHIVE_BUCKET          = aws_s3_bucket.archives.bucket
    BUG_REPORTS_BUCKET      = aws_s3_bucket.bug_reports.bucket
  }

  # -------------------------------------------------------------------------
  # The complete environment block shared by the API and every worker Lambda.
  # -------------------------------------------------------------------------
  lambda_environment = merge(
    {
      ENVIRONMENT         = var.environment
      RUNTIME_SECRET_NAME = aws_secretsmanager_secret.runtime.name
      # AWS_DEFAULT_REGION is reserved by the Lambda runtime; boto3 reads it
      # automatically from the execution context. See
      # https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html#configuration-envvars-runtime

      # Kill-switch for durable user_media *writes* (task-240 Phase 1). Read at
      # call time, so an emergency rollback is `aws lambda
      # update-function-configuration --environment
      # ...DURABLE_MEDIA_ENABLED=0` on the affected function; set the variable
      # below to false to make that rollback durable across applies.
      #
      # Since task-220 (Phase 3) the library, Search and folder READS come from
      # user_media unconditionally, so flipping this off alone would leave users
      # with an empty library. It is no longer a standalone rollback: it must be
      # paired with a code rollback to the pre-task-220 revision.
      DURABLE_MEDIA_ENABLED = var.durable_media_enabled ? "1" : "0"

      # Job TTL window (task-242, Phase 4). The processing_jobs table TTL is
      # re-enabled with a configurable window. Default: 90 days (conservative,
      # preserves debugging trails). The job creation code reads this to set
      # the expire_at timestamp. Range: 30-90 days.
      PROCESSING_JOBS_TTL_DAYS = tostring(var.processing_jobs_ttl_days)
    },
    local.bucket_names,
    local.table_names,
    local.queue_names,
  )
}

output "table_names" {
  description = "Map of environment-variable name to DynamoDB table name for this environment."
  value       = local.table_names
}

output "queue_names" {
  description = "Map of environment-variable name to SQS queue name for this environment."
  value       = local.queue_names
}
