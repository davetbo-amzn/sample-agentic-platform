"""
Test suite for AgentCore Gateway Client.

This test suite follows TDD principles and tests against actual AWS services
without mocking, as per user preferences.
"""

import pytest
import os
import json
from datetime import datetime
from unittest.mock import patch
import sys
sys.path.insert(0, '../../src')
from agentic_platform.service.agentcore.mcp_gateway.client.agentcore_gateway_client import AgentCoreGatewayClient

# Test configuration - using real AWS resources from .env
TEST_GATEWAY_NAME = "test-gateway-client"
TEST_ROLE_ARN = os.environ.get('TEST_ROLE_ARN', 'arn:aws:iam::165361166149:role/agentcore-agentpath-bedrock-agentcore-lambda-role')
TEST_DESCRIPTION = "Test gateway for client testing"
COGNITO_DISCOVERY_URL = os.environ.get('COGNITO_DISCOVERY_URL', 'https://cognito-idp.us-west-2.amazonaws.com/us-west-2_bA0e3osFu/.well-known/openid-configuration')

class TestAgentCoreGatewayClient:
    """Test cases for AgentCore Gateway Client functionality."""
    
    def test_create_gateway_basic(self):
        """Test basic gateway creation functionality."""
        # Test the create_gateway method with minimal required parameters
        result = AgentCoreGatewayClient.create_gateway(
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
        
        # Verify the result structure
        assert isinstance(result, dict)
        assert 'gateway_id' in result
        assert 'gateway_arn' in result
        assert 'gateway_url' in result
        assert 'name' in result
        assert 'status' in result
        assert result['name'] == TEST_GATEWAY_NAME
        
        print(f"Created gateway: {json.dumps(result, indent=2)}")
        
    def test_create_gateway_with_protocol_configuration(self):
        """Test gateway creation with MCP protocol configuration."""
        protocol_config = {
            'mcp': {
                'supportedVersions': ['2025-03-26'],
                'instructions': 'Test MCP gateway instructions',
                'searchType': 'SEMANTIC'
            }
        }
        
        result = AgentCoreGatewayClient.create_gateway(
            name=f"{TEST_GATEWAY_NAME}-mcp",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway with MCP configuration",
            protocol_configuration=protocol_config,
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        assert isinstance(result, dict)
        assert 'gateway_id' in result
        assert result['name'] == f"{TEST_GATEWAY_NAME}-mcp"
        
        print(f"Created MCP gateway: {json.dumps(result, indent=2)}")
        
    def test_get_gateway(self):
        """Test retrieving gateway details."""
        # First create a gateway
        create_result = AgentCoreGatewayClient.create_gateway(
            name=f"{TEST_GATEWAY_NAME}-get",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway for get operation",
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        gateway_id = create_result['gateway_id']
        
        # Now get the gateway details
        result = AgentCoreGatewayClient.get_gateway(gateway_id)
        
        assert isinstance(result, dict)
        assert result['gateway_id'] == gateway_id
        assert result['name'] == f"{TEST_GATEWAY_NAME}-get"
        assert 'status' in result
        assert 'role_arn' in result
        assert 'protocol_type' in result
        assert 'authorizer_type' in result
        
        print(f"Retrieved gateway: {json.dumps(result, indent=2)}")
        
    def test_list_gateways(self):
        """Test listing gateways."""
        result = AgentCoreGatewayClient.list_gateways(max_results=10)
        
        assert isinstance(result, dict)
        assert 'gateways' in result
        assert isinstance(result['gateways'], list)
        
        # If there are gateways, verify their structure
        if result['gateways']:
            gateway = result['gateways'][0]
            assert 'gateway_id' in gateway
            assert 'gateway_arn' in gateway
            assert 'name' in gateway
            assert 'status' in gateway
            
        print(f"Listed {len(result['gateways'])} gateways")
        
    def test_update_gateway(self):
        """Test updating gateway configuration."""
        # First create a gateway
        create_result = AgentCoreGatewayClient.create_gateway(
            name=f"{TEST_GATEWAY_NAME}-update",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway for update operation",
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        gateway_id = create_result['gateway_id']
        
        # Update the gateway description
        new_description = "Updated test gateway description"
        result = AgentCoreGatewayClient.update_gateway(
            gateway_id=gateway_id,
            description=new_description
        )
        
        assert isinstance(result, dict)
        assert result['gateway_id'] == gateway_id
        assert result['description'] == new_description
        
        print(f"Updated gateway: {json.dumps(result, indent=2)}")
        
    def test_delete_gateway(self):
        """Test deleting a gateway."""
        # First create a gateway
        create_result = AgentCoreGatewayClient.create_gateway(
            name=f"{TEST_GATEWAY_NAME}-delete",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway for delete operation",
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        gateway_id = create_result['gateway_id']
        
        # Delete the gateway
        result = AgentCoreGatewayClient.delete_gateway(gateway_id)
        
        assert isinstance(result, dict)
        assert result['gateway_id'] == gateway_id
        assert result['status'] == 'DELETING'
        
        print(f"Deleted gateway: {json.dumps(result, indent=2)}")
        
    def test_wait_for_gateway_creation(self):
        """Test waiting for gateway creation to complete."""
        # Create a gateway and test the wait functionality
        create_result = AgentCoreGatewayClient.create_gateway(
            name=f"{TEST_GATEWAY_NAME}-wait",
            role_arn=TEST_ROLE_ARN,
            description="Test gateway for wait operation",
            authorizer_configuration={
                'customJWTAuthorizer': {
                    'discoveryUrl': COGNITO_DISCOVERY_URL,
                    'allowedAudience': ['test-audience'],
                    'allowedClients': ['test-client']
                }
            }
        )
        
        gateway_id = create_result['gateway_id']
        
        # Test wait functionality with shorter timeout for testing
        result = AgentCoreGatewayClient.wait_for_gateway_creation(
            gateway_id=gateway_id,
            max_attempts=5,
            delay_seconds=10
        )
        
        assert isinstance(result, dict)
        assert result['gateway_id'] == gateway_id
        assert result['status'] in ['READY', 'CREATING']
        
        print(f"Wait result: {json.dumps(result, indent=2)}")

    def test_error_handling_invalid_gateway_id(self):
        """Test error handling for invalid gateway ID."""
        with pytest.raises(Exception) as exc_info:
            AgentCoreGatewayClient.get_gateway("invalid-gateway-id")
        
        # Verify that an appropriate error is raised
        # assert "Gateway not found" in str(exc_info.value) or "does not exist" in str(exc_info.value)
        # the line above was what the model created but the actual error thrown by the service
        # in this case is AccessDeniedException. I guess maybe this is to prevent probing for different errors.
        assert "AccessDeniedException" in str(exc_info.value)
        print(f"Expected error for invalid gateway ID: {exc_info.value}")

    def test_error_handling_missing_required_params(self):
        """Test error handling for missing required parameters."""
        with pytest.raises(Exception) as exc_info:
            # Missing required authorizer_configuration
            AgentCoreGatewayClient.create_gateway(
                name="test-missing-params",
                role_arn=TEST_ROLE_ARN
            )
        
        print(f"Expected error for missing params: {exc_info.value}")

if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
