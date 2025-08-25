# AgentCore Isolated Deployment (AgentPath Version)

This directory contains a standalone Terraform configuration to deploy only the AWS Bedrock AgentCore Memory Gateway component of the Sample Agentic Platform, with fixes to address Lambda packaging issues.

## Purpose

This configuration allows for testing the AgentCore functionality without deploying the entire infrastructure stack. It sets up:

- IAM roles and policies for accessing Bedrock AgentCore services
- Lambda function to provision and manage AgentCore Memory resources
- Automated Lambda invocation to create memory resources

## Key Improvements

This implementation addresses two key issues:

1. **Memory Gateway Dependency**: 
   - Properly creates and manages the AWS Bedrock AgentCore memory gateway
   - Handles memory ID creation and dependency requirements
   - Uses the correct API parameters for memory operations

2. **Lambda Packaging Reliability**:
   - Uses a reliable manual packaging process
   - Ensures proper handler reference (`agentcore_memory_client.handler`)
   - Eliminates dependency on the unreliable `null_resource` for package creation

## Prerequisites

- AWS CLI configured with proper credentials
- Terraform installed
- Access to AWS Bedrock services (available in us-west-2 region)
- Python with pip installed

## Deployment Steps

### 1. Create the Lambda Deployment Package

First, run the packaging script to create the Lambda function zip file:

```bash
cd agentcore-agentpath
./package_lambda.sh
```

The script will:
- Create a temporary package directory
- Copy the Lambda function code
- Install boto3 dependencies
- Create a properly structured zip file

### 2. Apply the Terraform Configuration

Once the Lambda package is created, deploy the infrastructure:

```bash
# Initialize Terraform
terraform init

# Review planned changes
terraform plan

# Apply the configuration
terraform apply
```

### Verification

After deployment, verify that the resources were created correctly:

```bash
# List the Lambda function
aws lambda get-function --function-name agentcore-agentpath-bedrock-agentcore-memory-setup --region us-west-2

# Check the IAM role
aws iam get-role --role-name agentcore-test-bedrock-agentcore-lambda-role

# Check the created memory resources
aws lambda invoke --function-name agentcore-test-bedrock-agentcore-memory-setup \
  --region us-west-2 \
  --payload '{"action":"provision"}' \
  response.json && cat response.json
```

### Cleanup

When you're done testing, remove all resources:

```bash
terraform destroy
```

## Configuration

You can modify the default settings in `terraform.tfvars`:

- `aws_region` - AWS region to deploy resources (default: "us-west-2")
- `environment_name` - Environment name prefix for resources (default: "agentcore-agentpath")
- `bedrock_agentcore_memory_retention_days` - Memory retention period (default: 7)
- `memory_lambda_zip_path` - Path to the Lambda deployment package (default: "agentcore-memory-provider-lambda.zip")

## Notes

- This deployment only includes the AgentCore components, not the full platform
- This agentpath version is streamlined for direct deployment without the reliability issues
- Directly includes all resources rather than referencing the module to avoid complexity
- The Lambda function correctly handles memory gateway creation and ID requirements
- The implementation addresses the parameter validation issues with the Bedrock AgentCore APIs

## Technical Details

### Memory Gateway Creation Process

This implementation properly handles the memory gateway creation process by:

1. Creating a memory resource with the control plane client first
2. Obtaining the memory ID from the creation response
3. Using the memory ID and namespace for all subsequent operations
4. Handling failure cases by looking for existing memories
5. Including proper error handling for various API scenarios

This approach ensures that the memory gateway is properly created and accessible before attempting any operations that depend on it.
