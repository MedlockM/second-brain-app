# Outputs consumed by CI (deploy-lambda.yml) and by the operator.

output "environment" {
  description = "Environment token owned by this root."
  value       = "staging"
}

output "api_endpoint" {
  description = "Public base URL of this environment's API."
  value       = module.platform.api_endpoint
}

output "api_function_name" {
  description = "Name of this environment's API Lambda function."
  value       = module.platform.api_function_name
}

output "api_gateway_id" {
  description = "API Gateway HTTP API ID. Stable across the task-237 rename."
  value       = module.platform.api_gateway_id
}

output "worker_function_names" {
  description = "Names of this environment's worker Lambda functions."
  value       = module.platform.worker_function_names
}

output "runtime_secret_name" {
  description = "Secrets Manager secret holding this environment's runtime configuration."
  value       = module.platform.runtime_secret_name
}

# Resource-name maps. Re-exposed from the module so an operator can read the real
# names of this environment instead of guessing at the suffix -- the code has no
# fallback for them (task-237), so a wrong name fails at import. .env.example
# points here for any environment other than dev.
output "table_names" {
  description = "Map of environment-variable name to DynamoDB table name."
  value       = module.platform.table_names
}

output "queue_names" {
  description = "Map of environment-variable name to SQS queue name."
  value       = module.platform.queue_names
}

output "bucket_names" {
  description = "Map of environment-variable name to S3 bucket name."
  value       = module.platform.bucket_names
}
