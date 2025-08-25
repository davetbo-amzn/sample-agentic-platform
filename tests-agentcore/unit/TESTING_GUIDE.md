# AgentCore Integration Testing Guide

This guide provides comprehensive instructions for testing AgentCore Runtime and Memory services with the updated boto3 service names and proper resource cleanup.

## Prerequisites

### 1. AWS Credentials
Ensure you have AWS credentials configured locally:
```bash
# Via AWS CLI
aws configure

# Or via environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-west-2
```

### 2. Required Permissions
Your AWS credentials need the following permissions:
- `bedrock-agentcore:*` (for AgentCore data plane operations)
- `bedrock-agentcore-control:*` (for AgentCore control plane operations)
- `ssm:GetParameter`, `ssm:PutParameter` (for memory operations)
- Additional permissions for ECR and IAM (if creating new runtimes)

### 3. Python Environment
```bash
cd sample-agentic-platform
uv sync  # This installs boto3 1.40.6+ with AgentCore service support
```

## Running the Tests

### Quick Validation Test
First, verify all imports work correctly:
```bash
cd sample-agentic-platform
uv run python -c "
import sys
sys.path.insert(0, 'src')
from agentic_platform.service.agentcore.runtime.client.agentcore_runtime_client import AgentCoreRuntimeClient
from agentic_platform.service.memory_gateway.client.memory.agentcore_memory_client import AgentCoreMemoryClient
from agentic_platform.core.middleware.auth.agentcore_token_auth_converter import AgentCoreTokenAuthConverter
import boto3
boto3.client('bedrock-agentcore', region_name='us-west-2')
boto3.client('bedrock-agentcore-control', region_name='us-west-2')
print('✅ All AgentCore components working correctly!')
"
```

### AgentCore Memory Tests
```bash
cd tests-agentcore
pytest test_agentcore_memory_client.py -v
```

**Environment Variables for Memory Tests:**
- `REGION` - AWS region (default: us-west-2)
- `TEST_WITH_MEMORY_ID` - Use existing memory ID instead of creating new one

### AgentCore Runtime Tests
```bash
cd tests-agentcore
pytest test_agentcore_runtime_client.py -v
```

**Environment Variables for Runtime Tests:**
- `REGION` - AWS region (default: us-west-2)
- `TEST_WITH_RUNTIME_ID` - Use existing runtime ID instead of creating new one
- `TEST_CONTAINER_URI` - ECR container URI (required for creating new runtimes)
- `TEST_ROLE_ARN` - IAM role ARN (required for creating new runtimes)

### Example with Environment Variables
```bash
# Test with existing resources (no new resource creation)
export REGION=us-west-2
export TEST_WITH_MEMORY_ID=existing-memory-id-123
export TEST_WITH_RUNTIME_ID=existing-runtime-id-456
pytest test_agentcore_memory_client.py test_agentcore_runtime_client.py -v

# Test with new resource creation (requires infrastructure)
export REGION=us-west-2
export TEST_CONTAINER_URI=123456789012.dkr.ecr.us-west-2.amazonaws.com/my-agent:latest
export TEST_ROLE_ARN=arn:aws:iam::123456789012:role/AgentCoreRuntimeRole
pytest test_agentcore_runtime_client.py -v
```

## Test Categories

### 1. Import and Service Name Tests
- Verify boto3 1.40.6+ recognizes new service names
- Test all AgentCore component imports
- Validate client creation with correct service names

### 2. Memory Integration Tests  
- `test_get_session_context_new_user()` - Creates session for new user
- `test_get_memories()` - Retrieves memories from session
- `test_create_memory_event()` - Creates memory events
- Proper cleanup of memory resources

### 3. Runtime Integration Tests
- `test_create_agentcore_runtime()` - Creates/verifies runtime
- `test_get_agentcore_runtime()` - Retrieves runtime details  
- `test_list_agentcore_runtimes()` - Lists available runtimes
- `test_update_agentcore_runtime()` - Updates runtime configuration
- `test_delete_agentcore_runtime()` - Deletes runtime with cleanup
- Error handling for non-existent resources

## Key Testing Principles

### ✅ What We DO
- **Use real AWS services** - All tests make actual API calls
- **Clean up resources** - Tests automatically clean up created resources
- **Use correct service names**:
  - `'bedrock-agentcore'` for data plane operations
  - `'bedrock-agentcore-control'` for control plane operations  
- **Respect constraints**:
  - `eventExpiryDuration` minimum value of 7
  - Use default delay/retry settings
  - Follow memory bank critical constraints

### ❌ What We DON'T DO
- **No mocking** - These are integration tests using real AWS services
- **No hardcoded delays** - Use AWS service default values
- **No manual resource cleanup** - Tests handle their own cleanup

## Troubleshooting

### "Unknown service: 'bedrock-agentcore'" Error
This indicates boto3 version is too old:
```bash
cd sample-agentic-platform
uv sync  # Updates to boto3 1.40.6+
```

### Permission Denied Errors
Ensure your AWS credentials have the required AgentCore permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:*",
                "bedrock-agentcore-control:*",
                "ssm:GetParameter",
                "ssm:PutParameter"
            ],
            "Resource": "*"
        }
    ]
}
```

### Resource Creation Failures
For runtime tests that create new resources:
1. Ensure `TEST_CONTAINER_URI` points to a valid ECR image
2. Ensure `TEST_ROLE_ARN` exists and has proper AgentCore permissions
3. Or use `TEST_WITH_RUNTIME_ID` to test with existing resources

### Test Cleanup Issues
If tests fail to clean up resources:
1. Check AWS console for orphaned AgentCore resources
2. Manually delete any test resources with names starting with `test_runtime` or `test-user`
3. Tests use session-scoped fixtures to minimize resource creation

## Memory Bank Integration

These tests follow the critical constraints documented in the memory bank:
- **AWS Service Names**: Always use correct service names as documented
- **No Mocking**: Integration tests use real AWS services only
- **Resource Cleanup**: All tests clean up their own resources
- **Default Settings**: Use AWS service defaults for timing parameters

## Continuous Integration

For CI/CD environments:
```bash
# Set environment variables in your CI system
export AWS_ACCESS_KEY_ID=${CI_AWS_ACCESS_KEY}
export AWS_SECRET_ACCESS_KEY=${CI_AWS_SECRET_KEY}
export REGION=us-west-2

# Run tests with existing resources (no new creation)
export TEST_WITH_MEMORY_ID=${CI_MEMORY_ID}
export TEST_WITH_RUNTIME_ID=${CI_RUNTIME_ID}

# Execute tests
cd tests-agentcore
pytest -v --tb=short
```

## Success Criteria

When all tests pass, you can be confident that:
✅ boto3 1.40.6+ is properly installed and configured  
✅ All AgentCore service names are correctly updated  
✅ AgentCore Runtime operations work end-to-end  
✅ AgentCore Memory operations work end-to-end  
✅ Resource cleanup is functioning properly  
✅ Error handling works for edge cases  

This validates that the AgentCore integration is production-ready and follows all documented best practices.
