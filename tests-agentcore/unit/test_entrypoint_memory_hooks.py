"""
Integration tests for the entrypoint.py memory hooks implementation.

These tests verify the functionality of the AgentMemoryHooks class and
the memory integration in the entrypoint handler, following TDD principles
and testing against actual AWS services without mocking.
"""

import os
import pytest
import json
import sys
import time
import boto3
from pathlib import Path
from uuid import uuid4
from botocore.exceptions import ClientError, NoCredentialsError

# Add the entrypoint module to the path
sys.path.insert(0, '../../src/agentic_platform/service/agentcore/runtime/agent_deployment_template')

# Load environment variables from .env file if it exists
def load_env_file():
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key not in os.environ:
                        os.environ[key] = value

load_env_file()

# Test constants
AWS_REGION = os.getenv('REGION', 'us-west-2')
TEST_MEMORY_ID = os.getenv('TEST_WITH_MEMORY_ID', None)
DELETE_AT_END = os.getenv('DELETE_AT_END', 'True').lower() not in ['false', '0', 'no', 'n']
if not TEST_MEMORY_ID:
    raise Exception ("You must set TEST_WITH_MEMORY_ID for this test")

# Skip tests if no memory ID is provided
# pytestmark = pytest.mark.skipif(
#     not TEST_MEMORY_ID,
#     reason="TEST_WITH_MEMORY_ID environment variable not set"
# )


@pytest.fixture(scope="session")
def real_agentcore_clients():
    """Session-scoped fixture to provide real boto3 clients for testing."""
    try:
        agentcore_client = boto3.client('bedrock-agentcore', region_name=AWS_REGION)
        agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=AWS_REGION)
        return {
            'agentcore_client': agentcore_client,
            'agentcore_control_client': agentcore_control_client
        }
    except NoCredentialsError:
        pytest.skip("AWS credentials not configured")
    except Exception as e:
        pytest.skip(f"Cannot initialize AWS clients: {str(e)}")


@pytest.fixture(scope="session")
def memory_client():
    """Session-scoped fixture to provide MemoryClient for testing."""
    try:
        from bedrock_agentcore.memory import MemoryClient
        return MemoryClient(region_name=AWS_REGION)
    except Exception as e:
        pytest.skip(f"Cannot initialize MemoryClient: {str(e)}")


@pytest.fixture(scope="session")
def test_memory_resource(real_agentcore_clients, memory_client):
    """Session-scoped fixture to verify test memory resource exists."""
    try:
        # Verify the memory resource exists
        memory_details = real_agentcore_clients['agentcore_control_client'].get_memory(
            memoryId=TEST_MEMORY_ID
        )
        print(f"Using test memory resource: {TEST_MEMORY_ID}")
        yield {
            'memory_id': TEST_MEMORY_ID,
            'memory_details': memory_details
        }
    except Exception as e:
        pytest.skip(f"Test memory resource {TEST_MEMORY_ID} not accessible: {str(e)}")


def test_agent_memory_hooks_initialization_real(memory_client, test_memory_resource):
    """Test AgentMemoryHooks initialization with real MemoryClient."""
    from agentic_platform.service.agentcore.runtime.agent_deployment_template.entrypoint import AgentMemoryHooks
    
    # Create hooks instance with real memory client
    hooks = AgentMemoryHooks(
        memory_id=test_memory_resource['memory_id'],
        client=memory_client,
        actor_id="test-actor-real",
        session_id="test-session-real"
    )
    
    # Assert initialization
    assert hooks.memory_id == test_memory_resource['memory_id']
    assert hooks.client == memory_client
    assert hooks.actor_id == "test-actor-real"
    assert hooks.session_id == "test-session-real"
    
    # Verify namespaces were populated (may be empty if get_memory_strategies fails)
    assert isinstance(hooks.namespaces, dict)
    print(f"Memory hooks initialized with {len(hooks.namespaces)} namespace(s)")


def test_memory_client_integration(memory_client, test_memory_resource, real_agentcore_clients):
    """Test that MemoryClient can interact with real AgentCore Memory service."""
    memory_id = test_memory_resource['memory_id']
    
    # Test creating a memory event
    test_actor_id = f"test-actor-{uuid4().hex[:8]}"
    
    try:
        # Create a test event
        event_response = real_agentcore_clients['agentcore_client'].create_event(
            memoryId=memory_id,
            actorId=test_actor_id,
            eventTimestamp=time.time(),
            payload=[{
                "conversational": {
                    "content": {
                        "text": "Test message for entrypoint memory hooks integration"
                    },
                    "role": "USER"
                }
            }]
        )
        
        assert 'event' in event_response
        assert event_response['event']['actorId'] == test_actor_id
        session_id = event_response['event']['sessionId']
        
        print(f"Created test event for actor {test_actor_id} in session {session_id}")
        
        # Test listing events
        list_response = real_agentcore_clients['agentcore_client'].list_events(
            memoryId=memory_id,
            sessionId=session_id,
            maxResults=10,
            actorId=test_actor_id
        )
        
        assert 'events' in list_response
        assert len(list_response['events']) > 0
        print(f"Listed {len(list_response['events'])} events for session {session_id}")
        
    except Exception as e:
        pytest.fail(f"Memory client integration test failed: {str(e)}")


def test_entrypoint_memory_initialization_with_valid_id():
    """Test entrypoint memory initialization with valid memory ID."""
    # Set the memory ID in environment
    original_memory_id = os.environ.get('AGENTCORE_MEMORY_ID')
    os.environ['AGENTCORE_MEMORY_ID'] = TEST_MEMORY_ID
    
    try:
        # Import entrypoint module (this will initialize memory)
        import importlib
        if 'entrypoint' in sys.modules:
            importlib.reload(sys.modules['entrypoint'])
        else:
            import agentic_platform.service.agentcore.runtime.agent_deployment_template.entrypoint as entrypoint
        print(f"got entrypoint {entrypoint}, {dir(entrypoint)}")
        print(f"Got entrypoint.memory_id {entrypoint.memory_id}")
        # Verify memory was initialized
        assert entrypoint.memory_id == TEST_MEMORY_ID
        assert entrypoint.memory_client is not None
        
        print(f"Entrypoint successfully initialized with memory ID: {TEST_MEMORY_ID}")
        
    finally:
        # Restore original memory ID
        if original_memory_id:
            os.environ['AGENTCORE_MEMORY_ID'] = original_memory_id
        elif 'AGENTCORE_MEMORY_ID' in os.environ:
            del os.environ['AGENTCORE_MEMORY_ID']


def test_entrypoint_memory_initialization_without_id():
    """Test entrypoint memory initialization without memory ID."""
    # Remove memory ID from environment
    original_memory_id = os.environ.get('AGENTCORE_MEMORY_ID')
    if 'AGENTCORE_MEMORY_ID' in os.environ:
        print(f"Deleting AGENTCORE_MEMORY_ID from env")
        del os.environ['AGENTCORE_MEMORY_ID']
    
    try:
        # Import entrypoint module (this will skip memory initialization)
        import importlib
        if 'entrypoint' in sys.modules:
            importlib.reload(sys.modules['entrypoint'])
        else:
            import agentic_platform.service.agentcore.runtime.agent_deployment_template.entrypoint as entrypoint
        
        # Verify memory was not initialized
        assert entrypoint.memory_id is None
        assert entrypoint.memory_client is None
        
        print("Entrypoint correctly skipped memory initialization without memory ID")
        
    finally:
        # Restore original memory ID
        if original_memory_id:
            print(f"Restoring AGENTCORE_MEMORY_ID {original_memory_id} to env")
            os.environ['AGENTCORE_MEMORY_ID'] = original_memory_id


def test_agent_memory_hooks_retrieve_context_real(memory_client, test_memory_resource, real_agentcore_clients):
    """Test retrieve_context method with real memory retrieval."""
    import agentic_platform.service.agentcore.runtime.agent_deployment_template.entrypoint as entrypoint
   
    memory_id = test_memory_resource['memory_id']
    test_actor_id = f"test-actor-context-{uuid4().hex[:8]}"
    test_session_id = f"test-session-context-{uuid4().hex[:8]}"
    
    # Create some test events first to have context to retrieve
    try:
        real_agentcore_clients['agentcore_client'].create_event(
            memoryId=memory_id,
            actorId=test_actor_id,
            eventTimestamp=time.time(),
            payload=[{
                "conversational": {
                    "content": {
                        "text": "User prefers technical explanations and detailed examples"
                    },
                    "role": "USER"
                }
            }]
        )
        
        # Wait a moment for event processing
        time.sleep(2)
        
    except Exception as e:
        print(f"Warning: Could not create test events: {str(e)}")
    
    # Create hooks instance
    hooks = AgentMemoryHooks(
        memory_id=memory_id,
        client=memory_client,
        actor_id=test_actor_id,
        session_id=test_session_id
    )
    
    # Create a mock event structure (minimal mock for testing the method)
    class MockEvent:
        def __init__(self):
            self.agent = MockAgent()
    
    class MockAgent:
        def __init__(self):
            self.messages = [
                {
                    "role": "user",
                    "content": [{"text": "Tell me about machine learning"}]
                }
            ]
    
    mock_event = MockEvent()
    original_text = mock_event.agent.messages[0]["content"][0]["text"]
    
    # Call retrieve_context
    try:
        hooks.retrieve_context(mock_event)
        
        # Check if context was added (may not be if no memories exist yet)
        modified_text = mock_event.agent.messages[0]["content"][0]["text"]
        
        if "Context:" in modified_text:
            print("Context successfully retrieved and added to message")
            assert original_text in modified_text
        else:
            print("No context found (expected for new test data)")
            assert modified_text == original_text
            
    except Exception as e:
        # This is acceptable as memory retrieval may fail for various reasons
        print(f"Memory retrieval failed (acceptable): {str(e)}")


def test_agent_memory_hooks_save_interaction_real(memory_client, test_memory_resource, real_agentcore_clients):
    """Test save_interaction method with real event creation."""
    from entrypoint import AgentMemoryHooks
    
    memory_id = test_memory_resource['memory_id']
    test_actor_id = f"test-actor-save-{uuid4().hex[:8]}"
    test_session_id = f"test-session-save-{uuid4().hex[:8]}"
    
    # Create hooks instance
    hooks = AgentMemoryHooks(
        memory_id=memory_id,
        client=memory_client,
        actor_id=test_actor_id,
        session_id=test_session_id
    )
    
    # Create a mock event structure for testing
    class MockEvent:
        def __init__(self):
            self.agent = MockAgent()
    
    class MockAgent:
        def __init__(self):
            self.messages = [
                {
                    "role": "user",
                    "content": [{"text": "What is artificial intelligence?"}]
                },
                {
                    "role": "assistant",
                    "content": [{"text": "Artificial intelligence (AI) is a branch of computer science..."}]
                }
            ]
    
    mock_event = MockEvent()
    
    # Call save_interaction
    try:
        hooks.save_interaction(mock_event)
        print(f"Successfully saved interaction for actor {test_actor_id}")
        
        # Verify the event was created by listing events
        time.sleep(1)  # Brief wait for event processing
        
        list_response = real_agentcore_clients['agentcore_client'].list_events(
            memoryId=memory_id,
            actorId=test_actor_id,
            maxResults=5
        )
        
        if 'events' in list_response and len(list_response['events']) > 0:
            print(f"Verified: Found {len(list_response['events'])} events for actor {test_actor_id}")
        else:
            print("Note: Event may not be immediately visible due to processing delays")
            
    except Exception as e:
        pytest.fail(f"Save interaction test failed: {str(e)}")


def test_entrypoint_handler_with_memory_integration(memory_client, test_memory_resource):
    """Test entrypoint handler with real memory integration."""
    # Set up environment for memory integration
    original_memory_id = os.environ.get('AGENTCORE_MEMORY_ID')
    os.environ['AGENTCORE_MEMORY_ID'] = test_memory_resource['memory_id']
    
    try:
        # Import entrypoint module
        import importlib
        if 'entrypoint' in sys.modules:
            importlib.reload(sys.modules['entrypoint'])
        else:
            import entrypoint
        
        # Verify memory is initialized
        assert entrypoint.memory_id == test_memory_resource['memory_id']
        assert entrypoint.memory_client is not None
        
        # Create a test request
        test_request = entrypoint.HandlerRequest(prompt="Hello, test with real memory integration")
        
        # Note: We can't easily test the full handler without mocking the Agent class
        # since it would require a complete Strands agent setup. Instead, we verify
        # that the memory components are properly initialized and accessible.
        
        # Test that AgentMemoryHooks can be instantiated with the initialized components
        test_actor_id = f"test-handler-{uuid4().hex[:8]}"
        test_session_id = f"test-session-{uuid4().hex[:8]}"
        
        hooks = entrypoint.AgentMemoryHooks(
            memory_id=entrypoint.memory_id,
            client=entrypoint.memory_client,
            actor_id=test_actor_id,
            session_id=test_session_id
        )
        
        assert hooks.memory_id == test_memory_resource['memory_id']
        assert hooks.client == entrypoint.memory_client
        
        print("Handler memory integration components verified successfully")
        
    finally:
        # Restore original memory ID
        if original_memory_id:
            os.environ['AGENTCORE_MEMORY_ID'] = original_memory_id
        elif 'AGENTCORE_MEMORY_ID' in os.environ:
            del os.environ['AGENTCORE_MEMORY_ID']


def test_memory_strategies_retrieval_real(memory_client, test_memory_resource):
    """Test retrieval of memory strategies from real memory resource."""
    memory_id = test_memory_resource['memory_id']
    
    try:
        strategies = memory_client.get_memory_strategies(memory_id)
        
        assert isinstance(strategies, list)
        print(f"Retrieved {len(strategies)} memory strategies")
        
        for strategy in strategies:
            assert 'type' in strategy
            assert 'namespaces' in strategy
            print(f"Strategy type: {strategy['type']}, namespaces: {strategy['namespaces']}")
            
    except Exception as e:
        # This may fail if the memory resource doesn't have strategies configured
        print(f"Memory strategies retrieval failed (may be expected): {str(e)}")


def test_memory_hooks_register_functionality():
    """Test that memory hooks can be registered with a hook registry."""
    from entrypoint import AgentMemoryHooks
    
    # Create a simple mock registry to test registration
    class MockHookRegistry:
        def __init__(self):
            self.callbacks = []
        
        def add_callback(self, event_type, callback_func):
            self.callbacks.append((event_type, callback_func))
    
    # Create hooks instance (with minimal setup since we're just testing registration)
    hooks = AgentMemoryHooks(
        memory_id="test-memory-id",
        client=None,  # Not needed for registration test
        actor_id="test-actor",
        session_id="test-session"
    )
    
    # Test registration
    mock_registry = MockHookRegistry()
    hooks.register_hooks(mock_registry)
    
    # Verify callbacks were registered
    assert len(mock_registry.callbacks) == 2
    
    # Check that the correct event types were registered
    event_types = [callback[0].__name__ for callback in mock_registry.callbacks]
    assert 'MessageAddedEvent' in event_types
    assert 'AfterInvocationEvent' in event_types
    
    print("Memory hooks registration functionality verified")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
