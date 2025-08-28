"""
Shared pytest configuration and fixtures for AgentCore tests across all test types.
Provides session-scoped memory provider and runtime that are shared across unit and system tests.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import uuid4
import hmac
import hashlib
import base64
import shutil
import tempfile

import boto3
import pytest
import requests
from dotenv import load_dotenv
import sys

sys.path.insert(1, '../src')

from agentic_platform.service.agentcore.runtime.client.agentcore_runtime_client import AgentCoreRuntimeClient
from agentic_platform.service.agentcore.types import (
    AgentRuntimeStatus,
    CreateAgentRuntimeRequest,
    DeleteAgentRuntimeRequest,
    GetAgentRuntimeRequest,
    ListAgentRuntimesRequest
)

DELETE_AT_END = os.getenv('DELETE_AT_END', 'True')
if DELETE_AT_END.lower() in ['false', '0', 'no', 'n']:
    DELETE_AT_END = False
else:
    DELETE_AT_END = True

def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_path = Path(__file__).parent / ".env"
    print(f"Loading env_path: {env_path}")
    
    if env_path.exists():
        load_dotenv(env_path)
        print("Environment variables loaded successfully")
    else:
        print("No .env file found, using system environment variables")


# Load .env file at module import time
load_env_file()


def get_terraform_outputs() -> Dict[str, Any]:
    """Get Terraform outputs for deployed resources."""
    try:
        # Path to the agentcore terraform stack
        terraform_dir = Path(__file__).parent.parent / "infrastructure" / "stacks" / "agentcore"
        
        if not terraform_dir.exists():
            print(f"Terraform directory not found: {terraform_dir}")
            return {}
        
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            outputs = json.loads(result.stdout)
            print(f"Retrieved Terraform outputs: {list(outputs.keys())}")
            return outputs
        else:
            print(f"Terraform output failed: {result.stderr}")
            return {}
            
    except Exception as e:
        print(f"Error getting Terraform outputs: {e}")
        return {}


def discover_agentcore_resources() -> Dict[str, str]:
    """Discover deployed AgentCore resources by tags and naming conventions."""
    resources = {}
    region = os.getenv("REGION", "us-west-2")
    environment = os.getenv("ENVIRONMENT", "agentcore-agentpath")
    
    try:
        # Lambda client for finding Lambda functions
        lambda_client = boto3.client("lambda", region_name=region)
        
        # List Lambda functions and find AgentCore functions
        response = lambda_client.list_functions()
        for function in response.get("Functions", []):
            function_name = function["FunctionName"]
            if "agentcore-memory-setup" in function_name:
                resources["memory_lambda_function_name"] = function_name
                resources["memory_lambda_function_arn"] = function["FunctionArn"]
                print(f"Found memory Lambda: {function_name}")
            elif "bedrock-agentcore-runtime-controller" in function_name:
                resources["bedrock_agentcore_runtime_controller_function_name"] = function_name
                resources["bedrock_agentcore_runtime_controller_arn"] = function["FunctionArn"]
                print(f"Found runtime controller Lambda: {function_name}")
                
    except Exception as e:
        print(f"Error discovering resources: {e}")
    
    return resources


@pytest.fixture(scope="session")
def aws_region():
    """Get AWS region for tests."""
    return os.getenv("REGION", "us-west-2")


@pytest.fixture(scope="session")
def environment(lambda_client, deployed_resources):
    """Get environment name from deployed Lambda function."""
    # Try to get the environment from the deployed Lambda function
    function_name = deployed_resources.get("bedrock_agentcore_runtime_controller_function_name")
    
    if function_name:
        try:
            response = lambda_client.get_function(FunctionName=function_name)
            env_vars = response["Configuration"].get("Environment", {}).get("Variables", {})
            deployed_environment = env_vars.get("ENVIRONMENT")
            
            if deployed_environment:
                print(f"Using environment from deployed Lambda: {deployed_environment}")
                return deployed_environment
        except Exception as e:
            print(f"Could not get environment from Lambda {function_name}: {e}")
    
    # Fall back to environment variable or default
    fallback_env = os.getenv("ENVIRONMENT", "agentcore-agentpath")
    print(f"Using fallback environment: {fallback_env}")
    return fallback_env


@pytest.fixture(scope="session")
def terraform_outputs():
    """Session-scoped fixture to get Terraform outputs."""
    outputs = get_terraform_outputs()
    return outputs


@pytest.fixture(scope="session")
def deployed_resources(terraform_outputs):
    """Session-scoped fixture to get information about deployed resources."""
    resources = {}
    
    # Try to get from Terraform outputs first
    if terraform_outputs:
        for key, value in terraform_outputs.items():
            if isinstance(value, dict) and "value" in value:
                resources[key] = value["value"]
    
    # Supplement with resource discovery
    discovered = discover_agentcore_resources()
    resources.update(discovered)
    
    # Fallback to environment variables
    env_mappings = {
        "memory_lambda_function_name": "DEPLOYED_LAMBDA_FUNCTION_NAME",
        "ecs_cluster_name": "DEPLOYED_ECS_CLUSTER_NAME", 
        "ecs_service_name": "DEPLOYED_ECS_SERVICE_NAME",
        "alb_dns_name": "DEPLOYED_ALB_DNS_NAME"
    }
    
    for resource_key, env_key in env_mappings.items():
        if resource_key not in resources:
            env_value = os.getenv(env_key)
            if env_value:
                resources[resource_key] = env_value
    
    print(f"Final deployed resources: {resources}")
    return resources


@pytest.fixture(scope="session")
def lambda_client(aws_region):
    """Session-scoped Lambda client."""
    return boto3.client("lambda", region_name=aws_region)


@pytest.fixture(scope="session")
def ecs_client(aws_region):
    """Session-scoped ECS client."""
    return boto3.client("ecs", region_name=aws_region)


@pytest.fixture(scope="session")
def logs_client(aws_region):
    """Session-scoped CloudWatch Logs client."""
    return boto3.client("logs", region_name=aws_region)


@pytest.fixture(scope="session")
def agentcore_client(aws_region):
    """Session-scoped Bedrock AgentCore client."""
    return boto3.client("bedrock-agentcore", region_name=aws_region)


@pytest.fixture(scope="session")
def agentcore_control_client(aws_region):
    """Session-scoped Bedrock AgentCore Control client."""
    return boto3.client("bedrock-agentcore-control", region_name=aws_region)


@pytest.fixture(scope="session")
def memory_lambda_function(deployed_resources):
    """Get the deployed memory Lambda function name."""
    function_name = deployed_resources.get("memory_lambda_function_name")
    if not function_name:
        function_name = deployed_resources.get("bedrock_agentcore_lambda_function_name")
    
    assert function_name, (
        "Memory Lambda function not found in deployed resources. "
        "Ensure AgentCore infrastructure is deployed and DEPLOYED_LAMBDA_FUNCTION_NAME "
        "is set in environment or Terraform outputs are available."
    )
    
    return function_name


@pytest.fixture(scope="session")
def cognito_config():
    """Get Cognito configuration for JWT token generation."""
    config = {
        "user_pool_id": os.getenv("USER_POOL_ID"),
        "client_id": os.getenv("COGNITO_USER_CLIENT_ID"),
        "username": os.getenv("COGNITO_USERNAME"),
        "password": os.getenv("COGNITO_PASSWORD"),
        "region": os.getenv("REGION", "us-west-2")
    }
    
    assert config["user_pool_id"], (
        "USER_POOL_ID environment variable is required for authentication tests. "
        "Ensure this is set in the .env file with a valid Cognito User Pool ID."
    )
    assert config["client_id"], (
        "COGNITO_USER_CLIENT_ID environment variable is required for authentication tests. "
        "Ensure this is set in the .env file with a valid Cognito User Pool Client ID."
    )
    assert config["username"], (
        "COGNITO_USERNAME environment variable is required for authentication tests. "
        "Ensure this is set in the .env file with a valid test username."
    )
    assert config["password"], (
        "COGNITO_PASSWORD environment variable is required for authentication tests. "
        "Ensure this is set in the .env file with a valid test password."
    )
    
    return config


def calculate_secret_hash(username, client_id, client_secret):
    """Calculate the SECRET_HASH for Cognito authentication"""
    message = bytes(username + client_id, 'utf-8')
    key = bytes(client_secret, 'utf-8')
    secret_hash = base64.b64encode(hmac.new(key, message, digestmod=hashlib.sha256).digest()).decode()
    return secret_hash


def get_jwt_token():
    """Get JWT token from Cognito for authentication"""
    try:
        # Get Cognito credentials from environment
        client_id = os.getenv("COGNITO_USER_CLIENT_ID") or os.getenv("USER_POOL_CLIENT_ID")
        username = os.getenv("COGNITO_USERNAME")
        password = os.getenv("COGNITO_PASSWORD")
        client_secret = os.getenv("COGNITO_CLIENT_SECRET")
        region = os.getenv("REGION", "us-west-2")
        
        if not all([client_id, username, password]):
            print("Warning: Missing Cognito credentials, JWT token generation will fail")
            return None
        
        # Create Cognito client
        client = boto3.client('cognito-idp', region_name=region)
        
        # Prepare authentication parameters
        auth_parameters = {
            'USERNAME': username,
            'PASSWORD': password
        }
        
        # Add SECRET_HASH if client secret is provided
        if client_secret:
            secret_hash = calculate_secret_hash(username, client_id, client_secret)
            auth_parameters['SECRET_HASH'] = secret_hash
        
        # Authenticate with Cognito
        response = client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters=auth_parameters
        )
        
        # Extract and return the token
        token = response['AuthenticationResult']['AccessToken']
        return token
        
    except Exception as e:
        print(f"Error getting JWT token: {str(e)}")
        return None




def _wait_for_runtime_active(client, agent_runtime_id, max_wait_time=300):
    """Helper function to wait for runtime to become active."""
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        try:
            response = client.get_agent_runtime(agentRuntimeId=agent_runtime_id)
            
            # Debug: Log the actual response structure to understand the API response
            print(f"API Response structure: {list(response.keys())}")
            print(f"Full API Response: {response}")
            
            # Handle potential variations in response structure
            if 'agentRuntime' in response:
                runtime_data = response['agentRuntime']
                status = runtime_data['status']
            elif 'status' in response:
                # Alternative response structure - status directly in response
                runtime_data = response
                status = response['status']
            else:
                # Log available keys and raise a more informative error
                available_keys = list(response.keys())
                print(f"Unexpected response structure. Available keys: {available_keys}")
                print(f"Full response: {response}")
                raise KeyError(f"Expected 'agentRuntime' or 'status' in response, but got keys: {available_keys}")
            
            if status == 'READY' or AgentRuntimeStatus.READY:
                return runtime_data
            elif status in ['FAILED', 'CREATE_FAILED']:
                raise Exception(f"Runtime failed to become active. Status: {status}")
            print(f"Runtime {agent_runtime_id} status: {status}, waiting...")
            time.sleep(10)
        except KeyError as ke:
            print(f"KeyError accessing response structure: {str(ke)}")
            print(f"Available response keys: {list(response.keys()) if 'response' in locals() else 'No response available'}")
            raise ke
        except Exception as e:
            if "not found" in str(e).lower():
                raise Exception(f"Runtime {agent_runtime_id} not found")
            # For ConflictException or other AWS errors, log more details
            print(f"Error waiting for runtime {agent_runtime_id}: {str(e)}")
            if "ConflictException" in str(e) or "while it's" in str(e):
                print(f"Runtime appears to be in transitional state, continuing to wait...")
                time.sleep(30)  # Wait longer for transitional states
                continue
            raise e
    raise Exception(f"Runtime {agent_runtime_id} did not become active within {max_wait_time} seconds")


@pytest.fixture(scope="session")
def session_memory_provider(lambda_client, memory_lambda_function):
    """Session-scoped fixture to create and manage a shared memory provider for all tests.
    
    Creates a single memory provider at the beginning of the test session and 
    cleans it up at the end of all tests, shared across unit and system tests.
    """
    memory_id = None
    TEST_MEMORY_PROVIDER_ID = os.getenv('TEST_MEMORY_PROVIDER_ID', None)
    if TEST_MEMORY_PROVIDER_ID:
        print(f"Using existing memory provider: {TEST_MEMORY_PROVIDER_ID}")
        yield TEST_MEMORY_PROVIDER_ID
    else:
        test_retention = 30
        
        print("\n=== Creating session-scoped shared memory provider ===")
        
        # Create the memory provider
        try:
            test_payload = {
                "input": {
                    "environment": "test",
                    "retention_days": test_retention
                },
                "operation": "create-memory-provider"
            }
            
            print("Creating agentcore memory provider with payload. This may take up to 3-4 minutes to complete...")
            response = lambda_client.invoke(
                FunctionName=memory_lambda_function,
                InvocationType="RequestResponse",
                Payload=json.dumps(test_payload)
            )
            print(f"Got response from creating agent memory provider: {response} ")
            # Check response
            assert response["StatusCode"] == 200
            
            # Parse response payload
            response_payload = json.loads(response["Payload"].read())
            print(f"Got response payload {response_payload}, type {type(response_payload)}")
            if "errorMessage" in response_payload:
                error_message = response_payload["errorMessage"]
                error_type = response_payload.get("errorType", "Unknown")
                pytest.fail(f"Failed to create memory provider: {error_type}: {error_message}")
            
            if "result" in response_payload:
                memory_id = response_payload.get("result", {}).get("memory_id")
            else:
                memory_id = response_payload.get("memory_id")
            
            assert memory_id, "Memory provider creation did not return a memory_id"
            print(f"✅ Created shared memory provider: {memory_id}")
            
            if not response_payload['result']['status'] == 'ACTIVE':
                # Wait for the memory provider to be fully created
                wait_payload = {
                    "input": {
                        "memory_id": memory_id,
                        "max_attempts": 10,
                        "delay_seconds": 20
                    },
                    "operation": "wait-for-memory-provider-creation"
                }
                print(f"Waiting for memory provider to be ACTIVE")
                
                wait_response = lambda_client.invoke(
                    FunctionName=memory_lambda_function,
                    InvocationType="RequestResponse",
                    Payload=json.dumps(wait_payload)
                )
                
                wait_response_payload = json.loads(wait_response["Payload"].read())
                if "errorMessage" in wait_response_payload:
                    error_message = wait_response_payload["errorMessage"]
                    error_type = wait_response_payload.get("errorType", "Unknown")
                    pytest.fail(f"Wait operation failed: {error_type}: {error_message}")
                else:
                    print("✅ Memory provider is active and ready for all tests")
            else:
                    print("✅ Memory provider is ACTIVE and ready for all tests")
        except Exception as e:
            pytest.fail(f"Failed to create session memory provider: {e}")
        
        # Yield the memory provider ID for tests to use
        yield memory_id
        
    # Cleanup after all tests are done
    if memory_id and DELETE_AT_END and not TEST_MEMORY_PROVIDER_ID:
        print(f"\n=== Cleaning up shared memory provider {memory_id} ===")
        try:
            delete_payload = {
                "input": {
                    "memory_id": memory_id
                },
                "operation": "delete-memory-provider"
            }
            
            delete_response = lambda_client.invoke(
                FunctionName=memory_lambda_function,
                InvocationType="RequestResponse",
                Payload=json.dumps(delete_payload)
            )
            
            # Check if delete was successful
            delete_response_payload = json.loads(delete_response["Payload"].read())
            
            if "errorMessage" in delete_response_payload:
                print(f"Warning: Memory provider cleanup returned error: {delete_response_payload['errorMessage']}")
            else:
                print(f"✅ Successfully cleaned up shared memory provider: {memory_id}")
                
        except Exception as e:
            print(f"Warning: Failed to clean up memory provider {memory_id}: {e}")


@pytest.fixture(scope="session")
def session_runtime(agentcore_control_client, deployed_resources):
    """Session-scoped fixture to create and manage a shared runtime for all tests.
    
    Creates a single runtime at the beginning of the test session using the same approach
    as the unit test's shared_test_runtime fixture, shared across unit and system tests.
    """
    TEST_AGENT_RUNTIME_ID = os.getenv('TEST_AGENT_RUNTIME_ID', None)
    if TEST_AGENT_RUNTIME_ID:
        print(f"Using existing agent runtime: {TEST_AGENT_RUNTIME_ID}")
        yield AgentCoreRuntimeClient.get_agentcore_runtime(
            GetAgentRuntimeRequest(
                agent_runtime_id=TEST_AGENT_RUNTIME_ID
            )
        )
    else:
        agent_runtime_id = None
        # Constants from unit test
        TEST_RUNTIME_NAME_PREFIX = "test_runtime"
        AWS_REGION = os.getenv('REGION', 'us-west-2')
        TEST_BUCKET = deployed_resources.get("agentcore_runtime_zip_files_bucket_id", 'agentcore-agentpath-agentcore-runtime-zip-files')
        
        try:
            # First, try to list existing runtimes and use one if available
            list_request = ListAgentRuntimesRequest()
            list_response = AgentCoreRuntimeClient.list_agent_runtimes(list_request)
            
            # Look for existing test runtimes first and check if they're ready
            for runtime in list_response.agent_runtimes:
                if runtime.agent_runtime_name.startswith(TEST_RUNTIME_NAME_PREFIX):
                    print(f"Found existing test runtime: {runtime.agent_runtime_id}")
                    # Check if the existing runtime is ready
                    try:
                        existing_runtime_data = _wait_for_runtime_active(agentcore_control_client, runtime.agent_runtime_id, max_wait_time=30)
                        if existing_runtime_data:
                            runtime = AgentCoreRuntimeClient.get_agentcore_runtime(
                                GetAgentRuntimeRequest(agent_runtime_id=runtime.agent_runtime_id)
                            )
                            print(f"Using existing ready runtime: {runtime.agent_runtime_id}")
                            agent_runtime_id = runtime.agent_runtime_id
                            yield runtime
                            return

                    except Exception as e:
                        print(f"Existing runtime {runtime.agent_runtime_id} not ready or failed: {e}")
                        continue

            # If we get here we're going to create a new one using the new create_agent_runtime function
            unique_suffix = uuid4().hex[-6:]
            test_runtime_name = f"{TEST_RUNTIME_NAME_PREFIX}_{unique_suffix}"
            print(f"Creating test_runtime_name {test_runtime_name}")
            
            # Use the new create_agent_runtime method that uses local templates and agentcore CLI
            create_request = CreateAgentRuntimeRequest(
                agent_description="A test agent for unit and system testing using the single agent deployment template",
                name=test_runtime_name,
                entrypoint="entrypoint.py",
                protocol="HTTP"
            )

            print(f"Sending request to create_agent_runtime {create_request}")
            runtime = AgentCoreRuntimeClient.create_agent_runtime(create_request, stream_output=True)
            print(f"Got agentcore runtime result {runtime}")
            agent_runtime_id = runtime.agent_runtime_id
            print(f"Created new test runtime with ID: {agent_runtime_id}")
            
            # Wait for runtime to be ready using the AgentCoreRuntimeClient's wait method
            print(f"Waiting for runtime {agent_runtime_id} to be READY...")
            runtime = AgentCoreRuntimeClient.wait_for_runtime_ready(agent_runtime_id, max_wait_time=600)
            print(f"Runtime {agent_runtime_id} is now READY: {runtime}")
            print(f"Yielding runtime with id: {agent_runtime_id}")
            yield runtime
        finally:
            if DELETE_AT_END and agent_runtime_id:
                # Cleanup the shared runtime at the end of the session if we created it
                print(f"\n\nDELETING TEST AGENTCORE RUNTIME {agent_runtime_id}\n\n")
                try:
                    delete_request = DeleteAgentRuntimeRequest(agent_runtime_id=agent_runtime_id)
                    AgentCoreRuntimeClient.delete_agentcore_runtime(delete_request)
                    print(f"Successfully cleaned up shared runtime: {agent_runtime_id}")
                except Exception as e:
                    print(f"Warning: Failed to clean up runtime {agent_runtime_id}: {e}")


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", 
        "lambda_test: mark test as a Lambda function test"
    )
    config.addinivalue_line(
        "markers", 
        "ecs_test: mark test as an ECS service test"
    )
    config.addinivalue_line(
        "markers", 
        "e2e_test: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add markers based on test file names
        if "lambda" in item.nodeid:
            item.add_marker(pytest.mark.lambda_test)
        # if "ecs" in item.nodeid:
        #     item.add_marker(pytest.mark.ecs_test)
        # if "e2e" in item.nodeid or "end_to_end" in item.nodeid:
        #     item.add_marker(pytest.mark.e2e_test)
        
        # Mark tests that might be slow
        if any(keyword in item.nodeid for keyword in ["load", "performance", "concurrent", "stress"]):
            item.add_marker(pytest.mark.slow)
