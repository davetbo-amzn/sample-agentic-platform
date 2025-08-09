# AgentCore Memory Client Tests

This directory contains pytest test cases for the `AgentCoreMemoryClient` class.

## Test Files

### Unit Tests
- `test_agentcore_memory_client.py` - Main unit tests for the AgentCoreMemoryClient class
- `test_agentcore_memory_wait_functions.py` - Specialized tests for the wait functions

### Integration Tests
- `../../../../../integ/service/memory_gateway/client/memory/test_agentcore_memory_client_integration.py` - Integration tests using real AWS services

## Running the Tests

### Unit Tests (Mock-based)
```bash
# Run all unit tests
pytest tests/unit/service/memory_gateway/client/memory/ -v

# Run specific test file
pytest tests/unit/service/memory_gateway/client/memory/test_agentcore_memory_client.py -v

# Run specific test
pytest tests/unit/service/memory_gateway/client/memory/test_agentcore_memory_client.py::TestAgentCoreMemoryClient::test_create_memory_provider -v
```

### Integration Tests (Real AWS Services)
**Warning**: These tests interact with real AWS services and may incur costs.

```bash
# Run integration tests
pytest tests/integ/service/memory_gateway/client/memory/test_agentcore_memory_client_integration.py -v -m integration

# Skip integration tests (set environment variable)
SKIP_INTEGRATION_TESTS=true pytest tests/integ/service/memory_gateway/client/memory/ -v
```

## Prerequisites

### For Unit Tests
- Python packages: `pytest`, `boto3`, `pydantic`
- No AWS credentials required (uses mocks)

### For Integration Tests
- Valid AWS credentials configured
- AWS permissions for:
  - `bedrock-agentcore:*`
  - `bedrock-agentcore-control:*`
  - `ssm:GetParameter`
  - `ssm:PutParameter`

## Environment Variables

- `AWS_REGION` - AWS region to use (default: us-west-2)
- `MEMORY_RETENTION_PERIOD` - Memory retention in days (default: 30)
- `ENVIRONMENT` - Environment name prefix (default: AgentCore-AgentPath)
- `SKIP_INTEGRATION_TESTS` - Set to 'true' to skip integration tests

## Test Coverage

The tests cover:
- ✅ Creating memory providers
- ✅ Deleting memory providers
- ✅ Updating memory providers
- ✅ Wait functions for memory operations
- ✅ Error handling scenarios
- ✅ Environment variable usage
- ✅ AWS service integration (real services)
- ✅ Resource cleanup
- ✅ Timeout handling

## Notes

- Unit tests use mocks and don't require AWS credentials
- Integration tests use real AWS services and require proper permissions
- All integration tests include automatic resource cleanup
- Test resources are uniquely named to avoid conflicts
- Integration tests can be expensive - use cautiously
