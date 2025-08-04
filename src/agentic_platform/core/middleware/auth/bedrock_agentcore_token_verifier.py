import boto3
from typing import Any, Optional

from .token_verifier import TokenVerifier


class BedrockAgentCoreTokenVerifier(TokenVerifier):
    def __init__(self, 
        bedrock_agentcore_client: boto3.client=None
    ):
        super().__init__()
        # this makes it easy to inject mocks at test time initialization
        if bedrock_agentcore_client == None:
            self.bedrock_agentcore_client = boto3.client('bedrock-agentcore')
        else:
            self.bedrock_agentcore_client = bedrock_agentcore_client

    # @param workloadName: str (Unique identifier for the registered agent)
    # returns workload access token, an opaque token representing both agent and user identity
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agentcore/client/get_workload_access_token_for_jwt.html
    def validate_token(self, token: str, *, workload_name) -> str:
        return self.bedrock_agentcore_client.get_workload_access_token_for_jwt(
            workloadName=workload_name,
            userToken=token
        )