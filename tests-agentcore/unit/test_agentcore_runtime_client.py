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
import shutil
import time
import zipfile
import tempfile

from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path
from uuid import uuid4

import sys
sys.path.insert(0, '../../src')

from agentic_platform.service.agentcore.runtime.client.agentcore_runtime_client import AgentCoreRuntimeClient
from agentic_platform.service.agentcore.types import (
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


# Get runtime ID from environment if provided for testing with existing runtime
# RUNTIME_ID = os.getenv('TEST_WITH_RUNTIME_ID', None)
# print(f"Got runtime id from env {RUNTIME_ID}")

# ECR container URI and IAM role ARN are required for creating new runtimes
# These must be provided via environment variables since they need to exist in your AWS account
# TEST_CONTAINER_URI = os.getenv('TEST_CONTAINER_URI', None)
# TEST_ROLE_ARN = os.getenv('TEST_ROLE_ARN', None)
USER_POOL_ID = os.getenv('USER_POOL_ID', None) 
USER_POOL_CLIENT_ID = os.getenv('USER_POOL_CLIENT_ID', None)
TEST_BUCKET = 'agentcore-agentpath-agentcore-runtime-zip-files'
# COGNITO_DISCOVERY_URL = os.getenv('COGNITO_DISCOVERY_URL', None)

# Check if we have the required infrastructure for creating new runtimes
# print(f"TEST_CONTAINER_URI: {TEST_CONTAINER_URI}")
# print(f"TEST_ROLE_ARN: {TEST_ROLE_ARN}")


# def get_test_container_uri():
#     """
#     Get the container URI for testing from environment variables.
    
#     Returns:
#         str: The ECR container URI to use for testing
        
#     Raises:
#         Exception: If TEST_CONTAINER_URI is not set
#     """
#     # if not TEST_CONTAINER_URI:
#     #     raise Exception("TEST_CONTAINER_URI environment variable must be set for runtime creation")
    
#     print(f"Using container URI from environment: {TEST_CONTAINER_URI}")
#     return TEST_CONTAINER_URI


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
            for runtime in list_response.agent_runtimes:
                if runtime.agent_runtime_name.startswith(TEST_RUNTIME_NAME_PREFIX):
                    print(f"Found existing test runtime: {runtime.agent_runtime_id}")
                    # Check if the existing runtime is ready
                    try:
                        existing_runtime_data = _wait_for_runtime_active(real_agentcore_control_client, runtime.agent_runtime_id, max_wait_time=30)
                        if existing_runtime_data:
                            runtime = AgentCoreRuntimeClient.get_agentcore_runtime(
                                GetAgentRuntimeRequest(agent_runtime_id=runtime.agent_runtime_id)
                            )
                            print(f"Using existing ready runtime: {runtime.agent_runtime_id}")
                            agent_runtime_id = runtime.agent_runtime_id
                            yield runtime

                    except Exception as e:
                        raise Exception (f"Existing runtime {runtime.agent_runtime_id} not ready or failed: {e}")

            # if we get here we're going to create a new one.
            unique_suffix = uuid4().hex[-6:]
            test_runtime_name = f"{TEST_RUNTIME_NAME_PREFIX}_{unique_suffix}"
            print(f"Creating test_runtime_name {test_runtime_name}")
            test_dir = './unit/test_deployment'
            if os.path.isdir(f"{test_dir}/__pycache__"):
                print(f"Removing previous pycache files.")
                shutil.rmtree(f"{test_dir}/__pycache__")
            
            print(f"os.getcwd() = {os.getcwd()}")
            print(f"Creating {test_dir}/create_agent_runtime_test.zip")
            result = shutil.make_archive('create_agent_runtime_test', 'zip', test_dir)
            print(f"Result from make_archive: {result}")
            s3_client = boto3.client('s3', region_name=AWS_REGION)
            source_zip_file = f"./create_agent_runtime_test.zip"
            s3_key = 's3_zip_files/create_agent_runtime_test.zip'
            print(f"Uploading {source_zip_file} to s3://{TEST_BUCKET}/{s3_key}")
            s3_client.upload_file(
                source_zip_file,
                TEST_BUCKET,
                s3_key
            )
            create_request = CreateAgentRuntimeRequest(
                s3_zip_path=f's3://{TEST_BUCKET}/{s3_key}',
                update_on_conflict=True,
                name='test_entrypoint'
            )

            print(f"sending request to create_agentcore_runtime {create_request}")
            runtime = AgentCoreRuntimeClient.create_agentcore_runtime(create_request)
            print(f"Got agentcore runtime result {runtime}")
            agent_runtime_id = runtime.agent_runtime_id
            print(f"Created new test runtime with ID: {agent_runtime_id}")
            # Wait for runtime to be ready - CRITICAL: must be READY before yielding
            print(f"Waiting for runtime {agent_runtime_id} to be READY...")
            runtime_data = _wait_for_runtime_active(real_agentcore_control_client, agent_runtime_id)
            print(f"Runtime {agent_runtime_id} is now READY: {runtime_data}")
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


def test_create_agentcore_runtime(shared_test_runtime, real_agentcore_control_client, env_setup):
    """Test creating a runtime - uses shared runtime to verify it exists."""
    # Act - The shared runtime fixture already creates/verifies the runtime
    assert shared_test_runtime is not None
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
        status = runtime_details['agentRuntime']['status']
    elif 'status' in runtime_details:
        status = runtime_details['status']
    else:
        print(f"Unexpected response structure in test. Available keys: {list(runtime_details.keys())}")
        print(f"Full response: {runtime_details}")
        raise KeyError(f"Expected 'agentRuntime' or 'status' in response, but got keys: {list(runtime_details.keys())}")
    
    assert status == 'READY'
    print(f"Successfully verified shared runtime with ID: {agent_runtime_id}")


def test_create_agentcore_runtime_direct(shared_test_runtime):
    """Test validating a runtime that was created using the shared runtime fixture."""
    # Use the shared runtime to validate the response structure that would come from create_agentcore_runtime
    response = shared_test_runtime
    
    # Assert response structure (validates what create_agentcore_runtime would return)
    assert response is not None
    assert isinstance(response, GetAgentRuntimeResponse)  # Shared runtime returns GetResponse, but structure is similar
    assert response.agent_runtime_id is not None
    assert response.agent_runtime_arn is not None
    assert response.status == AgentRuntimeStatus.READY # Should be ready since shared runtime waits for READY
    assert response.created_at is not None
    
    # Verify the ARN format
    assert response.agent_runtime_arn.startswith('arn:aws:bedrock-agentcore:')
    assert response.agent_runtime_arn.endswith(f'runtime/{response.agent_runtime_id}')
    
    # Verify workload identity details exist
    assert response.workload_identity_details is not None
    assert isinstance(response.workload_identity_details, dict)
    
    print(f"Successfully validated shared runtime structure with ID: {response.agent_runtime_id}")


def test_create_agentcore_runtime_with_validation(shared_test_runtime):
    """Test validation of runtime response structure using shared runtime."""
    # Use shared runtime to validate response structure
    response = shared_test_runtime
    
    # Assert response structure - validates what we expect from create/get operations
    assert response is not None
    assert hasattr(response, 'agent_runtime_id')
    assert hasattr(response, 'agent_runtime_arn') 
    assert hasattr(response, 'workload_identity_details')
    assert hasattr(response, 'agent_runtime_version')
    assert hasattr(response, 'status')
    assert hasattr(response, 'created_at')
    
    # Validate response data types
    assert isinstance(response.agent_runtime_id, str)
    assert isinstance(response.agent_runtime_arn, str)
    assert isinstance(response.workload_identity_details, dict)
    assert isinstance(response.agent_runtime_version, (str, type(None)))  # Can be None
    assert isinstance(response.status, AgentRuntimeStatus)
    assert isinstance(response.created_at, str)
    
    # Validate that runtime is in ready state (should be since shared fixture waits)
    assert response.status == AgentRuntimeStatus.READY
    
    print(f"Successfully validated shared runtime structure and types with ID: {response.agent_runtime_id}")


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
