"""
JWT Token Generation Utilities for Testing

This module contains JWT token generation functionality that should only be used
in test environments. These methods handle Cognito authentication for testing
AgentCore Runtime functionality.
"""

import os
import boto3
import hmac
import hashlib
import base64
import logging

logger = logging.getLogger(__name__)

# Get environment variables
REGION = os.environ.get('REGION', 'us-west-2')


class JWTTestUtils:
    """Utility class for generating JWT tokens in test environments."""
    
    @staticmethod
    def calculate_secret_hash(username: str, client_id: str, client_secret: str) -> str:
        """
        Calculate the SECRET_HASH for Cognito authentication.
        
        Args:
            username: Cognito username
            client_id: Cognito client ID
            client_secret: Cognito client secret
            
        Returns:
            Base64 encoded secret hash
        """
        message = bytes(username + client_id, 'utf-8')
        key = bytes(client_secret, 'utf-8')
        secret_hash = base64.b64encode(hmac.new(key, message, digestmod=hashlib.sha256).digest()).decode()
        return secret_hash

    @staticmethod
    def generate_fresh_jwt_token() -> str:
        """
        Generate a fresh JWT token from Cognito credentials for testing.
        
        This method should only be used in test environments as it requires
        Cognito credentials to be available in environment variables.
        
        Returns:
            Fresh JWT access token
            
        Raises:
            Exception: If token generation fails
        """
        # Get Cognito credentials from environment
        client_id = os.environ.get("COGNITO_CLIENT_ID")
        username = os.environ.get("COGNITO_USERNAME") 
        password = os.environ.get("COGNITO_PASSWORD")
        client_secret = os.environ.get("COGNITO_CLIENT_SECRET")
        
        # Check if we have all required values
        if not all([client_id, username, password]):
            missing = []
            if not client_id: missing.append("COGNITO_CLIENT_ID")
            if not username: missing.append("COGNITO_USERNAME")
            if not password: missing.append("COGNITO_PASSWORD")
            
            raise Exception(f"Missing required Cognito credentials: {', '.join(missing)}")
        
        try:
            # Create Cognito client
            cognito_client = boto3.client('cognito-idp', region_name=REGION)
            
            # Prepare authentication parameters
            auth_parameters = {
                'USERNAME': username,
                'PASSWORD': password
            }
            
            # Add SECRET_HASH if client secret is provided
            if client_secret:
                secret_hash = JWTTestUtils.calculate_secret_hash(username, client_id, client_secret)
                auth_parameters['SECRET_HASH'] = secret_hash
            
            # Try authentication with current parameters
            try:
                response = cognito_client.initiate_auth(
                    ClientId=client_id,
                    AuthFlow='USER_PASSWORD_AUTH',
                    AuthParameters=auth_parameters
                )
            except cognito_client.exceptions.NotAuthorizedException as e:
                if "SECRET_HASH was not received" in str(e):
                    raise Exception("Client requires SECRET_HASH but COGNITO_CLIENT_SECRET not provided.")
                else:
                    raise e
            
            # Extract and return the token
            token = response['AuthenticationResult']['AccessToken']
            logger.info("Successfully generated fresh JWT token from Cognito for testing")
            return token
            
        except Exception as e:
            logger.error(f"Error generating fresh JWT token for testing: {str(e)}")
            raise Exception(f"Failed to generate fresh JWT token for testing: {str(e)}")
