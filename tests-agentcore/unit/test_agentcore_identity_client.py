"""
Unit tests for the AgentCoreIdentityClient and AgentCoreIdentityController classes.

These tests verify the functionality of the AgentCore Identity components
that manage OAuth2 credential providers and other identity resources.

The tests include both unit tests with mocking and integration tests that
make real API calls to AWS Bedrock AgentCore services.
"""

import os
import pytest
import boto3
import time
from unittest.mock import Mock, patch, MagicMock
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
    OAuth2CredentialProviderOperation,
    OAuth2CredentialProviderRequest,
    OAuth2CredentialProviderResponse,
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
    """Unit tests for AgentCoreIdentityController class."""

    def test_handler_create_operation(self):
        """Test handler with CREATE operation."""
        # Arrange
        event = {
            'operation': 'create-oauth2-credential-provider',
            'input': {
                'name': 'test-provider',
                'provider_type': 'google',
                'scopes': ['openid', 'email'],
                'google_config': {
                    'client_id': 'test-client-id',
                    'client_secret': 'test-client-secret'
                }
            }
        }
        context = {}
        
        mock_response = CreateOauth2CredentialProviderResponse(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            credential_provider_id='test-id',
            name='test-provider',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.CREATING,
            scopes=['openid', 'email'],
            created_at='2023-01-01T00:00:00Z'
        )
        
        with patch.object(AgentCoreIdentityController, 'create_oauth2_credential_provider', return_value=mock_response) as mock_create:
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert result['status_code'] == 200
            assert 'result' in result
            mock_create.assert_called_once()

    def test_handler_delete_operation(self):
        """Test handler with DELETE operation."""
        # Arrange
        event = {
            'operation': 'delete-oauth2-credential-provider',
            'input': {
                'credential_provider_id': 'test-id'
            }
        }
        context = {}
        
        mock_response = DeleteOauth2CredentialProviderResponse(
            status=OAuth2CredentialProviderStatus.DELETING
        )
        
        with patch.object(AgentCoreIdentityController, 'delete_oauth2_credential_provider', return_value=mock_response) as mock_delete:
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert result['status_code'] == 200
            assert 'result' in result
            mock_delete.assert_called_once()

    def test_handler_get_operation(self):
        """Test handler with GET operation."""
        # Arrange
        event = {
            'operation': 'get-oauth2-credential-provider',
            'input': {
                'credential_provider_id': 'test-id'
            }
        }
        context = {}
        
        mock_response = GetOauth2CredentialProviderResponse(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            credential_provider_id='test-id',
            name='test-provider',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.READY,
            scopes=['openid', 'email'],
            created_at='2023-01-01T00:00:00Z',
            last_updated_at='2023-01-01T00:00:00Z'
        )
        
        with patch.object(AgentCoreIdentityController, 'get_oauth2_credential_provider', return_value=mock_response) as mock_get:
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert result['status_code'] == 200
            assert 'result' in result
            mock_get.assert_called_once()

    def test_handler_list_operation(self):
        """Test handler with LIST operation."""
        # Arrange
        event = {
            'operation': 'list-oauth2-credential-providers',
            'input': {
                'max_results': 10
            }
        }
        context = {}
        
        mock_provider = OAuth2CredentialProvider(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            credential_provider_id='test-id',
            name='test-provider',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.READY,
            scopes=['openid', 'email'],
            created_at='2023-01-01T00:00:00Z',
            last_updated_at='2023-01-01T00:00:00Z'
        )
        
        mock_response = ListOauth2CredentialProvidersResponse(
            oauth2_credential_providers=[mock_provider],
            next_token=None
        )
        
        with patch.object(AgentCoreIdentityController, 'list_oauth2_credential_providers', return_value=mock_response) as mock_list:
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert result['status_code'] == 200
            assert 'result' in result
            mock_list.assert_called_once()

    def test_handler_update_operation(self):
        """Test handler with UPDATE operation."""
        # Arrange
        event = {
            'operation': 'update-oauth2-credential-provider',
            'input': {
                'credential_provider_id': 'test-id',
                'name': 'test-provider',
                'provider_type': 'google',
                'scopes': ['openid', 'email']
            }
        }
        context = {}
        
        mock_response = UpdateOauth2CredentialProviderResponse(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            credential_provider_id='test-id',
            name='updated-provider',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.UPDATING,
            scopes=['openid', 'email', 'profile'],
            created_at='2023-01-01T00:00:00Z',
            last_updated_at='2023-01-01T01:00:00Z'
        )
        
        with patch.object(AgentCoreIdentityController, 'update_oauth2_credential_provider', return_value=mock_response) as mock_update:
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert result['status_code'] == 200
            assert 'result' in result
            mock_update.assert_called_once()

    def test_handler_invalid_operation(self):
        """Test handler with invalid operation."""
        # Arrange
        event = {
            'operation': 'INVALID_OPERATION',
            'input': {}
        }
        context = {}
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            AgentCoreIdentityController.handler(event, context)
        
        # The actual validation error will mention the valid enum values
        error_msg = str(exc_info.value)
        assert "validation error" in error_msg.lower()


class TestAgentCoreIdentityClientUnit:
    """Unit tests for AgentCoreIdentityClient class with mocking."""

    @patch('agentic_platform.service.agentcore.identity.client.agentcore_identity_client.agentcore_control_client')
    def test_create_oauth2_credential_provider_success(self, mock_client):
        """Test successful creation of OAuth2 credential provider."""
        # Arrange
        mock_response = {
            'arn': 'arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            'credentialProviderId': 'test-id',
            'name': 'test-provider',
            'providerType': 'GOOGLE',
            'status': 'CREATING',
            'scopes': ['openid', 'email'],
            'createdAt': datetime(2023, 1, 1, tzinfo=timezone.utc),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_client.create_oauth2_credential_provider.return_value = mock_response
        
        request = CreateOauth2CredentialProviderRequest(
            name='test-provider',
            provider_type='google',
            scopes=['openid', 'email'],
            google_config=GoogleOAuth2Config(
                client_id='test-client-id',
                client_secret='test-client-secret'
            )
        )
        
        # Act
        result = AgentCoreIdentityClient.create_oauth2_credential_provider(request)
        
        # Assert
        assert result.credential_provider_id == 'test-id'
        assert result.name == 'test-provider'
        assert result.provider_type == 'GOOGLE'
        assert result.status == OAuth2CredentialProviderStatus.CREATING
        assert result.scopes == ['openid', 'email']
        
        mock_client.create_oauth2_credential_provider.assert_called_once()

    @patch('agentic_platform.service.agentcore.identity.client.agentcore_identity_client.agentcore_control_client')
    def test_create_oauth2_credential_provider_failure(self, mock_client):
        """Test failure in OAuth2 credential provider creation."""
        # Arrange
        mock_client.create_oauth2_credential_provider.side_effect = Exception("AWS API Error")
        
        request = CreateOauth2CredentialProviderRequest(
            name='test-provider',
            provider_type='google',
            scopes=['openid', 'email'],
            google_config=GoogleOAuth2Config(
                client_id='test-client-id',
                client_secret='test-client-secret'
            )
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            AgentCoreIdentityClient.create_oauth2_credential_provider(request)
        
        assert "AWS API Error" in str(exc_info.value)

    @patch('agentic_platform.service.agentcore.identity.client.agentcore_identity_client.agentcore_control_client')
    def test_delete_oauth2_credential_provider_success(self, mock_client):
        """Test successful deletion of OAuth2 credential provider."""
        # Arrange
        mock_response = {'ResponseMetadata': {'HTTPStatusCode': 200}}
        mock_client.delete_oauth2_credential_provider.return_value = mock_response
        
        request = DeleteOauth2CredentialProviderRequest(
            credential_provider_id='test-id'
        )
        
        # Act
        result = AgentCoreIdentityClient.delete_oauth2_credential_provider(request)
        
        # Assert
        assert result.status == OAuth2CredentialProviderStatus.DELETING
        mock_client.delete_oauth2_credential_provider.assert_called_once_with(
            credentialProviderId='test-id'
        )

    @patch('agentic_platform.service.agentcore.identity.client.agentcore_identity_client.agentcore_control_client')
    def test_get_oauth2_credential_provider_success(self, mock_client):
        """Test successful retrieval of OAuth2 credential provider."""
        # Arrange
        mock_response = {
            'arn': 'arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            'credentialProviderId': 'test-id',
            'name': 'test-provider',
            'providerType': 'GOOGLE',
            'status': 'READY',
            'scopes': ['openid', 'email'],
            'createdAt': datetime(2023, 1, 1, tzinfo=timezone.utc),
            'lastUpdatedAt': datetime(2023, 1, 1, tzinfo=timezone.utc),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_client.get_oauth2_credential_provider.return_value = mock_response
        
        request = GetOauth2CredentialProviderRequest(
            credential_provider_id='test-id'
        )
        
        # Act
        result = AgentCoreIdentityClient.get_oauth2_credential_provider(request)
        
        # Assert
        assert result.credential_provider_id == 'test-id'
        assert result.name == 'test-provider'
        assert result.status == OAuth2CredentialProviderStatus.READY
        mock_client.get_oauth2_credential_provider.assert_called_once_with(
            credentialProviderId='test-id'
        )

    @patch('agentic_platform.service.agentcore.identity.client.agentcore_identity_client.agentcore_control_client')
    def test_get_oauth2_credential_provider_not_found(self, mock_client):
        """Test retrieval of non-existent OAuth2 credential provider."""
        # Arrange
        error_response = {
            'Error': {
                'Code': 'ResourceNotFoundException',
                'Message': 'The requested resource was not found.'
            }
        }
        mock_error = ClientError(error_response, 'GetOauth2CredentialProvider')
        mock_error.response = error_response
        mock_client.get_oauth2_credential_provider.side_effect = mock_error
        
        request = GetOauth2CredentialProviderRequest(
            credential_provider_id='non-existent-id'
        )
        
        # Act & Assert
        with pytest.raises(Exception):
            AgentCoreIdentityClient.get_oauth2_credential_provider(request)

    @patch('agentic_platform.service.agentcore.identity.client.agentcore_identity_client.agentcore_control_client')
    def test_list_oauth2_credential_providers_success(self, mock_client):
        """Test successful listing of OAuth2 credential providers."""
        # Arrange
        mock_response = {
            'oauth2CredentialProviders': [
                {
                    'arn': 'arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id-1',
                    'credentialProviderId': 'test-id-1',
                    'name': 'test-provider-1',
                    'providerType': 'GOOGLE',
                    'status': 'READY',
                    'scopes': ['openid', 'email'],
                    'createdAt': datetime(2023, 1, 1, tzinfo=timezone.utc),
                    'lastUpdatedAt': datetime(2023, 1, 1, tzinfo=timezone.utc)
                },
                {
                    'arn': 'arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id-2',
                    'credentialProviderId': 'test-id-2',
                    'name': 'test-provider-2',
                    'providerType': 'GOOGLE',
                    'status': 'READY',
                    'scopes': ['openid', 'profile'],
                    'createdAt': datetime(2023, 1, 2, tzinfo=timezone.utc),
                    'lastUpdatedAt': datetime(2023, 1, 2, tzinfo=timezone.utc)
                }
            ],
            'nextToken': 'next-token-value',
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_client.list_oauth2_credential_providers.return_value = mock_response
        
        request = ListOauth2CredentialProvidersRequest(
            max_results=10,
            next_token='some-token'
        )
        
        # Act
        result = AgentCoreIdentityClient.list_oauth2_credential_providers(request)
        
        # Assert
        assert len(result.oauth2_credential_providers) == 2
        assert result.next_token == 'next-token-value'
        assert result.oauth2_credential_providers[0].credential_provider_id == 'test-id-1'
        assert result.oauth2_credential_providers[1].credential_provider_id == 'test-id-2'
        
        mock_client.list_oauth2_credential_providers.assert_called_once_with(
            maxResults=10,
            nextToken='some-token'
        )

    @patch('agentic_platform.service.agentcore.identity.client.agentcore_identity_client.agentcore_control_client')
    def test_update_oauth2_credential_provider_success(self, mock_client):
        """Test successful update of OAuth2 credential provider."""
        # Arrange
        mock_response = {
            'arn': 'arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            'credentialProviderId': 'test-id',
            'name': 'updated-provider',
            'providerType': 'GOOGLE',
            'status': 'UPDATING',
            'scopes': ['openid', 'email', 'profile'],
            'createdAt': datetime(2023, 1, 1, tzinfo=timezone.utc),
            'lastUpdatedAt': datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        mock_client.update_oauth2_credential_provider.return_value = mock_response
        
        request = UpdateOauth2CredentialProviderRequest(
            credential_provider_id='test-id',
            name='updated-provider',
            scopes=['openid', 'email', 'profile']
        )
        
        # Act
        result = AgentCoreIdentityClient.update_oauth2_credential_provider(request)
        
        # Assert
        assert result.credential_provider_id == 'test-id'
        assert result.name == 'updated-provider'
        assert result.status == OAuth2CredentialProviderStatus.UPDATING
        assert result.scopes == ['openid', 'email', 'profile']
        
        mock_client.update_oauth2_credential_provider.assert_called_once()


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
    """Integration tests for AgentCoreIdentityClient with real AWS API calls."""

    @pytest.mark.integration
    def test_create_oauth2_provider_integration(self, real_agentcore_control_client, env_setup):
        """Integration test for creating an OAuth2 credential provider."""
        if not real_agentcore_control_client:
            pytest.fail("Real AWS client not available - ensure AWS credentials are configured")
        
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
        
        provider_id = None
        try:
            # Act
            response = AgentCoreIdentityClient.create_oauth2_credential_provider(create_request)
            provider_id = response.credential_provider_id
            
            # Assert
            assert response.credential_provider_id is not None
            assert response.name == provider_name
            assert response.provider_type == 'GOOGLE'
            assert response.scopes == ['openid', 'email']
            assert response.status in [OAuth2CredentialProviderStatus.CREATING, OAuth2CredentialProviderStatus.READY]
            
            print(f"Successfully created OAuth2 provider: {provider_id}")
            
        finally:
            # Cleanup
            if provider_id and DELETE_AT_END:
                try:
                    delete_request = DeleteOauth2CredentialProviderRequest(
                        credential_provider_id=provider_id
                    )
                    AgentCoreIdentityClient.delete_oauth2_credential_provider(delete_request)
                    print(f"Cleaned up OAuth2 provider: {provider_id}")
                except Exception as e:
                    print(f"Failed to cleanup provider {provider_id}: {str(e)}")

    @pytest.mark.integration
    def test_list_oauth2_providers_integration(self, real_agentcore_control_client, env_setup):
        """Integration test for listing OAuth2 credential providers."""
        if not real_agentcore_control_client:
            pytest.fail("Real AWS client not available - ensure AWS credentials are configured")
        
        # Arrange
        list_request = ListOauth2CredentialProvidersRequest(max_results=20)
        
        # Act
        response = AgentCoreIdentityClient.list_oauth2_credential_providers(list_request)
        
        # Assert
        assert response is not None
        assert response.oauth2_credential_providers is not None
        assert isinstance(response.oauth2_credential_providers, list)
        
        print(f"Successfully listed {len(response.oauth2_credential_providers)} OAuth2 providers")

    @pytest.mark.integration
    def test_get_oauth2_provider_integration(self, test_oauth2_provider):
        """Integration test for getting an OAuth2 credential provider."""
        if not test_oauth2_provider:
            pytest.fail("Test OAuth2 provider not available - ensure AWS credentials are configured")
        
        # Arrange
        provider_id = test_oauth2_provider.credential_provider_id
        get_request = GetOauth2CredentialProviderRequest(
            credential_provider_id=provider_id
        )
        
        # Act
        response = AgentCoreIdentityClient.get_oauth2_credential_provider(get_request)
        
        # Assert
        assert response.credential_provider_id == provider_id
        assert response.name == test_oauth2_provider.name
        assert response.provider_type == 'GOOGLE'
        assert response.scopes is not None
        assert response.created_at is not None
        
        print(f"Successfully retrieved OAuth2 provider: {provider_id}")
