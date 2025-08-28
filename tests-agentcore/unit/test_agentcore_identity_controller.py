"""
Unit tests for the AgentCore Identity Controller.

These tests verify the functionality of the AgentCoreIdentityController
which handles OAuth2 credential provider operations through a unified handler interface.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, '../../src')

from agentic_platform.service.agentcore.identity.api.agentcore_identity_controller import AgentCoreIdentityController, handler
from agentic_platform.service.agentcore.types import (
    OAuth2CredentialProviderOperation,
    OAuth2CredentialProviderRequest,
    OAuth2CredentialProviderResponse,
    OAuth2CredentialProviderStatus,
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
    OAuth2CredentialProvider,
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
                    if key not in os.environ:
                        os.environ[key] = value

load_env_file()


class TestAgentCoreIdentityControllerHandler:
    """Test the main handler function and operation routing."""

    def test_handler_function_delegates_to_controller(self):
        """Test that the standalone handler function delegates to the controller."""
        # Arrange
        event = {
            'operation': 'create-oauth2-credential-provider',
            'input': {
                'name': 'test-provider',
                'provider_type': 'google',
                'scopes': ['openid', 'email']
            }
        }
        context = {}
        
        mock_response = {
            'status_code': 200,
            'result': {'credential_provider_id': 'test-id'}
        }
        
        with patch.object(AgentCoreIdentityController, 'handler', return_value=mock_response) as mock_handler:
            # Act
            result = handler(event, context)
            
            # Assert
            assert result == mock_response
            mock_handler.assert_called_once_with(event, context)

    def test_controller_handler_create_operation_success(self):
        """Test successful CREATE operation handling."""
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
                },
                'client_token': 'test-token-123'
            }
        }
        context = {}
        
        mock_create_response = CreateOauth2CredentialProviderResponse(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            credential_provider_id='test-id',
            name='test-provider',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.CREATING,
            scopes=['openid', 'email'],
            created_at='2023-01-01T00:00:00Z'
        )
        
        with patch.object(AgentCoreIdentityController, 'create_oauth2_credential_provider', 
                         return_value=mock_create_response) as mock_create:
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert result['status_code'] == 200
            assert 'result' in result
            
            # Verify the create method was called with correct request
            mock_create.assert_called_once()
            call_args = mock_create.call_args[0][0]
            assert isinstance(call_args, CreateOauth2CredentialProviderRequest)
            assert call_args.name == 'test-provider'
            assert call_args.provider_type == 'google'
            assert call_args.scopes == ['openid', 'email']

    def test_controller_handler_delete_operation_success(self):
        """Test successful DELETE operation handling."""
        # Arrange
        event = {
            'operation': 'delete-oauth2-credential-provider',
            'input': {
                'credential_provider_id': 'test-id-to-delete'
            }
        }
        context = {}
        
        mock_delete_response = DeleteOauth2CredentialProviderResponse(
            status=OAuth2CredentialProviderStatus.DELETING
        )
        
        with patch.object(AgentCoreIdentityController, 'delete_oauth2_credential_provider',
                         return_value=mock_delete_response) as mock_delete:
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert result['status_code'] == 200
            assert 'result' in result
            
            # Verify the delete method was called with correct request
            mock_delete.assert_called_once()
            call_args = mock_delete.call_args[0][0]
            assert isinstance(call_args, DeleteOauth2CredentialProviderRequest)
            assert call_args.credential_provider_id == 'test-id-to-delete'

    def test_controller_handler_get_operation_success(self):
        """Test successful GET operation handling."""
        # Arrange
        event = {
            'operation': 'get-oauth2-credential-provider',
            'input': {
                'credential_provider_id': 'test-id-to-get'
            }
        }
        context = {}
        
        mock_get_response = GetOauth2CredentialProviderResponse(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id-to-get',
            credential_provider_id='test-id-to-get',
            name='retrieved-provider',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.READY,
            scopes=['openid', 'email'],
            created_at='2023-01-01T00:00:00Z',
            last_updated_at='2023-01-01T01:00:00Z'
        )
        
        with patch.object(AgentCoreIdentityController, 'get_oauth2_credential_provider',
                         return_value=mock_get_response) as mock_get:
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert result['status_code'] == 200
            assert 'result' in result
            
            # Verify the get method was called with correct request
            mock_get.assert_called_once()
            call_args = mock_get.call_args[0][0]
            assert isinstance(call_args, GetOauth2CredentialProviderRequest)
            assert call_args.credential_provider_id == 'test-id-to-get'

    def test_controller_handler_list_operation_success(self):
        """Test successful LIST operation handling."""
        # Arrange
        event = {
            'operation': 'list-oauth2-credential-providers',
            'input': {
                'max_results': 25,
                'next_token': 'some-next-token'
            }
        }
        context = {}
        
        mock_provider = OAuth2CredentialProvider(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/list-test-id',
            credential_provider_id='list-test-id',
            name='listed-provider',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.READY,
            scopes=['openid', 'email'],
            created_at='2023-01-01T00:00:00Z',
            last_updated_at='2023-01-01T00:00:00Z'
        )
        
        mock_list_response = ListOauth2CredentialProvidersResponse(
            oauth2_credential_providers=[mock_provider],
            next_token='next-next-token'
        )
        
        with patch.object(AgentCoreIdentityController, 'list_oauth2_credential_providers',
                         return_value=mock_list_response) as mock_list:
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert result['status_code'] == 200
            assert 'result' in result
            
            # Verify the list method was called with correct request
            mock_list.assert_called_once()
            call_args = mock_list.call_args[0][0]
            assert isinstance(call_args, ListOauth2CredentialProvidersRequest)
            assert call_args.max_results == 25
            assert call_args.next_token == 'some-next-token'

    def test_controller_handler_update_operation_success(self):
        """Test successful UPDATE operation handling."""
        # Arrange
        event = {
            'operation': 'update-oauth2-credential-provider',
            'input': {
                'credential_provider_id': 'test-id-to-update',
                'name': 'updated-provider-name',
                'scopes': ['openid', 'email', 'profile'],
                'google_config': {
                    'client_id': 'updated-client-id',
                    'client_secret': 'updated-client-secret'
                }
            }
        }
        context = {}
        
        mock_update_response = UpdateOauth2CredentialProviderResponse(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id-to-update',
            credential_provider_id='test-id-to-update',
            name='updated-provider-name',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.UPDATING,
            scopes=['openid', 'email', 'profile'],
            created_at='2023-01-01T00:00:00Z',
            last_updated_at='2023-01-01T02:00:00Z'
        )
        
        with patch.object(AgentCoreIdentityController, 'update_oauth2_credential_provider',
                         return_value=mock_update_response) as mock_update:
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert result['status_code'] == 200
            assert 'result' in result
            
            # Verify the update method was called with correct request
            mock_update.assert_called_once()
            call_args = mock_update.call_args[0][0]
            assert isinstance(call_args, UpdateOauth2CredentialProviderRequest)
            assert call_args.credential_provider_id == 'test-id-to-update'
            assert call_args.name == 'updated-provider-name'
            assert call_args.scopes == ['openid', 'email', 'profile']

    def test_controller_handler_invalid_operation_raises_exception(self):
        """Test that invalid operation raises appropriate exception."""
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

    def test_controller_handler_missing_operation_field(self):
        """Test handler behavior when operation field is missing."""
        # Arrange
        event = {
            'input': {
                'name': 'test-provider'
            }
        }
        context = {}
        
        # Act & Assert
        with pytest.raises(Exception):
            AgentCoreIdentityController.handler(event, context)

    def test_controller_handler_missing_input_field(self):
        """Test handler behavior when input field is missing."""
        # Arrange
        event = {
            'operation': 'CREATE'
        }
        context = {}
        
        # Act & Assert
        with pytest.raises(Exception):
            AgentCoreIdentityController.handler(event, context)


class TestAgentCoreIdentityControllerMethods:
    """Test individual controller methods that delegate to the client."""

    @patch('agentic_platform.service.agentcore.identity.api.agentcore_identity_controller.AgentCoreIdentityClient')
    def test_create_oauth2_credential_provider_delegates_to_client(self, mock_client):
        """Test that create method properly delegates to client."""
        # Arrange
        request = CreateOauth2CredentialProviderRequest(
            name='test-provider',
            provider_type='google',
            scopes=['openid', 'email']
        )
        
        mock_response = CreateOauth2CredentialProviderResponse(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            credential_provider_id='test-id',
            name='test-provider',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.CREATING,
            scopes=['openid', 'email'],
            created_at='2023-01-01T00:00:00Z'
        )
        
        mock_client.create_oauth2_credential_provider.return_value = mock_response
        
        # Act
        result = AgentCoreIdentityController.create_oauth2_credential_provider(request)
        
        # Assert
        assert result == mock_response
        mock_client.create_oauth2_credential_provider.assert_called_once_with(request)

    @patch('agentic_platform.service.agentcore.identity.api.agentcore_identity_controller.AgentCoreIdentityClient')
    def test_delete_oauth2_credential_provider_delegates_to_client(self, mock_client):
        """Test that delete method properly delegates to client."""
        # Arrange
        request = DeleteOauth2CredentialProviderRequest(
            credential_provider_id='test-id'
        )
        
        mock_response = DeleteOauth2CredentialProviderResponse(
            status=OAuth2CredentialProviderStatus.DELETING
        )
        
        mock_client.delete_oauth2_credential_provider.return_value = mock_response
        
        # Act
        result = AgentCoreIdentityController.delete_oauth2_credential_provider(request)
        
        # Assert
        assert result == mock_response
        mock_client.delete_oauth2_credential_provider.assert_called_once_with(request)

    @patch('agentic_platform.service.agentcore.identity.api.agentcore_identity_controller.AgentCoreIdentityClient')
    def test_get_oauth2_credential_provider_delegates_to_client(self, mock_client):
        """Test that get method properly delegates to client."""
        # Arrange
        request = GetOauth2CredentialProviderRequest(
            credential_provider_id='test-id'
        )
        
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
        
        mock_client.get_oauth2_credential_provider.return_value = mock_response
        
        # Act
        result = AgentCoreIdentityController.get_oauth2_credential_provider(request)
        
        # Assert
        assert result == mock_response
        mock_client.get_oauth2_credential_provider.assert_called_once_with(request)

    @patch('agentic_platform.service.agentcore.identity.api.agentcore_identity_controller.AgentCoreIdentityClient')
    def test_list_oauth2_credential_providers_delegates_to_client(self, mock_client):
        """Test that list method properly delegates to client."""
        # Arrange
        request = ListOauth2CredentialProvidersRequest(
            max_results=10
        )
        
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
        
        mock_client.list_oauth2_credential_providers.return_value = mock_response
        
        # Act
        result = AgentCoreIdentityController.list_oauth2_credential_providers(request)
        
        # Assert
        assert result == mock_response
        mock_client.list_oauth2_credential_providers.assert_called_once_with(request)

    @patch('agentic_platform.service.agentcore.identity.api.agentcore_identity_controller.AgentCoreIdentityClient')
    def test_update_oauth2_credential_provider_delegates_to_client(self, mock_client):
        """Test that update method properly delegates to client."""
        # Arrange
        request = UpdateOauth2CredentialProviderRequest(
            credential_provider_id='test-id',
            name='updated-name'
        )
        
        mock_response = UpdateOauth2CredentialProviderResponse(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            credential_provider_id='test-id',
            name='updated-name',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.UPDATING,
            scopes=['openid', 'email'],
            created_at='2023-01-01T00:00:00Z',
            last_updated_at='2023-01-01T01:00:00Z'
        )
        
        mock_client.update_oauth2_credential_provider.return_value = mock_response
        
        # Act
        result = AgentCoreIdentityController.update_oauth2_credential_provider(request)
        
        # Assert
        assert result == mock_response
        mock_client.update_oauth2_credential_provider.assert_called_once_with(request)


class TestAgentCoreIdentityControllerErrorHandling:
    """Test error handling in the controller."""

    @patch('agentic_platform.service.agentcore.identity.api.agentcore_identity_controller.AgentCoreIdentityClient')
    def test_create_oauth2_credential_provider_client_exception_propagated(self, mock_client):
        """Test that client exceptions are properly propagated."""
        # Arrange
        request = CreateOauth2CredentialProviderRequest(
            name='test-provider',
            provider_type='google',
            scopes=['openid', 'email']
        )
        
        mock_client.create_oauth2_credential_provider.side_effect = Exception("AWS API Error")
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            AgentCoreIdentityController.create_oauth2_credential_provider(request)
        
        assert "AWS API Error" in str(exc_info.value)
        mock_client.create_oauth2_credential_provider.assert_called_once_with(request)

    def test_handler_exception_during_request_parsing(self):
        """Test handler behavior when request parsing fails."""
        # Arrange
        event = {
            'operation': 'CREATE',
            'input': {
                'invalid_field': 'invalid_value'  # Missing required fields
            }
        }
        context = {}
        
        # Act & Assert
        with pytest.raises(Exception):
            AgentCoreIdentityController.handler(event, context)

    def test_handler_response_serialization(self):
        """Test that handler properly serializes response objects."""
        # Arrange
        event = {
            'operation': 'create-oauth2-credential-provider',
            'input': {
                'name': 'test-provider',
                'provider_type': 'google',
                'scopes': ['openid', 'email']
            }
        }
        context = {}
        
        mock_create_response = CreateOauth2CredentialProviderResponse(
            arn='arn:aws:bedrock:us-west-2:123456789012:credential-provider/test-id',
            credential_provider_id='test-id',
            name='test-provider',
            provider_type='GOOGLE',
            status=OAuth2CredentialProviderStatus.CREATING,
            scopes=['openid', 'email'],
            created_at='2023-01-01T00:00:00Z'
        )
        
        with patch.object(AgentCoreIdentityController, 'create_oauth2_credential_provider',
                         return_value=mock_create_response):
            # Act
            result = AgentCoreIdentityController.handler(event, context)
            
            # Assert
            assert isinstance(result, dict)
            assert result['status_code'] == 200
            assert 'result' in result
            assert isinstance(result['result'], dict)


class TestOAuth2CredentialProviderRequestParsing:
    """Test parsing and validation of OAuth2CredentialProviderRequest objects."""

    def test_valid_create_request_parsing(self):
        """Test parsing of valid CREATE request."""
        # Arrange
        event_data = {
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
        
        # Act
        request = OAuth2CredentialProviderRequest(**event_data)
        
        # Assert
        assert request.operation == OAuth2CredentialProviderOperation.CREATE
        assert 'name' in request.input
        assert request.input['name'] == 'test-provider'

    def test_valid_operations_enum_values(self):
        """Test that all expected operation values are handled."""
        # Test each operation type with correct kebab-case format
        operations = [
            ('create-oauth2-credential-provider', 'CREATE'),
            ('delete-oauth2-credential-provider', 'DELETE'), 
            ('get-oauth2-credential-provider', 'GET'),
            ('list-oauth2-credential-providers', 'LIST'),
            ('update-oauth2-credential-provider', 'UPDATE')
        ]
        
        for op_value, op_enum in operations:
            event_data = {
                'operation': op_value,
                'input': {}
            }
            
            request = OAuth2CredentialProviderRequest(**event_data)
            assert request.operation == getattr(OAuth2CredentialProviderOperation, op_enum)
