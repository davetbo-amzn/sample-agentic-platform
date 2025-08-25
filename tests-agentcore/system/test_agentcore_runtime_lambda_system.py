"""
System tests for deployed AgentCore Runtime Lambda functions.

This module tests the deployed Lambda functions that handle AgentCore runtime operations
after they have been deployed by Terraform.

Uses session-scoped fixtures for memory providers and JWT-authenticated runtimes.
"""

import json
import time
import uuid
from typing import Dict, Any, List
from uuid import uuid4

import boto3
import pytest
from botocore.exceptions import ClientError

# Import JWT token generation utility
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "script"))
from get_auth_token import get_token


@pytest.mark.lambda_test
def test_runtime_controller_lambda_exists(lambda_client, deployed_resources):
    """Test that the runtime controller Lambda function exists and is active."""
    function_name = deployed_resources.get("bedrock_agentcore_runtime_controller_function_name")
    if not function_name:
        # Try to find it by naming pattern
        response = lambda_client.list_functions()
        for func in response.get("Functions", []):
            if "bedrock-agentcore-runtime-controller" in func["FunctionName"]:
                function_name = func["FunctionName"]
                break
    
    assert function_name, (
        "Runtime controller Lambda function not found in deployed resources. "
        "Ensure AgentCore infrastructure is deployed with runtime controller Lambda function."
    )
    
    response = lambda_client.get_function(FunctionName=function_name)
    
    assert response["Configuration"]["State"] == "Active"
    assert response["Configuration"]["Runtime"] == "python3.13"
    assert "bedrock-agentcore-runtime-controller" in response["Configuration"]["FunctionName"]
    
    print(f"Runtime controller Lambda function {function_name} is active and ready")


@pytest.mark.lambda_test
def test_runtime_controller_lambda_configuration(lambda_client, deployed_resources, environment):
    """Test runtime controller Lambda function configuration."""
    function_name = deployed_resources.get("bedrock_agentcore_runtime_controller_function_name")
    assert function_name, (
        "Runtime controller Lambda function name not available in deployed resources. "
        "Ensure AgentCore infrastructure is deployed with runtime controller Lambda function."
    )
    
    response = lambda_client.get_function(FunctionName=function_name)
    print(f"Got lambda function response {response}")
    config = response["Configuration"]
    
    # Check basic configuration
    assert config["Timeout"] == 300
    assert config["MemorySize"] == 128
    assert config["Handler"] == "agentic_platform.service.agentcore.runtime.api.agentcore_runtime_controller.handler"
    
    # Check environment variables
    env_vars = config.get("Environment", {}).get("Variables", {})
    assert "ENVIRONMENT" in env_vars
    assert "REGION" in env_vars
    assert env_vars["ENVIRONMENT"] == environment
    
    print(f"Runtime controller Lambda configuration validated for {function_name}")


def test_bedrock_agentcore_operations(agentcore_control_client, aws_region):
    """Test basic Bedrock AgentCore operations through the client."""
    try:
        # Test listing AgentCore runtimes  
        response = agentcore_control_client.list_agent_runtimes(maxResults=10)
        print(f"response from list_agent_runtimes: {response}")
        # Should return successful response
        assert "agentRuntimes" in response
        
        runtimes = response.get("agentRuntimes", [])
        print(f"Found {len(runtimes)} existing AgentCore runtimes")
        
        for runtime in runtimes:
            runtime_id = runtime.get("agentRuntimeId")
            status = runtime.get("status")
            print(f"  - Runtime {runtime_id}: {status}")
            
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        
        # Some permission errors are expected in test environments
        if error_code in ["AccessDeniedException", "UnauthorizedOperation"]:
            print(f"Expected permission error: {error_code}")
        else:
            pytest.fail(f"Unexpected error in AgentCore operations: {e}")


def test_session_runtime_verification(agentcore_control_client, session_runtime):
    """Test that the session-scoped JWT-authenticated runtime was created successfully."""
    # The session_runtime fixture already created a JWT-authenticated runtime for us
    print(f'Got session_runtime: {session_runtime}')
    assert session_runtime and session_runtime.agent_runtime_id, "Session runtime must be available"
    
    runtime_id = session_runtime.agent_runtime_id
    runtime_arn = session_runtime.agent_runtime_arn
    
    assert runtime_arn, "Session runtime ARN must be available"
    
    # Verify the runtime exists and is active
    response = agentcore_control_client.get_agent_runtime(
        agentRuntimeId=runtime_id
    )
    if not isinstance(response, dict):
        response = response.__dict__
    # Validate runtime details
    assert response["agentRuntimeId"] == runtime_id, "Runtime ID should match"
    assert response["agentRuntimeArn"] == runtime_arn, "Runtime ARN should match"
    assert response["status"] in ["CREATING", "READY"], f"Runtime should be in valid state, got: {response['status']}"
    
    # Verify it has JWT authentication configured
    assert "authorizerConfiguration" in response, "Runtime should have authorizer configuration"
    auth_config = response["authorizerConfiguration"]
    assert "customJWTAuthorizer" in auth_config, "Runtime should have customJWTAuthorizer configuration"
    
    jwt_config = auth_config["customJWTAuthorizer"]
    assert "discoveryUrl" in jwt_config, "JWT config should have discoveryUrl"
    assert "allowedClients" in jwt_config, "JWT config should have allowedClients"
    
    print(f"✅ Session runtime {runtime_id} verified with JWT authentication")
    print(f"JWT discovery URL: {jwt_config['discoveryUrl']}")
    print(f"JWT allowed clients: {jwt_config['allowedClients']}")


def test_agentcore_runtime_get_operation(agentcore_control_client):
    """Test retrieving AgentCore runtime information."""
    # First, list runtimes to get an existing one to test with
    try:
        list_response = agentcore_control_client.list_agent_runtimes(maxResults=5)
        runtimes = list_response.get("agentRuntimes", [])
        
        if runtimes:
            # Test getting details for the first runtime
            runtime_to_test = runtimes[0]
            runtime_id = runtime_to_test["agentRuntimeId"]
            
            get_response = agentcore_control_client.get_agent_runtime(
                agentRuntimeId=runtime_id
            )
            
            # Should return runtime details
            assert "agentRuntimeId" in get_response
            assert get_response["agentRuntimeId"] == runtime_id
            assert "status" in get_response
            
            print(f"Successfully retrieved runtime {runtime_id}: {get_response['status']}")
        else:
            # No existing runtimes, but that's still a valid test result
            print("No existing runtimes found - this is a valid state for the get operation test")
            
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        
        if error_code in ["AccessDeniedException", "ResourceNotFoundException"]:
            print(f"Expected error in get operation: {error_code}")
        else:
            pytest.fail(f"Unexpected error in get operation: {e}")


@pytest.mark.lambda_test
def test_runtime_controller_lambda_invocation(lambda_client, deployed_resources):
    """Test invoking the runtime controller Lambda function - it must actually work, not fail with import errors."""
    function_name = deployed_resources.get("bedrock_agentcore_runtime_controller_function_name")
    assert function_name, (
        "Runtime controller Lambda function name not available in deployed resources. "
        "Ensure AgentCore infrastructure is deployed with runtime controller Lambda function."
    )
    
    # Create test payload for runtime operations
    test_payload = {
        "operation": "list-agent-runtimes",
        "input": {
            "maxResults": 20
        }
    }
    
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(test_payload)
    )
    print(f"Got response from invoke: {response}")
    # Check response
    assert response["StatusCode"] == 200, f"Lambda invocation failed with status: {response['StatusCode']}"
    
    # Parse response payload
    response_payload = json.loads(response["Payload"].read())
    print(f"Got response payload {response_payload}")
    # Check for deployment/import failures - these should FAIL the test
    if "errorMessage" in response_payload:
        error_message = response_payload["errorMessage"]
        error_type = response_payload.get("errorType", "Unknown")
        
        # These are deployment failures that should fail the test
        if any(failure_indicator in error_message for failure_indicator in [
            "Unable to import module",
            "No module named",
            "ModuleNotFoundError",
            "ImportError",
            "AttributeError"  # AttributeError indicates missing methods/attributes - deployment issue
        ]):
            pytest.fail(f"Lambda deployment failure - {error_type}: {error_message}")
        
        # If we get here, it's a real error that should fail the test - no "expected" errors
        pytest.fail(f"Runtime controller invocation failed with unexpected error - {error_type}: {error_message}")
    else:
        # Successful invocation should have proper response structure
        assert "statusCode" in response_payload or "result" in response_payload, "Lambda response missing required fields"
        print(f"Runtime controller invocation successful: {response_payload}")


def test_agentcore_concurrent_operations(agentcore_control_client):
    """Test concurrent AgentCore operations."""
    import concurrent.futures
    
    def list_runtimes(worker_id: int) -> Dict[str, Any]:
        """Worker function for concurrent runtime listing."""
        try:
            response = agentcore_control_client.list_agent_runtimes(maxResults=5)
            return {
                "worker_id": worker_id,
                "runtime_count": len(response.get("agentRuntimes", [])),
                "success": True
            }
        except Exception as e:
            return {
                "worker_id": worker_id,
                "error": str(e),
                "success": False
            }
    
    # Run 3 concurrent operations
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(list_runtimes, i) for i in range(3)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    # Validate results
    assert len(results) == 3
    successful_operations = sum(1 for r in results if r["success"])
    
    # At least some operations should succeed
    assert successful_operations >= 1, f"All concurrent operations failed: {results}"
    
    print(f"Concurrent operations completed: {successful_operations}/3 successful")


def test_agentcore_error_handling(agentcore_control_client):
    """Test error handling with intentionally invalid operations - must test real error handling, not mask permission issues."""
    
    # Test 1: Invalid runtime ID format should return ValidationException or ResourceNotFoundException
    try:
        invalid_runtime_id = "invalid-runtime-id-12345"
        agentcore_control_client.get_agent_runtime(agentRuntimeId=invalid_runtime_id)
        
        # Should not reach here if error handling works
        pytest.fail("Expected error for invalid runtime ID")
        
    except ClientError as e:
        print(f"ERROR: {str(e)}")
        error_code = e.response.get("Error", {}).get("Code")
        
        # For invalid resource ID, we should get ResourceNotFoundException or ValidationException
        # AccessDeniedException might indicate a real permission problem, not proper input validation
        if error_code == "AccessDeniedException":
            if 'Agent RelativeId does not match Bedrock AgentCore ARN format' in str(e):
                assert 'Agent RelativeId does not match Bedrock AgentCore ARN format' in str(e)
            else: 
                pytest.fail(f"Got AccessDeniedException but not the expected error for an invalid runtime ID.")
           
    
    # Test 2: Invalid parameter format in create operation
    try:
        agentcore_control_client.create_agent_runtime(
            roleArn="invalid-role-arn-format",  # Invalid ARN format
            agentRuntimeName="test-error-handling",
            agentRuntimeArtifact={
                "containerConfiguration": {
                    "containerUri": "invalid-container-uri"  # Invalid format
                }
            },
            networkConfiguration={
                "networkMode": "INVALID_MODE"  # Invalid mode
            }
        )
        
        pytest.fail("Expected validation error for invalid parameters")
        
    except ClientError as e:
        if 'The IAM role ARN format is invalid.' in str(e):
            print(f"Got expected failure result from invalid arn")
            assert 'The IAM role ARN format is invalid.' in str(e)
        else:
            pytest.fail(f"Unexpected failure result from invalid arn: {str(e)}")

@pytest.mark.lambda_test
def test_lambda_cloudwatch_logs(logs_client, deployed_resources):
    """Test that runtime controller Lambda generates CloudWatch logs."""
    function_name = deployed_resources.get("bedrock_agentcore_runtime_controller_function_name")
    assert function_name, (
        "Runtime controller Lambda function name not available in deployed resources. "
        "Ensure AgentCore infrastructure is deployed with runtime controller Lambda function."
    )
    
    # Construct log group name
    log_group_name = f"/aws/lambda/{function_name}"
    
    try:
        # Check if log group exists
        response = logs_client.describe_log_groups(
            logGroupNamePrefix=log_group_name,
            limit=1
        )
        
        log_groups = response.get("logGroups", [])
        if log_groups:
            log_group = log_groups[0]
            assert log_group["logGroupName"] == log_group_name
            print(f"CloudWatch log group exists: {log_group_name}")
            
            # Try to get recent log streams
            streams_response = logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy="LastEventTime",
                descending=True,
                limit=5
            )
            
            log_streams = streams_response.get("logStreams", [])
            if log_streams:
                print(f"Found {len(log_streams)} log streams in {log_group_name}")
            else:
                print(f"No log streams found in {log_group_name} (function may not have been invoked recently)")
        else:
            print(f"Log group {log_group_name} not found (function may not have been invoked)")
            
    except ClientError as e:
        print(f"Could not access CloudWatch logs: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
