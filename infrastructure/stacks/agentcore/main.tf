# Get current region and account data
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

provider "aws" {
  region = var.aws_region
}


# IAM Role for the AgentCore Lambda function
resource "aws_iam_role" "agentcore_runtime_lambda_role" {
  name = "${var.environment}-agentcore-runtime-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = [
            "lambda.amazonaws.com",
            "bedrock-agentcore.amazonaws.com"
          ]
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for the AgentCore Lambda function
resource "aws_iam_policy" "bedrock_agentcore_runtime_policy" {
  name        = "${var.environment}-bedrock-agentcore-runtime-policy"
  description = "Policy for Lambda to access Bedrock AgentCoreRuntime"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          "bedrock:*",
          "bedrock-agentcore:*",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents"
        ],
        Effect   = "Allow",
        Resource = "*"
      },
      {
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ],
        Effect   = "Allow",
        Resource = "*"
      },
      {
        Action = [
          "ssm:GetParameter",
          "ssm:GetParametersByPath", 
          "ssm:PutParameter"
        ],
        Effect   = "Allow",
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${var.environment}*"
      },
      {
        "Effect": "Allow", 
        "Action": [ 
            "xray:PutTraceSegments", 
            "xray:PutTelemetryRecords", 
            "xray:GetSamplingRules", 
            "xray:GetSamplingTargets"
            ],
         "Resource": [ "*" ] 
         },
         {
            "Effect": "Allow",
            "Resource": "*",
            "Action": "cloudwatch:PutMetricData",
            "Condition": {
                "StringEquals": {
                    "cloudwatch:namespace": "bedrock-agentcore"
                }
            }
        },
        {
            "Sid": "GetAgentAccessToken",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:GetWorkloadAccessToken",
                "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
            ],
            "Resource": [
              "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default",
              "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default/workload-identity/agentName-*"
            ]
        }
    ]
  })

  tags = var.tags
}

# Attach the policy to the role
resource "aws_iam_role_policy_attachment" "bedrock_agentcore_runtime_policy_attachment" {
  role       = aws_iam_role.agentcore_runtime_lambda_role.name
  policy_arn = aws_iam_policy.bedrock_agentcore_runtime_policy.arn
}

# IAM Role for the AgentCore Lambda function
resource "aws_iam_role" "agentcore_memory_lambda_role" {
  name = "${var.environment}-agentcore-memory-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = [
            "lambda.amazonaws.com",
            "bedrock-agentcore.amazonaws.com"
          ]
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for the AgentCore Lambda function
resource "aws_iam_policy" "bedrock_agentcore_memory_policy" {
  name        = "${var.environment}-bedrock-agentcore-memory-policy"
  description = "Policy for Lambda to access Bedrock AgentCore Memory"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          "bedrock:*",
          "bedrock-agentcore:*",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents"
        ],
        Effect   = "Allow",
        Resource = "*"
      },
      {
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ],
        Effect   = "Allow",
        Resource = "*"
      },
      {
        Action = [
          "ssm:GetParameter",
          "ssm:GetParametersByPath", 
          "ssm:PutParameter"
        ],
        Effect   = "Allow",
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${var.environment}*"
      },
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ],
        Effect   = "Allow",
        Resource = [
          "arn:aws:s3:::${var.environment}-agentcore-runtime-zip-files",
          "arn:aws:s3:::${var.environment}-agentcore-runtime-zip-files/*"
        ]
      },
      {
        "Effect": "Allow", 
        "Action": [ 
            "xray:PutTraceSegments", 
            "xray:PutTelemetryRecords", 
            "xray:GetSamplingRules", 
            "xray:GetSamplingTargets"
            ],
         "Resource": [ "*" ] 
         },
         {
            "Effect": "Allow",
            "Resource": "*",
            "Action": "cloudwatch:PutMetricData",
            "Condition": {
                "StringEquals": {
                    "cloudwatch:namespace": "bedrock-agentcore"
                }
            }
        }
    ]
  })

  tags = var.tags
}

# Attach the policy to the role
resource "aws_iam_role_policy_attachment" "bedrock_agentcore_memory_policy_attachment" {
  role       = aws_iam_role.agentcore_memory_lambda_role.name
  policy_arn = aws_iam_policy.bedrock_agentcore_memory_policy.arn
}

# S3 bucket for storing agentcore runtime zip files
resource "aws_s3_bucket" "agentcore_runtime_zip_files" {
  bucket = "${var.environment}-agentcore-runtime-zip-files"
  
  tags = var.tags
}

# S3 bucket lifecycle configuration
resource "aws_s3_bucket_lifecycle_configuration" "agentcore_runtime_lifecycle" {
  bucket = aws_s3_bucket.agentcore_runtime_zip_files.id

  rule {
    id     = "expire-old-zip-files"
    status = "Enabled"

    expiration {
      days = 30
    }
  }
}

# S3 bucket server-side encryption configuration
resource "aws_s3_bucket_server_side_encryption_configuration" "agentcore_runtime_encryption" {
  bucket = aws_s3_bucket.agentcore_runtime_zip_files.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 bucket public access block (security best practice)
resource "aws_s3_bucket_public_access_block" "agentcore_runtime_block_public" {
  bucket = aws_s3_bucket.agentcore_runtime_zip_files.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lambda function for setting up AgentCore Memory
resource "aws_lambda_function" "agentcore_memory_setup" {
  function_name    = "${var.environment}-agentcore-memory-setup"
  role             = aws_iam_role.agentcore_memory_lambda_role.arn
  handler          = "agentic_platform.service.agentcore.memory.api.agentcore_memory_provider_controller.handler"
  runtime          = "python3.13"
  timeout          = 300
  memory_size      = 128
  architectures    = ["arm64"]
  
  filename         = var.memory_lambda_zip_path
  source_code_hash = filebase64sha256(var.memory_lambda_zip_path)

  environment {
    variables = {
      MEMORY_RETENTION_PERIOD    = var.bedrock_agentcore_memory_retention_days
      ENVIRONMENT                = var.environment
      REGION                     = var.aws_region
      AGENTCORE_RUNTIME_BUCKET   = aws_s3_bucket.agentcore_runtime_zip_files.id
    }
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.bedrock_agentcore_runtime_policy_attachment
  ]
}

# # Lambda invocation resource to create/update the AgentCore Memory resources
# resource "aws_lambda_invocation" "bedrock_agentcore_memory_invocation" {
#   function_name = aws_lambda_function.bedrock_agentcore_memory_setup.function_name
#   input = jsonencode({
#     action      = "provision"
#     config      = {
#       memory_retention_days = var.bedrock_agentcore_memory_retention_days
#       environment          = var.environment
#     }
#   })
# 
#   lifecycle {
#     create_before_destroy = true
#   }

#   depends_on = [
#     aws_lambda_function.bedrock_agentcore_memory_setup
#   ]
# }


# Lambda function for AgentCore Runtime Controller
resource "aws_lambda_function" "bedrock_agentcore_runtime_controller" {
  function_name    = "${var.environment}-bedrock-agentcore-runtime-controller"
  role             = aws_iam_role.agentcore_runtime_lambda_role.arn
  handler          = "agentic_platform.service.agentcore.runtime.api.agentcore_runtime_controller.handler"
  runtime          = "python3.13"
  timeout          = 300
  memory_size      = 128
  architectures    = ["arm64"]
  
  filename         = var.runtime_lambda_zip_path
  source_code_hash = filebase64sha256(var.runtime_lambda_zip_path)

  environment {
    variables = {
      ENVIRONMENT = var.environment
      REGION      = var.aws_region
      S3_ZIPS_BUCKET = aws_s3_bucket.agentcore_runtime_zip_files.id
      USER_POOL_CLIENT_ID = var.cognito_user_pool_client_id
      USER_POOL_ID = var.cognito_user_pool_id
    }
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.bedrock_agentcore_runtime_policy_attachment
  ]
}

# CloudWatch Log Group for AgentCore Runtime Controller Lambda
resource "aws_cloudwatch_log_group" "agentcore_runtime_controller_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.bedrock_agentcore_runtime_controller.function_name}"
  retention_in_days = 7

  tags = var.tags
}
