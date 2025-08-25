# Docker-based Lambda Packaging

This directory uses Docker to build and package the Lambda function for deployment. This approach ensures that the Lambda function and its dependencies are built in an environment identical to the AWS Lambda runtime.

## How It Works

The Docker-based packaging approach works as follows:

1. Uses the official AWS Lambda Python 3.12 runtime image (`public.ecr.aws/lambda/python:3.12`)
2. Mounts the Lambda function source code and a build directory as volumes:
   - `/asset-input`: Contains the source code (maps to the `functions` directory)
   - `/asset-output`: Output directory for building the package (maps to the `build` directory)
3. Inside the container, it:
   - Copies the Lambda function code
   - Installs dependencies using pip
   - Creates a zip file with the function code and dependencies
4. The resulting zip file is then copied to the project root for Terraform to use

## Benefits

This approach offers several advantages:

1. **Platform Compatibility**: Ensures the package is built in the same environment where it will run
2. **Dependency Consistency**: All dependencies are installed within the Lambda runtime environment
3. **No Local Python Required**: No need to have Python 3.12 or dependencies installed locally
4. **Portable**: Works on any system with Docker, regardless of OS
5. **Reproducible**: Consistent builds every time

## Usage

To package the Lambda function:

```bash
# Make sure the script is executable
chmod +x docker_package_lambda.sh

# Run the packaging script
./docker_package_lambda.sh
```

The script will:
1. Create a local `build` directory if it doesn't exist
2. Run a Docker container to build the package
3. Create a zip file in the build directory
4. Copy the zip file to the project root as `agentcore-memory-provider-lambda.zip`

## Integration with Terraform

The Terraform configuration (`main.tf`) is set up to use the zip file created by the Docker packaging script:

```hcl
resource "aws_agentcore_memory_client" "bedrock_agentcore_memory_setup" {
  # ... other configuration ...
  filename         = var.memory_lambda_zip_path
  source_code_hash = filebase64sha256(var.memory_lambda_zip_path)
  # ... other configuration ...
}
```

The `var.memory_lambda_zip_path` defaults to "agentcore-memory-provider-lambda.zip" in the variables file.

## Before Deployment

Run the packaging script before applying Terraform:

```bash
# Package the Lambda function
./docker_package_lambda.sh

# Deploy with Terraform
terraform init
terraform apply
```

## Notes

- The original `package_lambda.sh` script is kept for reference
- The process requires Docker to be installed and running
- The Lambda zip file will be approximately 10-15 MB in size due to included dependencies
