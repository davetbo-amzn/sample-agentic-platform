# AgentCore Runtime Container

This directory contains the Docker configuration and build scripts for containerizing the AgentCore Runtime service for deployment to AWS ECR and EKS.

## Overview

The AgentCore Runtime Client provides methods to create, retrieve, update, delete, and list AgentCore Runtime resources using the AWS Bedrock AgentCore Control Plane API. This container allows you to deploy the runtime client as a containerized service.

## Files

- `Dockerfile` - Multi-stage Docker build configuration
- `build-container.sh` - Script to build and push container to ECR
- `README_DOCKER.md` - This documentation file

## Prerequisites

Before building the container, ensure you have:

1. **Docker** installed and running
2. **AWS CLI** configured with appropriate credentials
3. **Permissions** to create ECR repositories and push images
4. **Bedrock AgentCore** permissions for the runtime operations

### Required AWS Permissions

Your AWS credentials should have the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecr:CreateRepository",
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:PutImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore-control:CreateAgentRuntime",
                "bedrock-agentcore-control:DeleteAgentRuntime",
                "bedrock-agentcore-control:GetAgentRuntime",
                "bedrock-agentcore-control:ListAgentRuntimes",
                "bedrock-agentcore-control:UpdateAgentRuntime"
            ],
            "Resource": "*"
        }
    ]
}
```

## Building the Container

### Quick Build

```bash
# From the sample-agentic-platform root directory
./src/agentic_platform/service/agentcore/runtime/build-container.sh
```

### Custom Build Configuration

You can customize the build with environment variables:

```bash
# Set custom AWS region
export AWS_REGION=us-east-1

# Set custom image tag
export IMAGE_TAG=v1.0.0

# Run the build
./src/agentic_platform/service/agentcore/runtime/build-container.sh
```

### Manual Docker Build

If you prefer to build manually:

```bash
# From the sample-agentic-platform root directory
docker build -f src/agentic_platform/service/agentcore/runtime/Dockerfile \
    -t agentcore-runtime:latest \
    .
```

## Container Configuration

### Environment Variables

The container supports the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `REGION` | AWS region for Bedrock AgentCore resources | `us-west-2` |
| `AWS_ACCESS_KEY_ID` | AWS access key (if not using IAM roles) | - |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key (if not using IAM roles) | - |
| `PYTHONPATH` | Python module path | `/app` |

### Runtime Configuration

For production deployments, it's recommended to use IAM roles instead of access keys:

```yaml
# Example Kubernetes deployment snippet
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentcore-runtime
spec:
  template:
    spec:
      serviceAccountName: agentcore-runtime-sa  # With IAM role attached
      containers:
      - name: agentcore-runtime
        image: YOUR_ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/agentcore-runtime:latest
        env:
        - name: REGION
          value: "us-west-2"
```

## Usage Examples

### Running Locally

```bash
# Run the container locally for testing
docker run -it \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e REGION=us-west-2 \
  agentcore-runtime:latest
```

### EKS Deployment

1. **Create IAM Role** with Bedrock AgentCore permissions
2. **Attach role** to your EKS service account using IRSA
3. **Deploy** using the ECR image URI

```bash
# Example deployment command
kubectl apply -f your-agentcore-runtime-deployment.yaml
```

## Container Structure

The container includes:

- **Python 3.12.8** runtime environment
- **Core dependencies**: boto3, pydantic, fastapi, uvicorn
- **Observability**: OpenTelemetry instrumentation
- **AgentCore Platform** source code with proper module structure
- **Health check** endpoint for container orchestration

## Troubleshooting

### Build Issues

1. **AWS Authentication**: Ensure AWS CLI is configured
   ```bash
   aws sts get-caller-identity
   ```

2. **Docker Permissions**: Ensure Docker daemon is running
   ```bash
   docker info
   ```

3. **ECR Permissions**: Verify ECR access
   ```bash
   aws ecr describe-repositories --region us-west-2
   ```

### Runtime Issues

1. **Import Errors**: Check PYTHONPATH is set correctly
2. **AWS Permissions**: Verify IAM role has Bedrock AgentCore access
3. **Network**: Ensure container can reach AWS services

## Security Considerations

- **Use IAM roles** instead of access keys in production
- **Enable ECR image scanning** (automatically enabled in build script)
- **Regular updates** of base images and dependencies
- **Network policies** to restrict container access
- **Secrets management** for sensitive configuration

## Development

To modify the container:

1. **Edit Dockerfile** for dependency or configuration changes
2. **Update build script** for build process changes
3. **Test locally** before pushing to ECR
4. **Version your images** using appropriate tags

## Support

For issues related to:
- **Container building**: Check Docker and AWS CLI configuration
- **AgentCore APIs**: Refer to AWS Bedrock AgentCore documentation
- **Platform integration**: See main platform documentation
