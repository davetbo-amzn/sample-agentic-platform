"""
Test suite for AgentCore Gateway Controller.

This test suite follows TDD principles and tests against actual AWS services
without mocking, as per user preferences. Tests the controller layer which
orchestrates the client operations and handles request/response transformations.
"""

import pytest
import os
import json
import sys
from datetime import datetime
from unittest.mock import patch

# Add the source path for imports
sys.path.insert(0, '../../src')

from agentic_platform.service.agentcore.mcp_gateway.api.agentcore_gateway_controller import AgentCoreGatewayController
from agentic_platform.service.agentcore.types import (
    GatewayOperation,
    GatewayRequest,
    CreateGatewayRequest,
    DeleteGatewayRequest,
    GetGatewayRequest,
    ListGatewaysRequest,
    UpdateGatewayRequest,
    GatewayStatus
)

# Test configuration - using real AWS resources from .env
TEST_GATEWAY_NAME = "test-gateway-controller"
TEST_ROLE_ARN = os.environ.get('TEST_ROLE_ARN', 'arn:aws:iam::165361166149:role/agentcore-agentpath-bedrock-agentcore-lambda-role')
TEST_DESCRIPTION = "Test gateway for controller testing"
COGNITO_DISCOVERY_URL = os.environ.get('COGNITO_DISCOVERY_URL', 'https://cognito-idp.us-west-2.amazonaws.com/us-west-2_bA0e3osFu/.well-known/openid-configuration')


class TestAgentCoreGatewayController:
    """Test cases for AgentCore Gateway Controller functionality."""
    
    def test_create_gateway_controller(self):
        """Test gateway creation through controller."""
        request = CreateGatewayRequest(
            name=TEST_GATEWAY_NAME,
            role_arn=TEST_ROLE_ARN,
            description=TEST_DESCRIPTION,
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        result = AgentCoreGatewayController.create_gateway(request)
        
        # Verify the result structure and types
        assert hasattr(result, 'gateway_id')
        assert hasattr(result, 'gateway_arn')
        assert hasattr(result, 'gateway_url')
        assert hasattr(result, 'name')
        assert hasattr(result, 'status')
        assert result.name == TEST_GATEWAY_NAME
        assert isinstance(result.status, GatewayStatus)
        
        print(f"Created gateway via controller: {result.to_dict()}")
        
    def test_create_gateway_with_protocol_configuration_controller(self):
        """Test gateway creation with MCP protocol configuration through controller."""
        protocol_config = {
            'mcp': {
                'supportedVersions': ['2025-03-26'],
                'instructions': 'Test MCP gateway instructions',
                'searchType': 'SEMANTIC'
            }
        }
        
        request = CreateGatewayRequest(
            name=f"{TEST_GATEWAY_NAME}-mcp-controller",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway with MCP configuration via controller",
            protocol_configuration=protocol_config,
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        result = AgentCoreGatewayController.create_gateway(request)
        
        assert hasattr(result, 'gateway_id')
        assert result.name == f"{TEST_GATEWAY_NAME}-mcp-controller"
        assert isinstance(result.status, GatewayStatus)
        
        print(f"Created MCP gateway via controller: {result.to_dict()}")
        
    def test_get_gateway_controller(self):
        """Test retrieving gateway details through controller."""
        # First create a gateway
        create_request = CreateGatewayRequest(
            name=f"{TEST_GATEWAY_NAME}-get-controller",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway for get operation via controller",
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        create_result = AgentCoreGatewayController.create_gateway(create_request)
        gateway_id = create_result.gateway_id
        
        # Now get the gateway details
        get_request = GetGatewayRequest(gateway_id=gateway_id)
        result = AgentCoreGatewayController.get_gateway(get_request)
        
        assert hasattr(result, 'gateway_id')
        assert result.gateway_id == gateway_id
        assert result.name == f"{TEST_GATEWAY_NAME}-get-controller"
        assert hasattr(result, 'status')
        assert hasattr(result, 'role_arn')
        assert hasattr(result, 'protocol_type')
        assert hasattr(result, 'authorizer_type')
        assert isinstance(result.status, GatewayStatus)
        
        print(f"Retrieved gateway via controller: {result.to_dict()}")
        
    def test_list_gateways_controller(self):
        """Test listing gateways through controller."""
        request = ListGatewaysRequest(max_results=10)
        result = AgentCoreGatewayController.list_gateways(request)
        
        assert hasattr(result, 'gateways')
        assert hasattr(result, 'next_token')
        assert isinstance(result.gateways, list)
        
        # If there are gateways, verify their structure
        if result.gateways:
            gateway = result.gateways[0]
            assert hasattr(gateway, 'gateway_id')
            assert hasattr(gateway, 'gateway_arn')
            assert hasattr(gateway, 'name')
            assert hasattr(gateway, 'status')
            assert isinstance(gateway.status, GatewayStatus)
            
        print(f"Listed {len(result.gateways)} gateways via controller")
        
    def test_update_gateway_controller(self):
        """Test updating gateway configuration through controller."""
        # First create a gateway
        create_request = CreateGatewayRequest(
            name=f"{TEST_GATEWAY_NAME}-update-controller",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway for update operation via controller",
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        create_result = AgentCoreGatewayController.create_gateway(create_request)
        gateway_id = create_result.gateway_id
        
        # Update the gateway description
        new_description = "Updated test gateway description via controller"
        update_request = UpdateGatewayRequest(
            gateway_id=gateway_id,
            description=new_description
        )
        
        result = AgentCoreGatewayController.update_gateway(update_request)
        
        assert hasattr(result, 'gateway_id')
        assert result.gateway_id == gateway_id
        assert result.description == new_description
        assert isinstance(result.status, GatewayStatus)
        
        print(f"Updated gateway via controller: {result.to_dict()}")
        
    def test_delete_gateway_controller(self):
        """Test deleting a gateway through controller."""
        # First create a gateway
        create_request = CreateGatewayRequest(
            name=f"{TEST_GATEWAY_NAME}-delete-controller",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway for delete operation via controller",
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        create_result = AgentCoreGatewayController.create_gateway(create_request)
        gateway_id = create_result.gateway_id
        
        # Delete the gateway
        delete_request = DeleteGatewayRequest(gateway_id=gateway_id)
        result = AgentCoreGatewayController.delete_gateway(delete_request)
        
        assert hasattr(result, 'gateway_id')
        assert result.gateway_id == gateway_id
        assert hasattr(result, 'status')
        assert isinstance(result.status, GatewayStatus)
        assert result.status == GatewayStatus.DELETING
        
        print(f"Deleted gateway via controller: {result.to_dict()}")
        
    def test_wait_for_gateway_creation_controller(self):
        """Test waiting for gateway creation to complete through controller."""
        # Create a gateway and test the wait functionality
        create_request = CreateGatewayRequest(
            name=f"{TEST_GATEWAY_NAME}-wait-controller",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway for wait operation via controller",
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        create_result = AgentCoreGatewayController.create_gateway(create_request)
        gateway_id = create_result.gateway_id
        
        # Test wait functionality with shorter timeout for testing
        result = AgentCoreGatewayController.wait_for_gateway_creation(
            gateway_id=gateway_id,
            max_attempts=5,
            delay_seconds=10
        )
        
        assert isinstance(result, dict)
        assert 'gateway_id' in result
        assert result['gateway_id'] == gateway_id
        assert 'status' in result
        assert result['status'] in ['READY', 'CREATING']
        
        print(f"Wait result via controller: {json.dumps(result, indent=2)}")

    def test_handler_create_operation(self):
        """Test the Lambda handler with CREATE operation."""
        event = {
            'operation': 'create-gateway',
            'input': {
                'name': f"{TEST_GATEWAY_NAME}-handler",
                'role_arn': TEST_ROLE_ARN,
                'description': "Test gateway via handler",
                'authorizer_configuration': {
                    'customJWTAuthorizer': {
                        'discoveryUrl': COGNITO_DISCOVERY_URL,
                        'allowedAudience': ['test-audience'],
                        'allowedClients': ['test-client']
                    }
                }
            }
        }
        
        result = AgentCoreGatewayController.handler(event, None)
        
        assert isinstance(result, dict)
        assert 'status_code' in result
        assert result['status_code'] == 200
        assert 'result' in result
        assert 'gateway_id' in result['result']
        assert 'name' in result['result']
        assert result['result']['name'] == f"{TEST_GATEWAY_NAME}-handler"
        
        print(f"Handler CREATE result: {json.dumps(result, indent=2)}")

    def test_handler_list_operation(self):
        """Test the Lambda handler with LIST operation."""
        event = {
            'operation': 'list-gateways',
            'input': {
                'max_results': 5
            }
        }
        
        result = AgentCoreGatewayController.handler(event, None)
        
        assert isinstance(result, dict)
        assert 'status_code' in result
        assert result['status_code'] == 200
        assert 'result' in result
        assert 'gateways' in result['result']
        assert isinstance(result['result']['gateways'], list)
        
        print(f"Handler LIST result: Found {len(result['result']['gateways'])} gateways")

    def test_error_handling_invalid_gateway_id_controller(self):
        """Test error handling for invalid gateway ID through controller."""
        get_request = GetGatewayRequest(gateway_id="invalid-gateway-id")
        
        with pytest.raises(Exception) as exc_info:
            AgentCoreGatewayController.get_gateway(get_request)
        
        # Verify that an appropriate error is raised
        assert "Gateway not found" in str(exc_info.value) or "does not exist" in str(exc_info.value)
        print(f"Expected error for invalid gateway ID via controller: {exc_info.value}")

    def test_error_handling_invalid_operation_handler(self):
        """Test error handling for invalid operation in handler."""
        event = {
            'operation': 'invalid-operation',
            'input': {}
        }
        
        with pytest.raises(Exception) as exc_info:
            AgentCoreGatewayController.handler(event, None)
        
        assert "Parameter validation exception" in str(exc_info.value)
        print(f"Expected error for invalid operation: {exc_info.value}")

    def test_error_handling_missing_required_params_controller(self):
        """Test error handling for missing required parameters through controller."""
        with pytest.raises(Exception) as exc_info:
            # Missing required authorizer_configuration
            request = CreateGatewayRequest(
                name="test-missing-params-controller",
                role_arn=TEST_ROLE_ARN
            )
            AgentCoreGatewayController.create_gateway(request)
        
        print(f"Expected error for missing params via controller: {exc_info.value}")

    def test_gateway_status_enum_conversion(self):
        """Test that gateway status strings are properly converted to enums."""
        # Create a gateway to test status conversion
        create_request = CreateGatewayRequest(
            name=f"{TEST_GATEWAY_NAME}-status-test",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway for status enum conversion",
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        result = AgentCoreGatewayController.create_gateway(create_request)
        
        # Verify status is properly converted to enum
        assert isinstance(result.status, GatewayStatus)
        assert result.status in [GatewayStatus.CREATING, GatewayStatus.READY]
        
        # Test to_dict() method includes proper status value
        result_dict = result.to_dict()
        assert 'status' in result_dict
        assert result_dict['status'] in ['CREATING', 'READY']
        
        print(f"Status enum conversion test: {result.status} -> {result_dict['status']}")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
