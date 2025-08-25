########################################################
# IAM Outputs
########################################################

output "agentcore_runtime_lambda_role_arn" {
  description = "ARN of the IAM role for Bedrock AgentCore Runtime Lambda function"
  value       = aws_iam_role.agentcore_runtime_lambda_role.arn
}


output "agentcore_runtime_lambda_role_name" {
  description = "Name of the IAM role for Bedrock AgentCore Runtime Lambda function"
  value       = aws_iam_role.agentcore_runtime_lambda_role.name
}

output "bedrock_agentcore_runtime_policy_arn" {
  description = "ARN of the IAM policy for Bedrock AgentCore Runtime"
  value       = aws_iam_policy.bedrock_agentcore_runtime_policy.arn
}

########################################################
# Lambda Outputs
########################################################

output "bedrock_agentcore_memory_lambda_function_arn" {
  description = "ARN of the Lambda function for Bedrock AgentCore memory setup"
  value       = aws_lambda_function.agentcore_memory_setup.arn
}

output "bedrock_agentcore_memory_lambda_function_name" {
  description = "Name of the Lambda function for Bedrock AgentCore memory setup"
  value       = aws_lambda_function.agentcore_memory_setup.function_name
}

output "bedrock_agentcore_memory_lambda_invoke_arn" {
  description = "Invoke ARN of the Lambda function for Bedrock AgentCore memory setup"
  value       = aws_lambda_function.agentcore_memory_setup.invoke_arn
}

output "bedrock_agentcore_runtime_controller_function_arn" {
  description = "ARN of the Lambda function for Bedrock AgentCore Runtime Controller"
  value       = aws_lambda_function.bedrock_agentcore_runtime_controller.arn
}

output "bedrock_agentcore_runtime_controller_function_name" {
  description = "Function name of the AgentCore Runtime Controller Lambda"
  value       = aws_lambda_function.bedrock_agentcore_runtime_controller.function_name
}

########################################################
# Configuration Outputs
########################################################

output "memory_retention_days" {
  description = "Configured memory retention period in days"
  value       = var.bedrock_agentcore_memory_retention_days
}

output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

########################################################
# S3 Outputs
########################################################

output "agentcore_runtime_zip_files_bucket_id" {
  description = "ID of the S3 bucket for agentcore runtime zip files"
  value       = aws_s3_bucket.agentcore_runtime_zip_files.id
}

output "agentcore_runtime_zip_files_bucket_arn" {
  description = "ARN of the S3 bucket for agentcore runtime zip files"
  value       = aws_s3_bucket.agentcore_runtime_zip_files.arn
}

output "agentcore_runtime_zip_files_bucket_domain_name" {
  description = "Domain name of the S3 bucket for agentcore runtime zip files"
  value       = aws_s3_bucket.agentcore_runtime_zip_files.bucket_domain_name
}
