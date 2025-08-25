"""
Integration tests for the AgentCoreMemoryClient class.

These tests verify the functionality of the AgentCoreMemoryClient class,
which manages Bedrock AgentCore Memory resources using real AWS API calls.

Note: These tests require valid AWS credentials and will make real API calls
to AWS Bedrock AgentCore services. They may incur costs and should be run
with caution.
"""
import json
import os
import pytest
import boto3
import time
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError

import sys
sys.path.insert(0, '../src')

from agentic_platform.service.agentcore.memory.client.agentcore_memory_client import AgentCoreMemoryClient
from agentic_platform.service.agentcore.types import (
    CreateMemoryProviderRequest,
    DeleteMemoryProviderRequest,
    GetMemoryProviderRequest,
    ListEventsRequest,
    ListMemoryRecordsRequest,
    ListMemoryProvidersRequest,
    UpdateMemoryProviderRequest
)

# Test constants
TEST_ENVIRONMENT = "AgentCore-AgentPath-Test"
AWS_REGION = os.getenv('REGION', 'us-west-2')

MEMORY_ID = os.getenv('TEST_WITH_MEMORY_ID', None)
print(f"Got memory id from env {MEMORY_ID}")
DELETE_AT_END = os.getenv('DELETE_AT_END', 'True')
if DELETE_AT_END.lower() in ['false', '0', 'no', 'n']:
    DELETE_AT_END = False
else:
    DELETE_AT_END = True

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
        get_request = GetMemoryProviderRequest(

        )
        yield MEMORY_ID
    else:
        memory_id = None
        try:
            # Create a single memory for all tests to share
            create_request = CreateMemoryProviderRequest(
                environment=TEST_ENVIRONMENT,
                retention_days=7,
            )
            
            response = AgentCoreMemoryClient.create_memory_provider(create_request)
            print()
            memory_id = response.memory_id
            print(f"Created shared test memory with ID: {memory_id}")
            
            memory_details = AgentCoreMemoryClient.wait_for_memory_provider_creation(
                memory_id
            )
            yield memory_id
            # Verify the memory was created successfully
            # memory_details = real_agentcore_clients['agentcore_control_client'].get_memory(
            #     memoryId=memory_id
            # )['memory']
            # if 'createdAt' in memory_details and isinstance(memory_details['createdAt'], datetime):
            #     memory_details['createdAt'] = memory_details['createdAt'].isoformat()
            
            # if 'updatedAt' in memory_details and isinstance(memory_details['updatedAt'], datetime):
            #     memory_details['updatedAt'] = memory_details['updatedAt'].isoformat()
            
            # for i in range(len(memory_details['strategies'])):
            #     memory_details['strategies'][i]['createdAt'] = memory_details['strategies'][i]['createdAt'].isoformat()
            #     memory_details['strategies'][i]['updatedAt'] = memory_details['strategies'][i]['updatedAt'].isoformat()

            # print(f"Got memory details: {memory_details}")
            # print(f"Got memory details to JSON: {json.dumps(memory_details, indent=2)}")
            # assert memory_details['status'] == 'READY'
            
            # yield memory_id
            
        except Exception as e:
            if "Memory with name" in str(e) and "already exist" in str(e):
                print("Shared memory already exists - using existing memory")
                print(str(e))
                # Try to get the existing memory ID from SSM
                try:
                    memory_id = real_agentcore_clients['ssm_client'].put_parameter(
                        Name=f"/{TEST_ENVIRONMENT}/agentcore_memory_id"
                    )['Parameter']['Value']
                    print(f"Returning memory id {memory_id}")
                    yield memory_id
                except Exception as ssm_error:
                    raise Exception(f"Cannot retrieve existing memory ID: {str(ssm_error)}")
            else:
                raise Exception(f"Cannot create shared test memory: {str(e)}")
        
        finally:
            # Cleanup the shared memory at the end of the session
            if memory_id and DELETE_AT_END:
                with open('../.env', 'a') as f_out:
                    f_out.write(f"export MEMORY_ID={memory_id}\n")
                # try:
                #     delete_request = DeleteMemoryProviderRequest(
                #         memory_id=memory_id,
                #         agentcore_control_client=real_agentcore_clients['agentcore_control_client']
                #     )
                #     AgentCoreMemoryClient.delete_memory_provider(delete_request)
                #     print(f"Cleaned up shared test memory: {memory_id}")
                # except Exception as e:
                #     print(f"Failed to cleanup shared memory {memory_id}: {str(e)}")


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
                    delete_request = DeleteMemoryProviderRequest(
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
    assert memory_details['memory']['status'] == 'READY'
    print(f"Successfully verified shared memory with ID: {memory_id}")


# def dont_test_delete_memory_provider( real_agentcore_clients, env_setup, cleanup_additional_memories):
#     """Test deleting a memory provider with real AWS API calls."""
#     # Create a separate memory specifically for deletion testing
#     control_client = real_agentcore_clients['agentcore_control_client']
#     memory_name = f"{TEST_ENVIRONMENT}_Delete".replace('-','_')
    
#     try:
#         create_response = control_client.create_memory(
#             name=memory_name,
#             description=f"AgentCore memory for {TEST_ENVIRONMENT}-Delete environment",
#             eventExpiryDuration=7,
#             memoryStrategies={
#                 "semanticMemoryStrategy": {
#                     'name': 'semantic_memory',
#                     'description': 'Use this for long-term memories to be retrieved by semantic similarity.'
#                 }
#             }
            
#         )
#         memory_id = create_response['memory']['id']
        
#         # Wait for creation to complete
#         AgentCoreMemoryClient.wait_for_memory_provider_creation(
#             control_client,
#             memory_id
#         )
        
#         # Now test deletion
#         delete_request = DeleteMemoryProviderRequest(
#             memory_id=memory_id,
#             agentcore_control_client=control_client
#         )
        
#         # Act
#         result = AgentCoreMemoryClient.delete_memory_provider(delete_request)
        
#         # Assert
#         assert result == memory_id
#         print(f"Successfully deleted memory with ID: {memory_id}")
        
#         # Verify deletion by trying to get the memory (should fail)
#         with pytest.raises(Exception):
#             control_client.get_memory(memoryId=memory_id)
            
#     except Exception as e:
#         if "Memory with name" in str(e) and "already exist" in str(e):
#             pytest.skip("Cannot test deletion - memory already exists from previous runs")
#         else:
#             raise

def test_update_memory_provider( shared_test_memory, real_agentcore_clients, env_setup):
    """Test updating a memory provider with real AWS API calls."""
    memory_id = shared_test_memory
    print(f"Updating agentcore memory with id {memory_id}")
    # Test update using the shared memory
    update_request = UpdateMemoryProviderRequest(
        memory_id=memory_id,
        description="Updated test description for shared memory",
        event_expiry_duration=14
    )
     
    # Act
    result = AgentCoreMemoryClient.update_memory_provider(update_request)
    print(f"Got update result {result}")
    # Assert

    assert result['memory_id'] == memory_id
    assert result['description'] == "Updated test description for shared memory"
    assert result['event_expiry_duration'] == 14
    print(f"Successfully updated shared memory with ID: {memory_id}")


# def test_get_session_context_new_user( shared_test_memory, real_agentcore_clients, env_setup):
#     print("Test getting session context for a new user (should create initial session).")
#     memory_id = shared_test_memory
    
#     # Test getting session context for a new user
#     test_user_id = f"test-user-{int(time.time())}"
#     request = GetSessionContextRequest(
#         user_id=test_user_id,
#         session_id=None,  # Let it create a new session
#         next_token=None
#     )
    
#     # Act
#     response = AgentCoreMemoryClient.get_session_context(request)
#     print(f"Got response from get_session_context: {response}")
#     # Assert
#     assert response is not None
#     assert response.session_id is not None
#     assert response.user_id == test_user_id
#     assert len(response.messages) == 1
#     assert response.messages[0].content[0].text == 'Initializing new AgentCore memory session.'
#     # assert len(response.results) > 0
#     # assert response.results[0].user_id == test_user_id
#     # assert response.results[0].session_id is not None
#     print(f"Successfully created session context for new user: {test_user_id}")

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

def test_list_events( shared_test_memory, real_agentcore_clients, env_setup):
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
    request = ListEventsRequest(
        memory_id=memory_id,
        session_id=session_id,
        actor_id=test_user_id,
    )
    
    # Act
    response = AgentCoreMemoryClient.list_events(request)
    events = response.events
    # Assert
    assert events is not None
    assert len(events) > 0
    print(f"Successfully retrieved {len(events)} memories for session: {session_id}")

def test_list_memory_records(shared_test_memory, real_agentcore_clients, env_setup):
    """Test listing memory records for a memory provider."""
    memory_id = shared_test_memory
    
    # Create some events first to potentially generate memory records
    test_user_id = f"test-user-records-{int(time.time())}"
    agentcore_client = real_agentcore_clients['agentcore_client']
    
    # Create several events to increase chance of memory records being created
    for i in range(3):
        agentcore_client.create_event(
            memoryId=memory_id,
            actorId=test_user_id,
            eventTimestamp=datetime.now(),
            payload=[{
                "conversational": {
                    "content": {
                        "text": f"Test message {i} for memory record generation with some semantic content about testing AgentCore functionality"
                    },
                    "role": "USER"
                }
            }]
        )
    
    # Wait a moment for potential memory record processing
    wait_s = 3
    print(f"Waiting {wait_s} for event to be extracted to memory record.")
    time.sleep(wait_s)
    
    # Test listing memory records with a generic namespace
    request = ListMemoryRecordsRequest(
        memory_id=memory_id,
        namespace="/strategies",
        max_results=10
    )
    
    # Act
    response = AgentCoreMemoryClient.list_memory_records(request)
    print(f"Got response from list_memory_records: {response}")
    # Assert
    assert response is not None
    assert hasattr(response, 'memory_record_summaries')
    assert isinstance(response.memory_record_summaries, list)
    assert len(response.memory_record_summaries) > 0
    assert hasattr(response, 'next_token')
    
    print(f"Successfully retrieved {len(response.memory_record_summaries)} memory records for memory: {memory_id}")
    
    # If we got records, verify their structure
    if len(response.memory_record_summaries) > 0:
        record = response.memory_record_summaries[0]
        assert hasattr(record, 'memory_record_id')
        assert hasattr(record, 'content')
        assert hasattr(record, 'memory_strategy_id')
        assert hasattr(record, 'namespaces')
        assert hasattr(record, 'created_at')
        print(f"Memory record structure verified. First record ID: {record.memory_record_id}")
    else:
        print("No memory records found - this may be normal if records haven't been processed yet")

def test_list_memory_providers(shared_test_memory, real_agentcore_clients, env_setup):
    """Test listing memory providers."""
    memory_id = shared_test_memory
    
    # Create request to list memory providers
    request = ListMemoryProvidersRequest(
        max_results=10,
        next_token=None
    )
    
    # Act
    response = AgentCoreMemoryClient.list_memory_providers(request)
    print(f"Got response from list_memory_providers: {response}")
    
    # Assert
    assert response is not None
    assert 'memories' in response
    assert isinstance(response['memories'], list)
    assert len(response['memories']) > 0
    
    print(f"Successfully retrieved {len(response['memories'])} memory providers")
    print(f"Got response['memories'] {response['memories']}")
    # Verify that our shared test memory is in the list

    memory_ids = []
    for memory in response['memories']:
        print(f"Got memory: {memory}, type {type(memory)}")
        print(f"got memory_dict: {memory}")
        memory_ids.append(memory['memory_id'])

    assert memory_id in memory_ids, f"Shared test memory {memory_id} should be in the list of memory providers"
    
    # If we got memory providers, verify their structure
    if len(response['memories']) > 0:
        # I'm converting this to a dict because efor some reason 
        # assert hasattr(memory_entry, 'memory_id') and the rest
        # were failing, even though the attrs were there when
        # i did dir(memory_entry) and looked. This is a workaround
        # to quit wasting time on that oddity.
        memory_entry = response['memories'][0]
        print(f"inspecting memory entry {memory_entry}")
        assert 'memory_id' in memory_entry
        assert 'arn' in memory_entry
        assert 'status' in memory_entry
        assert 'created_at' in memory_entry
        assert 'updated_at' in memory_entry
        
        # Verify the memory_id is a valid string
        assert isinstance(memory_entry['memory_id'], str)
        assert len(memory_entry['memory_id']) > 0
        
        # Verify the ARN is a valid string
        assert isinstance(memory_entry['arn'], str)
        assert memory_entry['arn'].startswith('arn:aws:bedrock')
        
        # Verify the status is valid
        assert memory_entry['status'] in ['CREATING', 'ACTIVE', 'READY', 'DELETING', 'FAILED']
        
        print(f"Memory provider structure verified. First memory ID: {memory_entry['memory_id']}")
        print(f"Memory provider ARN: {memory_entry['arn']}")
        print(f"Memory provider status: {memory_entry['status']}")
