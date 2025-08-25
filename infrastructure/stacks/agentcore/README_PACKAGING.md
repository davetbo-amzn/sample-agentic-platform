# Lambda Function Packaging Guide

## Overview

This document explains how to correctly package the Lambda function for the AgentCore service, ensuring it uses Python 3.13 on ARM64 architecture.

## ✅ Recommended Approach: Docker-based Packaging

Always use the Docker-based packaging script to ensure the Lambda package contains the correct Python version and architecture:

```bash
./docker_package_lambda.sh
```

This script:
1. Uses the official AWS Lambda Python 3.13 ARM64 Docker image
2. Ensures all dependencies are built for the target environment
3. Creates a clean build with no local environment artifacts
4. Builds the package in an isolated environment that matches the Lambda runtime

## ❌ DO NOT USE: Local Environment Packaging

The `DO_NOT_USE_local_package_lambda.sh` script should be avoided as it:
1. Uses your local Python environment, which may not match the target Lambda environment
2. May include incompatible binary artifacts (like Python 3.12 .so files on a Python 3.13 runtime)
3. Can cause runtime errors in the Lambda function due to architecture mismatches

## Verifying Correct Packaging

To verify that your package has been correctly built for Python 3.13 ARM64:

```bash
# Unzip the package to a temporary directory
mkdir -p /tmp/lambda-check
cd /tmp/lambda-check
unzip -q ../agentcore-memory-provider-lambda.zip

# Check for Python version in compiled artifacts
find . -name '*.so' | grep python
```

You should see files with `cpython-313-aarch64-linux-gnu.so` extensions, NOT `cpython-312-*` or other versions.

## Troubleshooting

If you encounter issues where the wrong Python version artifacts are included:

1. Make sure to use the docker_package_lambda.sh script
2. Ensure the build directory is cleaned before packaging (this is done automatically by the script)
3. Check that Docker is running and can access the AWS Lambda container image

## Lambda Configuration

The Terraform configuration in `main.tf` is set to use:
- Runtime: Python 3.13
- Architecture: ARM64

Ensure any manual AWS Console changes maintain these settings.
