# User RSS feed subscriptions.
#
# This table was declared in the old `dynamodb_review_tables.tf`, which despite
# its name held three unrelated tables: the two FSRS ones and this one. task-364
# removed FSRS and deleted that whole file, taking this declaration with it and
# leaving `USER_RSS_FEEDS_TABLE` in runtime_env.tf pointing at nothing —
# `terraform validate` failed on the dangling reference. Restored here under a
# name that says what it holds.
#
# It is not dead code: `database_async.py` resolves the table through
# `required_env("USER_RSS_FEEDS_TABLE")`, so every Lambda fails fast at import
# without it, and `account_deletion_service.py` clears it on account deletion.
# The RSS subscription feature (task-58) reads and writes it.

# PK=id, GSI user-index, GSI status-index
resource "aws_dynamodb_table" "user_rss_feeds" {
  name         = "user_rss_feeds${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "user-index"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    projection_type = "ALL"
  }

  tags = {
    Name = "user_rss_feeds${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

output "user_rss_feeds_table_name" {
  value       = aws_dynamodb_table.user_rss_feeds.name
  description = "User RSS feed subscriptions table name"
}
