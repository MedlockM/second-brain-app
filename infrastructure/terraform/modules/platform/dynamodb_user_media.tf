# =============================================================================
# user_media -- the durable library record (task-240, Phase 1)
#
# Owner-validated Option A of
# docs/research/task-218-durable-media-library-persistence/README.md, §4.1.
#
# This table is the single source of truth for "what is in my library".
# `processing_jobs` is demoted to purely operational state that is free to
# expire, which is only safe because nothing user-facing depends on it any more.
#
# Two properties are load-bearing and must not be edited casually:
#
#   1. `purge_at` is the ONLY TTL attribute, and only a user-initiated deletion
#      may ever write it (invariant I2). No processing-driven TTL exists here.
#      The whole incident documented in §1.2 was a retention clock owned by the
#      pipeline being applied to user-owned data.
#   2. PITR is enabled from day one. `processing_jobs` and `user_folders` were
#      created without it, which is why the rows already lost are unrecoverable
#      (§1.5).
# =============================================================================

resource "aws_dynamodb_table" "user_media_v1" {
  name         = "user_media${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "media_item_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  # One random opaque "mi_" id per save. Content identity lives separately in
  # media_key, so several rows may point at the same processed content.
  attribute {
    name = "media_item_id"
    type = "S"
  }

  attribute {
    name = "media_key"
    type = "S"
  }

  attribute {
    name = "saved_at"
    type = "S"
  }

  # "<folder_id>#<saved_at>", so one folder's contents are a single Query
  # with a begins_with condition instead of a full-partition scan-and-filter.
  attribute {
    name = "folder_sort_key"
    type = "S"
  }

  # The engagement clock behind the Inbox "Continue learning" row (task-303,
  # Option A). ISO-8601, ABSENT until the user first launches a generation on this
  # item or opens one of its artifacts -- which is what keeps engaged-index below
  # sparse: one index entry per *engaged* item, not one per library row.
  #
  # Declared here only because the index below keys on it. The provider documents
  # that an `attribute` block which is neither a table key nor an index key
  # produces an infinite plan loop, so this block and that index move together.
  attribute {
    name = "last_engaged_at"
    type = "S"
  }

  # Local secondary indexes MUST be declared at table creation and can never be
  # added later, so §4.1 declares them now even though Phase 1 does not read
  # them: the alternative is recreating the authoritative library table.
  # They keep reads strongly consistent, which matters for read-after-save.
  local_secondary_index {
    name            = "saved-at-index"
    range_key       = "saved_at"
    projection_type = "ALL"
  }

  # Cross-user fan-out from one globally deduplicated processing job to every
  # save of that content. Also lets the purge cascade keep shared content until
  # the final visible reference disappears.
  global_secondary_index {
    name            = "media-key-index"
    hash_key        = "media_key"
    range_key       = "media_item_id"
    projection_type = "ALL"
  }

  local_secondary_index {
    name            = "folder-index"
    range_key       = "folder_sort_key"
    projection_type = "ALL"
  }

  # "Continue learning", in one bounded Query: newest engagements first, windowed
  # by a sort-key range condition on last_engaged_at (90 days, so the row empties
  # itself), capped by Limit.
  #
  # A GSI and not an LSI, deliberately: an LSI can only be created *with* the
  # table (see the comment above), and this table carries prevent_destroy,
  # deletion protection and PITR. A GSI is an online UpdateTable -- the table stays
  # available while the backfill runs, and the index is simply not queryable until
  # it reports ACTIVE. That is why the row is empty on the first deploy.
  #
  # INCLUDE and not ALL: the projected attributes are exactly what a tile draws, so
  # the read path is render-ready with no fetch back to the table. `deleted_at` is
  # projected so the read can drop a row the user soft-deleted before its purge_at
  # TTL sweeps it -- the signal disappears with its subject, which is the whole
  # reason task-303 stores it here instead of in an activity table.
  # user_id / media_item_id come for free: DynamoDB always projects the base keys.
  global_secondary_index {
    name            = "engaged-index"
    hash_key        = "user_id"
    range_key       = "last_engaged_at"
    projection_type = "INCLUDE"
    non_key_attributes = [
      "title",
      "creator_name",
      "thumbnail_url",
      "media_type",
      "deleted_at",
    ]
  }

  # THE ONLY TTL ON THIS TABLE, and it is user-driven.
  # `purge_at` is written exclusively by the user-deletion use case; the write
  # helpers in media_summarizer/utils/user_media.py reject it everywhere else.
  # Nothing about processing may ever expire a library row: that is the bug this
  # table exists to remove. Do not add a second TTL attribute here.
  ttl {
    attribute_name = "purge_at"
    enabled        = true
  }

  # NEW_AND_OLD_IMAGES rather than OLD_IMAGE: the stream is the substrate for the
  # deletion cascade (artifacts, S3, search records) and for the
  # user_media-vs-media_artifacts reconciliation of §6.5, both of which need the
  # post-image too.
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "user_media${local.suffix}"
  }
}

output "user_media_table_name" {
  value       = aws_dynamodb_table.user_media_v1.name
  description = "Durable user media library table name (task-240)"
}
