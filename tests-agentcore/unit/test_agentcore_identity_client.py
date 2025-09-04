"""
Unit tests for the AgentCoreIdentityClient and AgentCoreIdentityController classes.

These tests verify the functionality of the AgentCore Identity components
that manage OAuth2 credential providers and other identity resources.

All tests make real API calls to AWS Bedrock AgentCore services without mocking,
following TDD principles and testing against actual services.
"""

import os
import pytest
import boto3
import time
import json
from datetime import datetime, timezone
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path
from uuid import uuid4

import sys
sys.path.insert(0, '../../src')

from agentic_platform.service.agentcore.identity.client.agentcore_identity_client import AgentCoreIdentityClient
from agentic_platform.service.agentcore.identity.api.agentcore_identity_controller import AgentCoreIdentityController
from agentic_platform.service.agentcore.types import (
    # OAuth2 Credential Provider types
    OAuth2CredentialProvider,
    OAuth2CredentialProviderStatus,
    # OAuth2CredentialProviderOperation,
    # OAuth2CredentialProviderRequest,
    # OAuth2CredentialProviderResponse,
    CreateOauth2CredentialProviderRequest,
    CreateOauth2CredentialProviderResponse,
    DeleteOauth2CredentialProviderRequest,
    DeleteOauth2CredentialProviderResponse,
    GetOauth2CredentialProviderRequest,
    GetOauth2CredentialProviderResponse,
    ListOauth2CredentialProvidersRequest,
    ListOauth2CredentialProvidersResponse,
    UpdateOauth2CredentialProviderRequest,
    UpdateOauth2CredentialProviderResponse,
    GoogleOAuth2Config,
)

# Load environment variables from .env file if it exists
def load_env_file():
    env_file = Path(__file__).parent.parent / '.env'
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
TEST_PROVIDER_NAME_PREFIX = "test_oauth2_provider"
AWS_REGION = os.getenv('REGION', 'us-west-2')
DELETE_AT_END = os.getenv('DELETE_AT_END', 'True').lower() not in ['false', '0', 'no', 'n']


class TestAgentCoreIdentityController:
    """Real API tests for AgentCoreIdentityController class - no mocking."""

    def test_handler_invalid_operation(self):
        """Test handler with invalid operation."""
        # Arrange
        event = {
            'operation': 'INVALID_OPERATION',
            'input': {}
        }
        context = {}
        
        print("Testing handler with invalid operation...")
        print(f"Input event: {json.dumps(event, indent=2)}")
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            result = AgentCoreIdentityController.handler(event, context)
        
        # The actual validation error will mention the valid enum values
        error_msg = str(exc_info.value)
        print(f"Expected validation error received: {error_msg}")
        assert "validation error" in error_msg.lower()


class TestAgentCoreIdentityClientRealAPI:
    """Real API tests for AgentCoreIdentityClient class - no mocking."""

    def test_list_oauth2_credential_providers_real(self, real_agentcore_control_client, env_setup):
        """Test real listing of OAuth2 credential providers."""
        if not real_agentcore_control_client:
            pytest.fail("Real AWS client not available - ensure AWS credentials are configured")
        
        print("=== Testing real list_oauth2_credential_providers ===")
        
        # Arrange
        request = ListOauth2CredentialProvidersRequest(max_results=20)
        print(f"Request parameters: max_results={request.max_results}")
        
        # Act
        print("Making real API call to list OAuth2 credential providers...")
        result = AgentCoreIdentityClient.list_oauth2_credential_providers(request)
        
        # Print full response details
        print(f"API Response received:")
        print(f"  - Number of providers found: {len(result.oauth2_credential_providers)}")
        print(f"  - Next token: {result.next_token}")
        
        for i, provider in enumerate(result.oauth2_credential_providers):
            print(f"  - Provider {i+1}:")
            print(f"    * ARN: {provider.arn}")
            print(f"    * ID: {provider.credential_provider_id}")
            print(f"    * Name: {provider.name}")
            print(f"    * Provider Type: {provider.provider_type}")
            print(f"    * Status: {provider.status}")
            print(f"    * Scopes: {provider.scopes}")
            print(f"    * Created At: {provider.created_at}")
            print(f"    * Last Updated At: {provider.last_updated_at}")
        
        # Assert
        assert result is not None
        assert result.oauth2_credential_providers is not None
        assert isinstance(result.oauth2_credential_providers, list)
        
        print(f"✓ List OAuth2 providers test completed successfully")

    def test_create_and_delete_oauth2_provider_real(self, real_agentcore_control_client, env_setup):
        """Test real creation and deletion of OAuth2 credential provider."""
        if not real_agentcore_control_client:
            pytest.fail("Real AWS client not available - ensure AWS credentials are configured")
        
        print("=== Testing real create and delete OAuth2 credential provider ===")
        
        # Arrange
        unique_suffix = uuid4().hex[-6:]
        provider_name = f"{TEST_PROVIDER_NAME_PREFIX}_real_test_{unique_suffix}"
        
        create_request = CreateOauth2CredentialProviderRequest(
            name=provider_name,
            provider_type='google',
            scopes=['openid', 'email'],
            google_config=GoogleOAuth2Config(
                client_id='test-client-id-real',
                client_secret='test-client-secret-real'
            )
        )
        
        print(f"Create request parameters:")
        print(f"  - name: {create_request.name}")
        print(f"  - provider_type: {create_request.provider_type}")
        print(f"  - scopes: {create_request.scopes}")
        print(f"  - google_config.client_id: {create_request.google_config.client_id}")
        print(f"  - google_config.client_secret: {create_request.google_config.client_secret}")
        
        provider_id = None
        try:
            # Act - Create
            print("Making real API call to create OAuth2 credential provider...")
            create_response = AgentCoreIdentityClient.create_oauth2_credential_provider(create_request)
            provider_id = create_response.credential_provider_id
            
            # Print full create response details
            print(f"Create API Response:")
            print(f"  - ARN: {create_response.arn}")
            print(f"  - Provider ID: {create_response.credential_provider_id}")
            print(f"  - Name: {create_response.name}")
            print(f"  - Provider Type: {create_response.provider_type}")
            print(f"  - Status: {create_response.status}")
            print(f"  - Scopes: {create_response.scopes}")
            print(f"  - Created At: {create_response.created_at}")
            
            # Assert create response
            assert create_response.credential_provider_id is not None
            assert create_response.name == provider_name
            assert create_response.provider_type == 'GoogleOauth2'
            assert create_response.scopes == ['openid', 'email']
            assert create_response.status in [OAuth2CredentialProviderStatus.CREATING, OAuth2CredentialProviderStatus.READY]
            
            print(f"✓ OAuth2 provider created successfully: {provider_id}")
            
            # Test Get
            print("Making real API call to get OAuth2 credential provider...")
            get_request = GetOauth2CredentialProviderRequest(
                credential_provider_id=provider_id
            )
            get_response = AgentCoreIdentityClient.get_oauth2_credential_provider(get_request)
            
            # Print full get response details
            print(f"Get API Response:")
            print(f"  - ARN: {get_response.arn}")
            print(f"  - Provider ID: {get_response.credential_provider_id}")
            print(f"  - Name: {get_response.name}")
            print(f"  - Provider Type: {get_response.provider_type}")
            print(f"  - Status: {get_response.status}")
            print(f"  - Scopes: {get_response.scopes}")
            print(f"  - Created At: {get_response.created_at}")
            print(f"  - Last Updated At: {get_response.last_updated_at}")
            
            # Assert get response
            assert get_response.credential_provider_id == provider_id
            assert get_response.name == provider_name
            assert get_response.provider_type == 'GoogleOauth2'
            assert get_response.scopes is not None
            assert get_response.created_at is not None
            
            print(f"✓ OAuth2 provider retrieved successfully: {provider_id}")
            
        finally:
            # Cleanup - Delete
            if provider_id and DELETE_AT_END:
                try:
                    print("Making real API call to delete OAuth2 credential provider...")
                    delete_request = DeleteOauth2CredentialProviderRequest(
                        credential_provider_id=provider_id
                    )
                    delete_response = AgentCoreIdentityClient.delete_oauth2_credential_provider(delete_request)
                    
                    # Print full delete response details
                    print(f"Delete API Response:")
                    print(f"  - Status: {delete_response.status}")
                    
                    # Assert delete response
                    assert delete_response.status == OAuth2CredentialProviderStatus.DELETING
                    
                    print(f"✓ OAuth2 provider deleted successfully: {provider_id}")
                except Exception as e:
                    print(f"Failed to cleanup provider {provider_id}: {str(e)}")

    def test_get_nonexistent_oauth2_provider_real(self, real_agentcore_control_client, env_setup):
        """Test real get of non-existent OAuth2 credential provider."""
        if not real_agentcore_control_client:
            pytest.fail("Real AWS client not available - ensure AWS credentials are configured")
        
        print("=== Testing real get non-existent OAuth2 credential provider ===")
        
        # Arrange
        fake_provider_id = f"nonexistent-{uuid4().hex[-8:]}"
        request = GetOauth2CredentialProviderRequest(
            credential_provider_id=fake_provider_id
        )
        
        print(f"Request parameters:")
        print(f"  - credential_provider_id: {request.credential_provider_id}")
        
        # Act & Assert
        print("Making real API call to get non-existent OAuth2 credential provider...")
        with pytest.raises(Exception) as exc_info:
            AgentCoreIdentityClient.get_oauth2_credential_provider(request)
        
        error_msg = str(exc_info.value)
        print(f"Expected error received: {error_msg}")
        
        # Verify it's the right kind of error (should be ResourceNotFoundException or similar)
        assert "not found" in error_msg.lower() or "ResourceNotFoundException" in error_msg
        
        print(f"✓ Non-existent provider error test completed successfully")


@pytest.fixture(scope="session")
def real_agentcore_control_client():
    """Session-scoped fixture to provide real boto3 client for integration testing."""
    try:
        agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=AWS_REGION)
        return agentcore_control_client
    except NoCredentialsError:
        # Return None instead of skipping - tests should handle this
        return None


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


@pytest.fixture
def test_oauth2_provider(real_agentcore_control_client, env_setup):
    """Fixture to create a test OAuth2 credential provider for integration tests."""
    if not real_agentcore_control_client:
        # Return None instead of skipping - tests should handle this
        return None
    
    # Create a test provider
    unique_suffix = uuid4().hex[-6:]
    provider_name = f"{TEST_PROVIDER_NAME_PREFIX}_{unique_suffix}"
    
    create_request = CreateOauth2CredentialProviderRequest(
        name=provider_name,
        provider_type='google',
        scopes=['openid', 'email'],
        google_config=GoogleOAuth2Config(
            client_id='test-client-id',
            client_secret='test-client-secret'
        )
    )
    
    try:
        response = AgentCoreIdentityClient.create_oauth2_credential_provider(create_request)
        provider_id = response.credential_provider_id
        
        # Wait for provider to be ready (if needed)
        # Note: This might not be necessary for credential providers
        
        yield response
        
    except Exception as e:
        # Fail the test instead of skipping
        pytest.fail(f"Failed to create test OAuth2 provider: {e}")
    
    finally:
        # Cleanup
        if DELETE_AT_END and 'provider_id' in locals():
            try:
                delete_request = DeleteOauth2CredentialProviderRequest(
                    credential_provider_id=provider_id
                )
                AgentCoreIdentityClient.delete_oauth2_credential_provider(delete_request)
                print(f"Cleaned up test OAuth2 provider: {provider_id}")
            except Exception as e:
                print(f"Failed to cleanup test provider {provider_id}: {str(e)}")


class TestAgentCoreIdentityClientIntegration:
    """Integration tests for AgentCoreIdentityClient with real AWS API calls and detailed response printing."""

    @pytest.mark.integration
    def test_create_oauth2_provider_integration(self, real_agentcore_control_client, env_setup):
        """Integration test for creating an OAuth2 credential provider."""
        if not real_agentcore_control_client:
            pytest.fail("Real AWS client not available - ensure AWS credentials are configured")
        
        print("=== Integration Test: Create OAuth2 Provider ===")
        
        # Arrange
        unique_suffix = uuid4().hex[-6:]
        provider_name = f"{TEST_PROVIDER_NAME_PREFIX}_create_{unique_suffix}"
        
        create_request = CreateOauth2CredentialProviderRequest(
            name=provider_name,
            provider_type='google',
            scopes=['openid', 'email'],
            google_config=GoogleOAuth2Config(
                client_id='test-client-id',
                client_secret='test-client-secret'
            )
        )
        
        print(f"Create request parameters:")
        print(f"  - name: {create_request.name}")
        print(f"  - provider_type: {create_request.provider_type}")
        print(f"  - scopes: {create_request.scopes}")
        print(f"  - google_config.client_id: {create_request.google_config.client_id}")
        print(f"  - google_config.client_secret: {create_request.google_config.client_secret}")
        
        provider_id = None
        try:
            # Act
            print("Making real API call to create OAuth2 credential provider...")
            response = AgentCoreIdentityClient.create_oauth2_credential_provider(create_request)
            provider_id = response.credential_provider_id
            
            # Print full response details
            print(f"Integration Test Create API Response:")
            print(f"  - ARN: {response.arn}")
            print(f"  - Provider ID: {response.credential_provider_id}")
            print(f"  - Name: {response.name}")
            print(f"  - Provider Type: {response.provider_type}")
            print(f"  - Status: {response.status}")
            print(f"  - Scopes: {response.scopes}")
            print(f"  - Created At: {response.created_at}")
            
            # Assert
            assert response.credential_provider_id is not None
            assert response.name == provider_name
            assert response.provider_type == 'GoogleOauth2'
            assert response.scopes == ['openid', 'email']
            assert response.status in [OAuth2CredentialProviderStatus.CREATING, OAuth2CredentialProviderStatus.READY]
            
            print(f"✓ Integration test: OAuth2 provider created successfully: {provider_id}")
            
        finally:
            # Cleanup
            if provider_id and DELETE_AT_END:
                try:
                    print("Making real API call to delete OAuth2 credential provider...")
                    delete_request = DeleteOauth2CredentialProviderRequest(
                        credential_provider_id=provider_id
                    )
                    delete_response = AgentCoreIdentityClient.delete_oauth2_credential_provider(delete_request)
                    
                    print(f"Integration Test Delete API Response:")
                    print(f"  - Status: {delete_response.status}")
                    
                    print(f"✓ Integration test: Cleaned up OAuth2 provider: {provider_id}")
                except Exception as e:
                    print(f"Failed to cleanup provider {provider_id}: {str(e)}")

    @pytest.mark.integration
    def test_list_oauth2_providers_integration(self, real_agentcore_control_client, env_setup):
        """Integration test for listing OAuth2 credential providers."""
        if not real_agentcore_control_client:
            pytest.fail("Real AWS client not available - ensure AWS credentials are configured")
        
        print("=== Integration Test: List OAuth2 Providers ===")
        
        # Arrange
        list_request = ListOauth2CredentialProvidersRequest(max_results=20)
        print(f"Request parameters: max_results={list_request.max_results}")
        
        # Act
        print("Making real API call to list OAuth2 credential providers...")
        response = AgentCoreIdentityClient.list_oauth2_credential_providers(list_request)
        
        # Print full response details
        print(f"Integration Test List API Response:")
        print(f"  - Number of providers found: {len(response.oauth2_credential_providers)}")
        print(f"  - Next token: {response.next_token}")
        
        for i, provider in enumerate(response.oauth2_credential_providers):
            print(f"  - Provider {i+1}:")
            print(f"    * ARN: {provider.arn}")
            print(f"    * ID: {provider.credential_provider_id}")
            print(f"    * Name: {provider.name}")
            print(f"    * Provider Type: {provider.provider_type}")
            print(f"    * Status: {provider.status}")
            print(f"    * Scopes: {provider.scopes}")
            print(f"    * Created At: {provider.created_at}")
            print(f"    * Last Updated At: {provider.last_updated_at}")
        
        # Assert
        assert response is not None
        assert response.oauth2_credential_providers is not None
        assert isinstance(response.oauth2_credential_providers, list)
        
        print(f"✓ Integration test: Successfully listed {len(response.oauth2_credential_providers)} OAuth2 providers")

    @pytest.mark.integration
    def test_get_oauth2_provider_integration(self, test_oauth2_provider):
        """Integration test for getting an OAuth2 credential provider."""
        if not test_oauth2_provider:
            pytest.fail("Test OAuth2 provider not available - ensure AWS credentials are configured")
        
        print("=== Integration Test: Get OAuth2 Provider ===")
        
        # Arrange
        provider_id = test_oauth2_provider.credential_provider_id
        get_request = GetOauth2CredentialProviderRequest(
            credential_provider_id=provider_id
        )
        
        print(f"Get request parameters:")
        print(f"  - credential_provider_id: {get_request.credential_provider_id}")
        
        # Act
        print("Making real API call to get OAuth2 credential provider...")
        response = AgentCoreIdentityClient.get_oauth2_credential_provider(get_request)
        
        # Print full response details
        print(f"Integration Test Get API Response:")
        print(f"  - ARN: {response.arn}")
        print(f"  - Provider ID: {response.credential_provider_id}")
        print(f"  - Name: {response.name}")
        print(f"  - Provider Type: {response.provider_type}")
        print(f"  - Status: {response.status}")
        print(f"  - Scopes: {response.scopes}")
        print(f"  - Created At: {response.created_at}")
        print(f"  - Last Updated At: {response.last_updated_at}")
        
        # Assert
        assert response.credential_provider_id == provider_id
        assert response.name == test_oauth2_provider.name
        assert response.provider_type == 'GoogleOauth2'
        assert response.scopes is not None
        assert response.created_at is not None
        
        print(f"✓ Integration test: Successfully retrieved OAuth2 provider: {provider_id}")
