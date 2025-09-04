#!/bin/bash
set -e

echo "Packaging Lambda function for AgentCore MCP Gateway deployment using Docker..."

# Clean and recreate the build directory to ensure no previous artifacts remain
[ -d build ] && rm -rf build 
[ -f agentcore-mcp-gateway-lambda.zip ] && rm -f agentcore-mcp-gateway-lambda.zip

mkdir -p build

# Use Docker to package the Lambda function with the AWS Lambda Python 3.13 image
docker run --rm \
  -v "$(pwd)/../../../src:/asset-input" \
  -v "$(pwd)/build:/asset-output" \
  --entrypoint /bin/bash \
  public.ecr.aws/lambda/python:3.13-arm64 \
  -c "
    dnf install -y zip gcc && \
    echo 'Setting up Lambda package environment...' && \
    cd /asset-output && \
    # Install dependencies
    pip install -t /asset-output -r /asset-input/agentic_platform/service/agentcore/mcp_gateway/lambda-requirements.txt && \
    # Copy Lambda function to output directory
    cp -aR /asset-input/agentic_platform /asset-output && \
    # Create the zip file directly inside the container to ensure no local environment contamination
    zip -r agentcore_mcp_gateway_client.zip . && \
    echo 'Lambda package created successfully in /asset-output/agentcore_mcp_gateway_client.zip'
  "

# Copy the zip file to the project root for Terraform to use
cp build/agentcore_mcp_gateway_client.zip agentcore-mcp-gateway-lambda.zip

echo "Package created successfully: agentcore-mcp-gateway-lambda.zip"
echo "This package was built using Docker with Python 3.13 ARM64 environment"
