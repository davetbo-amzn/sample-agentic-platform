####################################################################
# Variables for AWS Bedrock AgentCore Memory Gateway
####################################################################

variable "environment_name" {
  description = "Environment name used as prefix for all resources"
  type        = string
}

variable "aws_region" {
  description = "AWS region where resources will be deployed"
  type        = string
  default     = "us-east-1"  # Default to us-east-1 as Bedrock services are typically available there
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

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
