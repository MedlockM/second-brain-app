# Spaced-repetition review tables.
#
# These three tables were read and written by the application (review_db.py,
# fsrs_service.py, api/endpoints/review.py, database_async.py RSS section) but
# had never been declared in Terraform — they only existed because the Python
# code fell back to a hardcoded unsuffixed name and something had created them
# out of band. task-237 removes those fallbacks, so the tables must be declared
# here or the corresponding endpoints would fail fast at runtime.
#
# The suffixed names are new objects: they cannot collide with whatever
# unsuffixed table currently exists in the account.

# Review schedule (FSRS cards): PK=user_id, SK=card_id
resource "aws_dynamodb_table" "review_schedule" {
  name         = "review_schedule${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "card_id"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "card_id"
    type = "S"
  }

  tags = {
    Name = "review_schedule${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# Per-user review preferences: PK=user_id
resource "aws_dynamodb_table" "user_review_settings" {
  name         = "user_review_settings${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  tags = {
    Name = "user_review_settings${local.suffix}"
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# User RSS feed subscriptions: PK=id, GSI user-index, GSI status-index
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

output "review_schedule_table_name" {
  value       = aws_dynamodb_table.review_schedule.name
  description = "Review schedule (FSRS cards) table name"
}

output "user_review_settings_table_name" {
  value       = aws_dynamodb_table.user_review_settings.name
  description = "User review settings table name"
}

output "user_rss_feeds_table_name" {
  value       = aws_dynamodb_table.user_rss_feeds.name
  description = "User RSS feed subscriptions table name"
}
