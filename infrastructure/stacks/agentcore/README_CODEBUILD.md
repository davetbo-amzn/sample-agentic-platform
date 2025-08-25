# AWS CodeBuild Lambda Packaging

This directory now uses AWS CodeBuild to build and package the Lambda function for deployment, replacing the previous local packaging script (`package_lambda.sh`).

## How It Works

The Terraform configuration now:

1. Creates an S3 bucket specifically for Lambda deployment packages
2. Sets up a CodeBuild project that:
   - Takes the Lambda function source code from the `functions` directory
   - Installs the required dependencies in a Linux environment
   - Packages everything into a zip file
   - Uploads the package to S3
   - Returns the S3 location for use by the Lambda resource

3. Updates the Lambda resource to reference the S3-based package instead of a local file

## Benefits

This approach offers several advantages over local packaging:

1. **Platform independence**: The build process runs in a standardized Linux container, ensuring the package is compatible with AWS Lambda's Linux environment
2. **Consistent dependencies**: Dependencies are installed within the CodeBuild environment, eliminating "works on my machine" issues
3. **Automatic triggers**: The build is automatically triggered when the Lambda code changes
4. **CI/CD friendly**: This approach integrates better with CI/CD pipelines
5. **Reduced local setup**: No need to have the right Python version or dependencies locally
6. **Artifact management**: S3 provides proper versioning and storage of Lambda packages

## Usage

To deploy:

```bash
terraform init
terraform apply
```

The CodeBuild project will automatically run during apply, build the Lambda package, and upload it to S3. The Lambda function will then be created or updated using that package.

## Implementation Details

- `lambda_build.tf`: Contains the S3, CodeBuild, and related resource definitions
- `main.tf`: Updated to use the S3 package instead of a local file
- The source code hash from the Lambda function file is used to trigger rebuilds when the code changes

## Notes

- The original `package_lambda.sh` script is kept for reference but is no longer used
- The CodeBuild project uses the Amazon Linux 2 image with Python 3.12
- The process creates temporary files (`build_id.txt` and `lambda_s3_path.txt`) in the module directory
- The S3 bucket has `force_destroy` set to true for easier cleanup
