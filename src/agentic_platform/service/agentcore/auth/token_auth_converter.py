from abc import ABC, abstractmethod
from typing import Any
from agentic_platform.core.models.auth_models import AgenticPlatformAuth
from .auth_provider_factory import AuthProviderFactory

token_converter_class = AuthProviderFactory.get_token_auth_converter()
class TokenAuthConverter:
    @staticmethod
    def convert_token(token_payload: Any) -> AgenticPlatformAuth:
        print(f'TokenAuthConverter.convert_token received {token_payload}')
        return token_converter_class.convert_token(token_payload)
