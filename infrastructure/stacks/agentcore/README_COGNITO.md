# Optional Cognito Stack for AgentCore

This directory includes an optional Cognito authentication stack that can be enabled or disabled based on your requirements.

## Overview

The Cognito stack provides:
- User Pool for user authentication
- User Pool Client for web applications
- Resource Server and Client for machine-to-machine authentication
- Identity Pool for AWS resource access
- Pre-signup Lambda trigger for email domain validation
- SSM parameters for easy configuration access

## Configuration

### Enable/Disable Cognito

Set the `enable_cognito` variable to control whether the Cognito stack is deployed:

```hcl
# In terraform.tfvars or as a variable
enable_cognito = true  # Enable Cognito stack
enable_cognito = false # Use external Cognito resources
```

### Variables

When `enable_cognito = true`, you can customize:

- `cognito_allowed_email_domains`: List of allowed email domains for signup (default: ["amazon.com"])
- `cognito_verification_email_subject`: Email verification subject
- `cognito_verification_email_body`: Email verification message body
- `cognito_callback_urls`: OAuth callback URLs
- `cognito_logout_urls`: OAuth logout URLs

When `enable_cognito = false`, provide external Cognito resource IDs:

- `cognito_user_pool_id`: External User Pool ID
- `cognito_user_pool_client_id`: External User Pool Client ID

## Resources Created

When enabled, the stack creates:

### Core Cognito Resources
- `aws_cognito_user_pool.agentcore_user_pool`: Main user pool
- `aws_cognito_user_pool_client.agentcore_user_pool_client`: Web application client
- `aws_cognito_user_pool_domain.agentcore_user_pool_domain`: Hosted UI domain
- `aws_cognito_identity_pool.agentcore_identity_pool`: Identity pool for AWS access

### Machine-to-Machine Authentication
- `aws_cognito_resource_server.agentcore_invoke_server`: Resource server for API access
- `aws_cognito_user_pool_client.agentcore_invoke_client`: M2M client with client credentials flow

### Lambda Triggers
- `aws_lambda_function.cognito_pre_signup_trigger`: Email domain validation
- Associated IAM roles and policies

### IAM Resources
- `aws_iam_role.cognito_authenticated_role`: Role for authenticated users
- `aws_iam_role_policy.cognito_authenticated_policy`: Permissions for authenticated users

### SSM Parameters
- `/${environment}/user_pool_id`
- `/${environment}/user_pool_client_id`
- `/${environment}/identity_pool_id`
- `/${environment}/invoke_client_id`
- `/${environment}/invoke_client_secret`

## Integration with AgentCore Services

The Lambda functions automatically use the appropriate Cognito resources:

```hcl
# Runtime Controller Lambda
environment {
  variables = {
    USER_POOL_ID = var.enable_cognito ? aws_cognito_user_pool.agentcore_user_pool[0].id : var.cognito_user_pool_id
    USER_POOL_CLIENT_ID = var.enable_cognito ? aws_cognito_user_pool_client.agentcore_user_pool_client[0].id : var.cognito_user_pool_client_id
  }
}

# Gateway Controller Lambda
environment {
  variables = {
    COGNITO_DISCOVERY_URL = "https://cognito-idp.${var.aws_region}.amazonaws.com/${var.enable_cognito ? aws_cognito_user_pool.agentcore_user_pool[0].id : var.cognito_user_pool_id}/.well-known/openid-configuration"
    COGNITO_USER_POOL_CLIENT_ID = var.enable_cognito ? aws_cognito_user_pool_client.agentcore_user_pool_client[0].id : var.cognito_user_pool_client_id
  }
}
```

## Outputs

The stack provides conditional outputs:

- `cognito_enabled`: Whether Cognito is enabled
- `cognito_user_pool_id`: User Pool ID (from created or external resource)
- `cognito_user_pool_arn`: User Pool ARN (only when enabled)
- `cognito_user_pool_client_id`: User Pool Client ID
- `cognito_identity_pool_id`: Identity Pool ID (only when enabled)
- `cognito_invoke_client_id`: M2M Client ID (only when enabled)
- `cognito_user_pool_domain`: Hosted UI domain (only when enabled)
- `cognito_authenticated_role_arn`: Authenticated role ARN (only when enabled)

## Usage Examples

### Enable Cognito with Custom Domain Restrictions

```hcl
# terraform.tfvars
enable_cognito = true
cognito_allowed_email_domains = ["mycompany.com", "partner.com"]
cognito_verification_email_subject = "Welcome to AgentCore Platform"
cognito_callback_urls = ["https://myapp.example.com/callback"]
```

### Use External Cognito Resources

```hcl
# terraform.tfvars
enable_cognito = false
cognito_user_pool_id = "us-west-2_ABC123DEF"
cognito_user_pool_client_id = "1234567890abcdef"
```

## Security Features

- **Email Domain Validation**: Pre-signup trigger validates email domains
- **Strong Password Policy**: Requires uppercase, lowercase, numbers, and symbols
- **Email Verification**: Auto-verifies email addresses
- **OAuth Scopes**: Proper scope separation for different access patterns
- **IAM Integration**: Identity pool provides AWS resource access with proper permissions

## Deployment

1. Set your desired configuration in `terraform.tfvars`
2. Run `terraform plan` to review changes
3. Run `terraform apply` to deploy

The stack is designed to be fully optional and can be toggled without affecting existing deployments.
