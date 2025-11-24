# DynamoDB table for Spotify playlist follows/tracking

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_dynamodb_table" "spotify_playlist_follows" {
  name         = "spotify_playlist_follows"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "playlist_id"
  
  attribute {
    name = "user_id"
    type = "S"
  }
  
  attribute {
    name = "playlist_id"
    type = "S"
  }
  
  tags = {
    Name        = "spotify_playlist_follows"
    Environment = var.environment
    Project     = var.project_name
  }
}

output "spotify_playlist_follows_table_name" {
  value = aws_dynamodb_table.spotify_playlist_follows.name
}
