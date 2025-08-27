#!/usr/bin/env python3
"""
Create a Cognito User Pool Client without client secret for testing purposes.
"""

import boto3
import sys
import os
import argparse

def create_app_client(user_pool_id, client_name="agentcore-test-client"):
    """Create a new Cognito User Pool Client without client secret."""
    try:
        client = boto3.client('cognito-idp')
        
        response = client.create_user_pool_client(
            UserPoolId=user_pool_id,
            ClientName=client_name,
            GenerateSecret=False,  # This is key - no client secret
            ExplicitAuthFlows=[
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH'
            ],
            SupportedIdentityProviders=['COGNITO'],
            PreventUserExistenceErrors='ENABLED'
        )
        
        client_id = response['UserPoolClient']['ClientId']
        print(f"✅ Successfully created Cognito app client:")
        print(f"   Client ID: {client_id}")
        print(f"   Client Name: {client_name}")
        print(f"   User Pool ID: {user_pool_id}")
        print(f"   Generate Secret: False")
        print()
        print("You can now use this client ID for JWT authentication without requiring a client secret.")
        print(f"Update your .env file with: COGNITO_CLIENT_ID={client_id}")
        
        return client_id
        
    except Exception as e:
        print(f"❌ Error creating app client: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create Cognito User Pool Client without secret')
    parser.add_argument('--user-pool-id', required=True, help='Cognito User Pool ID')
    parser.add_argument('--client-name', default='agentcore-test-client', help='Name for the app client')
    
    args = parser.parse_args()
    
    create_app_client(args.user_pool_id, args.client_name)
