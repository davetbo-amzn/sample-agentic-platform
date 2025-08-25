"""
Integration tests for the invoke_agentcore_runtime function.

These tests verify the functionality of the invoke_agentcore_runtime method
using real AWS API calls to ensure proper behavior with actual AWS services.

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
from pathlib import Path
import logging

import sys
import os
sys.path.insert(0, '../src')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../script'))
# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from agentic_platform.service.agentcore.runtime.client.agentcore_runtime_client import AgentCoreRuntimeClient
try:
    from get_auth_token import get_token
except ImportError:
    try:
        # Try absolute import from the script directory
        script_dir = os.path.join(os.path.dirname(__file__), '../script')
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        from get_auth_token import get_token
    except ImportError as e:
        logging.error("Warning: Could not import get_auth_token, JWT authentication may not work")
        raise e
        get_token = None

from agentic_platform.service.agentcore.types import (
    InvokeAgentRuntimeRequest,
    InvokeAgentRuntimeResponse,
    CreateAgentRuntimeRequest,
    DeleteAgentRuntimeRequest,
    GetAgentRuntimeRequest,
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
    
    # Generate JWT token if Cognito credentials are available and get_token function is available
    if get_token and all([os.getenv('COGNITO_CLIENT_ID'), os.getenv('COGNITO_USERNAME'), os.getenv('COGNITO_PASSWORD')]):
        try:
            # Only generate token if JWT_TOKEN is not already set
            if not os.getenv('JWT_TOKEN'):
                logging.info("Generating JWT token for AgentCore authentication...")
                token = get_token(
                    client_id=os.getenv('COGNITO_CLIENT_ID'),
                    username=os.getenv('COGNITO_USERNAME'),
                    password=os.getenv('COGNITO_PASSWORD')
                )
                os.environ['JWT_TOKEN'] = token
                logging.info("JWT token generated successfully for tests")
        except Exception as e:
            logging.error(f"Warning: Could not generate JWT token: {e}")
            raise e
        
# Load .env file at module import time
load_env_file()

# Test constants
TEST_RUNTIME_NAME_PREFIX = "test_invoke_runtime"
AWS_REGION = os.getenv('REGION', 'us-west-2')

# Environment variables for testing
RUNTIME_ID = os.getenv('TEST_WITH_RUNTIME_ID', None)
TEST_CONTAINER_URI = os.getenv('TEST_CONTAINER_URI', None)
TEST_ROLE_ARN = os.getenv('TEST_ROLE_ARN', None)
USER_POOL_ID = os.getenv('USER_POOL_ID', None) 
USER_POOL_CLIENT_ID = os.getenv('USER_POOL_CLIENT_ID', None)
TEST_DISCOVERY_URL = f"https://cognito-idp.us-west-2.amazonaws.com/{USER_POOL_ID}/.well-known/openid-configuration"

# Check if we have the required infrastructure for creating new runtimes
INFRASTRUCTURE_AVAILABLE = TEST_CONTAINER_URI is not None and TEST_ROLE_ARN is not None

logging.info(f"Infrastructure available for runtime creation: {INFRASTRUCTURE_AVAILABLE}")
logging.info(f"Using runtime ID from env: {RUNTIME_ID}")



@pytest.fixture(scope="session")
def real_agentcore_clients():
    """Session-scoped fixture to provide real boto3 clients for testing."""
    try:
        agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=AWS_REGION)
        agentcore_data_client = boto3.client('bedrock-agentcore', region_name=AWS_REGION)
        return {
            'control_client': agentcore_control_client,
            'data_client': agentcore_data_client
        }
    except Exception as e:
       raise e


@pytest.fixture(scope="session")
def env_setup():
    """Session-scoped fixture to set up environment variables for tests."""
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
def active_runtime(real_agentcore_clients, env_setup):
    """Session-scoped fixture to provide an active runtime for invoke tests."""
    control_client = real_agentcore_clients['control_client']
    created_runtime_id = None
    
    try:
        if RUNTIME_ID:
            # Use existing runtime
            logging.info(f"Using existing runtime ID: {RUNTIME_ID}")
            # Verify it exists and is active
            try:
                response = control_client.get_agent_runtime(agentRuntimeId=RUNTIME_ID)
                runtime_arn = response.get('agentRuntimeArn') or response.get('agentRuntime', {}).get('agentRuntimeArn')
                if not runtime_arn:
                    raise Exception("Failed to get agentRuntimeArn.")
                
                yield {
                    'id': RUNTIME_ID,
                    'arn': runtime_arn
                }
                return
            except Exception as e:
                raise e
        
        if not INFRASTRUCTURE_AVAILABLE:
            raise Exception("No runtime ID provided and infrastructure not available for creating new runtime")
        
        # Create a new runtime for testing
        test_runtime_name = f"{TEST_RUNTIME_NAME_PREFIX}_{int(time.time())}"
        
        # Create using the new from_text strategy
        sample_agent_code = '''
def handler(event, context):
    """Simple test agent handler for invoke tests."""
    return {
        "statusCode": 200,
        "body": {
            "message": "Hello from invoke test agent",
            "event": event,
            "test_mode": "invoke_integration"
        }
    }
'''
        
        sample_requirements = '''
boto3==1.34.0
requests==2.31.0
'''
        
        create_request = CreateAgentRuntimeRequest(
            agentCode=sample_agent_code,
            requirements=sample_requirements,
            agentRoleArnrn=TEST_ROLE_ARN
        )
        
        created_runtime_id = AgentCoreRuntimeClient.create_agentcore_runtime(create_request)
        logging.info(f"Created test runtime with ID: {created_runtime_id}")
        
        # Wait for runtime to be ready
        _wait_for_runtime_active(control_client, created_runtime_id)
        
        # Get the runtime ARN
        runtime_details = AgentCoreRuntimeClient.get_agentcore_runtime(
            GetAgentRuntimeRequest(agentRuntimeId=created_runtime_id)
        )
        
        yield {
            'id': created_runtime_id,
            'arn': runtime_details.agentRuntimeArn
        }
        
    except Exception as e:
        if "already exists" in str(e).lower():
            # Try to find existing runtime
            try:
                list_response = AgentCoreRuntimeClient.list_agent_runtimes(
                    ListAgentRuntimesRequest(maxResults=100)
                )
                for runtime in list_response.runtimes:
                    if runtime['agent_runtime_name'].startswith(TEST_RUNTIME_NAME_PREFIX):
                        yield {
                            'id': runtime['agentRuntimeId'],
                            'arn': runtime.get('agentRuntimeArn', f"arn:aws:bedrock-agentcore:{AWS_REGION}:123456789012:agent-runtime/{runtime['agentRuntimeId']}")
                        }
                        return
                pytest.skip("Cannot find existing runtime to use")
            except Exception as list_error:
                raise Exception(f"Cannot create or find runtime: {str(list_error)}")
        else:
            raise Exception(f"Cannot create runtime for invoke tests: {str(e)}")
    
    # finally:
    #     # Cleanup created runtime
    #     if created_runtime_id:
    #         try:
    #             delete_request = DeleteAgentRuntimeRequest(agentRuntimeId=created_runtime_id)
    #             AgentCoreRuntimeClient.delete_agentcore_runtime(delete_request)
    #             logging.info(f"Cleaned up test runtime: {created_runtime_id}")
    #         except Exception as e:
    #             raise Exception(f"Failed to cleanup runtime {created_runtime_id}: {str(e)}")


def _wait_for_runtime_active(client, agentRuntimeId, max_wait_time=300):
    """Helper function to wait for runtime to become active."""
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        try:
            response = client.get_agent_runtime(agentRuntimeId=agentRuntimeId)
            
            # Handle potential variations in response structure
            if 'agentRuntime' in response:
                status = response['agentRuntime']['status']
            elif 'status' in response:
                status = response['status']
            else:
                available_keys = list(response.keys())
                logging.warning(f"Unexpected response structure. Available keys: {available_keys}")
                raise KeyError(f"Expected 'agentRuntime' or 'status' in response")
            
            if status == 'READY':
                return response
            elif status in ['FAILED', 'STOPPED']:
                raise Exception(f"Runtime failed to become active. Status: {status}")
            
            logging.info(f"Runtime {agentRuntimeId} status: {status}, waiting...")
            time.sleep(10)
            
        except Exception as e:
            if "not found" in str(e).lower():
                raise Exception(f"Runtime {agentRuntimeId} not found")
            logging.error(f"Error waiting for runtime {agentRuntimeId}: {str(e)}")
            if "ConflictException" in str(e) or "while it's" in str(e):
                logging.info("Runtime in transitional state, continuing to wait...")
                time.sleep(30)
                continue
            raise e
    
    raise Exception(f"Runtime {agentRuntimeId} did not become active within {max_wait_time} seconds")


class TestInvokeAgentCoreRuntimeIntegration:
    """Integration test suite for the invoke_agentcore_runtime method."""

    def test_invoke_agentcore_runtime_minimal_parameters(self, active_runtime, real_agentcore_clients, env_setup):
        """Test invoke_agentcore_runtime with minimal required parameters using real AWS services."""
        # Arrange
        test_payload = {"message": "Hello, agent!", "test_type": "minimal_parameters"}
        
        request = InvokeAgentRuntimeRequest(
            agentRuntimeArn=active_runtime['arn'],
            payload=test_payload
        )
        logger.info(f"Sending InvokeAgentRuntimeRequest {request}")
        # Act
        response = AgentCoreRuntimeClient.invoke_agentcore_runtime(request)
        
        # Assert
        assert isinstance(response, InvokeAgentRuntimeResponse)
        assert response.statusCode == 200
        assert response.contentType == 'application/json'
        assert response.response is not None  # StreamingBody should be present
        logging.info(f"Successfully invoked runtime with minimal parameters. Status: {response.statusCode}")

    def test_invoke_agentcore_runtime_with_optional_parameters(self, active_runtime, real_agentcore_clients, env_setup):
        """Test invoke_agentcore_runtime with optional parameters using real AWS services."""
        # Arrange
        test_payload = {"message": "Hello with options!", "test_type": "optional_parameters"}
        
        request = InvokeAgentRuntimeRequest(
            agentRuntimeArn=active_runtime['arn'],
            payload=test_payload,
            contentType='application/json',
            accept='application/json',
            runtimeUserId='test-user-123',
            mcpSessionId='test-session-456',
            mcpProtocolVersion='1.0'
        )
        
        # Act
        response = AgentCoreRuntimeClient.invoke_agentcore_runtime(request)
        
        # Assert
        assert isinstance(response, InvokeAgentRuntimeResponse)
        assert response.statusCode == 200
        assert response.contentType == 'application/json'
        assert response.response is not None
        logging.info(f"Successfully invoked runtime with optional parameters. Status: {response.statusCode}")

    def test_invoke_agentcore_runtime_complex_payload(self, active_runtime, real_agentcore_clients, env_setup):
        """Test invoke_agentcore_runtime with complex nested payload using real AWS services."""
        # Arrange
        test_payload = {
            "action": "process_document",
            "parameters": {
                "document_id": "doc-integration-test",
                "processing_options": {
                    "extract_entities": True,
                    "sentiment_analysis": False,
                    "confidence_threshold": 0.8
                },
                "output_format": "json",
                "metadata": {
                    "user_id": "integration-test-user",
                    "session_id": "integration-test-session",
                    "timestamp": datetime.now().isoformat()
                }
            },
            "test_type": "complex_payload"
        }
        
        request = InvokeAgentRuntimeRequest(
            agentRuntimeArn=active_runtime['arn'],
            payload=test_payload
        )
        
        # Act
        response = AgentCoreRuntimeClient.invoke_agentcore_runtime(request)
        
        # Assert
        assert isinstance(response, InvokeAgentRuntimeResponse)
        assert response.statusCode == 200
        assert response.response is not None
        logging.info(f"Successfully invoked runtime with complex payload. Status: {response.statusCode}")

    def test_invoke_agentcore_runtime_empty_payload(self, active_runtime, real_agentcore_clients, env_setup):
        """Test invoke_agentcore_runtime with empty payload using real AWS services."""
        # Arrange
        test_payload = {}
        
        request = InvokeAgentRuntimeRequest(
            agentRuntimeArn=active_runtime['arn'],
            payload=test_payload
        )
        
        # Act
        response = AgentCoreRuntimeClient.invoke_agentcore_runtime(request)
        
        # Assert
        assert isinstance(response, InvokeAgentRuntimeResponse)
        assert response.statusCode == 200
        assert response.response is not None
        logging.info(f"Successfully invoked runtime with empty payload. Status: {response.statusCode}")

    def test_invoke_agentcore_runtime_unicode_payload(self, active_runtime, real_agentcore_clients, env_setup):
        """Test invoke_agentcore_runtime with Unicode characters in payload using real AWS services."""
        # Arrange
        test_payload = {
            "message": "Hello with unicode: é, 中文, 🚀, русский",
            "emoji_test": "😀😁😂🤣😃😄😅😆😉😊",
            "multilingual": {
                "english": "Hello World",
                "spanish": "Hola Mundo", 
                "chinese": "你好世界",
                "japanese": "こんにちは世界",
                "arabic": "مرحبا بالعالم"
            },
            "test_type": "unicode_payload"
        }
        
        request = InvokeAgentRuntimeRequest(
            agentRuntimeArn=active_runtime['arn'],
            payload=test_payload
        )
        
        # Act
        response = AgentCoreRuntimeClient.invoke_agentcore_runtime(request)
        
        # Assert
        assert isinstance(response, InvokeAgentRuntimeResponse)
        assert response.statusCode == 200
        assert response.response is not None
        logging.info(f"Successfully invoked runtime with Unicode payload. Status: {response.statusCode}")

    def test_invoke_agentcore_runtime_invalid_arn_error(self, real_agentcore_clients, env_setup):
        """Test invoke_agentcore_runtime with invalid ARN to verify error handling."""
        # Arrange
        invalid_arn = "arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/invalid-runtime-id"
        test_payload = {"message": "This should fail", "test_type": "invalid_arn"}
        
        request = InvokeAgentRuntimeRequest(
            agentRuntimeArn=invalid_arn,
            payload=test_payload
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            AgentCoreRuntimeClient.invoke_agentcore_runtime(request)
        
        # Verify we got an appropriate error
        error_str = str(exc_info.value)
        assert "not found" in error_str.lower() or "invalid" in error_str.lower() or "does not exist" in error_str.lower()
        logging.info(f"Successfully caught expected error for invalid ARN: {error_str}")

    def test_invoke_agentcore_runtime_different_content_types(self, active_runtime, real_agentcore_clients, env_setup):  
        """Test invoke_agentcore_runtime with different content types using real AWS services."""
        # Test with text/plain content type
        test_payload = {"message": "Testing content type", "test_type": "content_type_test"}
        
        request = InvokeAgentRuntimeRequest(
            agentRuntimeArn=active_runtime['arn'],
            payload=test_payload,
            contentType='text/plain',
            accept='text/plain'
        )
        
        # Act
        response = AgentCoreRuntimeClient.invoke_agentcore_runtime(request)
        
        # Assert
        assert isinstance(response, InvokeAgentRuntimeResponse)
        assert response.statusCode == 200
        assert response.response is not None
        logging.info(f"Successfully invoked runtime with text/plain content type. Status: {response.statusCode}")

    def test_invoke_agentcore_runtime_with_tracing_headers(self, active_runtime, real_agentcore_clients, env_setup):
        """Test invoke_agentcore_runtime with tracing headers using real AWS services."""
        # Arrange
        test_payload = {"message": "Testing with tracing", "test_type": "tracing_headers"}
        
        request = InvokeAgentRuntimeRequest(
            agentRuntimeArn=active_runtime['arn'],
            payload=test_payload,
            traceId='test-trace-123',
            traceParent='00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
            traceState='test-state=active',
            baggage='test-baggage=value1'
        )
        
        # Act
        response = AgentCoreRuntimeClient.invoke_agentcore_runtime(request)
        
        # Assert
        assert isinstance(response, InvokeAgentRuntimeResponse)
        assert response.statusCode == 200
        assert response.response is not None
        logging.info(f"Successfully invoked runtime with tracing headers. Status: {response.statusCode}")

    def test_invoke_agentcore_runtime_large_payload(self, active_runtime, real_agentcore_clients, env_setup):
        """Test invoke_agentcore_runtime with a large payload using real AWS services."""
        # Arrange - Create a reasonably large payload (but not too large to avoid timeout)
        large_data = {
            "test_type": "large_payload",
            "data_array": [{"item": i, "description": f"This is item number {i} with some descriptive text"} for i in range(100)],
            "large_text": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 50,
            "nested_structure": {
                "level1": {
                    "level2": {
                        "level3": {
                            "items": [f"nested_item_{i}" for i in range(50)]
                        }
                    }
                }
            }
        }
        
        request = InvokeAgentRuntimeRequest(
            agentRuntimeArn=active_runtime['arn'],
            payload=large_data
        )
        
        # Act
        response = AgentCoreRuntimeClient.invoke_agentcore_runtime(request)
        
        # Assert
        assert isinstance(response, InvokeAgentRuntimeResponse)
        assert response.statusCode == 200
        assert response.response is not None
        logging.info(f"Successfully invoked runtime with large payload. Status: {response.statusCode}")
