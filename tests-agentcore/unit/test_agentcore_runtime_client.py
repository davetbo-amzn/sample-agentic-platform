"""
Integration tests for the AgentCoreRuntimeClient class.

These tests verify the functionality of the AgentCoreRuntimeClient class,
which manages Bedrock AgentCore Runtime resources using real AWS API calls.

Note: These tests require valid AWS credentials and will make real API calls
to AWS Bedrock AgentCore services. They may incur costs and should be run
with caution.
"""

import os
import pytest
import boto3
import time

from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path
from uuid import uuid4

import sys
sys.path.insert(0, '../../src')

from agentic_platform.service.agentcore.runtime.client.agentcore_runtime_client import AgentCoreRuntimeClient
from agentic_platform.service.agentcore.types import (
    AgentRuntime,
    AgentRuntimeStatus,
    CreateAgentRuntimeRequest,
    DeleteAgentRuntimeRequest,
    GetAgentRuntimeRequest,
    GetAgentRuntimeResponse,
    ListAgentRuntimesRequest
)

# Load environment variables from .env file if it exists
def load_env_file():
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value

# Load .env file at module import time
load_env_file()

# Test constants
TEST_RUNTIME_NAME_PREFIX = "test_runtime"
AWS_REGION = os.getenv('REGION', 'us-west-2')

DELETE_AT_END = os.getenv('DELETE_AT_END', 'True')
if DELETE_AT_END.lower() in ['false', '0', 'no', 'n']:
    DELETE_AT_END = False
else:
    DELETE_AT_END = True




@pytest.fixture(scope="session")
def real_agentcore_control_client():
    """Session-scoped fixture to provide real boto3 client for testing."""
    agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=AWS_REGION)
    return agentcore_control_client


@pytest.fixture(scope="session")
def env_setup():
    """Session-scoped fixture to set up environment variables for tests and restore them after."""
    original_env = {
        'REGION': os.getenv('REGION')
    }
    
    os.environ['REGION'] = AWS_REGION
    
    yield
    
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]


@pytest.fixture(scope="session")
def shared_test_runtime(real_agentcore_control_client, env_setup):
    """Session-scoped fixture to get or create a runtime for all tests."""
    TEST_AGENT_RUNTIME_ID = os.getenv('TEST_AGENT_RUNTIME_ID', None)
    if TEST_AGENT_RUNTIME_ID:
        yield AgentCoreRuntimeClient.get_agentcore_runtime(
            GetAgentRuntimeRequest(
                agent_runtime_id=TEST_AGENT_RUNTIME_ID
            )
        )
    else:
        agent_runtime_id = None
        try:
            # First, try to list existing runtimes and use one if available
            list_request = ListAgentRuntimesRequest()
            list_response = AgentCoreRuntimeClient.list_agent_runtimes(list_request)
            
            # Look for existing test runtimes first and check if they're ready
            found_runtime = None
            for runtime in list_response.agent_runtimes:
                print(f"Got runtime from list_agent_runtimes: {runtime}")
                if isinstance(runtime, AgentRuntime):
                    runtime = runtime.to_dict()
                if runtime['agent_runtime_name'].startswith(TEST_RUNTIME_NAME_PREFIX):
                    print(f"Found existing test runtime: {runtime['agent_runtime_id']}")
                    # Check if the existing runtime is ready
                    found_runtime = runtime
            
            if found_runtime:
                try:
                    existing_runtime_data = _wait_for_runtime_active(real_agentcore_control_client, runtime['agent_runtime_id'], max_wait_time=30)
                    if existing_runtime_data:
                        response = AgentCoreRuntimeClient.get_agentcore_runtime(
                            GetAgentRuntimeRequest(agent_runtime_id=runtime['agent_runtime_id'])
                        )
                        print(f"Using existing ready runtime: {response.agent_runtime_id}")
                        agent_runtime_id = response.agent_runtime_id
                        yield runtime

                except Exception as e:
                    raise Exception (f"Existing runtime {runtime['agent_runtime_id']} not ready or failed: {e}")
            else:
                # If we get here we're going to create a new one using the new create_agent_runtime function
                unique_suffix = uuid4().hex[-6:]
                test_runtime_name = f"{TEST_RUNTIME_NAME_PREFIX}_{unique_suffix}"
                print(f"Creating test_runtime_name {test_runtime_name}")
                
                # Use the new create_agent_runtime method that uses local templates and agentcore CLI
                create_request = CreateAgentRuntimeRequest(
                    agent_description="A test agent for unit testing using the single agent deployment template",
                    name=test_runtime_name,
                    entrypoint="entrypoint.py",
                    protocol="HTTP"
                )

                print(f"Sending request to create_agent_runtime {create_request}")
                runtime = AgentCoreRuntimeClient.create_agent_runtime(create_request)
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
            if agent_runtime_id and DELETE_AT_END:
                # Cleanup the shared runtime at the end of the session if we created it
                print(f"\n\nDELETING TEST AGENTCORE RUNTIME {agent_runtime_id}\n\n")
                real_agentcore_control_client.delete_agent_runtime(
                    agentRuntimeId=agent_runtime_id
                )
                # if agent_runtime_id:
                #     print(f'Logging agent runtime id to .env: {agent_runtime_id}')
                #     with open('.env', 'a') as f_out:
                #         f_out.write(f'export RUNTIME_ID={agent_runtime_id}\n')


@pytest.fixture
def cleanup_additional_runtimes():
    """Fixture to clean up any additional runtime resources created during specific tests."""
    created_runtime_ids = []
    
    def track_runtime_id(agent_runtime_id):
        created_runtime_ids.append(agent_runtime_id)
    
    yield track_runtime_id
    
    # Cleanup additional runtimes created during tests
    for agent_runtime_id in created_runtime_ids:
        try:
            delete_request = DeleteAgentRuntimeRequest(agent_runtime_id=agent_runtime_id)
            AgentCoreRuntimeClient.delete_agentcore_runtime(delete_request)
            print(f"Cleaned up additional test runtime: {agent_runtime_id}")
        except Exception as e:
            print(f"Failed to cleanup additional runtime {agent_runtime_id}: {str(e)}")


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
            raise e
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


def test_create_agent_runtime(shared_test_runtime, real_agentcore_control_client, env_setup):
    """Test creating a runtime - uses shared runtime to verify it exists."""
    # Act - The shared runtime fixture already creates/verifies the runtime
    assert shared_test_runtime is not None
    print(f"test_create_agent_runtime received runtime {shared_test_runtime}")
    agent_runtime_id = shared_test_runtime.agent_runtime_id
    
    # Assert
    assert agent_runtime_id is not None
    assert isinstance(agent_runtime_id, str)
    
    # Verify the runtime was actually created by checking its status
    runtime_details = real_agentcore_control_client.get_agent_runtime(
        agentRuntimeId=agent_runtime_id
    )
    print(f"Got runtime details {runtime_details}")
    # Handle potential variations in response structure
    if 'agentRuntime' in runtime_details:
        status = runtime_details.agent_runtime['agentRuntime']['status']
    elif 'status' in runtime_details:
        status = runtime_details['status']
    else:
        print(f"Unexpected response structure in test. Available keys: {list(runtime_details.keys())}")
        print(f"Full response: {runtime_details}")
        raise KeyError(f"Expected 'agentRuntime' or 'status' in response, but got keys: {list(runtime_details.keys())}")
    
    assert status == 'READY'
    print(f"Successfully verified shared runtime with ID: {agent_runtime_id}")


def test_get_agentcore_runtime(shared_test_runtime, real_agentcore_control_client, env_setup):
    """Test getting runtime details with real AWS API calls."""
    agent_runtime_id = shared_test_runtime.agent_runtime_id
    
    # Test getting runtime details
    get_request = GetAgentRuntimeRequest(agent_runtime_id=agent_runtime_id)
    
    # Act
    response = AgentCoreRuntimeClient.get_agentcore_runtime(get_request)
    print(f"Got response from get_agentcore_runtime: {response}")
    # Assert
    assert response is not None
    assert response.agent_runtime_id == agent_runtime_id
    assert response.agent_runtime_name is not None
    assert response.status == AgentRuntimeStatus.READY
    assert response.created_at is not None
    print(f"Successfully retrieved runtime details for ID: {agent_runtime_id}")


def test_list_agentcore_runtimes(shared_test_runtime, real_agentcore_control_client, env_setup):
    """Test listing runtimes with real AWS API calls."""
    agent_runtime_id = shared_test_runtime.agent_runtime_id
    print(f"Testing with shared_test_runtime {shared_test_runtime}")
    print(f"test agent_runtime_id {agent_runtime_id}")

    # Test listing runtimes
    list_request = ListAgentRuntimesRequest(
        max_results=20
    )
    
    # Act
    response = AgentCoreRuntimeClient.list_agent_runtimes(list_request)
    print(f"test_list_agentcore_runtimes got response {response}")
    # Assert
    assert response is not None
    assert response.agent_runtimes is not None
    assert len(response.agent_runtimes) > 0
    
    # Verify our shared runtime is in the list
    runtime_found = False
    for runtime in response.agent_runtimes:
        print(f"Got runtime: {runtime} ")
        if runtime.agent_runtime_id == agent_runtime_id:
            runtime_found = True
            assert runtime.status == AgentRuntimeStatus.READY
            assert runtime.agent_runtime_name is not None
            break
    
    assert runtime_found, f"Shared runtime {agent_runtime_id} not found in list"
    print(f"Successfully listed {len(response.agent_runtimes)} runtimes, including shared runtime")

# def dont_test_update_agentcore_runtime(shared_test_runtime, real_agentcore_control_client, env_setup):
#     """Test updating a runtime with real AWS API calls."""
#     # Only run this test if we have infrastructure for updating runtimes
        
#     agent_runtime_id = shared_test_runtime.agent_runtime_id
#     print(f"test_update_agentcore_runtime got shared_test_runtime {shared_test_runtime} and agent_runtime_id {agent_runtime_id}")
    
#     # Test updating runtime description
#     new_description = "Updated test description for shared runtime"
#     update_request = UpdateAgentRuntimeRequest(
#         agent_runtime_id=agent_runtime_id,
#         agentRuntimeArtifact={
#             "s3Configuration": {
#                 "s3_zip_path": TEST_S3_ZIP_PATH,
#                 "entrypoint": TEST_ENTRYPOINT
#             }
#         },
#         roleArn=TEST_ROLE_ARN,
#         networkConfiguration={
#             "networkMode": "PUBLIC"
#         },
#         protocolConfiguration={
#             "serverProtocol": "HTTP"
#         },
#         authorizerConfiguration={
#             "customJWTAuthorizer": {
#                 "discoveryUrl": COGNITO_DISCOVERY_URL,
#                 "allowedClients": [USER_POOL_CLIENT_ID] if USER_POOL_CLIENT_ID else []
#             }
#         } if COGNITO_DISCOVERY_URL else {},
#         clientToken=str(uuid4()) + "asdf",
#         description=new_description
#     )
#     print(f"update_request before sending {update_request}")
    
#     # Act
#     response = AgentCoreRuntimeClient.update_agentcore_runtime(update_request)
#     print(f"update_agentcore_runtime response {response}")
    
#     assert response is not None
#     assert response['agent_runtime_id'] == agent_runtime_id
#     assert response['status'] is not None
#     assert response['lastUpdatedAt'] is not None
#     print(f"Successfully updated shared runtime with ID: {agent_runtime_id}")
    
#     # Verify the update by getting the runtime details
#     get_request = GetAgentRuntimeRequest(agent_runtime_id=agent_runtime_id)
#     updated_runtime = AgentCoreRuntimeClient.get_agentcore_runtime(get_request)
#     assert updated_runtime.description == new_description

# def dont_test_delete_agentcore_runtime(real_agentcore_control_client, env_setup):
#     """Test deleting a runtime with real AWS API calls."""
#     runtimes = AgentCoreRuntimeClient.list_agent_runtimes(
#         ListAgentRuntimesRequest(
#             max_results=100
#         )
#     ).agent_runtimes
#     print(f"Got listRuntimesResponse {runtimes} ")
#     delete_runtimes_with_prefix = 'test_runtime'
#     for rt in runtimes:
#         if rt['agent_runtime_id'].startswith(delete_runtimes_with_prefix):
#             delete_request = DeleteAgentRuntimeRequest(agent_runtime_id=rt['agent_runtime_id'])
#             # Act
#             response = AgentCoreRuntimeClient.delete_agentcore_runtime(delete_request)

#             # Assert
#             assert response is not None
#             assert response.agent_runtime_id == rt['agent_runtime_id']
#             assert response.status == "DELETING"
#             print(f"Successfully initiated deletion of runtime with ID: {rt['agent_runtime_id']}")
