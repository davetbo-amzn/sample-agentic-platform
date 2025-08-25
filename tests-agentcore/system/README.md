# AgentCore System Tests

This directory contains system tests for deployed AgentCore services after Terraform deployment.

## Overview

These system tests validate the deployed AgentCore infrastructure by testing:

- **AgentCore Memory Lambda** - Tests the deployed Lambda function for memory operations
- **AgentCore Runtime ECS Service** - Tests the deployed ECS service for runtime operations
- **End-to-End Workflows** - Tests complete workflows using deployed services

Unlike integration tests that start services locally, system tests invoke actual AWS resources deployed by Terraform.

## Test Files

- `test_agentcore_memory_lambda_system.py` - Tests deployed Lambda function for memory operations
- `test_agentcore_runtime_lambda_system.py` - Tests deployed ECS service for runtime operations
- `test_jwt_runtime_memory_integration.py` - Integration test for JWT runtime invocation with memory event creation

## Prerequisites

1. **Deployed Infrastructure**: Services must be deployed via Terraform:
   ```bash
   cd sample-agentic-platform/infrastructure/stacks/agentcore
   terraform init
   terraform plan
   terraform apply
   ```

2. **Environment Variables**: Configure `.env` file with deployed resource information:
   ```bash
   # Required for system tests
   export DEPLOYED_LAMBDA_FUNCTION_NAME=<terraform-output-lambda-name>
   export DEPLOYED_ECS_CLUSTER_NAME=<terraform-output-cluster-name>
   export DEPLOYED_ECS_SERVICE_NAME=<terraform-output-service-name>
   export DEPLOYED_ALB_DNS_NAME=<terraform-output-alb-dns>
   export REGION=us-west-2
   ```

3. **AWS Credentials**: Ensure AWS credentials have permissions for:
   - Lambda function invocation
   - ECS service interaction
   - CloudWatch logs access
   - Bedrock AgentCore operations

## Test Categories

### Lambda Function Tests
- Memory provider operations
- Resource provisioning
- Error handling and validation
- Performance and timeout testing

### ECS Service Tests  
- Runtime creation and management
- Container health and status
- Service scaling and availability
- Network connectivity

### End-to-End Tests
- Complete agent workflows
- Service-to-service communication
- Data persistence and consistency
- Production scenario simulation

## Running Tests

### Run All System Tests
```bash
pytest -v
```

### Run Specific Test Categories
```bash
# Memory Lambda tests only
pytest test_agentcore_memory_lambda_system.py -v

# Runtime ECS tests only  
pytest test_agentcore_runtime_ecs_system.py -v

# End-to-end tests only
pytest test_agentcore_end_to_end_system.py -v
```

### Run Tests with AWS Resource Discovery
```bash
# Auto-discover deployed resources using Terraform outputs
pytest --discover-resources -v
```

## Configuration

### Terraform Integration
System tests can automatically discover deployed resources from Terraform state:

```python
import subprocess
import json

def get_terraform_outputs():
    """Get Terraform outputs for deployed resources."""
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd="../../infrastructure/stacks/agentcore",
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)
```

### AWS Resource Discovery
Tests can discover resources using AWS tags and naming conventions:

```python
import boto3

def discover_agentcore_resources():
    """Discover deployed AgentCore resources by tags."""
    # Use boto3 to find resources with specific tags
    # Return resource ARNs, names, and endpoints
```

## Test Data Management

### Resource Cleanup
- System tests clean up any test data created
- Test resources use unique identifiers to avoid conflicts
- Failed test cleanup is logged for manual review

### Test Isolation
- Each test uses unique resource identifiers
- Tests can run in parallel without conflicts
- Shared resources are accessed read-only when possible

## Monitoring and Observability

### CloudWatch Integration
```python
def get_lambda_logs(function_name, start_time):
    """Retrieve CloudWatch logs for Lambda function."""
    logs_client = boto3.client('logs')
    # Query logs for test validation
```

### X-Ray Tracing
```python
def validate_trace_data(trace_id):
    """Validate X-Ray trace data for end-to-end requests."""
    xray_client = boto3.client('xray')
    # Analyze trace segments and timing
```

## Performance Testing

### Load Testing
```python
def test_lambda_under_load():
    """Test Lambda function performance under concurrent load."""
    # Use threading to simulate multiple concurrent invocations
```

### Resource Monitoring
```python
def monitor_resource_utilization():
    """Monitor ECS task CPU/memory during tests."""
    # Query CloudWatch metrics for resource usage
```

## Security Testing

### IAM Permission Validation
```python
def test_least_privilege_access():
    """Validate IAM roles have minimum required permissions."""
    # Test that roles cannot access unauthorized resources
```

### Network Security
```python
def test_network_isolation():
    """Validate network security groups and VPC configuration."""
    # Test that services are properly isolated
```

## Troubleshooting

### Common Issues

1. **Lambda Timeout**: Increase timeout in test configuration
2. **ECS Service Not Ready**: Wait for service to reach stable state
3. **Network Connectivity**: Verify security groups and VPC configuration
4. **Permission Errors**: Check IAM roles and policies

### Debug Commands
```bash
# Check Lambda function status
aws lambda get-function --function-name <function-name>

# View CloudWatch logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/"
```

### Log Analysis
```python
def analyze_test_logs():
    """Analyze CloudWatch logs for test failures."""
    # Parse logs and extract error patterns
    # Generate diagnostic reports
```

## CI/CD Integration

### Pipeline Configuration
```yaml
# Example GitHub Actions step
- name: Run AgentCore System Tests
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  run: |
    cd sample-agentic-platform/tests-agentcore/system
    pip install -r requirements.txt
    pytest -v --tb=short --junit-xml=results.xml
```

### Test Reporting
```python
def generate_test_report():
    """Generate comprehensive test report with AWS resource status."""
    # Include resource health, performance metrics, and test results
```

## Best Practices

1. **Resource Discovery**: Use Terraform outputs when available
2. **Error Handling**: Test both success and failure scenarios  
3. **Cleanup**: Always clean up test resources
4. **Monitoring**: Validate metrics and logs
5. **Security**: Test with least-privilege permissions
6. **Performance**: Include load and stress testing
7. **Documentation**: Document test scenarios and expected outcomes

## Security Notes

- Tests use production-equivalent security configuration
- Sensitive data is handled according to security policies
- Test credentials have minimal required permissions
- All test activities are logged and auditable
