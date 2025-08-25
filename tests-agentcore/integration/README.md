# AgentCore Integration Tests

This directory contains integration tests for the AgentCore services:

- **AgentCore Runtime** - Tests for the agentcore-runtime service
- **Memory Gateway** - Tests for the memory-gateway service
- **Combined Integration** - Tests for both services working together

## Overview

These integration tests use multiprocessing to spin up actual services and make HTTP requests to test their functionality. Each test module:

1. Starts the required service(s) using `make` commands
2. Waits for the service(s) to become ready
3. Executes test scenarios against the live services
4. Cleans up the service processes after testing

## Test Files

- `test_agentcore_runtime_integration.py` - AgentCore Runtime service tests
- `test_memory_gateway_integration.py` - Memory Gateway service tests
- `test_agentcore_combined_integration.py` - Combined service interaction tests

## Prerequisites

1. **Environment Variables**: Copy and configure `.env` file with required AWS credentials and settings:
   ```bash
   cp ../tests-agentcore/.env.example ../tests-agentcore/.env
   # Edit .env with your values
   ```

2. **Dependencies**: Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

3. **Services**: Ensure the sample-agentic-platform services can be started via make commands:
   ```bash
   # From sample-agentic-platform directory
   make agentcore-runtime  # Should start on port 8003
   make memory-gateway     # Should start on port 8004
   ```

## Required Environment Variables

The tests require these environment variables (defined in `.env`):

### AgentCore Runtime Tests
- `TEST_CONTAINER_URI` - ECR container URI for AgentCore runtime
- `TEST_ROLE_ARN` - IAM role ARN for AgentCore runtime execution
- `RUNTIME_ID` - Existing runtime ID for get/update tests
- `TEST_DELETE_RUNTIME_ID` - Runtime ID for delete tests (optional)

### Memory Gateway Tests
- `MEMORY_CLIENT` - Set to "AGENTCORE" to enable AgentCore memory provider tests

### General
- `REGION` - AWS region (default: us-west-2)

## Running Tests

### Run All Integration Tests
```bash
pytest -v
```

### Run Specific Test Files
```bash
# AgentCore Runtime tests only
pytest test_agentcore_runtime_integration.py -v

# Memory Gateway tests only
pytest test_memory_gateway_integration.py -v

# Combined integration tests only
pytest test_agentcore_combined_integration.py -v
```

### Run Specific Test Classes
```bash
# Runtime integration tests
pytest test_agentcore_runtime_integration.py::TestAgentCoreRuntimeIntegration -v

# Memory gateway tests
pytest test_memory_gateway_integration.py::TestMemoryGatewayIntegration -v

# Combined tests
pytest test_agentcore_combined_integration.py::TestAgentCoreCombinedIntegration -v
```

### Run Tests with Output
```bash
pytest -v -s  # Shows print statements and detailed output
```

## Test Architecture

### Service Management
Each test class uses a server manager that:
- Starts services using subprocess and make commands
- Waits for services to become ready (health check endpoints)
- Manages service cleanup after tests complete

### Multiprocessing Strategy
- **Server Process**: Runs the actual service(s) via make commands
- **Test Process**: Executes pytest and makes HTTP requests to services
- **Worker Processes**: For concurrency testing

### Test Categories

#### Basic Functionality Tests
- Health/ping endpoints
- CRUD operations (Create, Read, Update, Delete)
- Error handling and edge cases

#### Integration Tests
- Service-to-service communication
- End-to-end workflows
- Data consistency across services

#### Concurrency Tests
- Multiple simultaneous requests
- Process safety
- Resource cleanup

## Test Data

Tests generate dynamic test data using:
- `uuid4()` for unique IDs
- Timestamps for temporal data
- Environment variables for AWS resources

## Troubleshooting

### Service Startup Issues
```bash
# Check if services can start manually
cd ../../../sample-agentic-platform
make agentcore-runtime
make memory-gateway
```

### Port Conflicts
- AgentCore Runtime uses port 8003
- Memory Gateway uses port 8004
- Ensure these ports are available

### AWS Permissions
- Verify AWS credentials have necessary permissions
- Check IAM roles and ECR access
- Validate environment variable values

### Environment Issues
```bash
# Check environment variables
cat ../.env

# Verify Python dependencies
pip list | grep -E "(pytest|requests|dotenv)"
```

### Test Debugging
```bash
# Run with maximum verbosity
pytest -vvv -s --tb=long

# Run single test with debugging
pytest test_agentcore_runtime_integration.py::TestAgentCoreRuntimeIntegration::test_ping_endpoint -vvv -s
```

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions step
- name: Run AgentCore Integration Tests
  env:
    TEST_CONTAINER_URI: ${{ secrets.TEST_CONTAINER_URI }}
    TEST_ROLE_ARN: ${{ secrets.TEST_ROLE_ARN }}
    RUNTIME_ID: ${{ secrets.RUNTIME_ID }}
  run: |
    cd sample-agentic-platform/tests-agentcore/integration
    pip install -r requirements.txt
    pytest -v --tb=short
```

## Performance Considerations

- **Startup Time**: Services may take 30-45 seconds to start
- **Test Duration**: Full test suite may take 5-10 minutes
- **Resource Usage**: Tests spawn multiple processes
- **Cleanup**: Services are properly terminated after tests

## Extending Tests

To add new tests:

1. **Add Test Methods**: Follow existing patterns in test classes
2. **Use Fixtures**: Consider pytest fixtures for common setup
3. **Environment Variables**: Add new variables to `.env` as needed
4. **Service Management**: Reuse existing server manager classes
5. **Assertions**: Use flexible assertions that handle various response codes

## Security Notes

- Tests use test-specific AWS resources
- Sensitive data should be in environment variables
- Test data includes random UUIDs to avoid conflicts
- Services are cleaned up to prevent resource leaks
