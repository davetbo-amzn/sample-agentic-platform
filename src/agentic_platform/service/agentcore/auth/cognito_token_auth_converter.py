import os
from typing import Any

from agentic_platform.core.models.auth_models import AgenticPlatformAuth, UserAuth, ServiceAuth

M2M_CLIENT_ID = os.getenv("COGNITO_M2M_CLIENT_ID")
USER_CLIENT_ID = os.getenv("COGNITO_USER_CLIENT_ID")


class CognitoTokenAuthConverter:
    @classmethod
    def convert_user_token(cls, token_payload: Any) -> UserAuth:
        user_auth: UserAuth = UserAuth(
            user_id=token_payload.get('sub'),
            username=token_payload.get('username'),
            email=token_payload.get('email'),
            groups=token_payload.get('groups', []),
            provider="cognito",
            metadata=token_payload
        )
        print(f"convert_user_token got user auth {user_auth}")
        return AgenticPlatformAuth.from_user(user_auth)
    
    @classmethod
    def convert_m2m_token(cls, token_payload: Any, headers: dict = None) -> AgenticPlatformAuth:
        service_id = headers.get('X-Service-ID', 'NONE')
        service_auth: ServiceAuth = ServiceAuth(
            service_id=service_id if service_id != 'NONE' else token_payload.get('client_id'),
            name=token_payload.get('name', 'NONE'),
            namespace=token_payload.get('namespace', 'NONE'),
            groups=token_payload.get('groups', []),
            provider="cognito",
            metadata=token_payload
        )

        return AgenticPlatformAuth.from_service(service_auth)

    @classmethod
    def convert_token(cls, token_payload: Any, headers: dict = None) -> AgenticPlatformAuth:
        print(f"convert_token got token_payload {token_payload}, headers {headers}")
        client_id = token_payload.get('client_id')

        if client_id == M2M_CLIENT_ID:
            print("got M2M client ID")
            return cls.convert_m2m_token(token_payload, headers)
        elif client_id == USER_CLIENT_ID:
            print(f"got User client ID {client_id}")
            return cls.convert_user_token(token_payload)
        print(f"Shouldn't have gotten here. Got an unexpected client ID:\n received: {client_id}\nM2M: {M2M_CLIENT_ID}\nUSER: {USER_CLIENT_ID}")
        return None
