#!/bin/bash
set -e

echo "Building AgentCore Runtime container for ECR deployment..."

# Configuration variables
SERVICE_NAME="agentpath-agentcore-runtime"
ECR_REPOSITORY_NAME="${SERVICE_NAME}"
AWS_REGION="${AWS_REGION:-us-west-2}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS CLI is not configured or credentials are not available"
    exit 1
fi

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY_NAME}"

echo "Building container for ECR URI: ${ECR_URI}:${IMAGE_TAG}"

# Check if ECR repository exists, create if it doesn't
if ! aws ecr describe-repositories --repository-names ${ECR_REPOSITORY_NAME} --region ${AWS_REGION} &> /dev/null; then
    echo "Creating ECR repository: ${ECR_REPOSITORY_NAME}"
    aws ecr create-repository \
        --repository-name ${ECR_REPOSITORY_NAME} \
        --region ${AWS_REGION} \
        --image-scanning-configuration scanOnPush=true
else
    echo "ECR repository ${ECR_REPOSITORY_NAME} already exists"
fi

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build the Docker image from the sample-agentic-platform root directory
echo "Building Docker image..."
DIRNAME=$(dirname "0")
echo $DIRNAME
echo "$DIRNAME/../../../.."
cd "$DIRNAME/../../../"  # Navigate to sample-agentic-platform root
docker build --platform linux/arm64 -f src/agentic_platform/service/agentcore/runtime/Dockerfile \
    -t ${ECR_REPOSITORY_NAME}:${IMAGE_TAG} \
    -t ${ECR_URI}:${IMAGE_TAG} \
    .

# Push the image to ECR
echo "Pushing image to ECR..."
docker push ${ECR_URI}:${IMAGE_TAG}
# change directory back to where we were
cd -

echo "Successfully built and pushed ${ECR_URI}:${IMAGE_TAG}"
echo ""
echo "To deploy this container, you can reference it as:"
echo "  Image URI: ${ECR_URI}:${IMAGE_TAG}"
echo ""
echo "Environment variables that can be set at runtime:"
echo "  - REGION: AWS region (default: us-west-2)"
echo "  - AWS_ACCESS_KEY_ID: AWS access key (if not using IAM roles)"
echo "  - AWS_SECRET_ACCESS_KEY: AWS secret key (if not using IAM roles)"
echo ""
echo "For EKS deployment, ensure your pods have proper IAM roles with bedrock-agentcore-control permissions"
