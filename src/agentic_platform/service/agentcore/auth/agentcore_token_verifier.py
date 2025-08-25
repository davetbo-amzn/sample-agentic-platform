"""
AgentCore Token Verifier

NOTE: This file is intentionally minimal. 

For AgentCore authentication, we reuse the CognitoTokenVerifier since AWS Bedrock AgentCore 
uses Cognito JWTs behind the scenes. The AuthProviderFactory has been configured to use 
CognitoTokenVerifier for both AGENTPATH and AGENTCORE auth providers.

The differentiation between AgentPath and AgentCore authentication happens in the 
token auth converters:
- CognitoTokenAuthConverter: For AGENTPATH provider  
- AgentCoreTokenAuthConverter: For AGENTCORE provider (with workload token integration)

See: 
- agentic_platform.core.middleware.auth.cognito_token_verifier.CognitoTokenVerifier
- agentic_platform.core.middleware.auth.agentcore_token_auth_converter.AgentCoreTokenAuthConverter
"""

# This file is intentionally empty - see note above
