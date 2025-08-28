# AgentCore Tests

This directory contains pytest test cases for AgentCore services.

## Test Files

### Memory Client Tests
- `test_agentcore_memory_client.py` - Integration tests for the AgentCoreMemoryClient class (uses real AWS services)

### Runtime Client Tests  
- `test_agentcore_runtime_client.py` - Integration tests for the AgentCoreRuntimeClient class (uses real AWS services)
- `test_invoke_agentcore_runtime.py` - Integration tests for the invoke_agentcore_runtime function (uses real AWS services)

## Running the Tests

### Memory Client Tests (Integration - Real AWS Services)
**Warning**: Memory client tests interact with real AWS services and may incur costs.

```bash
# Run memory client integration tests
pytest tests-agentcore/test_agentcore_memory_client.py -v
```

### Runtime Client Tests (Integration - Real AWS Services)  
**Warning**: Runtime client tests interact with real AWS services and may incur costs.

```bash
# Run runtime client integration tests
pytest tests-agentcore/test_agentcore_runtime_client.py -v

# Run all tests
pytest tests-agentcore/ -v

# Run specific test
pytest tests-agentcore/test_agentcore_runtime_client.py::test_create_agent_runtime -v
```

## Prerequisites

### For Both Integration Test Suites
- Python packages: `pytest`, `boto3`, `pydantic`
- Valid AWS credentials configured
- AWS permissions for:
  - Memory Client: `bedrock-agentcore:*`, `bedrock-agentcore-control:*`, `ssm:GetParameter`, `ssm:PutParameter`
  - Runtime Client: `bedrock-agentcore-control:*` (for agent runtime operations)

## Environment Variables

- `REGION` - AWS region to use (default: us-west-2)
- `MEMORY_RETENTION_PERIOD` - Memory retention in days (default: 30) [Memory tests only]
- `ENVIRONMENT` - Environment name prefix (default: AgentCore-AgentPath) [Memory tests only]
- `TEST_WITH_MEMORY_ID` - Use existing memory ID for testing [Memory tests only]
- `TEST_WITH_RUNTIME_ID` - Use existing runtime ID for testing [Runtime tests only]
- `TEST_CONTAINER_URI` - **Required for runtime creation**: Real ECR container URI (e.g., `123456789012.dkr.ecr.us-west-2.amazonaws.com/my-agent:latest`)
- `TEST_ROLE_ARN` - **Required for runtime creation**: Real IAM role ARN (e.g., `arn:aws:iam::123456789012:role/MyAgentCoreRuntimeRole`)

### Runtime Test Infrastructure Requirements

To run tests that create new agent runtimes, you must provide:

1. **ECR Container Image**: A real container image in ECR that contains your agent code
2. **IAM Role**: A real IAM role with appropriate permissions for AgentCore runtime execution

If these are not provided via environment variables, those tests will be **automatically skipped**.

#### Alternative: Use Existing Runtime
Set `TEST_WITH_RUNTIME_ID` to use an existing runtime and avoid infrastructure requirements:
```bash
export TEST_WITH_RUNTIME_ID="your-existing-runtime-id"
```

## Test Coverage

### Memory Client Tests
- ✅ Creating memory providers
- ✅ Deleting memory providers
- ✅ Updating memory providers
- ✅ Wait functions for memory operations
- ✅ Session context management
- ✅ Memory retrieval and creation
- ✅ Error handling scenarios
- ✅ AWS service integration (real services)
- ✅ Resource cleanup

### Runtime Client Tests (Integration Tests with Real AWS Services)
- ✅ Creating agent runtimes (minimal and full parameters)
- ✅ Retrieving runtime details
- ✅ Listing runtimes (with and without pagination)
- ✅ Updating runtime configurations
- ✅ Deleting runtimes
- ✅ Error handling for non-existent resources
- ✅ Environment variable configuration
- ✅ Edge cases (empty results, no changes)
- ✅ AWS service integration (real services)
- ✅ Resource cleanup and lifecycle management

## Notes

### Both Test Suites (Integration Tests)
- Use real AWS services and require proper AWS credentials and permissions
- Include automatic resource cleanup to minimize costs
- Test resources are uniquely named with timestamps to avoid conflicts
- Can be expensive - use cautiously
- Support using existing resources via environment variables to reduce costs
- Runtime tests include wait functions to handle asynchronous AWS operations
- Memory tests include session management and event creation functionality
- Both test suites provide comprehensive validation of client functionality against real AWS APIs
