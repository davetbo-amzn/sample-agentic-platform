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
from agentcore_gateway_client import AgentCoreGatewayClient

# Test configuration
TEST_GATEWAY_NAME = "test-gateway-client"
TEST_ROLE_ARN = "arn:aws:iam::123456789012:role/test-gateway-role"
TEST_DESCRIPTION = "Test gateway for client testing"

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
                    'discoveryUrl': 'https://example.com/.well-known/openid_configuration',
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
                'supportedVersions': ['1.0'],
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
                    'discoveryUrl': 'https://example.com/.well-known/openid_configuration',
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
                    'discoveryUrl': 'https://example.com/.well-known/openid_configuration',
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
                    'discoveryUrl': 'https://example.com/.well-known/openid_configuration',
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
                    'discoveryUrl': 'https://example.com/.well-known/openid_configuration',
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
                    'discoveryUrl': 'https://example.com/.well-known/openid_configuration',
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
        assert "Gateway not found" in str(exc_info.value) or "does not exist" in str(exc_info.value)
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

    def test_create_gateway_without_role_arn(self):
        """Test creating a gateway without providing role_arn - should create default role."""
        import time
        import boto3
        
        gateway_name = f"test-gateway-no-role-{int(time.time())}"
        created_roles = []
        
        try:
            print(f"Testing gateway creation without role_arn: {gateway_name}")
            
            # Create gateway without role_arn
            result = AgentCoreGatewayClient.create_gateway(
                name=gateway_name,
                description="Test gateway created without explicit role_arn",
                authorizer_configuration={
                    "customJWTAuthorizer": {
                        "discoveryUrl": "https://test-issuer.example.com/.well-known/openid_configuration",
                        "allowedAudience": ["test-audience"],
                        "allowedClients": ["test-client"]
                    }
                }
            )
            
            # Verify the gateway was created successfully
            assert result['gateway_id'] is not None
            assert result['gateway_arn'] is not None
            assert result['name'] == gateway_name
            assert result['status'] in ['READY', 'CREATING']
            
            print(f"Gateway created successfully: {result['gateway_id']}")
            
            # Get the full gateway details to verify role was created
            gateway_details = AgentCoreGatewayClient.get_gateway(result['gateway_id'])
            
            # Verify that a role_arn was assigned
            assert gateway_details['role_arn'] is not None
            assert 'AgentCoreGateway' in gateway_details['role_arn']
            
            print(f"Gateway has role ARN: {gateway_details['role_arn']}")
            
            # Extract role name from ARN for cleanup tracking
            role_arn = gateway_details['role_arn']
            role_name = role_arn.split('/')[-1]
            created_roles.append(role_name)
            
            print(f"Test passed: Gateway created with auto-generated role")
            
            # Clean up gateway
            AgentCoreGatewayClient.delete_gateway(result['gateway_id'])
            
        finally:
            # Clean up IAM roles
            iam_client = boto3.client('iam')
            for role_name in created_roles:
                try:
                    print(f"Cleaning up IAM role: {role_name}")
                    # First, delete inline policies
                    try:
                        policies = iam_client.list_role_policies(RoleName=role_name)
                        for policy_name in policies['PolicyNames']:
                            iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                    except Exception as policy_error:
                        print(f"Error deleting policies for role {role_name}: {str(policy_error)}")
                    
                    # Then delete the role
                    iam_client.delete_role(RoleName=role_name)
                    print(f"Successfully cleaned up IAM role: {role_name}")
                except Exception as e:
                    print(f"Error cleaning up IAM role {role_name}: {str(e)}")

    def test_default_iam_role_creation_directly(self):
        """Test the _create_default_iam_role method directly."""
        import time
        import boto3
        
        gateway_name = f"test-direct-role-{int(time.time())}"
        created_roles = []
        
        try:
            print(f"Testing direct IAM role creation for gateway: {gateway_name}")
            
            # Call the private method directly
            role_arn = AgentCoreGatewayClient._create_default_iam_role(gateway_name)
            
            # Extract role name for cleanup
            role_name = role_arn.split('/')[-1]
            created_roles.append(role_name)
            
            # Verify the role was created
            assert role_arn is not None
            assert 'AgentCoreGateway' in role_arn
            assert gateway_name in role_arn
            
            print(f"Role created with ARN: {role_arn}")
            
            # Verify the role exists in AWS
            iam_client = boto3.client('iam')
            
            role_response = iam_client.get_role(RoleName=role_name)
            assert role_response['Role']['Arn'] == role_arn
            print(f"Role verified in AWS: {role_name}")
            
            # Verify the role has the correct trust policy
            trust_policy = role_response['Role']['AssumeRolePolicyDocument']
            assert 'bedrock-agentcore.amazonaws.com' in str(trust_policy)
            assert 'lambda.amazonaws.com' in str(trust_policy)
            print(f"Trust policy verified for role: {role_name}")
            
            # Verify the role has the correct inline policy
            policies = iam_client.list_role_policies(RoleName=role_name)
            assert len(policies['PolicyNames']) > 0
            
            policy_name = policies['PolicyNames'][0]
            policy_response = iam_client.get_role_policy(RoleName=role_name, PolicyName=policy_name)
            policy_document = policy_response['PolicyDocument']
            
            assert 'lambda:InvokeFunction' in str(policy_document)
            print(f"Inline policy verified for role: {role_name}")
            
            print(f"Test passed: Default IAM role created successfully")
            
        finally:
            # Clean up IAM roles
            iam_client = boto3.client('iam')
            for role_name in created_roles:
                try:
                    print(f"Cleaning up IAM role: {role_name}")
                    # First, delete inline policies
                    try:
                        policies = iam_client.list_role_policies(RoleName=role_name)
                        for policy_name in policies['PolicyNames']:
                            iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                    except Exception as policy_error:
                        print(f"Error deleting policies for role {role_name}: {str(policy_error)}")
                    
                    # Then delete the role
                    iam_client.delete_role(RoleName=role_name)
                    print(f"Successfully cleaned up IAM role: {role_name}")
                except Exception as e:
                    print(f"Error cleaning up IAM role {role_name}: {str(e)}")

if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
