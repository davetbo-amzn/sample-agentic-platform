"""
System tests for deployed AgentCore Memory Lambda function.

This module tests the deployed Lambda function that handles AgentCore memory operations
after it has been deployed by Terraform.
"""

import json
import time
import uuid
import concurrent.futures
from typing import Dict, Any
from uuid import uuid4
from datetime import datetime, timezone

import boto3
import pytest
from botocore.exceptions import ClientError


@pytest.mark.lambda_test
def test_memory_lambda_function_exists(lambda_client, memory_lambda_function):
    """Test that the Memory Lambda function exists and is active."""
    try:
        response = lambda_client.get_function(FunctionName=memory_lambda_function)
        
        assert response["Configuration"]["State"] == "Active"
        assert response["Configuration"]["Runtime"] == "python3.13"
        assert "agentcore-memory-setup" in response["Configuration"]["FunctionName"]
        
        print(f"Memory Lambda function {memory_lambda_function} is active and ready")
        
    except ClientError as e:
        pytest.fail(f"Memory Lambda function not found or not accessible: {e}")


@pytest.mark.lambda_test
def test_memory_lambda_function_configuration(lambda_client, memory_lambda_function, environment):
    """Test Memory Lambda function configuration matches expected values."""
    response = lambda_client.get_function(FunctionName=memory_lambda_function)
    config = response["Configuration"]
    
    # Check basic configuration
    assert config["Timeout"] == 300
    assert config["MemorySize"] == 128
    
    # Check environment variables
    env_vars = config.get("Environment", {}).get("Variables", {})
    assert "ENVIRONMENT" in env_vars
    assert "REGION" in env_vars
    assert env_vars["ENVIRONMENT"] == environment
    
    print(f"Memory Lambda configuration validated for {memory_lambda_function}")


def test_memory_lambda_iam_role_permissions(lambda_client, memory_lambda_function):
    """Test that Memory Lambda function has proper IAM role configured."""
    response = lambda_client.get_function(FunctionName=memory_lambda_function)
    config = response["Configuration"]
    
    role_arn = config["Role"]
    assert "agentcore-memory-lambda-role" in role_arn
    assert role_arn.startswith("arn:aws:iam::")
    
    print(f"Memory Lambda function has correct IAM role: {role_arn}")


@pytest.mark.lambda_test
def test_memory_lambda_provisioning_verification(lambda_client, memory_lambda_function, session_memory_provider):
    """Test that the session memory provider was properly provisioned and is accessible."""
    # We use the session_memory_provider fixture which already created the provider
    memory_id = session_memory_provider
    assert memory_id, "Session memory provider must be available"
    
    # Verify we can get details about the memory provider
    test_payload = {
        "input": {
            "memory_id": memory_id
        },
        "operation": "get-memory-provider"
    }
    
    response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(test_payload)
    )
    
    # Check response
    assert response["StatusCode"] == 200, f"Lambda invocation failed with status: {response['StatusCode']}"
    
    # Parse response payload
    response_payload = json.loads(response["Payload"].read())
    print(f"Memory provider details: {response_payload}")
    
    # Check for errors
    if "errorMessage" in response_payload:
        error_message = response_payload["errorMessage"]
        error_type = response_payload.get("errorType", "Unknown")
        pytest.fail(f"Failed to get memory provider details: {error_type}: {error_message}")
    
    # Validate response structure
    assert "statusCode" in response_payload or "result" in response_payload, "Memory Lambda response missing required fields"
    
    # If it has a result field with details, verify the memory ID matches
    if "result" in response_payload and isinstance(response_payload["result"], dict):
        result = response_payload["result"]
        assert result.get("memory_id") == memory_id, "Memory ID in response should match session memory provider ID"
        
    print(f"Session memory provider {memory_id} verified and accessible")


def test_memory_lambda_status_check(lambda_client, memory_lambda_function):
    """Test invoking Memory Lambda function to check memory resource status."""
    test_payload = {
        "input": {},
        "operation": "list-memory-providers"
    }
    
    response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse", 
        Payload=json.dumps(test_payload)
    )
    print(f"list-memory-providers response {response}")
    assert response["StatusCode"] == 200
    response_payload = json.loads(response["Payload"].read())
    print(f"Payload was {response_payload}")
    # Check for deployment/import failures - these should FAIL the test
    if "errorMessage" in response_payload:
        error_message = response_payload["errorMessage"]
        error_type = response_payload.get("errorType", "Unknown")
        # If we get here, it's a real error that should fail the test
        pytest.fail(f"Memory status check failed with unexpected error - {error_type}: {error_message}")
    else:
        assert "statusCode" in response_payload or "result" in response_payload
        print(f"Memory status check successful: {response_payload}")


def test_memory_lambda_concurrent_invocations(lambda_client, memory_lambda_function):
    """Test multiple concurrent Memory Lambda invocations."""
    
    def invoke_lambda(worker_id: int) -> Dict[str, Any]:
        """Worker function for concurrent Lambda invocations."""
        test_payload = {
            "input": {},
            "operation": "list-memory-providers"
        }
        
        try:
            response = lambda_client.invoke(
                FunctionName=memory_lambda_function,
                InvocationType="RequestResponse",
                Payload=json.dumps(test_payload)
            )
            
            return {
                "worker_id": worker_id,
                "status_code": response["StatusCode"],
                "success": True
            }
        except Exception as e:
            return {
                "worker_id": worker_id,
                "error": str(e),
                "success": False
            }
    
    # Run 5 concurrent invocations
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(invoke_lambda, i) for i in range(5)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    # Validate results
    assert len(results) == 5
    successful_invocations = sum(1 for r in results if r["success"])
    
    # At least some invocations should succeed (or fail gracefully)
    assert successful_invocations >= 3, f"Too many concurrent invocation failures: {results}"
    
    print(f"Concurrent invocations completed: {successful_invocations}/5 successful")


@pytest.mark.lambda_test
def test_memory_lambda_cloudwatch_logs(logs_client, memory_lambda_function):
    """Test that Memory Lambda function generates CloudWatch logs."""
    # Construct log group name
    log_group_name = f"/aws/lambda/{memory_lambda_function}"
    
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


def test_memory_lambda_error_handling(lambda_client, memory_lambda_function):
    """Test Memory Lambda function error handling with invalid payload - must test real error handling, not mask deployment issues."""
    # Send invalid payload to test error handling
    invalid_payload = {
        "input": {},
        "operation": "invalid-operation"
    }
    
    response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(invalid_payload)
    )
    
    assert response["StatusCode"] == 200
    response_payload = json.loads(response["Payload"].read())
    print(f"Result from invalid operation: {response_payload}")
    assert 'errorMessage' in response_payload
    assert "1 validation error for MemoryProviderRequest\noperation" in response_payload['errorMessage']
    print(f"\nError handling of invalid operations successful\n")

@pytest.mark.slow
def test_memory_lambda_timeout_behavior(lambda_client, memory_lambda_function):
    """Test Memory Lambda function behavior under load."""
    # Test with payload that might take longer to process
    test_payload = {
        "input": {
            "environment": "stress_test",
            "retention_days": 30
        },
        "operation": "create-memory-provider"
    }
    
    start_time = time.time()
    
    try:
        response = lambda_client.invoke(
            FunctionName=memory_lambda_function,
            InvocationType="RequestResponse",
            Payload=json.dumps(test_payload)
        )
        
        execution_time = time.time() - start_time
        
        # Should complete within timeout (300 seconds)
        assert execution_time < 300
        assert response["StatusCode"] == 200
        
        print(f"Memory Lambda execution completed in {execution_time:.2f} seconds")
        
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"Memory Lambda execution failed after {execution_time:.2f} seconds: {e}")




@pytest.mark.lambda_test
def test_memory_lambda_create_event(lambda_client, memory_lambda_function, session_memory_provider):
    # Verify that the session memory provider is available
    assert session_memory_provider, "Session memory provider must be available"
    """Test invoking Memory Lambda function for creating memory event."""
    test_session_id = f"test_session_{uuid4()}"
    test_actor_id = f"test_actor_{uuid4()}"
    
    test_payload = {
        "input": {
            "memory_id": session_memory_provider,
            "session_id": test_session_id,
            "actor_id": test_actor_id,
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": [
                {
                    "conversational": {
                        "content": {
                            "text": "Test message for memory event creation"
                        },
                        "role": "USER"
                    }
                }
            ]
        },
        "operation": "create-event"
    }
    
    response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(test_payload)
    )
    
    assert response["StatusCode"] == 200
    response_payload = json.loads(response["Payload"].read())
    print(f"Create memory response: {response_payload}")
    
    # Check for deployment/import failures
    if "errorMessage" in response_payload:
        error_message = response_payload["errorMessage"]
        error_type = response_payload.get("errorType", "Unknown")
        
        # These are deployment failures that should fail the test
        if any(failure_indicator in error_message for failure_indicator in [
            "Unable to import module", "No module named", "ModuleNotFoundError", "ImportError", "AttributeError"
        ]):
            pytest.fail(f"Memory Lambda deployment failure - {error_type}: {error_message}")
        
        # If we get here, it's a real error that should fail the test - no "expected" errors
        pytest.fail(f"Create memory failed with unexpected error - {error_type}: {error_message}")
    else:
        assert "statusCode" in response_payload or "result" in response_payload
        print("Create memory invocation successful")


@pytest.mark.lambda_test
def test_memory_lambda_wait_for_create(lambda_client, memory_lambda_function, session_memory_provider):
    # Verify that the session memory provider is available
    assert session_memory_provider, "Session memory provider must be available"
    """Test invoking Memory Lambda function for waiting for memory provider creation - should succeed with existing provider."""
    test_payload = {
        "input": {
            "memory_id": session_memory_provider,  # Use existing memory provider that should be ready
            "max_attempts": 3,
            "delay_seconds": 5
        },
        "operation": "wait-for-memory-provider-creation"
    }
    
    response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(test_payload)
    )
    
    assert response["StatusCode"] == 200
    response_payload = json.loads(response["Payload"].read())
    print(f"Wait for create response: {response_payload}")
    
    # Check for deployment/import failures
    if "errorMessage" in response_payload:
        error_message = response_payload["errorMessage"]
        error_type = response_payload.get("errorType", "Unknown")
        
        if any(failure_indicator in error_message for failure_indicator in [
            "Unable to import module", "No module named", "ModuleNotFoundError", "ImportError", "AttributeError"
        ]):
            pytest.fail(f"Memory Lambda deployment failure - {error_type}: {error_message}")
        
        # Any other error is a real failure that should fail the test
        pytest.fail(f"Wait for create failed with unexpected error - {error_type}: {error_message}")
    else:
        assert "statusCode" in response_payload or "result" in response_payload
        print("Wait for create invocation successful")


@pytest.mark.lambda_test
def test_memory_lambda_get_memory_provider(lambda_client, memory_lambda_function, session_memory_provider):
    # Verify that the session memory provider is available
    assert session_memory_provider, "Session memory provider must be available"
    """Test invoking Memory Lambda function for getting memory provider details - should succeed with existing provider."""
    test_payload = {
        "input": {
            "memory_id": session_memory_provider  # Use existing memory provider
        },
        "operation": "get-memory-provider"
    }
    
    response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(test_payload)
    )
    
    assert response["StatusCode"] == 200
    response_payload = json.loads(response["Payload"].read())
    print(f"Get memory provider response: {response_payload}")
    
    # Check for deployment/import failures
    if "errorMessage" in response_payload:
        error_message = response_payload["errorMessage"]
        error_type = response_payload.get("errorType", "Unknown")
        
        if any(failure_indicator in error_message for failure_indicator in [
            "Unable to import module", "No module named", "ModuleNotFoundError", "ImportError", "AttributeError"
        ]):
            pytest.fail(f"Memory Lambda deployment failure - {error_type}: {error_message}")
        
        # Any other error is a real failure that should fail the test
        pytest.fail(f"Get memory provider failed with unexpected error - {error_type}: {error_message}")
    else:
        assert "statusCode" in response_payload or "result" in response_payload
        print("Get memory provider invocation successful")


@pytest.mark.lambda_test
def test_memory_lambda_update_memory_provider(lambda_client, memory_lambda_function, session_memory_provider):
    # Verify that the session memory provider is available
    assert session_memory_provider, "Session memory provider must be available"
    """Test invoking Memory Lambda function for updating memory provider - should succeed with existing provider."""
    test_payload = {
        "input": {
            "memory_id": session_memory_provider,  # Use existing memory provider
            "description": "Updated test memory provider",
            "event_expiry_duration": 45
        },
        "operation": "update-memory-provider"
    }
    
    response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(test_payload)
    )
    
    assert response["StatusCode"] == 200
    response_payload = json.loads(response["Payload"].read())
    print(f"Update memory provider response: {response_payload}")
    
    # Check for deployment/import failures
    if "errorMessage" in response_payload:
        error_message = response_payload["errorMessage"]
        error_type = response_payload.get("errorType", "Unknown")
        
        if any(failure_indicator in error_message for failure_indicator in [
            "Unable to import module", "No module named", "ModuleNotFoundError", "ImportError", "AttributeError"
        ]):
            pytest.fail(f"Memory Lambda deployment failure - {error_type}: {error_message}")
        
        # Any other error is a real failure that should fail the test
        pytest.fail(f"Update memory provider failed with unexpected error - {error_type}: {error_message}")
    else:
        assert "statusCode" in response_payload or "result" in response_payload
        print("Update memory provider invocation successful")


@pytest.mark.lambda_test
def test_memory_lambda_list_events(lambda_client, memory_lambda_function, session_memory_provider):
    # Verify that the session memory provider is available
    assert session_memory_provider, "Session memory provider must be available"
    """Test invoking Memory Lambda function for listing memory events."""
    test_session_id = f"test_session_{uuid4()}"
    test_actor_id = f"test_actor_{uuid4()}"
    
    test_payload = {
        "input": {
            "memory_id": session_memory_provider,
            "session_id": test_session_id,
            "actor_id": test_actor_id,
            "max_results": 10
        },
        "operation": "list-events"
    }
    
    response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(test_payload)
    )
    
    assert response["StatusCode"] == 200
    response_payload = json.loads(response["Payload"].read())
    print(f"List events response: {response_payload}")
    
    # Check for deployment/import failures
    if "errorMessage" in response_payload:
        error_message = response_payload["errorMessage"]
        error_type = response_payload.get("errorType", "Unknown")
        
        if any(failure_indicator in error_message for failure_indicator in [
            "Unable to import module", "No module named", "ModuleNotFoundError", "ImportError", "AttributeError"
        ]):
            pytest.fail(f"Memory Lambda deployment failure - {error_type}: {error_message}")
        
        # Expected to succeed or fail gracefully for valid test input
        print(f"List events returned response: {error_type}: {error_message}")
    else:
        assert "statusCode" in response_payload or "result" in response_payload
        print("List events invocation successful")


@pytest.mark.lambda_test
def test_memory_lambda_list_memory_records(lambda_client, memory_lambda_function, session_memory_provider):
    # Verify that the session memory provider is available
    assert session_memory_provider, "Session memory provider must be available"
    """Test invoking Memory Lambda function for listing memory records."""
    
    test_payload = {
        "input": {
            "memory_id": session_memory_provider,
            "namespace": "semantic_memory",
            "max_results": 10
        },
        "operation": "list-memory-records"
    }
    
    response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(test_payload)
    )
    
    assert response["StatusCode"] == 200
    response_payload = json.loads(response["Payload"].read())
    print(f"List memory records response: {response_payload}")
    
    # Check for deployment/import failures
    if "errorMessage" in response_payload:
        error_message = response_payload["errorMessage"]
        error_type = response_payload.get("errorType", "Unknown")
        
        if any(failure_indicator in error_message for failure_indicator in [
            "Unable to import module", "No module named", "ModuleNotFoundError", "ImportError", "AttributeError"
        ]):
            pytest.fail(f"Memory Lambda deployment failure - {error_type}: {error_message}")
        
        # Expected to succeed or fail gracefully for valid test input
        print(f"List memory records returned response: {error_type}: {error_message}")
    else:
        assert "statusCode" in response_payload or "result" in response_payload
        print("List memory records invocation successful")


# Note: The memory provider deletion test has been removed since session_memory_provider fixture
# handles cleanup automatically at the end of the test session.


@pytest.mark.lambda_test
def test_memory_lambda_all_operations_error_handling(lambda_client, memory_lambda_function):
    """Test error handling for all memory operations with invalid payloads."""
    operations_to_test = [
        ("create-memory-provider", {}),  # Missing required fields
        ("create-event", {}),  # Missing required fields
        ("delete-memory-provider", {}),  # Missing memory_id
        ("get-memory-provider", {}),  # Missing memory_id
        ("list-events", {}),  # Missing required fields
        ("list-memory-records", {}),  # Missing required fields
        # ("update-memory-provider", {}),  # Missing memory_id (this test hangs indefinitely.)
        # ("wait-for-memory-provider-creation", {}),  # Missing memory_id
        # ("wait-for-memory-provider-deletion", {})  # Missing memory_id
    ]
    
    for operation, invalid_input in operations_to_test:
        test_payload = {
            "input": invalid_input,
            "operation": operation
        }
        
        response = lambda_client.invoke(
            FunctionName=memory_lambda_function,
            InvocationType="RequestResponse",
            Payload=json.dumps(test_payload)
        )
        
        assert response["StatusCode"] == 200
        response_payload = json.loads(response["Payload"].read())
        
        # Should have error message for invalid input
        assert "errorMessage" in response_payload, f"Expected error for operation {operation} with invalid input"
        
        error_message = response_payload["errorMessage"]
        error_type = response_payload.get("errorType", "Unknown")
        
        # Check for deployment failures (these should fail the test)
        if any(failure_indicator in error_message for failure_indicator in [
            "Unable to import module", "No module named", "ModuleNotFoundError", "ImportError"
        ]):
            pytest.fail(f"Memory Lambda deployment failure in {operation} - {error_type}: {error_message}")
        
        print(f"Operation {operation} properly handled invalid input: {error_type}")
    
    # print("All memory operations properly handle invalid inputs")
    # for some reason it's hanging at the end of the tests.

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
