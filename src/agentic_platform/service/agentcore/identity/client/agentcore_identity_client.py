"""
AgentCore Identity Client for managing AWS Bedrock AgentCore Identity resources.

This client provides methods to create, retrieve, update, delete, and list
AgentCore Identity resources using the AWS Bedrock AgentCore Control Plane API.

Usage:
  - Create and manage OAuth2 credential providers for outbound authentication
  - Handle workload identities and token management
  - Manage API key credential providers

Environment Variables:
  - REGION: AWS region for Bedrock AgentCore resources (default: us-west-2)
"""

import boto3
import logging
import os

from typing import Any, Dict, List, Optional

from agentic_platform.service.agentcore.types import (
    # OAuth2 Credential Provider types
    OAuth2CredentialProvider,
    OAuth2CredentialProviderStatus,
    CreateOauth2CredentialProviderRequest,
    CreateOauth2CredentialProviderResponse,
    DeleteOauth2CredentialProviderRequest,
    DeleteOauth2CredentialProviderResponse,
    GetOauth2CredentialProviderRequest,
    GetOauth2CredentialProviderResponse,
    ListOauth2CredentialProvidersRequest,
    ListOauth2CredentialProvidersResponse,
    UpdateOauth2CredentialProviderRequest,
    UpdateOauth2CredentialProviderResponse,
)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Get environment variables
REGION = os.getenv('REGION', 'us-west-2')

# Initialize AWS clients
agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)


class AgentCoreIdentityClient:

    # OAuth2 Credential Provider Methods
    @staticmethod
    def create_oauth2_credential_provider(
        request: CreateOauth2CredentialProviderRequest
    ) -> CreateOauth2CredentialProviderResponse:
        """
        Create an OAuth2 Credential Provider for outbound authentication.
        
        Args:
            request: CreateOauth2CredentialProviderRequest containing provider details
            
        Returns:
            CreateOauth2CredentialProviderResponse with provider creation details
            
        Raises:
            Exception: If credential provider creation fails
        """
        logger.info(f"Creating OAuth2 Credential Provider: {request.name}")
        
        try:
            # Prepare the create request parameters according to AWS API
            # oauth2ProviderConfigInput is a tagged union - use googleOauth2ProviderConfig for Google
            google_oauth2_config = {}
            
            # Add Google-specific configuration
            if request.google_config:
                google_oauth2_config['clientId'] = request.google_config.client_id
                google_oauth2_config['clientSecret'] = request.google_config.client_secret
            
            # Map provider type to AWS API enum values
            vendor_mapping = {
                'google': 'GoogleOauth2',
                'atlassian': 'AtlassianOauth2',
                'microsoft': 'MicrosoftOauth2',
                'slack': 'SlackOauth2',
                'custom': 'CustomOauth2',
                'linkedin': 'LinkedinOauth2',
                'salesforce': 'SalesforceOauth2',
                'github': 'GithubOauth2'
            }
            
            provider_vendor = vendor_mapping.get(request.provider_type.lower(), request.provider_type)
            
            create_params = {
                'name': request.name,
                'credentialProviderVendor': provider_vendor,
                'oauth2ProviderConfigInput': {
                    'googleOauth2ProviderConfig': google_oauth2_config
                }
            }
            
            # Note: scopes are not supported by the AWS API in create requests
            
            # Note: clientToken is not supported in the top-level API
            
            # Create the OAuth2 credential provider
            response = agentcore_control_client.create_oauth2_credential_provider(**create_params)
            
            # Debug: Log the actual response structure
            logger.info(f"Full AWS API response: {response}")
            
            # Convert datetime fields to ISO format strings
            if 'createdAt' in response:
                response['createdAt'] = response['createdAt'].isoformat()
            
            # Remove AWS metadata
            if 'ResponseMetadata' in response:
                del response['ResponseMetadata']
            
            logger.info(f"Successfully created OAuth2 Credential Provider: {response.get('name')}")
            
            # Handle the actual API response structure
            # The API returns 'credentialProviderArn' instead of 'arn'
            # Many fields are not returned in create response, so we provide defaults
            arn = response.get('credentialProviderArn', '')
            
            # Extract provider ID from the ARN if not directly provided
            credential_provider_id = response.get('credentialProviderId')
            if not credential_provider_id and arn:
                # Extract from ARN: arn:aws:bedrock-agentcore:region:account:token-vault/default/oauth2credentialprovider/NAME
                credential_provider_id = arn.split('/')[-1] if '/' in arn else response['name']
            
            return CreateOauth2CredentialProviderResponse(
                arn=arn,
                credential_provider_id=credential_provider_id or response['name'],
                name=response['name'],
                provider_type=provider_vendor,  # Use the vendor we sent since it's not returned
                status=OAuth2CredentialProviderStatus.CREATING,  # Default status for new providers
                scopes=request.scopes or [],  # Use requested scopes since not returned
                created_at=response.get('createdAt', '')  # May not be returned
            )
            
        except Exception as e:
            logger.error(f"Error creating OAuth2 Credential Provider: {str(e)}")
            raise e

    @staticmethod
    def delete_oauth2_credential_provider(
        request: DeleteOauth2CredentialProviderRequest
    ) -> DeleteOauth2CredentialProviderResponse:
        """
        Delete an OAuth2 Credential Provider.
        
        Args:
            request: DeleteOauth2CredentialProviderRequest containing provider ID/name
            
        Returns:
            DeleteOauth2CredentialProviderResponse with deletion status
            
        Raises:
            Exception: If credential provider deletion fails
        """
        logger.info(f"Deleting OAuth2 Credential Provider with ID/name: {request.credential_provider_id}")
        
        try:
            # Delete the credential provider using name parameter
            # The API now requires 'name' instead of 'credentialProviderId'
            response = agentcore_control_client.delete_oauth2_credential_provider(
                name=request.credential_provider_id
            )
            
            logger.info(f"Successfully deleted OAuth2 Credential Provider with ID/name: {request.credential_provider_id}")
            
            return DeleteOauth2CredentialProviderResponse(
                status=OAuth2CredentialProviderStatus.DELETING
            )
            
        except Exception as e:
            logger.error(f"Error deleting OAuth2 Credential Provider: {str(e)}")
            raise e

    @staticmethod
    def get_oauth2_credential_provider(
        request: GetOauth2CredentialProviderRequest
    ) -> GetOauth2CredentialProviderResponse:
        """
        Retrieve details of an OAuth2 Credential Provider.
        
        Args:
            request: GetOauth2CredentialProviderRequest containing provider ID/name
            
        Returns:
            GetOauth2CredentialProviderResponse with provider details
            
        Raises:
            Exception: If credential provider retrieval fails
        """
        logger.info(f"Getting OAuth2 Credential Provider with ID/name: {request.credential_provider_id}")
        
        try:
            # Get the credential provider details using name parameter
            # The API now requires 'name' instead of 'credentialProviderId'
            response = agentcore_control_client.get_oauth2_credential_provider(
                name=request.credential_provider_id
            )
            
            # Convert datetime fields to ISO format strings
            if 'createdAt' in response:
                response['createdAt'] = response['createdAt'].isoformat()
            if 'lastUpdatedAt' in response:
                response['lastUpdatedAt'] = response['lastUpdatedAt'].isoformat()
            
            # Remove AWS metadata
            if 'ResponseMetadata' in response:
                del response['ResponseMetadata']
            
            logger.info(f"Successfully retrieved OAuth2 Credential Provider with ID/name: {request.credential_provider_id}")
            
            # Handle the actual API response structure for get operations
            arn = response.get('credentialProviderArn', response.get('arn', ''))
            credential_provider_id = response.get('credentialProviderId', request.credential_provider_id)
            
            return GetOauth2CredentialProviderResponse(
                arn=arn,
                credential_provider_id=credential_provider_id,
                name=response.get('name', request.credential_provider_id),
                provider_type=response.get('providerType', 'GoogleOauth2'),
                status=OAuth2CredentialProviderStatus(response.get('status', 'READY')),
                scopes=response.get('scopes', []),
                created_at=response.get('createdAt', ''),
                last_updated_at=response.get('lastUpdatedAt', '')
            )
            
        except Exception as e:
            logger.error(f"Error getting OAuth2 Credential Provider: {str(e)}")
            # Check if this is a ResourceNotFoundException that should return 404
            if hasattr(e, 'response') and 'Error' in e.response:
                error_code = e.response['Error'].get('Code', '')
                if error_code == 'ResourceNotFoundException':
                    from fastapi import HTTPException
                    raise HTTPException(status_code=404, detail=f"OAuth2 Credential Provider not found: {request.credential_provider_id}")
            raise e

    @staticmethod
    def list_oauth2_credential_providers(
        request: ListOauth2CredentialProvidersRequest
    ) -> ListOauth2CredentialProvidersResponse:
        """
        List OAuth2 Credential Provider resources.
        
        Args:
            request: ListOauth2CredentialProvidersRequest containing listing parameters
            
        Returns:
            ListOauth2CredentialProvidersResponse with list of providers
            
        Raises:
            Exception: If credential provider listing fails
        """
        logger.info(f"Listing OAuth2 Credential Providers")
        
        try:
            # Prepare list parameters
            list_params = {}
            
            if request.max_results:
                list_params['maxResults'] = request.max_results
                
            if request.next_token:
                list_params['nextToken'] = request.next_token
            
            # List the OAuth2 credential providers
            response = agentcore_control_client.list_oauth2_credential_providers(**list_params)
            
            # Remove AWS metadata
            if 'ResponseMetadata' in response:
                del response['ResponseMetadata']
            
            # Convert response to our format
            providers = []
            for provider in response.get('oauth2CredentialProviders', []):
                # Convert datetime fields if present
                created_at = None
                if 'createdAt' in provider:
                    created_at = provider['createdAt'].isoformat() if hasattr(provider['createdAt'], 'isoformat') else provider['createdAt']
                
                last_updated_at = None
                if 'lastUpdatedAt' in provider:
                    last_updated_at = provider['lastUpdatedAt'].isoformat() if hasattr(provider['lastUpdatedAt'], 'isoformat') else provider['lastUpdatedAt']
                
                providers.append(OAuth2CredentialProvider(
                    arn=provider['arn'],
                    credential_provider_id=provider['credentialProviderId'],
                    name=provider['name'],
                    provider_type=provider['providerType'],
                    status=OAuth2CredentialProviderStatus(provider['status']),
                    scopes=provider['scopes'],
                    created_at=created_at,
                    last_updated_at=last_updated_at
                ))
            
            logger.info(f"Successfully listed {len(providers)} OAuth2 Credential Providers")
            
            return ListOauth2CredentialProvidersResponse(
                oauth2_credential_providers=providers,
                next_token=response.get('nextToken')
            )
            
        except Exception as e:
            logger.error(f"Error listing OAuth2 Credential Providers: {str(e)}")
            raise e

    @staticmethod
    def update_oauth2_credential_provider(
        request: UpdateOauth2CredentialProviderRequest
    ) -> UpdateOauth2CredentialProviderResponse:
        """
        Update an OAuth2 Credential Provider resource.
        
        Args:
            request: UpdateOauth2CredentialProviderRequest containing update parameters
            
        Returns:
            UpdateOauth2CredentialProviderResponse with updated provider details
            
        Raises:
            Exception: If credential provider update fails
        """
        logger.info(f"Updating OAuth2 Credential Provider with ID: {request.credential_provider_id}")
        
        try:
            # Prepare update parameters - only include non-None values
            update_params = {
                'credentialProviderId': request.credential_provider_id
            }
            
            if request.name is not None:
                update_params['name'] = request.name
            
            # Note: scopes are not supported by the AWS API in update requests
            
            # Build oauth2ProviderConfigInput if any oauth2-specific fields are provided
            google_oauth2_config = {}
            has_oauth2_updates = False
                
            if request.google_config is not None:
                google_oauth2_config['clientId'] = request.google_config.client_id
                google_oauth2_config['clientSecret'] = request.google_config.client_secret
                has_oauth2_updates = True
            
            # Only add oauth2ProviderConfigInput if we have oauth2-specific updates
            if has_oauth2_updates:
                update_params['oauth2ProviderConfigInput'] = {
                    'googleOauth2ProviderConfig': google_oauth2_config
                }
            
            # Note: clientToken is not supported in update operations
            
            # Update the credential provider
            response = agentcore_control_client.update_oauth2_credential_provider(**update_params)
            
            # Convert datetime fields to ISO format strings
            if 'createdAt' in response:
                response['createdAt'] = response['createdAt'].isoformat()
            if 'lastUpdatedAt' in response:
                response['lastUpdatedAt'] = response['lastUpdatedAt'].isoformat()
            
            # Remove AWS metadata
            if 'ResponseMetadata' in response:
                del response['ResponseMetadata']
            
            logger.info(f"Successfully updated OAuth2 Credential Provider with ID: {request.credential_provider_id}")
            
            return UpdateOauth2CredentialProviderResponse(
                arn=response['arn'],
                credential_provider_id=response['credentialProviderId'],
                name=response['name'],
                provider_type=response['providerType'],
                status=OAuth2CredentialProviderStatus(response['status']),
                scopes=response['scopes'],
                created_at=response['createdAt'],
                last_updated_at=response['lastUpdatedAt']
            )
            
        except Exception as e:
            logger.error(f"Error updating OAuth2 Credential Provider: {str(e)}")
            raise e
