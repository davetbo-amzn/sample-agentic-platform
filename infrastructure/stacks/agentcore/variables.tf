########################################################
# Global Variables
########################################################

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Deployment environment (e.g., dev, staging, prod)"
  type        = string
  default     = "agentcore-agentpath"
}

variable "stack_name" {
  description = "Name of the stack to prefix to resource names"
  type        = string
  default     = "agent-ptfm"
}

########################################################
# Variables to be connected from Cognito stack elsewhere
########################################################
variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  type        = string
  default     = "us-west-2_bA0e3osFu"
}

variable "cognito_user_pool_client_id" {
  description = "Cognito User Pool Client ID"
  type        = string
  default     = "7ljspeqi6oeq43nrvkekh86lfc"
}

########################################################
# AgentCore Variables
########################################################

variable "bedrock_agentcore_memory_retention_days" {
  description = "Number of days to retain memory in the Bedrock AgentCore memory store"
  type        = number
  default     = 30
  validation {
    condition     = var.bedrock_agentcore_memory_retention_days >= 7 && var.bedrock_agentcore_memory_retention_days <= 365
    error_message = "Memory retention period must be between 7 and 365 days."
  }
}

variable "memory_lambda_zip_path" {
  description = "Path to the Lambda deployment package zip file for memory operations"
  type        = string
  default     = "agentcore-memory-provider-lambda.zip"
}

variable "runtime_lambda_zip_path" {
  description = "Path to the Lambda deployment package zip file for runtime controller"
  type        = string
  default     = "agentcore-runtime-lambda.zip"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {
    Project   = "Agentic Platform Sample"
    Component = "AgentCore"
    ManagedBy = "Terraform"
  }
}
