#!/usr/bin/env python3
"""
Create a test user specifically for AgentCore Runtime testing.

This script creates a Cognito user with appropriate permissions for testing
AgentCore runtime functionality, including authentication and authorization.
"""

import boto3
import os
import argparse
import sys
import random
import string
import json
from botocore.exceptions import ClientError

def generate_random_string(length=8):
    """Generate a random string of letters and digits"""
    characters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def generate_random_email():
    """Generate a random email address for testing"""
    username = f"agentcore-test-{generate_random_string(8)}"
    domain = "example.com"
    return f"{username}@{domain}"

def get_terraform_outputs():
    """Attempt to get Terraform outputs for Cognito configuration"""
    try:
        import subprocess
        result = subprocess.run([
            'terraform', 'output', '-json'
        ], capture_output=True, text=True, cwd='../infrastructure/terraform')
        
        if result.returncode == 0:
            outputs = json.loads(result.stdout)
            return {
                'user_pool_id': outputs.get('cognito_user_pool_id', {}).get('value'),
                'user_client_id': outputs.get('cognito_user_client_id', {}).get('value'),
                'm2m_client_id': outputs.get('cognito_m2m_client_id', {}).get('value'),
                'super_admin_group': outputs.get('cognito_super_admin_group_name', {}).get('value'),
                'platform_admin_group': outputs.get('cognito_platform_admin_group_name', {}).get('value'),
                'platform_user_group': outputs.get('cognito_platform_user_group_name', {}).get('value'),
                'oauth_token_endpoint': outputs.get('oauth_token_endpoint', {}).get('value'),
                'm2m_secret_arn': outputs.get('m2m_credentials_secret_arn', {}).get('value')
            }
    except Exception as e:
        print(f"Warning: Could not get Terraform outputs: {e}")
        return {}
    
    return {}

def create_agentcore_test_user(
    user_pool_id=None,
    email=None, 
    password=None, 
    user_group="platform_user",
    auto_confirm=True, 
    set_permanent_password=True
):
    """Create a test user specifically for AgentCore testing"""
    
    # Try to get values from Terraform outputs first
    tf_outputs = get_terraform_outputs()
    
    # Use provided values, terraform outputs, or environment variables
    user_pool_id = user_pool_id or tf_outputs.get('user_pool_id') or os.environ.get("COGNITO_USER_POOL_ID")
    
    # Generate random values if not provided
    email = email or generate_random_email()
    temporary_password = generate_random_string(12) + "Aa1!"  # Ensure it meets complexity requirements
    permanent_password = password or generate_random_string(12) + "Bb2@"  # Test password for debugging locally
    
    # In this user pool, username must be an email
    username = email
    
    # Check if we have the required user pool ID
    if not user_pool_id:
        print("Error: Missing COGNITO_USER_POOL_ID")
        print("Please provide it as an argument, ensure Terraform is deployed, or set as environment variable.")
        print("\nIf Terraform is deployed, make sure you're running this from the correct directory:")
        print("  cd sample-agentic-platform/script")
        print("  python create_agentcore_test_user.py")
        sys.exit(1)
    
    try:
        # Create Cognito client
        client = boto3.client('cognito-idp')
        
        # Create the user
        print(f"\n🔧 Creating AgentCore test user with email: {email}")
        client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=email,
            TemporaryPassword=temporary_password,
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': email
                },
                {
                    'Name': 'email_verified',
                    'Value': 'true' if auto_confirm else 'false'
                }
            ],
            MessageAction='SUPPRESS'  # Don't send welcome email
        )
        print(f"✅ User created successfully")
        
        # Auto-confirm the user if requested
        if auto_confirm:
            print("🔐 Auto-confirming user...")
            client.admin_update_user_attributes(
                UserPoolId=user_pool_id,
                Username=email,
                UserAttributes=[
                    {
                        'Name': 'email_verified',
                        'Value': 'true'
                    }
                ]
            )
            print("✅ User confirmed")
        
        # Set permanent password if requested
        if set_permanent_password:
            print("🔑 Setting permanent password...")
            client.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=email,
                Password=permanent_password,
                Permanent=True
            )
            print("✅ Permanent password set")
        
        # Add user to specified group for AgentCore access
        group_name = user_group
        if tf_outputs.get(f'{user_group}_group'):
            group_name = tf_outputs[f'{user_group}_group']
        
        try:
            print(f"👥 Adding user to group: {group_name}")
            client.admin_add_user_to_group(
                UserPoolId=user_pool_id,
                Username=email,
                GroupName=group_name
            )
            print(f"✅ User added to {group_name} group")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"⚠️  Warning: Group '{group_name}' not found. User created without group membership.")
                print("Available groups might be: super_admin, platform_admin, platform_user")
            else:
                print(f"⚠️  Warning: Could not add user to group: {str(e)}")
        
        # Save user info to file for future reference
        user_info = {
            "user_pool_id": user_pool_id,
            "username": email,  # Username is the email
            "email": email,
            "password": permanent_password if set_permanent_password else temporary_password,
            "is_permanent_password": set_permanent_password,
            "user_group": group_name,
            "terraform_outputs": tf_outputs
        }
        
        # Save to file
        output_file = f"agentcore_test_user_{generate_random_string(4)}.json"
        with open(output_file, 'w') as f:
            json.dump(user_info, f, indent=2)
        
        print("\n" + "="*60)
        print("🎉 AGENTCORE TEST USER CREATED SUCCESSFULLY")
        print("="*60)
        print(f"📧 Email/Username: {email}")
        print(f"🔒 Password: {permanent_password if set_permanent_password else temporary_password}")
        print(f"👥 Group: {group_name}")
        print(f"✅ Status: {'Confirmed' if auto_confirm else 'Unconfirmed'}")
        print(f"📁 User info saved to: {output_file}")
        
        # Provide next steps
        print("\n" + "="*60)
        print("📋 NEXT STEPS FOR AGENTCORE TESTING")
        print("="*60)
        
        if tf_outputs.get('user_client_id'):
            print("\n1️⃣  Get User Authentication Token:")
            print(f"   python script/get_auth_token.py \\")
            print(f"     --username '{email}' \\")
            print(f"     --password '{permanent_password if set_permanent_password else temporary_password}' \\")
            print(f"     --client-id '{tf_outputs['user_client_id']}'")
        
        if tf_outputs.get('m2m_secret_arn'):
            print("\n2️⃣  Get M2M Token (for service-to-service calls):")
            print(f"   python script/get_m2m_token.py \\")
            print(f"     --secret-arn '{tf_outputs['m2m_secret_arn']}'")
        
        print("\n3️⃣  Test AgentCore Runtime API:")
        print("   # First get a token using step 1 or 2, then:")
        print("   curl -H \"Authorization: Bearer <your_token>\" \\")
        print("        -H \"Content-Type: application/json\" \\")
        print("        https://your-agentcore-endpoint/runtimes")
        
        print("\n4️⃣  Create AgentCore Runtime:")
        print("   # Use the AgentCore runtime client to create a test runtime")
        print("   # See tests-agentcore/test_agentcore_runtime_client.py for examples")
        
        if not tf_outputs:
            print("\n⚠️  Note: Some configuration values are missing because Terraform")
            print("   outputs are not available. Make sure the infrastructure is deployed:")
            print("   cd infrastructure/terraform && terraform apply")
        
        return user_info
        
    except Exception as e:
        print(f"❌ Error creating user: {str(e)}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='Create a test user for AgentCore Runtime testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a user with auto-detected configuration
  python create_agentcore_test_user.py

  # Create a user with specific email and assign to admin group
  python create_agentcore_test_user.py --email admin@example.com --user-group platform_admin

  # Create a user with manual configuration
  python create_agentcore_test_user.py --user-pool-id us-west-2_XXXXXXXXX --email test@example.com

User Groups:
  - super_admin: Full system access for AgentCore operations
  - platform_admin: Administrative access for AgentCore management  
  - platform_user: Standard user access for AgentCore usage (default)
        """
    )
    
    parser.add_argument('--user-pool-id', 
                       help='Cognito user pool ID (auto-detected from Terraform if available)')
    parser.add_argument('--email', 
                       help='Email address (random if not provided)')
    parser.add_argument('--password', 
                       help='Password (random if not provided)')
    parser.add_argument('--user-group', 
                       choices=['super_admin', 'platform_admin', 'platform_user'],
                       default='platform_user',
                       help='User group for AgentCore access (default: platform_user)')
    parser.add_argument('--no-auto-confirm', 
                       action='store_true', 
                       help='Do not auto-confirm the user')
    parser.add_argument('--no-set-permanent-password', 
                       action='store_true',
                       help='Do not set a permanent password (leave as temporary)')
    
    args = parser.parse_args()
    
    # Create user
    user_info = create_agentcore_test_user(
        user_pool_id=args.user_pool_id,
        email=args.email,
        password=args.password,
        user_group=args.user_group,
        auto_confirm=not args.no_auto_confirm,
        set_permanent_password=not args.no_set_permanent_password
    )
    
    print("\n🚀 AgentCore test user is ready for testing!")

if __name__ == "__main__":
    main()
