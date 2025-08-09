####################################################################
# AWS Bedrock AgentCore Memory Gateway - Main Module Definition
#
# This is the main configuration file for the AgentCore memory gateway
# module that connects with the rest of the infrastructure.
####################################################################

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0.0"
    }
  }
}

# Import common variables and configurations
# These references ensure consistency with the parent module

locals {
  # Default tags applied to all resources
  default_tags = {
    Project     = "Agentic Platform"
    Component   = "AgentCore Memory Gateway"
    Environment = var.environment_name
    ManagedBy   = "Terraform"
  }
  
  # Combine default tags with user-provided tags
  tags = merge(local.default_tags, var.tags)
}
