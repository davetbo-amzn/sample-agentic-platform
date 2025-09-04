########################################################
# Optional Cognito Stack for AgentCore
########################################################

# Create Cognito resources only if enabled
locals {
  create_cognito = var.enable_cognito
}

########################################################
# Pre-signup Lambda Trigger
########################################################

# IAM Role for Pre-signup Lambda
resource "aws_iam_role" "cognito_pre_signup_lambda_role" {
  count = local.create_cognito ? 1 : 0
  name  = "${var.environment}-cognito-pre-signup-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for Pre-signup Lambda
resource "aws_iam_policy" "cognito_pre_signup_lambda_policy" {
  count       = local.create_cognito ? 1 : 0
  name        = "${var.environment}-cognito-pre-signup-lambda-policy"
  description = "Policy for Cognito pre-signup Lambda function"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })

  tags = var.tags
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "cognito_pre_signup_lambda_policy_attachment" {
  count      = local.create_cognito ? 1 : 0
  role       = aws_iam_role.cognito_pre_signup_lambda_role[0].name
  policy_arn = aws_iam_policy.cognito_pre_signup_lambda_policy[0].arn
}

# Pre-signup Lambda function (simplified version without bundling)
resource "aws_lambda_function" "cognito_pre_signup_trigger" {
  count         = local.create_cognito ? 1 : 0
  function_name = "${var.environment}-cognito-pre-signup-trigger"
  role          = aws_iam_role.cognito_pre_signup_lambda_role[0].arn
  handler       = "index.handler"
  runtime       = "python3.12"
  timeout       = 60
  memory_size   = 128
  architectures = ["arm64"]

  # Inline code for pre-signup trigger
  filename = data.archive_file.cognito_pre_signup_trigger_zip[0].output_path

  environment {
    variables = {
      ALLOWED_EMAIL_DOMAINS = join(",", var.cognito_allowed_email_domains)
      STACK_NAME           = var.environment
    }
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.cognito_pre_signup_lambda_policy_attachment,
    data.archive_file.cognito_pre_signup_trigger_zip
  ]
}

# Create a simple pre-signup trigger zip file
data "archive_file" "cognito_pre_signup_trigger_zip" {
  count       = local.create_cognito ? 1 : 0
  type        = "zip"
  output_path = "${path.module}/cognito_pre_signup_trigger.zip"
  
  source {
    content = <<EOF
import json
import os

def handler(event, context):
    """
    Pre-signup trigger to validate email domains
    """
    allowed_domains = os.environ.get('ALLOWED_EMAIL_DOMAINS', '').split(',')
    
    # If no domains specified, allow all
    if not allowed_domains or allowed_domains == ['']:
        return event
    
    email = event['request']['userAttributes'].get('email', '')
    email_domain = email.split('@')[-1] if '@' in email else ''
    
    if email_domain not in allowed_domains:
        raise Exception(f"Email domain {email_domain} is not allowed")
    
    return event
EOF
    filename = "index.py"
  }
}

########################################################
# Cognito User Pool
########################################################

resource "aws_cognito_user_pool" "agentcore_user_pool" {
  count = local.create_cognito ? 1 : 0
  name  = "${var.environment}-user-pool"

  # User pool configuration
  alias_attributes         = ["email"]
  auto_verified_attributes = ["email"]

  # Password policy
  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  # Email verification
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = var.cognito_verification_email_subject
    email_message        = var.cognito_verification_email_body
  }

  # Lambda triggers
  lambda_config {
    pre_sign_up = local.create_cognito ? aws_lambda_function.cognito_pre_signup_trigger[0].arn : null
  }

  tags = var.tags
}

# Lambda permission for Cognito to invoke pre-signup trigger
resource "aws_lambda_permission" "cognito_pre_signup_trigger_permission" {
  count         = local.create_cognito ? 1 : 0
  statement_id  = "AllowCognitoInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cognito_pre_signup_trigger[0].function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.agentcore_user_pool[0].arn
}

########################################################
# Cognito User Pool Client
########################################################

resource "aws_cognito_user_pool_client" "agentcore_user_pool_client" {
  count        = local.create_cognito ? 1 : 0
  name         = "${var.environment}-user-pool-client"
  user_pool_id = aws_cognito_user_pool.agentcore_user_pool[0].id

  generate_secret = false

  # OAuth configuration
  allowed_oauth_flows                  = ["code", "implicit"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  
  # Callback URLs (can be customized via variables)
  callback_urls = var.cognito_callback_urls
  logout_urls   = var.cognito_logout_urls

  # Token validity
  access_token_validity  = 24
  id_token_validity     = 24
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Prevent user existence errors
  prevent_user_existence_errors = "ENABLED"
}

########################################################
# Cognito Resource Server and Client for AgentCore Invoke
########################################################

resource "aws_cognito_resource_server" "agentcore_invoke_server" {
  count      = local.create_cognito ? 1 : 0
  identifier = "AgentCoreInvokeServer"
  name       = "AgentCore Invoke Server"

  user_pool_id = aws_cognito_user_pool.agentcore_user_pool[0].id

  scope {
    scope_name        = "invoke"
    scope_description = "Scope for invoking the agentcore gateway"
  }
}

resource "aws_cognito_user_pool_client" "agentcore_invoke_client" {
  count        = local.create_cognito ? 1 : 0
  name         = "agentcore-invoke-client"
  user_pool_id = aws_cognito_user_pool.agentcore_user_pool[0].id

  generate_secret = true

  # OAuth configuration for machine-to-machine
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["AgentCoreInvokeServer/invoke"]

  # Token validity
  access_token_validity = 24

  token_validity_units {
    access_token = "hours"
  }

  # Prevent user existence errors
  prevent_user_existence_errors = "ENABLED"

  depends_on = [aws_cognito_resource_server.agentcore_invoke_server]
}

########################################################
# Cognito User Pool Domain
########################################################

resource "aws_cognito_user_pool_domain" "agentcore_user_pool_domain" {
  count       = local.create_cognito ? 1 : 0
  domain      = "auth-${lower(var.environment)}-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  user_pool_id = aws_cognito_user_pool.agentcore_user_pool[0].id
}

########################################################
# Cognito Identity Pool
########################################################

resource "aws_cognito_identity_pool" "agentcore_identity_pool" {
  count                            = local.create_cognito ? 1 : 0
  identity_pool_name               = "${var.environment}-identity-pool"
  allow_unauthenticated_identities = false

  cognito_identity_providers {
    client_id               = aws_cognito_user_pool_client.agentcore_user_pool_client[0].id
    provider_name           = aws_cognito_user_pool.agentcore_user_pool[0].endpoint
    server_side_token_check = false
  }

  tags = var.tags
}

########################################################
# IAM Roles for Identity Pool
########################################################

# Authenticated role for identity pool
resource "aws_iam_role" "cognito_authenticated_role" {
  count = local.create_cognito ? 1 : 0
  name  = "${var.environment}-cognito-authenticated-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "cognito-identity.amazonaws.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "cognito-identity.amazonaws.com:aud" = aws_cognito_identity_pool.agentcore_identity_pool[0].id
          }
          "ForAnyValue:StringLike" = {
            "cognito-identity.amazonaws.com:amr" = "authenticated"
          }
        }
      }
    ]
  })

  tags = var.tags
}

# Policy for authenticated users
resource "aws_iam_role_policy" "cognito_authenticated_policy" {
  count = local.create_cognito ? 1 : 0
  name  = "${var.environment}-cognito-authenticated-policy"
  role  = aws_iam_role.cognito_authenticated_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "execute-api:*"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach roles to identity pool
resource "aws_cognito_identity_pool_roles_attachment" "agentcore_identity_pool_roles" {
  count            = local.create_cognito ? 1 : 0
  identity_pool_id = aws_cognito_identity_pool.agentcore_identity_pool[0].id

  roles = {
    "authenticated" = aws_iam_role.cognito_authenticated_role[0].arn
  }
}

########################################################
# SSM Parameters for Cognito Resources
########################################################

resource "aws_ssm_parameter" "cognito_user_pool_id" {
  count = local.create_cognito ? 1 : 0
  name  = "/${var.environment}/user_pool_id"
  type  = "String"
  value = aws_cognito_user_pool.agentcore_user_pool[0].id

  tags = var.tags
}

resource "aws_ssm_parameter" "cognito_user_pool_client_id" {
  count = local.create_cognito ? 1 : 0
  name  = "/${var.environment}/user_pool_client_id"
  type  = "String"
  value = aws_cognito_user_pool_client.agentcore_user_pool_client[0].id

  tags = var.tags
}

resource "aws_ssm_parameter" "cognito_identity_pool_id" {
  count = local.create_cognito ? 1 : 0
  name  = "/${var.environment}/identity_pool_id"
  type  = "String"
  value = aws_cognito_identity_pool.agentcore_identity_pool[0].id

  tags = var.tags
}

resource "aws_ssm_parameter" "cognito_invoke_client_id" {
  count = local.create_cognito ? 1 : 0
  name  = "/${var.environment}/invoke_client_id"
  type  = "String"
  value = aws_cognito_user_pool_client.agentcore_invoke_client[0].id

  tags = var.tags
}

resource "aws_ssm_parameter" "cognito_invoke_client_secret" {
  count = local.create_cognito ? 1 : 0
  name  = "/${var.environment}/invoke_client_secret"
  type  = "SecureString"
  value = aws_cognito_user_pool_client.agentcore_invoke_client[0].client_secret

  tags = var.tags
}
