#!/usr/bin/env python3
"""
Diagnostic script for JWT authentication issues with AgentCore Runtime.

This script performs comprehensive diagnostics to identify JWT authentication
problems by examining:
1. JWT token generation and claims
2. Cognito configuration and discovery endpoint
3. Runtime configuration and allowed clients
4. Token validation and expiry
"""

import os
import sys
import json
import base64
import boto3
import requests
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, '../src')
sys.path.insert(0, '../script')

from agentic_platform.service.agentcore.runtime.client.agentcore_runtime_client import AgentCoreRuntimeClient
from agentic_platform.service.agentcore.types import ListAgentRuntimesRequest, GetAgentRuntimeRequest
from jwt_test_utils import JWTTestUtils

def load_env_file():
    """Load environment variables from .env file"""
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        print("Loading environment variables from .env file...")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove 'export ' prefix if present
                    if key.startswith('export '):
                        key = key[7:]
                    if key not in os.environ:
                        os.environ[key] = value
        print("Environment variables loaded.")
    else:
        print("No .env file found.")

def decode_jwt_token(token):
    """Decode JWT token and return header and payload"""
    try:
        # Split the token into parts
        parts = token.split('.')
        if len(parts) != 3:
            return None, None, "Invalid JWT format - should have 3 parts"
        
        # Decode header
        header_padding = '=' * (4 - len(parts[0]) % 4)
        header_data = base64.urlsafe_b64decode(parts[0] + header_padding)
        header = json.loads(header_data.decode('utf-8'))
        
        # Decode payload
        payload_padding = '=' * (4 - len(parts[1]) % 4)
        payload_data = base64.urlsafe_b64decode(parts[1] + payload_padding)
        payload = json.loads(payload_data.decode('utf-8'))
        
        return header, payload, None
    except Exception as e:
        return None, None, f"Error decoding JWT: {str(e)}"

def check_cognito_discovery_url(discovery_url):
    """Check if the Cognito discovery URL is accessible and returns valid configuration"""
    try:
        print(f"\nTesting Cognito discovery URL: {discovery_url}")
        response = requests.get(discovery_url, timeout=10)
        response.raise_for_status()
        
        config = response.json()
        print("✅ Discovery URL accessible")
        print(f"   Issuer: {config.get('issuer', 'NOT FOUND')}")
        print(f"   JWKS URI: {config.get('jwks_uri', 'NOT FOUND')}")
        print(f"   Token endpoint: {config.get('token_endpoint', 'NOT FOUND')}")
        print(f"   Supported algorithms: {config.get('id_token_signing_alg_values_supported', 'NOT FOUND')}")
        
        return config
    except Exception as e:
        print(f"❌ Error accessing discovery URL: {str(e)}")
        return None

def test_jwt_token_generation():
    """Test JWT token generation and examine the token"""
    print("\n" + "="*60)
    print("TESTING JWT TOKEN GENERATION")
    print("="*60)
    
    # Check required environment variables
    required_vars = ['COGNITO_CLIENT_ID', 'COGNITO_USERNAME', 'COGNITO_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        return None
    
    print("✅ All required Cognito credentials found")
    print(f"   Client ID: {os.getenv('COGNITO_CLIENT_ID')}")
    print(f"   Username: {os.getenv('COGNITO_USERNAME')}")
    print(f"   Password: {'*' * len(os.getenv('COGNITO_PASSWORD', ''))}")
    
    try:
        # Generate fresh JWT token
        print("\nGenerating fresh JWT token...")
        token = JWTTestUtils.generate_fresh_jwt_token()
        print(f"✅ JWT token generated successfully")
        print(f"   Token length: {len(token)} characters")
        print(f"   Token preview: {token[:50]}...")
        
        # Decode and examine the token
        print("\nDecoding JWT token...")
        header, payload, error = decode_jwt_token(token)
        
        if error:
            print(f"❌ Error decoding token: {error}")
            return token
        
        print("✅ JWT token decoded successfully")
        print("\n--- JWT HEADER ---")
        print(json.dumps(header, indent=2))
        
        print("\n--- JWT PAYLOAD ---")
        print(json.dumps(payload, indent=2))
        
        # Check important claims
        print("\n--- TOKEN VALIDATION ---")
        current_time = datetime.now(timezone.utc).timestamp()
        
        # Check expiration
        exp = payload.get('exp')
        if exp:
            exp_time = datetime.fromtimestamp(exp, timezone.utc)
            if exp > current_time:
                time_remaining = exp - current_time
                print(f"✅ Token valid for {time_remaining:.0f} more seconds (expires: {exp_time})")
            else:
                print(f"❌ Token is expired (expired: {exp_time})")
        else:
            print("❌ No expiration claim found")
        
        # Check issuer
        iss = payload.get('iss')
        if iss:
            print(f"✅ Issuer: {iss}")
        else:
            print("❌ No issuer claim found")
        
        # Check audience
        aud = payload.get('aud')
        if aud:
            print(f"✅ Audience: {aud}")
        else:
            print("❌ No audience claim found")
        
        # Check client_id
        client_id = payload.get('client_id')
        if client_id:
            print(f"✅ Client ID in token: {client_id}")
            expected_client_id = os.getenv('COGNITO_CLIENT_ID')
            if client_id == expected_client_id:
                print("✅ Client ID matches environment variable")
            else:
                print(f"❌ Client ID mismatch - token: {client_id}, env: {expected_client_id}")
        else:
            print("❌ No client_id claim found")
        
        return token
        
    except Exception as e:
        print(f"❌ Error generating JWT token: {str(e)}")
        return None

def test_cognito_configuration():
    """Test Cognito configuration and discovery endpoint"""
    print("\n" + "="*60)
    print("TESTING COGNITO CONFIGURATION")
    print("="*60)
    
    # Check environment variables
    user_pool_id = os.getenv('USER_POOL_ID')
    client_id = os.getenv('COGNITO_CLIENT_ID')
    region = os.getenv('REGION', 'us-west-2')
    
    if not user_pool_id:
        print("❌ USER_POOL_ID not found")
        return
    
    print(f"✅ User Pool ID: {user_pool_id}")
    print(f"✅ Client ID: {client_id}")
    print(f"✅ Region: {region}")
    
    # Test discovery URL
    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
    config = check_cognito_discovery_url(discovery_url)
    
    if config:
        # Check if issuer matches expected format
        expected_issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        actual_issuer = config.get('issuer')
        if actual_issuer == expected_issuer:
            print("✅ Issuer URL format is correct")
        else:
            print(f"❌ Issuer mismatch - expected: {expected_issuer}, actual: {actual_issuer}")

def get_runtime_configuration(runtime_id=None):
    """Get runtime configuration to check authorized clients"""
    print("\n" + "="*60)
    print("TESTING RUNTIME CONFIGURATION")
    print("="*60)
    
    try:
        # If no runtime_id provided, find test runtimes
        if not runtime_id:
            print("No specific runtime ID provided, searching for test runtimes...")
            list_request = ListAgentRuntimesRequest(maxResults=50)
            list_response = AgentCoreRuntimeClient.list_agent_runtimes(list_request)
            
            test_runtimes = [r for r in list_response.runtimes if r.get('agent_runtime_name', '').startswith('test_invoke_runtime')]
            
            if not test_runtimes:
                print("❌ No test runtimes found")
                return
            
            print(f"✅ Found {len(test_runtimes)} test runtime(s)")
            runtime_id = test_runtimes[0]['agentRuntimeId']
            print(f"   Using runtime: {runtime_id}")
        
        # Get runtime details
        print(f"\nGetting configuration for runtime: {runtime_id}")
        get_request = GetAgentRuntimeRequest(agentRuntimeId=runtime_id)
        runtime_details = AgentCoreRuntimeClient.get_agentcore_runtime(get_request)
        
        print("✅ Runtime details retrieved")
        print(f"   Runtime Name: {runtime_details.agentRuntimeName}")
        print(f"   Status: {runtime_details.status}")
        print(f"   ARN: {runtime_details.agentRuntimeArn}")
        
        # Check authorizer configuration - try multiple ways to access it
        auth_config = None
        
        # Try as attribute first
        if hasattr(runtime_details, 'authorizerConfiguration') and runtime_details.authorizerConfiguration:
            auth_config = runtime_details.authorizerConfiguration
            print("\n✅ Found authorizerConfiguration as attribute")
        # Try as dictionary key if it's a dict-like object
        elif hasattr(runtime_details, '__dict__') and 'authorizerConfiguration' in runtime_details.__dict__:
            auth_config = runtime_details.__dict__['authorizerConfiguration']
            print("\n✅ Found authorizerConfiguration in __dict__")
        # Try accessing the raw response if available
        elif hasattr(runtime_details, '_raw_response'):
            raw_response = runtime_details._raw_response
            if 'authorizerConfiguration' in raw_response:
                auth_config = raw_response['authorizerConfiguration']
                print("\n✅ Found authorizerConfiguration in raw response")
        
        if auth_config:
            print("\n--- AUTHORIZER CONFIGURATION ---")
            print(json.dumps(auth_config, indent=2, default=str))
            
            # Check JWT authorizer specifically
            if 'customJWTAuthorizer' in auth_config:
                jwt_config = auth_config['customJWTAuthorizer']
                print("\n✅ Custom JWT Authorizer found")
                
                discovery_url = jwt_config.get('discoveryUrl')
                allowed_clients = jwt_config.get('allowedClients', [])
                
                print(f"   Discovery URL: {discovery_url}")
                print(f"   Allowed Clients: {allowed_clients}")
                
                # Check if our client ID is in allowed clients
                our_client_id = os.getenv('COGNITO_CLIENT_ID')
                if our_client_id in allowed_clients:
                    print(f"✅ Our client ID ({our_client_id}) is in allowed clients")
                else:
                    print(f"❌ Our client ID ({our_client_id}) is NOT in allowed clients")
                    print(f"   This is likely the cause of the authentication failure!")
                
                # Test the discovery URL from runtime config
                if discovery_url:
                    check_cognito_discovery_url(discovery_url)
            else:
                print("❌ No customJWTAuthorizer configuration found")
        else:
            print("❌ No authorizerConfiguration found")
            print("   Let me check if it's in the raw API response...")
            # As a fallback, let's examine what we actually got
            print(f"   Runtime details type: {type(runtime_details)}")
            if hasattr(runtime_details, '__dict__'):
                available_attrs = [attr for attr in dir(runtime_details) if not attr.startswith('_')]
                print(f"   Available attributes: {available_attrs}")
        
        return runtime_details
        
    except Exception as e:
        print(f"❌ Error getting runtime configuration: {str(e)}")
        return None

def test_runtime_invocation(token, runtime_arn):
    """Test runtime invocation with the generated token"""
    print("\n" + "="*60)
    print("TESTING RUNTIME INVOCATION")
    print("="*60)
    
    if not token or not runtime_arn:
        print("❌ Missing token or runtime ARN for invocation test")
        return
    
    try:
        from agentic_platform.service.agentcore.types import InvokeAgentRuntimeRequest
        
        print(f"Testing invocation with runtime: {runtime_arn}")
        
        # Prepare test request
        test_payload = {"message": "Diagnostic test", "timestamp": datetime.now().isoformat()}
        request = InvokeAgentRuntimeRequest(
            agentRuntimeArn=runtime_arn,
            payload=test_payload
        )
        
        # Try invocation
        print("Attempting runtime invocation...")
        response = AgentCoreRuntimeClient.invoke_agentcore_runtime(request)
        
        print(f"✅ Invocation successful!")
        print(f"   Status Code: {response.statusCode}")
        print(f"   Content Type: {response.contentType}")
        
    except Exception as e:
        print(f"❌ Invocation failed: {str(e)}")
        # Extract more specific error information
        if "424" in str(e):
            print("   This is a 424 Failed Dependency error - likely JWT configuration issue")
        elif "AccessDeniedException" in str(e):
            print("   This is an Access Denied error - likely client not in allowed list")

def main():
    """Main diagnostic function"""
    print("JWT AUTHENTICATION DIAGNOSTICS")
    print("=" * 60)
    print(f"Timestamp: {datetime.now()}")
    print(f"Working Directory: {os.getcwd()}")
    
    # Load environment
    load_env_file()
    
    # Run diagnostics in sequence
    token = test_jwt_token_generation()
    test_cognito_configuration()
    runtime_details = get_runtime_configuration()
    
    # If we have both token and runtime, test invocation
    if token and runtime_details:
        test_runtime_invocation(token, runtime_details.agentRuntimeArn)
    
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    print("Review the output above to identify authentication issues.")
    print("Key things to check:")
    print("1. JWT token generation successful and not expired")
    print("2. Client ID in token matches COGNITO_CLIENT_ID environment variable")
    print("3. Runtime's allowedClients list includes our client ID")
    print("4. Discovery URLs are accessible and match between token issuer and runtime config")

if __name__ == "__main__":
    main()
