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
