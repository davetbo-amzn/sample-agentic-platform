from typing import Any, Optional
from .auth_provider_factory import AuthProviderFactory

token_verifier_class = AuthProviderFactory.get_token_verifier()
class TokenVerifier:
    @staticmethod
    def validate_token(token: str, **kwargs) -> Optional[Any]:
        return token_verifier_class.validate_token(token)

