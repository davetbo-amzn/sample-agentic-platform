variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"  # Default to us-west-2 as Bedrock services are typically available there
}

variable "environment_name" {
  description = "Environment name used as prefix for all resources"
  type        = string
  default     = "agentcore-agentpath"
}

variable "bedrock_agentcore_memory_retention_days" {
  description = "Number of days to retain memory in the Bedrock AgentCore memory store"
  type        = number
  default     = 30
  validation {
    condition     = var.bedrock_agentcore_memory_retention_days >= 1 && var.bedrock_agentcore_memory_retention_days <= 365
    error_message = "Memory retention period must be between 1 and 365 days."
  }
}

variable "memory_lambda_zip_path" {
  description = "Path to the Lambda deployment package zip file"
  type        = string
  default     = "agentcore-memory-provider-lambda.zip"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {
    Project     = "Agentic Platform"
    Component   = "AgentCore Memory Gateway"
    Environment = "Test"
    ManagedBy   = "Terraform"
  }
}
