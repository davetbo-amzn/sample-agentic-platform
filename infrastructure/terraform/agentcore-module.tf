####################################################################
# AWS Bedrock AgentCore Memory Gateway - Module Import
#
# This file imports the AgentCore memory gateway module into the
# main Terraform configuration.
####################################################################

module "bedrock_agentcore" {
  source = "./agentcore"
  
  # Pass required variables to the module
  environment_name = var.environment_name
  aws_region       = var.aws_region
  
  # Optional: Override default memory retention period
  bedrock_agentcore_memory_retention_days = lookup(var.service_configuration, "agentcore_memory_retention_days", 30)
  
  # Pass common tags
  tags = local.common_tags
  
  # Dependencies
  depends_on = [
    # Add dependencies as needed
    # For example, if we need to ensure networking is set up first
    module.networking
  ]
}

# Expose outputs from the module
output "bedrock_agentcore_lambda_role_arn" {
  description = "ARN of the IAM role for Bedrock AgentCore Lambda function"
  value       = module.bedrock_agentcore.bedrock_agentcore_lambda_role_arn
}

output "bedrock_agentcore_lambda_function_arn" {
  description = "ARN of the Lambda function for Bedrock AgentCore setup"
  value       = module.bedrock_agentcore.bedrock_agentcore_lambda_function_arn
}
