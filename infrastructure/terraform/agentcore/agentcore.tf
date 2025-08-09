####################################################################
# AWS Bedrock AgentCore Memory Gateway
#
# This configuration file creates resources for integrating with 
# AWS Bedrock AgentCore's memory capabilities.
# Since Terraform doesn't have native resources for Bedrock AgentCore yet,
# we'll use Lambda trigger functions to provision and manage the resources.
####################################################################

# IAM Role for the AgentCore Lambda function
resource "aws_iam_role" "bedrock_agentcore_lambda_role" {
  name = "${var.environment_name}-bedrock-agentcore-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.environment_name}-bedrock-agentcore-lambda-role"
    }
  )
}

# IAM Policy for the AgentCore Lambda function
resource "aws_iam_policy" "bedrock_agentcore_policy" {
  name        = "${var.environment_name}-bedrock-agentcore-policy"
  description = "Policy for Lambda to access Bedrock AgentCore"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          "bedrock:*",
          "bedrock-agentcore:*",
          "bedrock-agentcore-control:*",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect   = "Allow",
        Resource = "*"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.environment_name}-bedrock-agentcore-policy"
    }
  )
}

# Attach the policy to the role
resource "aws_iam_role_policy_attachment" "bedrock_agentcore_policy_attachment" {
  role       = aws_iam_role.bedrock_agentcore_lambda_role.name
  policy_arn = aws_iam_policy.bedrock_agentcore_policy.arn
}

# Lambda function for setting up AgentCore Memory
resource "aws_lambda_function" "bedrock_agentcore_memory_setup" {
  function_name    = "${var.environment_name}-bedrock-agentcore-memory-setup"
  role             = aws_iam_role.bedrock_agentcore_lambda_role.arn
  handler          = "index.handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 256
  
  filename         = "${path.module}/functions/agentcore-memory-setup.zip"
  source_code_hash = filebase64sha256("${path.module}/functions/agentcore-memory-setup.zip")

  environment {
    variables = {
      MEMORY_RETENTION_PERIOD = var.bedrock_agentcore_memory_retention_days
      ENVIRONMENT             = var.environment_name
      REGION                  = var.aws_region
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.environment_name}-bedrock-agentcore-memory-setup"
    }
  )

  depends_on = [
    aws_iam_role_policy_attachment.bedrock_agentcore_policy_attachment
  ]
}

# # Lambda invocation resource to create/update the AgentCore Memory resources
# resource "aws_lambda_invocation" "bedrock_agentcore_memory_invocation" {
#   function_name = aws_lambda_function.bedrock_agentcore_memory_setup.function_name
#   input = jsonencode({
#     action      = "provision"
#     config      = {
#       memory_retention_days = var.bedrock_agentcore_memory_retention_days
#       environment          = var.environment_name
#     }
#   })

#   lifecycle {
#     create_before_destroy = true
#   }

#   depends_on = [
#     aws_lambda_function.bedrock_agentcore_memory_setup
#   ]
# }

# Null resource to create the Lambda deployment package
resource "null_resource" "bedrock_agentcore_lambda_package" {
  triggers = {
    lambda_code_hash = "${filemd5("${path.module}/functions/agentcore_memory_setup.py")}"
  }

  provisioner "local-exec" {
    command = <<EOF
mkdir -p ${path.module}/functions/package
cp ${path.module}/functions/agentcore_memory_setup.py ${path.module}/functions/package/index.py
cd ${path.module}/functions/package
pip install -t . boto3
zip -r ../agentcore-memory-setup.zip .
cd ..
rm -rf package
EOF
  }
}

# Output the ARNs for reference
output "bedrock_agentcore_lambda_role_arn" {
  description = "ARN of the IAM role for Bedrock AgentCore Lambda function"
  value       = aws_iam_role.bedrock_agentcore_lambda_role.arn
}

output "bedrock_agentcore_lambda_function_arn" {
  description = "ARN of the Lambda function for Bedrock AgentCore setup"
  value       = aws_lambda_function.bedrock_agentcore_memory_setup.arn
}
