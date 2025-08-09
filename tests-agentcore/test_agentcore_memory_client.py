"""
Integration tests for the AgentCoreMemoryClient class.

These tests verify the functionality of the AgentCoreMemoryClient class,
which manages Bedrock AgentCore Memory resources using real AWS API calls.

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

import sys
sys.path.insert(0, '../src')

from agentic_platform.service.memory_gateway.client.memory.agentcore_memory_client import AgentCoreMemoryClient
from agentic_platform.core.models.memory_models import (
    CreateAgentCoreMemoryProviderRequest,
    DeleteAgentCoreMemoryProviderRequest,
    UpdateAgentCoreMemoryProviderRequest,
    GetSessionContextRequest,
    GetMemoriesRequest,
    CreateMemoryRequest,
    SessionContext,
    Memory
)

# Test constants
TEST_ENVIRONMENT = "AgentCore-AgentPath-Test"
AWS_REGION = os.getenv('REGION', 'us-west-2')

MEMORY_ID = os.getenv('TEST_WITH_MEMORY_ID', None)
print(f"Got memory id from env {MEMORY_ID}")

@pytest.fixture(scope="session")
def real_agentcore_clients():
    """Session-scoped fixture to provide real boto3 clients for testing."""
    try:
        agentcore_client = boto3.client('bedrock-agentcore', region_name=AWS_REGION)
        agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=AWS_REGION)
        ssm_client = boto3.client('ssm', region_name=AWS_REGION)
        return {
            'agentcore_client': agentcore_client,
            'agentcore_control_client': agentcore_control_client,
            'ssm_client': ssm_client
        }
    except NoCredentialsError:
        pytest.skip("AWS credentials not configured")
    except Exception as e:
        pytest.skip(f"Cannot initialize AWS clients: {str(e)}")


@pytest.fixture(scope="session")
def env_setup():
    """Session-scoped fixture to set up environment variables for tests and restore them after."""
    original_env = {
        'MEMORY_RETENTION_PERIOD': os.getenv('MEMORY_RETENTION_PERIOD'),
        'ENVIRONMENT': os.getenv('ENVIRONMENT'),
        'AWS_REGION': os.getenv('AWS_REGION')
    }
    
    os.environ['MEMORY_RETENTION_PERIOD'] = '7'
    os.environ['ENVIRONMENT'] = TEST_ENVIRONMENT
    os.environ['AWS_REGION'] = AWS_REGION
    
    yield
    
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]


@pytest.fixture(scope="session")
def shared_test_memory(real_agentcore_clients, env_setup):
    global MEMORY_ID
    """Session-scoped fixture to create a single shared memory for all tests."""
    if MEMORY_ID:
        print(f"Skipping memory service creation and using {MEMORY_ID}")
        yield MEMORY_ID
    else:
        memory_id = None
        try:
            # Create a single memory for all tests to share
            create_request = CreateAgentCoreMemoryProviderRequest(
                environment=TEST_ENVIRONMENT,
                retention_days=7,
            )
            
            memory_id = AgentCoreMemoryClient.create_memory_provider(create_request)
            print(f"Created shared test memory with ID: {memory_id}")
            
            # Verify the memory was created successfully
            memory_details = real_agentcore_clients['agentcore_control_client'].get_memory(
                memoryId=memory_id
            )
            assert memory_details['memory']['status'] == 'ACTIVE'
            
            yield memory_id
            
        except Exception as e:
            if "Memory with name" in str(e) and "already exist" in str(e):
                print("Shared memory already exists - using existing memory")
                print(str(e))
                # Try to get the existing memory ID from SSM
                try:
                    memory_id = real_agentcore_clients['ssm_client'].put_parameter(
                        Name=f"/{TEST_ENVIRONMENT}/agentcore_memory_id"
                    )['Parameter']['Value']
                    yield memory_id
                except Exception as ssm_error:
                    pytest.skip(f"Cannot retrieve existing memory ID: {str(ssm_error)}")
            else:
                pytest.skip(f"Cannot create shared test memory: {str(e)}")
        
        finally:
            # Cleanup the shared memory at the end of the session
            if memory_id:
                try:
                    delete_request = DeleteAgentCoreMemoryProviderRequest(
                        memory_id=memory_id,
                        agentcore_control_client=real_agentcore_clients['agentcore_control_client']
                    )
                    AgentCoreMemoryClient.delete_memory_provider(delete_request)
                    print(f"Cleaned up shared test memory: {memory_id}")
                except Exception as e:
                    print(f"Failed to cleanup shared memory {memory_id}: {str(e)}")


@pytest.fixture
def cleanup_additional_memories():
    """Fixture to clean up any additional memory resources created during specific tests."""
    created_memory_ids = []
    
    def track_memory_id(memory_id):
        created_memory_ids.append(memory_id)
    
    yield track_memory_id
    
    # Cleanup additional memories created during tests
    if created_memory_ids:
        try:
            agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=AWS_REGION)
            for memory_id in created_memory_ids:
                try:
                    delete_request = DeleteAgentCoreMemoryProviderRequest(
                        memory_id=memory_id,
                        agentcore_control_client=agentcore_control_client
                    )
                    AgentCoreMemoryClient.delete_memory_provider(delete_request)
                    print(f"Cleaned up additional test memory: {memory_id}")
                except Exception as e:
                    print(f"Failed to cleanup additional memory {memory_id}: {str(e)}")
        except Exception as e:
            print(f"Failed to initialize cleanup client: {str(e)}")


def dont_test_create_memory_provider(shared_test_memory, real_agentcore_clients, env_setup):
    """Test creating a memory provider - uses shared memory to verify it exists."""
    # Act - The shared memory fixture already creates/verifies the memory
    memory_id = shared_test_memory
    
    # Assert
    assert memory_id is not None
    assert isinstance(memory_id, str)
    
    # Verify the memory was actually created by checking its status
    memory_details = real_agentcore_clients['agentcore_control_client'].get_memory(
        memoryId=memory_id
    )
    assert memory_details['memory']['status'] == 'ACTIVE'
    print(f"Successfully verified shared memory with ID: {memory_id}")

def dont_test_create_memory_provider_idempotent( shared_test_memory, real_agentcore_clients, env_setup):
    """Test that creating the same memory provider twice handles the conflict gracefully."""
    # This test verifies behavior when memory already exists
    request = CreateAgentCoreMemoryProviderRequest(
        environment=TEST_ENVIRONMENT,
        retention_days=7,
    )
    
    # This test expects that the memory might already exist from previous runs
    # We're testing the error handling behavior
    try:
        memory_id = AgentCoreMemoryClient.create_memory_provider(request)
        # Should return the existing memory ID
        assert memory_id == shared_test_memory
        print(f"Created or found existing memory with ID: {memory_id}")
    except Exception as e:
        if "Memory with name" in str(e) and "already exist" in str(e):
            print("Memory already exists - this is expected behavior")
        else:
            pytest.fail(f"Unexpected error: {str(e)}")

def dont_test_delete_memory_provider( real_agentcore_clients, env_setup, cleanup_additional_memories):
    """Test deleting a memory provider with real AWS API calls."""
    # Create a separate memory specifically for deletion testing
    control_client = real_agentcore_clients['agentcore_control_client']
    memory_name = f"{TEST_ENVIRONMENT}_Delete".replace('-','_')
    
    try:
        create_response = control_client.create_memory(
            name=memory_name,
            description=f"AgentCore memory for {TEST_ENVIRONMENT}-Delete environment",
            eventExpiryDuration=7,
            memoryStrategies=[
                {
                    "semanticMemoryStrategy": {
                        'name': 'semantic_memory',
                        'description': 'Use this for long-term memories to be retrieved by semantic similarity.'
                    }
                }
            ]
        )
        memory_id = create_response['memory']['id']
        
        # Wait for creation to complete
        AgentCoreMemoryClient._wait_for_memory_provider_creation(
            control_client,
            memory_id
        )
        
        # Now test deletion
        delete_request = DeleteAgentCoreMemoryProviderRequest(
            memory_id=memory_id,
            agentcore_control_client=control_client
        )
        
        # Act
        result = AgentCoreMemoryClient.delete_memory_provider(delete_request)
        
        # Assert
        assert result == memory_id
        print(f"Successfully deleted memory with ID: {memory_id}")
        
        # Verify deletion by trying to get the memory (should fail)
        with pytest.raises(Exception):
            control_client.get_memory(memoryId=memory_id)
            
    except Exception as e:
        if "Memory with name" in str(e) and "already exist" in str(e):
            pytest.skip("Cannot test deletion - memory already exists from previous runs")
        else:
            raise

def dont_test_update_memory_provider( shared_test_memory, real_agentcore_clients, env_setup):
    """Test updating a memory provider with real AWS API calls."""
    memory_id = shared_test_memory
    
    # Test update using the shared memory
    update_request = UpdateAgentCoreMemoryProviderRequest(
        memory_id=memory_id,
        agentcore_control_client=real_agentcore_clients['agentcore_control_client'],
        description="Updated test description for shared memory",
        event_expiry_duration=14,
        memory_strategies=None
    )
    
    # Act
    result = AgentCoreMemoryClient.update_memory_provider(update_request)
    
    # Assert
    assert result['memoryId'] == memory_id
    assert result['description'] == "Updated test description for shared memory"
    assert result['eventExpiryDuration'] == 14
    print(f"Successfully updated shared memory with ID: {memory_id}")

def dont_test_wait_for_memory_provider_creation( real_agentcore_clients, env_setup, cleanup_additional_memories):
    """Test the wait function with a real memory creation."""
    control_client = real_agentcore_clients['agentcore_control_client']
    memory_name = f"{TEST_ENVIRONMENT}_Wait".replace('-','_')
    
    try:
        create_response = control_client.create_memory(
            name=memory_name,
            description=f"AgentCore memory for {TEST_ENVIRONMENT}-Wait environment",
            eventExpiryDuration=14,
            memoryStrategies=[
                {
                    "semanticMemoryStrategy": {
                        'name': 'semantic_memory',
                        'description': 'Use this for long-term memories to be retrieved by semantic similarity.'
                    }
                }
            ]
        )
        memory_id = create_response['memory']['id']
        cleanup_additional_memories(memory_id)
        
        # Now test the wait function
        result = AgentCoreMemoryClient._wait_for_memory_provider_creation(
            control_client,
            memory_id
        )
        
        # Assert
        assert result['id'] == memory_id
        assert result['status'] == 'ACTIVE'
        print(f"Successfully waited for memory creation: {memory_id}")
        
    except Exception as create_error:
        if "Memory with name" in str(create_error) and "already exist" in str(create_error):
            pytest.skip("Cannot test wait function - memory already exists")
        else:
            raise

def dont_test_wait_for_memory_provider_deletion( real_agentcore_clients, env_setup):
    """Test the wait for deletion function with a real memory deletion."""
    control_client = real_agentcore_clients['agentcore_control_client']
    memory_name = f"{TEST_ENVIRONMENT}_DeleteWait".replace('-','_')
    
    try:
        create_response = control_client.create_memory(
            name=memory_name,
            description=f"AgentCore memory for {TEST_ENVIRONMENT}-DeleteWait environment",
            eventExpiryDuration=7,
            memoryStrategies=[
                {
                    "semanticMemoryStrategy": {
                        'name': 'semantic_memory',
                        'description': 'Use this for long-term memories to be retrieved by semantic similarity.'
                    }
                }
            ]
        )
        memory_id = create_response['memory']['id']
        
        # Wait for creation to complete first
        AgentCoreMemoryClient._wait_for_memory_provider_creation(
            control_client,
            memory_id
        )
        
        # Now delete the memory
        control_client.delete_memory(memoryId=memory_id)
        
        # Test the deletion wait function
        result = AgentCoreMemoryClient._wait_for_memory_provider_deletion(
            control_client,
            memory_id
        )
        
        # Assert
        assert result is True
        print(f"Successfully waited for memory deletion: {memory_id}")
        
    except Exception as create_error:
        if "Memory with name" in str(create_error) and "already exist" in str(create_error):
            pytest.skip("Cannot test deletion wait function - memory already exists")
        else:
            raise

def test_get_session_context_new_user( shared_test_memory, real_agentcore_clients, env_setup):
    print("Test getting session context for a new user (should create initial session).")
    memory_id = shared_test_memory
    
    # Test getting session context for a new user
    test_user_id = f"test-user-{int(time.time())}"
    request = GetSessionContextRequest(
        user_id=test_user_id,
        session_id=None,  # Let it create a new session
        next_token=None
    )
    
    # Act
    response = AgentCoreMemoryClient.get_session_context(request)
    print(f"Got response from get_session_context: {response}")
    # Assert
    assert response is not None
    assert response.session_id is not None
    assert response.user_id == test_user_id
    assert len(response.messages) == 1
    assert response.messages[0].content[0].text == 'Initializing new AgentCore memory session.'
    # assert len(response.results) > 0
    # assert response.results[0].user_id == test_user_id
    # assert response.results[0].session_id is not None
    print(f"Successfully created session context for new user: {test_user_id}")

def test_get_memories( shared_test_memory, real_agentcore_clients, env_setup):
    """Test getting memories for a session."""
    memory_id = shared_test_memory
    
    # Create a session with some events first
    test_user_id = f"test-user-memories-{int(time.time())}"
    agentcore_client = real_agentcore_clients['agentcore_client']
    
    # Create an event to have something to retrieve
    event_response = agentcore_client.create_event(
        memoryId=memory_id,
        actorId=test_user_id,
        eventTimestamp=datetime.now(),
        payload=[{
            "conversational": {
                "content": {
                    "text": "Test message for memory retrieval"
                },
                "role": "USER"
            }
        }]
    )
    session_id = event_response['event']['sessionId']
    
    # Now test getting memories
    request = GetMemoriesRequest(
        session_id=session_id,
        user_id=test_user_id,
        limit=10,
        next_token=None
    )
    
    # Act
    memories = AgentCoreMemoryClient.get_memories(request)
    
    # Assert
    assert memories is not None
    assert len(memories) > 0
    print(f"Successfully retrieved {len(memories)} memories for session: {session_id}")

def test_create_memory_event( shared_test_memory, real_agentcore_clients, env_setup):
    """Test creating a memory event."""
    """Test getting memories for a session."""
    memory_id = shared_test_memory
    
    # Create a session with some events first
    test_user_id = f"test-user-memories-{int(time.time())}"
    agentcore_client = real_agentcore_clients['agentcore_client']
    
    # Create an event to have something to retrieve
    event = agentcore_client.create_event(
        memoryId=memory_id,
        actorId=test_user_id,
        eventTimestamp=datetime.now(),
        payload=[{
            "conversational": {
                "content": {
                    "text": "Test message for memory retrieval"
                },
                "role": "USER"
            }
        }]
    )['event']
    assert event['sessionId'] is not None
    assert event['actorId'] == test_user_id