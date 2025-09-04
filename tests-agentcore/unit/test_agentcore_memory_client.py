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
    RetrieveMemoryRecordsRequest,
    UpdateMemoryProviderRequest
)

# Test constants
TEST_ENVIRONMENT = "AgentCore-AgentPath-Test-09-01"
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
        yield MEMORY_ID
    else:
        memory_id = None
        try:
            # Create a single memory for all tests to share
            create_request = CreateMemoryProviderRequest(
                name=TEST_ENVIRONMENT,
                retention_days=7,
            )
            print("Creating a shared test memory fixture. Please wait. This takes about three and a half minutes.")
            response = AgentCoreMemoryClient.create_memory_provider(create_request)
            print(f"response from create_memory_provider: {response}")
            memory_id = response.memory_id
            print(f"Created shared test memory with ID: {memory_id}")
            
            AgentCoreMemoryClient.wait_for_memory_provider_creation(
                memory_id
            )
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
                    print(f"Returning memory id {memory_id}")
                    yield memory_id
                except Exception as ssm_error:
                    raise Exception(f"Cannot retrieve existing memory ID: {str(ssm_error)}")
            else:
                raise Exception(f"Cannot create shared test memory: {str(e)}")
        
        finally:
            # Cleanup the shared memory at the end of the session
            if memory_id and DELETE_AT_END:
                # with open('../.env', 'a') as f_out:
                #     f_out.write(f"export MEMORY_ID={memory_id}\n")
                try:
                    delete_request = DeleteMemoryProviderRequest(
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
    print(f"test_update_memory_provider sending request {update_request}")
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
    # this doesn't really work because memory extraction is too async. 30 seconds isn't enough and it's not worth testing the service itself.
    # if our event got saved above and retrieved, we're good.
    # wait_s = 30
    # print(f"Waiting {wait_s} for event to be extracted to memory record.")
    # time.sleep(wait_s)
    
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
    # the memory extraction from an event is too async to test here and it's not worth testing the AgentCore service itself.
    # assert len(response.memory_record_summaries) > 0

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

def test_retrieve_memory_records(shared_test_memory, real_agentcore_clients, env_setup):
    """Test retrieving memory records using semantic search."""
    memory_id = shared_test_memory
    
    # Create some events first to potentially generate memory records
    test_user_id = f"test-user-retrieve-{int(time.time())}"
    agentcore_client = real_agentcore_clients['agentcore_client']
    agentcore_control_client = real_agentcore_clients['agentcore_control_client']
    
    # Create several events with semantic content
    for i in range(3):
        agentcore_client.create_event(
            memoryId=memory_id,
            actorId=test_user_id,
            eventTimestamp=datetime.now(),
            payload=[{
                "conversational": {
                    "content": {
                        "text": f"Test message {i} about artificial intelligence and machine learning for semantic retrieval testing"
                    },
                    "role": "USER"
                }
            }]
        )
    
    # Get memory provider details to find strategy IDs
    memory_provider = agentcore_control_client.get_memory(memoryId=memory_id)['memory']
    
    # Find a semantic memory strategy ID
    semantic_strategy_id = None
    for strategy in memory_provider['strategies']:
        if 'semantic' in strategy.get('name', '').lower():
            semantic_strategy_id = strategy['strategyId']
            break
    
    if not semantic_strategy_id:
        # If no semantic strategy found, use the first available strategy
        semantic_strategy_id = memory_provider['strategies'][0]['strategyId']
    
    print(f"Using memory strategy ID: {semantic_strategy_id}")
    
    # Test retrieving memory records with semantic search
    request = RetrieveMemoryRecordsRequest(
        memory_id=memory_id,
        query="artificial intelligence machine learning",
        memory_strategy_id=semantic_strategy_id,
        actor_id=test_user_id,
        max_results=5,
        session_id=None  # Test without session ID
    )
    
    # Act
    response = AgentCoreMemoryClient.retrieve_memory_records(request)
    print(f"Got response from retrieve_memory_records: {response}")
    
    # Assert
    assert response is not None
    assert hasattr(response, 'memory_record_summaries')
    assert isinstance(response.memory_record_summaries, list)
    
    # Note: Memory extraction from events is asynchronous, so we might not get results immediately
    # But the method should execute without errors and return a valid response structure
    print(f"Successfully executed retrieve_memory_records. Found {len(response.memory_record_summaries)} records")
    
    # If we do get records, verify their structure
    if len(response.memory_record_summaries) > 0:
        record = response.memory_record_summaries[0]
        assert hasattr(record, 'memory_record_id')
        assert hasattr(record, 'content')
        assert hasattr(record, 'memory_strategy_id')
        assert hasattr(record, 'namespaces')
        assert hasattr(record, 'created_at')
        assert hasattr(record, 'score')  # Should have score for semantic search
        
        print(f"Memory record structure verified. Record ID: {record.memory_record_id}")
        print(f"Memory record strategy ID: {record.memory_strategy_id}")
        if record.score is not None:
            print(f"Memory record score: {record.score}")
    
    # Test with a session ID as well
    session_id = f"test-session-{int(time.time())}"
    request_with_session = RetrieveMemoryRecordsRequest(
        memory_id=memory_id,
        query="testing semantic search functionality",
        memory_strategy_id=semantic_strategy_id,
        actor_id=test_user_id,
        max_results=3,
        session_id=session_id
    )
    
    # Act
    response_with_session = AgentCoreMemoryClient.retrieve_memory_records(request_with_session)
    print(f"Got response from retrieve_memory_records with session: {response_with_session}")
    
    # Assert
    assert response_with_session is not None
    assert hasattr(response_with_session, 'memory_record_summaries')
    assert isinstance(response_with_session.memory_record_summaries, list)
    
    print(f"Successfully executed retrieve_memory_records with session ID. Found {len(response_with_session.memory_record_summaries)} records")
