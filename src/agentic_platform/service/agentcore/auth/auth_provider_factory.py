import os
from importlib import import_module

from agentic_platform.core.models.auth_models import AuthProviderType

class AuthProviderFactory: 
    # def get_auth_provider(auth_provider_type: AuthProviderType=AuthProviderType.AGENTPATH) : 
    @staticmethod
    def get_token_verifier():
        # Both AGENTPATH and AGENTCORE use CognitoTokenVerifier since AgentCore uses Cognito JWTs
        token_verifier_path = 'agentic_platform.core.middleware.auth.cognito_token_verifier.CognitoTokenVerifier'
        parts = token_verifier_path.split('.')
        client_file = '.'.join(parts[:-1])
        client_classname = parts[-1]
        client_module = import_module(client_file)
        return getattr(client_module, client_classname)

    def get_token_auth_converter():
        auth_provider_config = os.getenv('AUTH_PROVIDER', 'AGENTPATH')
        auth_provider_type = AuthProviderType(auth_provider_config)
        # Only the converter differs between providers
        token_auth_converter_path = 'agentic_platform.core.middleware.auth.cognito_token_auth_converter.CognitoTokenAuthConverter' \
            if auth_provider_type == AuthProviderType.AGENTPATH \
            else 'agentic_platform.core.middleware.auth.agentcore_token_auth_converter.AgentCoreTokenAuthConverter'
        parts = token_auth_converter_path.split('.')
        client_file = '.'.join(parts[:-1])
        client_classname = parts[-1]
        client_module = import_module(client_file)
        return getattr(client_module, client_classname)
       
