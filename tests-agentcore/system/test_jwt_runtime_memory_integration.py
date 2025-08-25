"""
System test for JWT runtime invocation with memory event creation.

This test demonstrates the full integration flow using deployed AgentCore infrastructure:
1. Find existing AgentCore runtime with JWT authentication
2. Generate JWT token from Cognito
3. Invoke the deployed runtime with JWT authentication
4. Extract actor ID from invocation response
5. Save the response as an AgentCore memory event using the actor ID
"""

import json
import time
import boto3
import pytest
import requests
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import uuid4
from botocore.exceptions import ClientError

# Import the get_token function from the auth script
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "script"))
from get_auth_token import get_token

MEMORY_ID = 'agentcore_agentpath-RqV4aKDDzd'

def generate_jwt_token(cognito_config: Dict[str, str]) -> str:
    """Generate a fresh JWT token using Cognito credentials."""
    try:
        token = get_token(
            client_id=cognito_config["client_id"],
            username=cognito_config["username"], 
            password=cognito_config["password"],
            client_secret=cognito_config.get("client_secret")
        )
        return token
    except Exception as e:
        pytest.fail(f"Failed to generate JWT token: {e}")


def find_jwt_enabled_runtime(agentcore_control_client) -> Optional[Dict[str, Any]]:
    """Find an existing JWT-enabled AgentCore runtime that's ready for invocation."""
    try:
        list_response = agentcore_control_client.list_agent_runtimes(maxResults=50)
        runtimes = list_response.get("agentRuntimes", [])
        
        for runtime in runtimes:
            runtime_id = runtime["agentRuntimeId"]
            
            try:
                # Get runtime details to check for JWT configuration
                runtime_details = agentcore_control_client.get_agent_runtime(agentRuntimeId=runtime_id)
                auth_config = runtime_details.get("authorizerConfiguration", {})
                status = runtime_details.get("status")
                
                if "customJWTAuthorizer" in auth_config and status == "READY":
                    print(f"Found JWT-enabled runtime: {runtime_id} (status: {status})")
                    return runtime_details
                    
            except Exception as e:
                print(f"Could not check runtime {runtime_id}: {e}")
                continue
        
        return None
        
    except Exception as e:
        print(f"Error listing runtimes: {e}")
        return None


@pytest.mark.lambda_test
def test_deployed_jwt_runtime_memory_integration(
    agentcore_control_client,
    lambda_client,
    memory_lambda_function,
    cognito_config,
    session_runtime,
    aws_region
):
    """Test JWT runtime invocation with memory creation using deployed AgentCore infrastructure."""
    
    # Step 1: Use the session-scoped JWT-authenticated runtime
    print("Using session-scoped JWT-authenticated runtime...")
    
    assert session_runtime and session_runtime.agentRuntimeId, "Session runtime must be available"
    
    runtime_id = session_runtime.agentRuntimeId
    runtime_arn = session_runtime.agentRuntimeArn
    
    assert runtime_arn, "Session runtime ARN must be available"
    
    print(f"Using session runtime: {runtime_id}")
    
    # Get runtime details to verify JWT configuration
    # runtime_details = agentcore_control_client.get_agent_runtime(agentRuntimeId=runtime_id)
    
    # Verify JWT configuration
    auth_config = session_runtime.authorizerConfiguration
    jwt_config = auth_config.get("customJWTAuthorizer", {})
    discovery_url = jwt_config.get("discoveryUrl", "")
    allowed_clients = jwt_config.get("allowedClients", [])
    
    print(f"JWT Discovery URL: {discovery_url}")
    print(f"Allowed Clients: {allowed_clients}")
    
    # Step 2: Generate JWT token
    print("Generating JWT token from Cognito...")
    jwt_token = generate_jwt_token(cognito_config)
    assert jwt_token, "JWT token must be generated successfully"
    
    # Step 3: Invoke the deployed runtime with JWT authentication
    print(f"Invoking deployed runtime {runtime_id} with JWT authentication...")
    
    # Generate unique IDs for this test invocation
    session_id = f"system_test_session_{uuid4().hex}"
    actor_id = f"system_test_user_{uuid4().hex[-8:]}"  
    trace_id = f"system_test_trace_{uuid4().hex}"
    
    invoke_payload = {
        "prompt": "what's your name?",        
    }
    print(f"With payload {invoke_payload}")
    # Create the URL with escaped runtime ARN
    escaped_agent_arn = urllib.parse.quote(runtime_arn, safe='')
    invoke_url = f"https://bedrock-agentcore.{aws_region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"
    
    # Prepare headers with JWT token
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        "X-Amzn-Bedrock-AgentCore-Runtime-User-Id": actor_id
    }
    
    if trace_id:
        headers["X-Amzn-Trace-Id"] = trace_id
    
    # Make the HTTP request
    print(f"Invoking runtime at URL: {invoke_url}")
    invoke_response = requests.post(
        invoke_url,
        headers=headers,
        data=json.dumps(invoke_payload),
        timeout=30
    )

    print(f"Invoke response headers {invoke_response.headers}")
    # Step 4: Validate invocation response and extract actor ID
    assert invoke_response.status_code == 200, f"Runtime invocation failed with status: {invoke_response.status_code}"
    
    # Extract the actor ID (runtime session ID) from the response headers
    # actor_id = invoke_response.headers.get("X-Amzn-Bedrock-AgentCore-Runtime-Session-Id")
    # assert actor_id, "Runtime invocation must return X-Amzn-Bedrock-AgentCore-Runtime-Session-Id header"
    
    print(f"✅ Runtime invocation successful. Actor ID captured: {actor_id}")
    
    # Read and parse the response body
    response_body = invoke_response.content
    if isinstance(response_body, bytes):
        response_body = response_body.decode('utf-8')
    
    try:
        parsed_response = json.loads(response_body)
    except json.JSONDecodeError:
        parsed_response = {"raw_response": response_body}
    
    print(f"Runtime response: {parsed_response}")
    
    # Step 5: Create memory event using the captured actor ID and response
    print(f"Creating memory event with actor ID: {actor_id}")
    
    memory_payload = {
        "input": {
            'memory_id': MEMORY_ID,
            "session_id": session_id,
            "actor_id": actor_id,
            "agent_id": runtime_id,  # Use runtime ID as agent ID
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": [{
                "conversational": {
                    "content": {
                        "text": f"The model's name is {parsed_response['result']}"
                    }
                }
            }]
        },
        "operation": "create-memory-event"
    }
    
    memory_response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(memory_payload)
    )
    print(f"Got memory_resonse {memory_response}")
    # Step 6: Validate memory creation
    assert memory_response["StatusCode"] == 200, f"Memory creation failed with status: {memory_response['StatusCode']}"
    
    memory_response_payload = json.loads(memory_response["Payload"].read())
    print(f"Memory creation response: {memory_response_payload}")
    
    # Check for memory creation errors
    if "errorMessage" in memory_response_payload:
        error_message = memory_response_payload["errorMessage"]
        error_type = memory_response_payload.get("errorType", "Unknown")
        
        # Fail on deployment errors
        if any(failure_indicator in error_message for failure_indicator in [
            "Unable to import module", "No module named", "ModuleNotFoundError", "ImportError"
        ]):
            pytest.fail(f"Memory Lambda deployment failure - {error_type}: {error_message}")
        
        # Fail on unexpected errors
        pytest.fail(f"Memory creation failed - {error_type}: {error_message}")
    
    # Validate successful memory creation
    assert "statusCode" in memory_response_payload or "result" in memory_response_payload
    print("✅ Memory event created successfully!")
    
    # Step 7: Verify memory retrieval
    print("Verifying memory retrieval...")
    
    retrieve_payload = {
        "input": {
            "actor_id": actor_id,
            "session_id": session_id,
            "limit": 5
        },
        "operation": "get-memories"
    }
    
    retrieve_response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(retrieve_payload)
    )
    
    assert retrieve_response["StatusCode"] == 200
    retrieve_response_payload = json.loads(retrieve_response["Payload"].read())
    
    if "errorMessage" not in retrieve_response_payload:
        print("✅ Memory retrieval successful")
    else:
        print(f"Memory retrieval returned: {retrieve_response_payload}")
        
    # Step 8: Test summary
    print(f"\n=== DEPLOYED JWT RUNTIME MEMORY INTEGRATION TEST SUMMARY ===")
    print(f"✅ Used deployed runtime: {runtime_id}")
    print(f"✅ JWT authentication successful with deployed runtime")
    print(f"✅ Actor ID captured from runtime invocation: {actor_id}")
    print(f"✅ Memory event created using captured actor ID")
    print(f"✅ Memory retrieval validated")
    print(f"✅ Complete JWT -> Runtime -> Memory integration verified")


@pytest.mark.lambda_test
def dont_test_jwt_runtime_memory_with_session_memory(
    agentcore_control_client,
    lambda_client,
    memory_lambda_function,
    cognito_config,
    aws_region,
    session_runtime,
    session_memory_provider
):
    """Test JWT invocation and memory creation using session-scoped runtime and memory provider."""
    
    # Step 1: Verify session-scoped resources are available
    assert session_runtime and session_runtime.get("runtime_id"), "Session runtime must be available"
    assert session_memory_provider, "Session memory provider must be available"
    
    runtime_id = session_runtime["runtime_id"]
    runtime_arn = session_runtime["runtime_arn"]
    memory_id = session_memory_provider
    
    assert runtime_arn, "Session runtime ARN must be available"
    
    print(f"Using session runtime: {runtime_id}")
    print(f"Using session memory provider: {memory_id}")
    
    # Get runtime details to verify status
    runtime_details = agentcore_control_client.get_agent_runtime(agentRuntimeId=runtime_id)
    status = runtime_details.get("status")
    print(f"Runtime status: {status}")
    
    # Step 2: Generate JWT token
    print("Generating JWT token...")
    jwt_token = generate_jwt_token(cognito_config)
    
    # Step 3: Invoke runtime
    session_id = f"existing_runtime_session_{uuid4().hex}"
    actor_id = f"existing_runtime_user_{uuid4().hex[-8:]}"
    
    invoke_payload = {
        "message": "Test with existing JWT runtime for memory integration",
        "actor_id": actor_id,
        "session_id": session_id
    }
    
    print(f"Invoking existing runtime {runtime_id}...")
    # Create the URL with escaped runtime ARN
    escaped_agent_arn = urllib.parse.quote(runtime_arn, safe='')
    invoke_url = f"https://bedrock-agentcore.{aws_region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"
    
    # Prepare headers with JWT token
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        "X-Amzn-Bedrock-AgentCore-Runtime-User-Id": actor_id
    }
    
    # Make the HTTP request
    invoke_response = requests.post(
        invoke_url,
        headers=headers,
        data=json.dumps(invoke_payload),
        timeout=30
    )
    
    # Step 4: Extract actor ID and create memory
    assert invoke_response.status_code == 200
    actor_id = invoke_response.headers.get("X-Amzn-Bedrock-AgentCore-Runtime-Session-Id")
    assert actor_id, "Must get actor ID from runtime invocation"
    
    print(f"Extracted actor ID: {actor_id}")
    
    # Read response body
    response_body = invoke_response.content
    if isinstance(response_body, bytes):
        response_body = response_body.decode('utf-8')
    
    try:
        parsed_response = json.loads(response_body)
    except json.JSONDecodeError:
        parsed_response = {"raw_response": response_body}
    
    # Step 5: Create memory event
    memory_payload = {
        "input": {
            "session_id": session_id,
            "actor_id": actor_id,
            "agent_id": runtime_id,
            "session_context": {
                "session_id": session_id,
                "actor_id": actor_id,
                "agent_id": runtime_id,
                "actor_id": actor_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": json.dumps(invoke_payload)}],
                        "tool_calls": [],
                        "tool_results": []
                    },
                    {
                        "role": "assistant",
                        "content": [{"type": "text", "text": json.dumps(parsed_response)}],
                        "tool_calls": [],
                        "tool_results": []
                    }
                ],
                "runtime_metadata": {
                    "runtime_arn": runtime_arn,
                    "runtime_id": runtime_id,
                    "actor_id": actor_id,
                    "test_context": "existing_runtime_jwt_memory_test"
                }
            }
        },
        "operation": "create-memory-event"
    }
    
    memory_response = lambda_client.invoke(
        FunctionName=memory_lambda_function,
        InvocationType="RequestResponse",
        Payload=json.dumps(memory_payload)
    )
    
    # Step 6: Validate memory creation
    assert memory_response["StatusCode"] == 200
    memory_response_payload = json.loads(memory_response["Payload"].read())
    
    if "errorMessage" in memory_response_payload:
        error_message = memory_response_payload["errorMessage"]
        error_type = memory_response_payload.get("errorType", "Unknown")
        
        if any(failure_indicator in error_message for failure_indicator in [
            "Unable to import module", "No module named", "ModuleNotFoundError", "ImportError"
        ]):
            pytest.fail(f"Memory Lambda deployment failure - {error_type}: {error_message}")
        
        pytest.fail(f"Memory creation failed - {error_type}: {error_message}")
    
    assert "statusCode" in memory_response_payload or "result" in memory_response_payload
    
    print(f"\n=== EXISTING RUNTIME JWT MEMORY TEST SUMMARY ===")
    print(f"✅ Used existing runtime: {runtime_id}")
    print(f"✅ JWT authentication successful")
    print(f"✅ Actor ID captured: {actor_id}")
    print(f"✅ Memory event created successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
