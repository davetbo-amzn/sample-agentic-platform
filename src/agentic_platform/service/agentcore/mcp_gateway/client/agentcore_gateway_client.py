"""
AWS Lambda function to provision and manage Bedrock AgentCore Gateway resources.

This function is used by Terraform to create and update Bedrock AgentCore gateway
capabilities for the Agentic Platform.

Usage:
  - The function is invoked by Terraform with appropriate configuration parameters
  - It creates or updates gateway resources using the boto3 SDK
  - It handles provision action for now

Environment Variables:
  - REGION: AWS region for Bedrock AgentCore resources
"""

import boto3
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get environment variables
REGION = os.environ.get('REGION', 'us-west-2')

agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
ssm_client = boto3.client('ssm', region_name=REGION)
iam_client = boto3.client('iam', region_name=REGION)

class AgentCoreGatewayClient:

    @staticmethod
    def _create_default_iam_role(gateway_name: str) -> str:
        """
        Create a default IAM role for the AgentCore Gateway.
        
        Args:
            gateway_name: Name of the gateway to create role for
            
        Returns:
            ARN of the created IAM role
        """
        # Generate unique role name
        role_name = f"AgentCoreGateway-{gateway_name}-{uuid.uuid4().hex[:8]}"
        
        # Trust policy allowing bedrock-agentcore and lambda services to assume the role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": [
                            "lambda.amazonaws.com",
                            "bedrock-agentcore.amazonaws.com"
                        ]
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        # Role policy allowing lambda invocation
        role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "lambda:InvokeFunction",
                    "Resource": "*",
                    "Effect": "Allow"
                }
            ]
        }
        
        try:
            print(f"Creating IAM role: {role_name}")
            
            # Create the IAM role
            create_role_response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"Default IAM role for AgentCore Gateway {gateway_name}",
                Tags=[
                    {
                        'Key': 'Purpose',
                        'Value': 'AgentCoreGateway'
                    },
                    {
                        'Key': 'GatewayName',
                        'Value': gateway_name
                    }
                ]
            )
            
            role_arn = create_role_response['Role']['Arn']
            print(f"Created IAM role with ARN: {role_arn}")
            
            # Attach the inline policy to the role
            policy_name = f"AgentCoreGatewayPolicy-{gateway_name}"
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(role_policy)
            )
            
            print(f"Attached policy {policy_name} to role {role_name}")
            
            # Wait a moment for IAM consistency
            print("Waiting for IAM role to be available...")
            time.sleep(10)
            
            return role_arn
            
        except Exception as e:
            logger.error(f"Error creating default IAM role: {str(e)}")
            raise e

    @staticmethod
    def create_gateway(
        name: str,
        role_arn: Optional[str] = None,
        protocol_type: str = 'MCP',
        description: Optional[str] = None,
        protocol_configuration: Optional[Dict[str, Any]] = None,
        authorizer_type: str = 'CUSTOM_JWT',
        authorizer_configuration: Optional[Dict[str, Any]] = None,
        kms_key_arn: Optional[str] = None,
        exception_level: Optional[str] = None,
        client_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Bedrock AgentCore Gateway resource.
        
        Args:
            name: The name of the gateway. Must be unique within your account.
            role_arn: Optional Amazon Resource Name (ARN) of the IAM role that provides 
                     permissions for the gateway to access AWS services. If not provided,
                     a default role will be created.
            protocol_type: The protocol type for the gateway. Currently supports MCP.
            description: Optional description of the gateway.
            protocol_configuration: Configuration settings for the protocol.
            authorizer_type: The type of authorizer to use for the gateway.
            authorizer_configuration: The authorizer configuration for the Gateway.
            kms_key_arn: Optional ARN of the KMS key used to encrypt data.
            exception_level: The verbosity of exception messages (DEBUG or None).
            client_token: Optional unique token to ensure idempotency.
            
        Returns:
            Dictionary with the gateway creation result
        """
        
        print(f"Creating AgentCore Gateway {name} with protocol {protocol_type}")
        try:
            # Create default IAM role if role_arn is not provided
            if role_arn is None:
                print("No role_arn provided, creating default IAM role...")
                role_arn = AgentCoreGatewayClient._create_default_iam_role(name)
                print(f"Created default IAM role: {role_arn}")
            
            # Prepare create parameters
            create_params = {
                'name': name,
                'roleArn': role_arn,
                'protocolType': protocol_type,
                'authorizerType': authorizer_type
            }
            
            # Add optional parameters if provided
            if description:
                create_params['description'] = description
            if client_token:
                create_params['clientToken'] = client_token
            if protocol_configuration:
                create_params['protocolConfiguration'] = protocol_configuration
            if authorizer_configuration:
                create_params['authorizerConfiguration'] = authorizer_configuration
            else:
                create_params['authorizerConfiguration'] = {
                    'customJWTAuthorizer': {
                        'discoveryUrl': os.getenv('COGNITO_DISCOVERY_URL'),
                        'allowedClients': [
                            os.getenv('COGNITO_USER_POOL_CLIENT_ID')
                        ]
                    }
                }
            if kms_key_arn:
                create_params['kmsKeyArn'] = kms_key_arn
            if exception_level:
                create_params['exceptionLevel'] = exception_level
            
            print(f"Creating gateway with parameters: {create_params}")
            
            # Create gateway using the control plane client
            create_response = agentcore_control_client.create_gateway(**create_params)
            
            print(f"Got create response: {create_response}")
            gateway_id = create_response['gatewayId']
            
            print(f"Creating AgentCore gateway resource with ID: {gateway_id}")
            print("Waiting for gateway creation to complete.")
            
            result = AgentCoreGatewayClient.wait_for_gateway_creation(gateway_id)
            print(f"Gateway creation result: {result}")
            
            status = agentcore_control_client.get_gateway(
                gatewayIdentifier=gateway_id
            )['status']

            print(f"Gateway {gateway_id} status {status}")
            if status not in ['READY', 'CREATING']:
                raise Exception(f'Failed to create gateway {name}')
            
            logger.info("AgentCore Gateway provisioning completed successfully")
            
            return {
                'gateway_id': gateway_id,
                'gateway_arn': create_response['gatewayArn'],
                'gateway_url': create_response['gatewayUrl'],
                'name': create_response['name'],
                'status': create_response['status'],
                'created_at': create_response['createdAt'].isoformat() if 'createdAt' in create_response else None,
                'updated_at': create_response['updatedAt'].isoformat() if 'updatedAt' in create_response else None
            }
        
        except Exception as create_error:
            print(f"ERROR: {str(create_error)}")
            if "already exists" in str(create_error):
                print(f"Gateway {name} already exists")
                gateways = agentcore_control_client.list_gateways()['items']
                for gateway in gateways:
                    if gateway['name'] == name:
                        print(f"Found existing gateway {gateway}")
                        # Get full gateway details using get_gateway
                        full_gateway = agentcore_control_client.get_gateway(
                            gatewayIdentifier=gateway['gatewayId']
                        )
                        return {
                            'gateway_id': full_gateway['gatewayId'],
                            'gateway_arn': full_gateway['gatewayArn'],
                            'gateway_url': full_gateway.get('gatewayUrl', ''),
                            'name': full_gateway['name'],
                            'status': full_gateway['status'],
                            'created_at': full_gateway['createdAt'].isoformat() if 'createdAt' in full_gateway else None,
                            'updated_at': full_gateway['updatedAt'].isoformat() if 'updatedAt' in full_gateway else None
                        }
            else:
                logger.error(f"Could not create gateway resource: {str(create_error)}")
                raise create_error
            
    @staticmethod
    def delete_gateway(gateway_id: str) -> Dict[str, Any]:
        """
        Delete a Bedrock AgentCore Gateway resource.
        
        Args:
            gateway_id: ID of the gateway resource to delete
            
        Returns:
            Dictionary indicating success
        """
        print(f"Deleting gateway with id {gateway_id}")
        try:
            # Delete the gateway resource 
            agentcore_control_client.delete_gateway(
                gatewayIdentifier=gateway_id
            )
            
            print(f"Successfully deleted gateway resource with ID: {gateway_id}")
            return {'gateway_id': gateway_id, 'status': 'DELETING'}
            
        except Exception as e:
            logger.error(f"Error deleting AgentCore Gateway resource: {str(e)}")
            raise e

    @staticmethod
    def get_gateway(gateway_id: str) -> Dict[str, Any]:
        """
        Get a Bedrock AgentCore Gateway resource.
        
        Args:
            gateway_id: ID of the gateway resource to retrieve
            
        Returns:
            Dictionary with gateway details
        """
        print(f"Retrieving gateway with id {gateway_id}")
        try:
            # Get the gateway resource 
            response = agentcore_control_client.get_gateway(
                gatewayIdentifier=gateway_id
            )
            
            print(f"Successfully retrieved gateway resource with ID: {gateway_id}")
            return {
                'gateway_id': response['gatewayId'],
                'gateway_arn': response['gatewayArn'],
                'gateway_url': response.get('gatewayUrl', ''),
                'name': response['name'],
                'description': response.get('description', ''),
                'status': response['status'],
                'role_arn': response['roleArn'],
                'protocol_type': response['protocolType'],
                'protocol_configuration': response.get('protocolConfiguration', {}),
                'authorizer_type': response['authorizerType'],
                'authorizer_configuration': response.get('authorizerConfiguration', {}),
                'created_at': response['createdAt'].isoformat() if 'createdAt' in response else None,
                'updated_at': response['updatedAt'].isoformat() if 'updatedAt' in response else None
            }
            
        except Exception as e:
            logger.error(f"Error retrieving AgentCore Gateway resource: {str(e)}")
            raise e
    
    @staticmethod
    def list_gateways(
        max_results: Optional[int] = None,
        next_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List AgentCore Gateway resources.
        
        Args:
            max_results: Maximum number of results to return
            next_token: Token for pagination
            
        Returns:
            Dictionary with a list of Gateway resources
        """
        print(f"Listing gateways with max_results={max_results}, next_token={next_token}")
        try:
            # Prepare parameters for list_gateways call
            list_params = {}
            if max_results:
                list_params['maxResults'] = max_results
            if next_token:
                list_params['nextToken'] = next_token
                
            print(f"Listing gateways with params: {list_params}")
            
            # List all gateway resources
            response = agentcore_control_client.list_gateways(**list_params)
            gateways = response.get('items', [])
            
            print(f"Successfully retrieved {len(gateways)} gateway resources")
            
            gateway_entries = []
            for gateway in gateways:
                print(f"Got gateway: {gateway}")
                entry = {
                    'gateway_id': gateway['gatewayId'],
                    'gateway_arn': gateway.get('gatewayArn', ''),
                    'gateway_url': gateway.get('gatewayUrl', ''),
                    'name': gateway['name'],
                    'status': gateway['status'],
                    'created_at': gateway['createdAt'].isoformat() if 'createdAt' in gateway else None,
                    'updated_at': gateway['updatedAt'].isoformat() if 'updatedAt' in gateway else None
                }
                gateway_entries.append(entry)
                
            print(f"list_gateways returning gateways {gateway_entries}")
            return {
                'gateways': gateway_entries,
                'next_token': response.get('nextToken')
            }
            
        except Exception as e:
            logger.error(f"Error listing AgentCore Gateway resources: {str(e)}")
            raise e

    @staticmethod
    def update_gateway(
        gateway_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        role_arn: Optional[str] = None,
        protocol_configuration: Optional[Dict[str, Any]] = None,
        authorizer_configuration: Optional[Dict[str, Any]] = None,
        kms_key_arn: Optional[str] = None,
        exception_level: Optional[str] = None,
        client_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update a Bedrock AgentCore Gateway resource.
        
        Args:
            gateway_id: ID of the gateway resource to update
            name: Optional new name for the gateway
            description: Optional new description for the gateway
            role_arn: Optional new IAM role ARN
            protocol_configuration: Optional new protocol configuration
            authorizer_configuration: Optional new authorizer configuration
            kms_key_arn: Optional new KMS key ARN
            exception_level: Optional new exception level
            client_token: Optional unique token for idempotency
            
        Returns:
            Updated gateway details
        """
        print(f"Updating AgentCore Gateway resource with ID: {gateway_id}")
        try:
            # First get current gateway details to ensure we have all required parameters
            current_gateway = agentcore_control_client.get_gateway(
                gatewayIdentifier=gateway_id
            )
            
            # Prepare update parameters with required fields from current gateway
            update_params = {
                'gatewayIdentifier': gateway_id,
                # AWS requires these parameters even for updates
                'name': name if name is not None else current_gateway['name'],
                'roleArn': role_arn if role_arn is not None else current_gateway['roleArn'],
                'protocolType': current_gateway['protocolType'],  # This cannot be changed
                'authorizerType': current_gateway['authorizerType'],  # This cannot be changed
                'authorizerConfiguration': authorizer_configuration if authorizer_configuration is not None else current_gateway.get('authorizerConfiguration', {})
            }
            
            # Add optional parameters
            if description is not None:
                update_params['description'] = description
                logger.info(f"Updating description to: {description}")
            elif current_gateway.get('description'):
                update_params['description'] = current_gateway['description']
                
            if protocol_configuration is not None:
                update_params['protocolConfiguration'] = protocol_configuration
                logger.info(f"Updating protocol configuration")
            elif current_gateway.get('protocolConfiguration'):
                update_params['protocolConfiguration'] = current_gateway['protocolConfiguration']
                
            if kms_key_arn is not None:
                update_params['kmsKeyArn'] = kms_key_arn
                logger.info(f"Updating KMS key ARN to: {kms_key_arn}")
            elif current_gateway.get('kmsKeyArn'):
                update_params['kmsKeyArn'] = current_gateway['kmsKeyArn']
                
            if exception_level is not None:
                update_params['exceptionLevel'] = exception_level
                logger.info(f"Updating exception level to: {exception_level}")
            elif current_gateway.get('exceptionLevel'):
                update_params['exceptionLevel'] = current_gateway['exceptionLevel']
                
            if client_token is not None:
                update_params['clientToken'] = client_token
                
            logger.info(f"Updating gateway with parameters: {update_params}")
            
            # Update the gateway resource
            response = agentcore_control_client.update_gateway(**update_params)
            logger.info(f"Successfully updated gateway resource with ID: {response['gatewayId']}")
            print(f"update_gateway response {response}")
            
            return {
                'gateway_id': response['gatewayId'],
                'gateway_arn': response['gatewayArn'],
                'gateway_url': response.get('gatewayUrl', ''),
                'name': response['name'],
                'description': response.get('description', ''),
                'status': response['status'],
                'role_arn': response['roleArn'],
                'protocol_type': response['protocolType'],
                'protocol_configuration': response.get('protocolConfiguration', {}),
                'authorizer_type': response['authorizerType'],
                'authorizer_configuration': response.get('authorizerConfiguration', {}),
                'created_at': response['createdAt'].isoformat() if 'createdAt' in response else None,
                'updated_at': response['updatedAt'].isoformat() if 'updatedAt' in response else None
            }
            
        except Exception as e:
            logger.error(f"Error updating Gateway resource: {str(e)}")
            raise e

    @staticmethod
    def wait_for_gateway_creation(
        gateway_id: str,
        max_attempts: int = 20,
        delay_seconds: int = 15
    ) -> Dict[str, Any]:
        """
        Wait for gateway creation to complete.
        
        Args:          
            gateway_id: Gateway ID to check
            max_attempts: Maximum number of polling attempts
            delay_seconds: Delay between polling attempts in seconds
            
        Returns:
            Gateway details when available
            
        Raises:
            TimeoutError: If the gateway creation doesn't complete within the timeout period
        """
        print(f"Called wait_for_gateway_creation for gateway {gateway_id}")
        logger.info(f"Waiting for gateway {gateway_id} to be fully created...")
        
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Attempt {attempt}")
                # Try to get the gateway details
                gateway_details = agentcore_control_client.get_gateway(
                    gatewayIdentifier=gateway_id
                )
                print(f"Got gateway details {gateway_details}")

                status = gateway_details['status']
                # Check if the gateway exists and has all expected attributes
                if status == 'READY':
                    logger.info(f"Gateway {gateway_id} is now available after {attempt} attempts")
                    print(f"wait_for_gateway_creation returning gateway_details {gateway_details}")
                    return {
                        'gateway_id': gateway_details['gatewayId'],
                        'gateway_arn': gateway_details['gatewayArn'],
                        'gateway_url': gateway_details.get('gatewayUrl', ''),
                        'name': gateway_details['name'],
                        'status': gateway_details['status'],
                        'created_at': gateway_details['createdAt'].isoformat() if 'createdAt' in gateway_details else None,
                        'updated_at': gateway_details['updatedAt'].isoformat() if 'updatedAt' in gateway_details else None
                    }
                else:
                    print(f"Gateway status: {status} (waiting {delay_seconds} seconds to check again)")
                    
            except Exception as e:
                if "Gateway not found" in str(e) or "does not exist" in str(e):
                    logger.info(f"Attempt {attempt}/{max_attempts}: Gateway {gateway_id} not yet available")
                else:
                    logger.warning(f"Unexpected error checking gateway: {str(e)}")
            
            # Wait before the next attempt
            if attempt < max_attempts:
                for t in range(1, delay_seconds + 1):
                    print('.', end='')
                time.sleep(1)
                print()  # New line after dots
        
        raise TimeoutError(f"Gateway {gateway_id} did not become available within the timeout period")

    @staticmethod
    def wait_for_gateway_deletion(
        gateway_id: str,
        max_attempts: int = 20,
        delay_seconds: int = 15
    ) -> bool:
        """
        Wait for gateway deletion to complete.
        
        Args:
            gateway_id: Gateway ID that was deleted
            max_attempts: Maximum number of polling attempts
            delay_seconds: Delay between polling attempts in seconds
            
        Returns:
            Boolean indicating if the gateway was successfully deleted
            
        Raises:
            TimeoutError: If the gateway deletion doesn't complete within the timeout period
        """
        logger.info(f"Waiting for gateway {gateway_id} to be fully deleted...")
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Try to get the gateway details - this should eventually fail
                gateway_details = agentcore_control_client.get_gateway(
                    gatewayIdentifier=gateway_id
                )
                
                # If we get here, the gateway still exists
                logger.info(f"Attempt {attempt}/{max_attempts}: Gateway {gateway_id} still exists")
                
            except Exception as e:
                if "Gateway not found" in str(e) or "does not exist" in str(e):
                    logger.info(f"Gateway {gateway_id} successfully deleted after {attempt} attempts")
                    return True
                else:
                    logger.warning(f"Unexpected error checking gateway deletion: {str(e)}")
            
            # Wait before the next attempt
            if attempt < max_attempts:
                time.sleep(delay_seconds)
        
        raise TimeoutError(f"Gateway {gateway_id} was not deleted within the timeout period")
