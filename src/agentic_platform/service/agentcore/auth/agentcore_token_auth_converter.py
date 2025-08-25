import os
import boto3
import logging
from typing import Any, Optional

from agentic_platform.core.models.auth_models import AgenticPlatformAuth, UserAuth, ServiceAuth
from .token_auth_converter import TokenAuthConverter

# Environment variables
M2M_CLIENT_ID = os.getenv("COGNITO_M2M_CLIENT_ID")
USER_CLIENT_ID = os.getenv("COGNITO_USER_CLIENT_ID")
AGENTCORE_WORKLOAD_NAME = os.getenv("AGENTCORE_WORKLOAD_NAME")
REGION = os.getenv("REGION", "us-west-2")

# Configure logging
logger = logging.getLogger(__name__)

# Initialize AgentCore client
agentcore_client = boto3.client('bedrock-agentcore', region_name=REGION)

class AgentCoreTokenAuthConverter(TokenAuthConverter):
    """
    Token converter for AWS Bedrock AgentCore authentication.
    
    Converts JWT tokens to AgenticPlatformAuth and integrates with AgentCore workload APIs:
    - User tokens: get_workload_access_token_for_jwt()
    - M2M tokens: get_workload_access_token()
    """

    @classmethod
    def _get_workload_access_token_for_user(cls, original_jwt: str) -> Optional[str]:
        """
        Get workload access token for user-based JWT using AgentCore API.
        
        Args:
            original_jwt: The original JWT token from the user
            
        Returns:
            Workload access token or None if failed
        """
        if not AGENTCORE_WORKLOAD_NAME:
            logger.warning("AGENTCORE_WORKLOAD_NAME not configured, skipping workload token acquisition")
            return None
            
        try:
            response = agentcore_client.get_workload_access_token_for_jwt(
                workloadName=AGENTCORE_WORKLOAD_NAME,
                userToken=original_jwt
            )
            return response.get('workloadAccessToken')
        except Exception as e:
            logger.error(f"Failed to get workload access token for user: {str(e)}")
            return None

    @classmethod
    def _get_workload_access_token_for_service(cls) -> Optional[str]:
        """
        Get workload access token for service (M2M) using AgentCore API.
        
        Returns:
            Workload access token or None if failed
        """
        if not AGENTCORE_WORKLOAD_NAME:
            logger.warning("AGENTCORE_WORKLOAD_NAME not configured, skipping workload token acquisition")
            return None
            
        try:
            response = agentcore_client.get_workload_access_token(
                workloadName=AGENTCORE_WORKLOAD_NAME
            )
            return response.get('workloadAccessToken')
        except Exception as e:
            logger.error(f"Failed to get workload access token for service: {str(e)}")
            return None

    @classmethod
    def convert_user_token(cls, token_payload: Any, original_jwt: str = None) -> AgenticPlatformAuth:
        """
        Convert user JWT token to AgenticPlatformAuth with AgentCore workload token.
        
        Args:
            token_payload: Decoded JWT payload
            original_jwt: Original JWT string for workload token acquisition
            
        Returns:
            AgenticPlatformAuth with user details and workload token
        """
        # Get workload access token for the user
        workload_token = cls._get_workload_access_token_for_user(original_jwt) if original_jwt else None
        
        # Enhance metadata with workload token
        metadata = dict(token_payload) if token_payload else {}
        if workload_token:
            metadata['agentcore_workload_token'] = workload_token

        user_auth = UserAuth(
            user_id=token_payload.get('sub'),
            username=token_payload.get('username'),
            email=token_payload.get('email'),
            groups=token_payload.get('groups', []),
            provider="agentcore",  # Changed from "cognito" to "agentcore"
            metadata=metadata
        )

        return AgenticPlatformAuth.from_user(user_auth)
    
    @classmethod
    def convert_m2m_token(cls, token_payload: Any, headers: dict = None) -> AgenticPlatformAuth:
        """
        Convert M2M JWT token to AgenticPlatformAuth with AgentCore workload token.
        
        Args:
            token_payload: Decoded JWT payload
            headers: Request headers
            
        Returns:
            AgenticPlatformAuth with service details and workload token
        """
        # Get workload access token for the service
        workload_token = cls._get_workload_access_token_for_service()
        
        # Enhance metadata with workload token
        metadata = dict(token_payload) if token_payload else {}
        if workload_token:
            metadata['agentcore_workload_token'] = workload_token

        service_id = headers.get('X-Service-ID', 'NONE') if headers else 'NONE'
        service_auth = ServiceAuth(
            service_id=service_id if service_id != 'NONE' else token_payload.get('client_id'),
            name=token_payload.get('name', 'NONE'),
            namespace=token_payload.get('namespace', 'NONE'),
            groups=token_payload.get('groups', []),
            provider="agentcore",  # Changed from "cognito" to "agentcore"
            metadata=metadata
        )

        return AgenticPlatformAuth.from_service(service_auth)

    @classmethod
    def convert_token(cls, token_payload: Any, headers: dict = None, original_jwt: str = None) -> AgenticPlatformAuth:
        """
        Convert JWT token to AgenticPlatformAuth based on client ID.
        
        Args:
            token_payload: Decoded JWT payload
            headers: Request headers
            original_jwt: Original JWT string for workload token acquisition
            
        Returns:
            AgenticPlatformAuth or None if conversion fails
        """
        if not token_payload:
            logger.error("No token payload provided")
            return None
            
        client_id = token_payload.get('client_id')
        
        if client_id == M2M_CLIENT_ID:
            return cls.convert_m2m_token(token_payload, headers)
        elif client_id == USER_CLIENT_ID:
            return cls.convert_user_token(token_payload, original_jwt)
        else:
            logger.warning(f"Unknown client_id: {client_id}, expected {M2M_CLIENT_ID} or {USER_CLIENT_ID}")
            return None
