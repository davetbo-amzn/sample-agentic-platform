"""
AgentCore Identity Controller for managing AWS Bedrock AgentCore Identity resources.

This controller provides static methods to create, retrieve, update, delete, and list
AgentCore Identity resources using the AWS Bedrock AgentCore Identity Control Plane API.

This controller handles all inbound and outbound authentication mechanisms including:
  - OAuth2 credential providers for outbound authentication
  - API key credential providers for outbound authentication  
  - Workload identity management for inbound authentication
  - Token management and validation
  - Provider lifecycle and configuration management

Usage:
  - Create and manage OAuth2 credential providers with scopes and provider-specific configurations
  - Handle credential provider lifecycle (create, update, delete, list)
  - Future: Manage API key credential providers
  - Future: Handle workload identity configurations
"""

from agentic_platform.service.agentcore.types import (
    OAuth2CredentialProviderOperation,
    OAuth2CredentialProviderRequest,
    OAuth2CredentialProviderResponse,
    CreateOauth2CredentialProviderRequest,
    CreateOauth2CredentialProviderResponse,
    DeleteOauth2CredentialProviderRequest,
    DeleteOauth2CredentialProviderResponse,
    GetOauth2CredentialProviderRequest,
    GetOauth2CredentialProviderResponse,
    ListOauth2CredentialProvidersRequest,
    ListOauth2CredentialProvidersResponse,
    UpdateOauth2CredentialProviderRequest,
    UpdateOauth2CredentialProviderResponse
)
from agentic_platform.service.agentcore.identity.client.agentcore_identity_client import AgentCoreIdentityClient


class AgentCoreIdentityController:

    @staticmethod
    def handler(event, context):
        evt = OAuth2CredentialProviderRequest(**event)
        if evt.operation == OAuth2CredentialProviderOperation.CREATE:
            result = AgentCoreIdentityController.create_oauth2_credential_provider(
                CreateOauth2CredentialProviderRequest(**evt.input)
            )
        
        elif evt.operation == OAuth2CredentialProviderOperation.DELETE:
            result = AgentCoreIdentityController.delete_oauth2_credential_provider(
                DeleteOauth2CredentialProviderRequest(**evt.input)
            )
        
        elif evt.operation == OAuth2CredentialProviderOperation.GET:
            result = AgentCoreIdentityController.get_oauth2_credential_provider(
                GetOauth2CredentialProviderRequest(**evt.input)
            )
        
        elif evt.operation == OAuth2CredentialProviderOperation.LIST:
            result = AgentCoreIdentityController.list_oauth2_credential_providers(
                ListOauth2CredentialProvidersRequest(**evt.input)
            )
        
        elif evt.operation == OAuth2CredentialProviderOperation.UPDATE:
            result = AgentCoreIdentityController.update_oauth2_credential_provider(
                UpdateOauth2CredentialProviderRequest(**evt.input)
            )
        
        else:
            raise Exception(f"Parameter validation exception: operation must be an OAuth2CredentialProviderOperation (one of {OAuth2CredentialProviderOperation.__dict__})")
        
        return OAuth2CredentialProviderResponse(
            status_code=200,
            result=result.to_dict()
        ).to_dict()
    
    @staticmethod
    def create_oauth2_credential_provider(request: CreateOauth2CredentialProviderRequest) -> CreateOauth2CredentialProviderResponse:
        return AgentCoreIdentityClient.create_oauth2_credential_provider(request)
    
    @staticmethod
    def delete_oauth2_credential_provider(request: DeleteOauth2CredentialProviderRequest) -> DeleteOauth2CredentialProviderResponse:
        return AgentCoreIdentityClient.delete_oauth2_credential_provider(request)
    
    @staticmethod
    def get_oauth2_credential_provider(request: GetOauth2CredentialProviderRequest) -> GetOauth2CredentialProviderResponse:
        return AgentCoreIdentityClient.get_oauth2_credential_provider(request)

    @staticmethod
    def list_oauth2_credential_providers(request: ListOauth2CredentialProvidersRequest) -> ListOauth2CredentialProvidersResponse:
        return AgentCoreIdentityClient.list_oauth2_credential_providers(request)
    
    @staticmethod
    def update_oauth2_credential_provider(request: UpdateOauth2CredentialProviderRequest) -> UpdateOauth2CredentialProviderResponse:
        return AgentCoreIdentityClient.update_oauth2_credential_provider(request)


def handler(event, context):
    return AgentCoreIdentityController.handler(event, context)
