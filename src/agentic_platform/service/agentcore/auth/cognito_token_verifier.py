import jwt
import logging
import os

from jwt.exceptions import PyJWKClientError, InvalidKeyError
from fastapi import HTTPException
from typing import Any, Optional


logger = logging.getLogger(__name__)

REGION = os.getenv('REGION',   
    os.getenv('AWS_REGION',  
        os.getenv('AWS_DEFAULT_REGION', None)
    )
)
USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID')
jwks_url = f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json'
print(f"jwks_url: {jwks_url}")
jwks_client = jwt.PyJWKClient(jwks_url)
print(f"jwks_client: {jwks_client}, {jwks_client.__dict__}")

class CognitoTokenVerifier:
    @staticmethod
    def validate_token(token) -> Optional[Any]:
        try:
            # PyJWKClient automatically fetches the key matching the token's kid
            print(f"extracting signing key from jwt: {token}")
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            print(f"Got signing key {signing_key.key}")
            # Use the signing key to decode and validate the token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],  # Specify the algorithms you expect
                options={"verify_aud": False}  # Customize verification options as needed
            )
            print(f"returning payload {payload}")
            return payload
        except PyJWKClientError as e:
            # Handle JWKS client errors (e.g., key not found)
            logger.error(f"JWKS client error: {e}")
            # this should return the original error instead of the invalid error because it
            # obfuscates the real problem.
            raise e # HTTPException(status_code=401, detail="Invalid authentication token")
        except InvalidKeyError as e:
            # Handle key validation errors
            logger.error(f"Invalid key error: {e}")
            raise HTTPException(status_code=401, detail="Invalid token signature")
        except jwt.PyJWTError as e:
            # Handle general JWT errors
            logger.error(f"JWT validation error: {e}")
            raise HTTPException(status_code=401, detail=str(e))
