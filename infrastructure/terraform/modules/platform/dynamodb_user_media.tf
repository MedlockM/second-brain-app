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
