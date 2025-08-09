"""
AWS Lambda function to provision and manage Bedrock AgentCore Memory resources.

This function is used by Terraform to create and update Bedrock AgentCore memory
capabilities for the Agentic Platform.

Usage:
  - The function is invoked by Terraform with appropriate configuration parameters
  - It creates or updates AgentCore resources using the boto3 SDK
  - It handles provision action for now

Environment Variables:
  - MEMORY_RETENTION_PERIOD: Number of days to retain memory (default: 30)
  - ENVIRONMENT: Deployment environment (e.g., dev, prod)
  - REGION: AWS region for Bedrock AgentCore resources
"""

import boto3
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List
from enum import Enum
from pydantic import BaseModel

from agentic_platform.core.models.memory_models import (
    CreateAgentCoreMemoryProviderRequest,
    CreateAgentCoreMemoryProviderResponse,
    DeleteAgentCoreMemoryProviderRequest,
    DeleteAgentCoreMemoryProviderResponse,
    UpdateAgentCoreMemoryProviderRequest,
    UpdateAgentCoreMemoryProviderResponse,
    SessionContext, 
    Memory,
    Message,
    GetSessionContextRequest,
    GetSessionContextResponse,
    GetMemoriesRequest,
    GetMemoriesResponse,
    CreateMemoryRequest,
    CreateMemoryResponse,
    UpsertSessionContextRequest,
    UpsertSessionContextResponse
    
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get environment variables
MEMORY_RETENTION_DAYS = int(os.environ.get('MEMORY_RETENTION_PERIOD', 30))
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'AgentCore-AgentPath')
REGION = os.environ.get('REGION', 'us-west-2')

agentcore_client = boto3.client('bedrock-agentcore', region_name=REGION)
agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
ssm_client = boto3.client('ssm', region_name=REGION)
agentcore_memory_id = None


class AgentCoreMemoryClient:

    @classmethod
    def _get_agentcore_memory_id(cls):
        global agentcore_memory_id
        if not agentcore_memory_id:
            try:
                param_name = f"/{ENVIRONMENT}/agentcore_memory_id"
                print(f"Checking for ssm param {param_name}")
                parameters = ssm_client.get_parameters_by_path(
                    Path=param_name
                )['Parameters']
                if len(parameters) > 0:
                    agentcore_memory_id = parameters[0]['Value']
                else:
                    print(f"Creating agentcore model {ENVIRONMENT}")
                    # Create a proper CreateAgentCoreMemoryProviderRequest with default values
                    create_request = CreateAgentCoreMemoryProviderRequest(
                        environment=ENVIRONMENT,
                        retention_days=MEMORY_RETENTION_DAYS
                    )
                    response = cls.create_memory_provider(create_request)
                    print(f"response from create_model_provider {response}")

                    cls._wait_for_memory_provider_creation(
                        response
                    )
                    agentcore_memory_id = response
                    ssm_client.put_parameter(
                        Name=param_name,
                        Value=agentcore_memory_id,
                        Type='String',
                        Overwrite=True
                    )

            except Exception as e:
                raise e
        return agentcore_memory_id

    @classmethod
    def create_memory_provider(
        cls, 
        request: CreateAgentCoreMemoryProviderRequest
    ) -> CreateAgentCoreMemoryProviderResponse:
        """
        Provision Bedrock AgentCore Memory resources.
        
        Args:
            agentcore_client: Boto3 client for AgentCore
            agentcore_control_client: Boto3 client for AgentCore Control
            retention_days: Number of days to retain memory
            environment: Deployment environment
            
        Returns:
            Dictionary with the provision result
        """
        global agentcore_memory_id

        logger.info(f"Provisioning AgentCore Memory {ENVIRONMENT} with {request.retention_days} day retention for environment {ENVIRONMENT}")
        try:
            # Create a unique resource name and namespace for this environment            
            # Create memory configuration using the control plane client
            memory_name = ENVIRONMENT.replace('-','_')
            create_response = agentcore_control_client.create_memory(
                name=memory_name,
                description=f"AgentCore memory for {ENVIRONMENT} environment",
                eventExpiryDuration=request.retention_days, 
                memoryStrategies=[
                    {
                        "semanticMemoryStrategy": {
                            'name': 'semantic_memory',
                            'description': 'Use this for long-term memories to be retrieved by semantic similarity for future reference and continuous improvement.'
                        }
                    },
                    {
                        "summaryMemoryStrategy": {
                            "name": "summary_memory",
                            "description": "Use this to summarize learnings from a task for future reference and continuous improvement."
                        }
                    },
                    {
                        "userPreferenceMemoryStrategy": {
                            "name": "user_preferences_memory",
                            "description": "Use this to store preferences from users for future reference and continuous improvement."
                        }
                    }
                ]
            )
            print(f"Got create response {create_response}")
            memory_id = create_response['memory']['id']
            logger.info(f"Creating agentcore memory resource with ID: {memory_id}")
            logger.info("Waiting for memory creation to complete.")
            result = cls._wait_for_memory_provider_creation(agentcore_control_client, memory_id)
            print(f"Memory creation result: {result}")

            status = agentcore_control_client.get_memory(
                memoryId=memory_id
            )['memory']['status']

            print(f"memory {memory_id} status {status}")
            if not status == 'ACTIVE':
                raise Exception(f'Failed to create memory {memory_name}')
            
            ssm_client.put_parameter(
                Name=f"/{ENVIRONMENT}/agentcore_memory_id",
                Value=memory_id,
                Type="String",
                Overwrite=True
            )
            logger.info("AgentCore Memory provisioning completed successfully")
            agentcore_memory_id = memory_id

        except Exception as create_error:
            if "already exists" in str(create_error):
                logger.info(f"Memory {memory_name} already exists")
                memories = agentcore_control_client.list_memories()['memories']
                for mem in memories:
                    if mem['id'].split('-')[0] == memory_name:
                        agentcore_memory_id = mem['id']
            else:
                logger.error(f"Could not create memory resource: {str(create_error)}")
                raise create_error
        return agentcore_memory_id

    @classmethod
    def delete_memory_provider(
        cls,
        request: DeleteAgentCoreMemoryProviderRequest
    ) -> DeleteAgentCoreMemoryProviderResponse:
        """
        Delete a Bedrock AgentCore Memory resource.
        
        Args:
            agentcore_control_client: Boto3 client for AgentCore Control
            memory_id: ID of the memory resource to delete
            
        Returns:
            Boolean indicating success
        """
        logger.info(f"Deleting AgentCore Memory resource with ID: {request.memory_id}")
        if not agentcore_control_client:
            agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
        try:
            # Delete the memory resource
            agentcore_control_client.delete_memory(
                memoryId=request.memory_id
            )
            
            logger.info(f"Successfully deleted memory resource with ID: {request.memory_id}")
            return request.memory_id
            
        except Exception as e:
            logger.error(f"Error deleting AgentCore Memory resource: {str(e)}")
            raise e

    @staticmethod
    def update_memory_provider(
        request: UpdateAgentCoreMemoryProviderRequest
    ) -> UpdateAgentCoreMemoryProviderResponse:
        """
        Update a Bedrock AgentCore Memory resource.
        
        Args:
            agentcore_control_client: Boto3 client for AgentCore Control
            memory_id: ID of the memory resource to update
            description: Optional new description for the memory
            event_expiry_duration: Optional new retention period in days
            memory_strategies: Optional list of new memory strategies
            
        Returns:
            Updated memory details
        """
        logger.info(f"Updating AgentCore Memory resource with ID: {request.memory_id}")
        if not agentcore_control_client:
            agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
       
        try:
            # First get current memory details to only update what's provided
            current_memory = agentcore_control_client.get_memory(
                memoryId=request.memory_id
            )
            
            # Prepare update parameters
            update_params = {
                'id': request.memory_id
            }
            
            # Only add parameters that are provided
            if request.description is not None:
                update_params['description'] = request.description
                logger.info(f"Updating description to: {request.description}")
                
            if request.event_expiry_duration is not None:
                update_params['eventExpiryDuration'] = request.event_expiry_duration
                logger.info(f"Updating event expiry duration to: {request.event_expiry_duration} days")
                
            if request.memory_strategies is not None:
                update_params['memoryStrategies'] = request.memory_strategies
                logger.info(f"Updating memory strategies")
                
            # Only perform update if we have parameters to update
            if len(update_params) > 1:  # more than just memoryId
                # Update the memory resource
                agentcore_control_client.update_memory(**update_params)
                logger.info(f"Successfully updated memory resource with ID: {request.memory_id}")
                

                # Get the updated memory details to return
                updated_memory = agentcore_control_client.get_memory(
                    memoryId=request.memory_id
                )
                print(f"Got updated memory {updated_memory}")

                # Format the response
                result = {
                    'memoryId': request.memory_id,
                    'name': updated_memory.get('name'),
                    'description': updated_memory.get('description', ''),
                    'eventExpiryDuration': updated_memory.get('eventExpiryDuration'),
                    'memoryStrategies': updated_memory.get('memoryStrategies', []),
                    'createdAt': updated_memory.get('createdAt', '').isoformat() if hasattr(updated_memory.get('createdAt', ''), 'isoformat') else updated_memory.get('createdAt', ''),
                    'updatedAt': updated_memory.get('updatedAt', '').isoformat() if hasattr(updated_memory.get('updatedAt', ''), 'isoformat') else updated_memory.get('updatedAt', '')
                }
                
                return result
            else:
                logger.info(f"No updates provided for memory ID: {request.memory_id}")
                return current_memory
            
        except Exception as e:
            logger.error(f"Error updating AgentCore Memory resource: {str(e)}")
            raise e


    # def save_to_ssm_parms(memory_strategy, namespaces, memory_id, ssm_client=None):
    #     if not ssm_client:
    #         ssm_client = boto3.client('ssm', region_name=REGION)

    #     for ns in namespaces:
    #         ssm_client.put_parameter(
    #             Name=f'/agentcore/memory/{ns}/{memory_strategy}/memory_id',
    #             Value=memory_id,
    #             Type='String',
    #             Overwrite=True
    #         )


    def _wait_for_memory_provider_creation(
        memory_id: str,
        max_attempts: int = 20,
        delay_seconds: int = 30
    ) -> Dict[str, Any]:
        
        print(f"Called _wait_for_memory_provider_creation for memory {memory_id}")
        """
        Wait for memory creation to complete.
        
        Args:          
            memory_id: Memory ID to check
            max_attempts: Maximum number of polling attempts
            delay_seconds: Delay between polling attempts in seconds
            
        Returns:
            Memory details when available
            
        Raises:
            TimeoutError: If the memory creation doesn't complete within the timeout period
        """

        logger.info(f"Waiting for memory {memory_id} to be fully created...")
        
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Attempt {attempt}")
                # Try to get the memory details
                memory_details = agentcore_control_client.get_memory(
                    memoryId=memory_id
                )['memory']
                
                status = memory_details['status']
                # Check if the memory exists and has all expected attributes
                if status == 'ACTIVE':
                    logger.info(f"Memory {memory_id} is now available after {attempt} attempts")
                    return memory_details
                else:
                    print(f"Memory status: {status} (waiting {delay_seconds} seconds to check again)")
                    
            except Exception as e:
                if "Memory not found" in str(e) or "does not exist" in str(e):
                    logger.info(f"Attempt {attempt}/{max_attempts}: Memory {memory_id} not yet available")
                else:
                    logger.warning(f"Unexpected error checking memory: {str(e)}")
            
            # Wait before the next attempt
            if attempt < max_attempts:
                time.sleep(delay_seconds)
        
        raise TimeoutError(f"Memory {memory_id} did not become available within the timeout period")


    def _wait_for_memory_provider_deletion(
        agentcore_control_client,
        memory_id: str,
        max_attempts: int=20,
        delay_seconds: int=10
    ) -> bool:
        """
        Wait for memory deletion to complete.
        
        Args:
            agentcore_control_client: Boto3 client for AgentCore Control
            memory_id: Memory ID that was deleted
            max_attempts: Maximum number of polling attempts
            delay_seconds: Delay between polling attempts in seconds
            
        Returns:
            Boolean indicating if the memory was successfully deleted
            
        Raises:
            TimeoutError: If the memory deletion doesn't complete within the timeout period
        """
        logger.info(f"Waiting for memory {memory_id} to be fully deleted...")
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Try to get the memory details - this should eventually fail
                memory_details = agentcore_control_client.get_memory(
                    memoryId=memory_id
                )
                
                # If we get here, the memory still exists
                logger.info(f"Attempt {attempt}/{max_attempts}: Memory {memory_id} still exists")
                
            except Exception as e:
                if "Memory not found" in str(e) or "does not exist" in str(e):
                    logger.info(f"Memory {memory_id} successfully deleted after {attempt} attempts")
                    return True
                else:
                    logger.warning(f"Unexpected error checking memory deletion: {str(e)}")
            
            # Wait before the next attempt
            if attempt < max_attempts:
                time.sleep(delay_seconds)
        
        raise TimeoutError(f"Memory {memory_id} was not deleted within the timeout period")

    # @classmethod
    # def _get_events(request: GetMemoriesRequest) -> GetMemoriesR:
    #     args = {
    #         "memoryId": agentcore_memory_id,
    #         "sessionId": session_id,
    #         "actorId": user_id,
    #         "includePayloads": True,
    #         "maxResults": max_results
    #     }
    #     if next_token:
    #         args['nextToken'] = next_token

    #     events = agentcore_client.list_events(**args)['events']
    #     context = []
    #     for evt in events:
    #         del evt['memoryId']
    #         del evt['actorId']
    #         context.append(evt)
    #     return context
    
    @classmethod
    def initialize_session(cls, actor_id):
        payload = [{
            "conversational": {
                "content": {
                    "text": "Initializing new AgentCore memory session."
                },
                "role": "ASSISTANT"
            }
        }]
        event = agentcore_client.create_event(
            memoryId=agentcore_memory_id,
            actorId=actor_id,
            eventTimestamp=datetime.now(),
            payload=payload
        )['event']
        print(f"Got event response {event}")
        
        
        session_ctx = SessionContext(
            session_id=event['sessionId'],
            user_id=event['actorId'],
            messages=[Message(
                role='assistant',
                content=[{
                    "type": "text",
                    "text": payload[0]['conversational']['content']['text']
                }]
            )]
        )
    
        return session_ctx
    
    @classmethod
    def get_session_context(cls, request: GetSessionContextRequest) -> GetSessionContextResponse:
        global agentcore_memory_id
        """
        Retrieves session contexts based on user_id or session_id using Bedrock AgentCore.
        """
        logger.info(f"Getting session context for request: {request}")
        if not agentcore_memory_id:
            agentcore_memory_id = cls._get_agentcore_memory_id()
            print(f"Using agentcore_memory_id {agentcore_memory_id}")

        # if session ID wasn't passed in, get the most recent session ID.
        if not request.session_id:
            try:
                args = {
                    'memoryId': agentcore_memory_id,
                    'actorId': request.user_id,
                }
                if request.next_token:
                    args['nextToken'] = request.next_token

                try:
                    response = agentcore_client.list_sessions(**args)
                except Exception as e:
                    if 'ResourceNotFoundException' in str(e):
                        print("User not found. Creating new session.")
                        return cls.initialize_session(request.user_id)
                print(f"Got session summaries {response}")
                if len(response.get('sessionSummaries', [])) == 0:
                    logger.info(f"No sessions found for user {request.user_id} in agentcore memory {agentcore_memory_id}. Initializing new session.")
                    
                    return cls.initialize_session(request.user_id)
                
                else:
                    most_recent_session_id = None
                    most_recent_session_time = datetime(1970,1,1)

                    for session in response['sessionSummaries']:
                        if session['createdAt'] > most_recent_session_time:
                            most_recent_session_id = session['sesssionId']
                            most_recent_session_time = session['createdAt']
                    request.session_id = most_recent_session_id                    
            except Exception as e:
                logger.error(f"Error retrieving session context: {e}")
                raise e
        
        contexts = cls.get_memories(request)
        return GetSessionContextResponse(results=contexts)
    
    @classmethod
    def get_memories(cls, request: GetMemoriesRequest) -> GetMemoriesResponse:
        args = {
            "memoryId": agentcore_memory_id,
            "sessionId": request.session_id,
            "actorId": request.user_id,
            "includePayloads": True,
            "maxResults": request.limit
        }
        if request.next_token:
            args['nextToken'] = request.next_token

        events = agentcore_client.list_events(**args)['events']
        context = []
        for evt in events:
            del evt['memoryId']
            del evt['actorId']
            context.append(evt)
        return context
    
    @classmethod
    def upsert_session_context(cls, request: UpsertSessionContextRequest):
        # not implemented in AgentCore. You just create events and give them the same session ID
        pass

    @classmethod
    def create_memory(cls, request: CreateMemoryRequest) -> CreateMemoryResponse:
        newest_msg = request.session_context.messages[-1]
        response = agentcore_client.create_event(
            memoryId=agentcore_memory_id,
            sessionId=request.session_id,
            actorId=request.user_id,
            payload=[{
                "conversational": {
                    "content": {
                        "text": newest_msg.content,
                    },
                    "role": newest_msg.role
                }
            }]
        )['event']
        
        memory_event = Memory(
            role=response['payload'][0]['conversational']['role'],
            content=response['payload'][0]['content']['text']
        )
        logging.info(f"Created memory event {memory_event}")
        return memory_event
