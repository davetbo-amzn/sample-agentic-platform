"""
AWS Lambda function to provision and manage Bedrock  Memory resources.

This function is used by Terraform to create and update Bedrock  memory
capabilities for the Agentic Platform.

Usage:
  - The function is invoked by Terraform with appropriate configuration parameters
  - It creates or updates  resources using the boto3 SDK
  - It handles provision action for now

Environment Variables:
  - REGION: AWS region for Bedrock  resources
"""

import boto3
import json
import logging
import os
import time
from typing import Any, Dict

from agentic_platform.service.agentcore.types import (
    MemoryEvent,
    MemoryStrategy,
    CreateMemoryProviderRequest,
    CreateMemoryProviderResponse,
    CreateEventRequest,
    CreateEventResponse,
    DeleteMemoryProviderRequest,
    DeleteMemoryProviderResponse,
    DeleteMemoryRecordRequest,
    DeleteMemoryRecordResponse,
    GetMemoryProviderRequest,
    GetMemoryProviderResponse,
    ListEventsRequest,
    ListEventsResponse,
    ListMemoryRecordsRequest,
    ListMemoryRecordsResponse,
    ListMemoryProvidersRequest,
    ListMemoryProvidersResponse,
    ListMemoryProvidersResponseEntry,
    MemoryRecordSummary,
    RetrieveMemoryRecordsRequest,
    RetrieveMemoryRecordsResponse,
    UpdateMemoryProviderRequest,
    UpdateMemoryProviderResponse
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get environment variables
REGION = os.environ.get('REGION', 'us-west-2')

agentcore_client = boto3.client('bedrock-agentcore', region_name=REGION)
agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
ssm_client = boto3.client('ssm', region_name=REGION)
agentcore_memory_id = None

class AgentCoreMemoryClient:
    
    @staticmethod
    def dates_to_strings(agentcore_memory):
        # logger.info(f"dates_to_strings received agentcore_memory {agentcore_memory}")
        if not isinstance(agentcore_memory, dict):
            agentcore_memory = agentcore_memory.__dict__
        if 'createdAt' in agentcore_memory:
            agentcore_memory['createdAt'] = agentcore_memory['createdAt'].isoformat()
        if 'updatedAt' in agentcore_memory:
            agentcore_memory['updatedAt'] = agentcore_memory['updatedAt'].isoformat()
        for i in range(len(agentcore_memory['strategies'])):
            agentcore_memory['strategies'][i]['createdAt'] = agentcore_memory['strategies'][i]['createdAt'].isoformat()
            agentcore_memory['strategies'][i]['updatedAt'] = agentcore_memory['strategies'][i]['updatedAt'].isoformat()
        return agentcore_memory
    
    @staticmethod
    def create_memory_provider( 
        request: CreateMemoryProviderRequest
    ) -> CreateMemoryProviderResponse:
        """
        Provision Bedrock  Memory resources.
        
        Args:
            retention_days: Number of days to retain memory
            environment: Deployment environment
            
        Returns:
            Dictionary with the provision result
        """
        global agentcore_memory_id
        
        logger.info(f"Provisioning  Memory {request.name} with {request.retention_days} day retention.")
        try:
            # Create a unique resource name and namespace for this environment            
            # Create memory configuration using the control plane client
            memory_name = request.name.replace('-','_')[:47]
            logger.info(f"creating memory name {memory_name}")
            create_response = agentcore_control_client.create_memory(
                name=memory_name,
                description=f"{request.name} AgentCore Memory",
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
            )['memory']
            logger.info(f"Got create response {create_response}")
            memory_id = create_response['id']
            logger.info(f"Creating agentcore memory resource with ID: {memory_id}")
            logger.info("Waiting for memory creation to complete.")
            result = AgentCoreMemoryClient.wait_for_memory_provider_creation(memory_id)
            logger.info(f"Memory creation result: {result}")
            status = agentcore_control_client.get_memory(
                memoryId=memory_id
            )['memory']['status']

            logger.info(f"memory {memory_id} status {status}")
            if not status == 'ACTIVE':
                raise Exception(f'Failed to create memory {memory_name}')
            
            AgentCoreMemoryClient._save_agentcore_memory_id(memory_id, memory_name)
            logger.info(" Memory provisioning completed successfully")
            agentcore_memory_id = memory_id
            return CreateMemoryProviderResponse(
                memory_id=agentcore_memory_id,
                name=memory_name,
                status=create_response['status'],
            )
        
        except Exception as create_error:
            logger.debug(f"ERROR: {str(create_error)}")
            if "already exists" in str(create_error):
                logger.info(f"Memory {memory_name} already exists")
                memories = agentcore_control_client.list_memories()['memories']
                for mem in memories:
                    if mem['id'].split('-')[0] == memory_name:
                        logger.info(f"Found memory {mem}")
                        agentcore_memory_id = mem['id']
                        AgentCoreMemoryClient._save_agentcore_memory_id(agentcore_memory_id, memory_name)
                        logger.info(f"Returning existing agentcore_memory_id {agentcore_memory_id}")
                        return CreateMemoryProviderResponse(
                            memory_id=agentcore_memory_id,
                            name=memory_name,
                            status=mem['status'],
                        )
            else:
                logger.error(f"Could not create memory resource: {str(create_error)}")
                raise create_error
            
    @staticmethod
    def delete_memory_provider(
        request: DeleteMemoryProviderRequest
    ) -> DeleteMemoryProviderResponse:
        """
        Delete a Bedrock  Memory resource.
        
        Args:
            memory_id: ID of the memory resource to delete
            
        Returns:
            Boolean indicating success
        """
        logger.info(f"delete_memory_provider got request {request}")
        try:
            memory_id = request.memory_id
            logger.info(f"Deleting memory with id {memory_id}")
            # Delete the memory resource 
            agentcore_control_client.delete_memory(
                memoryId=memory_id
            )
            
            logger.info(f"Successfully deleted memory resource with ID: {memory_id}")
            return DeleteMemoryProviderResponse(memory_id=memory_id)
            
        except Exception as e:
            logger.error(f"Error deleting  Memory resource: {str(e)}")
            raise e

    @staticmethod
    def delete_memory_record(
        request: DeleteMemoryRecordRequest
    ) -> DeleteMemoryRecordResponse:
        """
        Delete a memory record from an AgentCore Memory resource.
        
        Args:
            request: DeleteMemoryRecordRequest containing memory_id and memory_record_id
            
        Returns:
            DeleteMemoryRecordResponse with the deleted memory record ID
        """
        logger.info(f"delete_memory_record got request {request}")
        try:
            memory_id = request.memory_id
            memory_record_id = request.memory_record_id
            logger.info(f"Deleting memory record {memory_record_id} from memory {memory_id}")
            
            # Delete the memory record using the data plane client
            response = agentcore_client.delete_memory_record(
                memoryId=memory_id,
                memoryRecordId=memory_record_id
            )
            
            deleted_record_id = response['memoryRecordId']
            logger.info(f"Successfully deleted memory record with ID: {deleted_record_id}")
            return DeleteMemoryRecordResponse(memory_record_id=deleted_record_id)
            
        except Exception as e:
            logger.error(f"Error deleting memory record: {str(e)}")
            logger.error(f"Request details - memory_id: {request.memory_id}, memory_record_id: {request.memory_record_id}")
            raise e

    @staticmethod
    def get_memory_provider(
        request: GetMemoryProviderRequest
    ) -> GetMemoryProviderResponse:
        """
        Get a Bedrock  Memory resource.
        
        Args:
            request: GetMemoryProviderRequest containing memory_id
            
        Returns:
            GetMemoryProviderResponse with memory details
        """
        logger.info(f"get_memory_provider got request {request}")
        try:
            memory_id = request.memory_id
            logger.info(f"Retrieving memory with id {memory_id}")
            # Get the memory resource 
            response = agentcore_control_client.get_memory(
                memoryId=memory_id
            )['memory']
            
            logger.info(f"Successfully retrieved memory resource with ID: {memory_id}, response {response}")
            strats = []
            for strat in response['strategies']:
                logger.info(f"Got strategy {strat}")
                strats.append(MemoryStrategy(
                    strategy_id=strat['strategyId'],
                    name=strat['name'],
                    description=strat['description'],
                    memory_type=strat['type'],
                    namespaces=strat['namespaces'],
                    created_at=strat['createdAt'],
                    updated_at=strat['updatedAt'],
                    status=strat['status']
                ))
            return GetMemoryProviderResponse(
                arn=response['arn'],
                memory_id=response['id'],
                name=response['name'],
                description=response['description'],
                event_expiry_duration=response['eventExpiryDuration'],
                status=response['status'],
                failure_reason=response['failureReason'] if 'failureReason' in response else '',
                created_at=response['createdAt'],
                updated_at=response['updatedAt'],
                strategies=strats
            )
            
        except Exception as e:
            logger.error(f"Error retrieving  Memory resource: {str(e)}")
            raise e
    
    @staticmethod
    def list_events(
        request: ListEventsRequest
    )->ListEventsResponse:
        args = {
            'memoryId': request.memory_id,
            'sessionId': request.session_id,
            'actorId': request.actor_id,
            'includePayloads': request.include_payloads,
            'maxResults': request.max_results
        }
        if request.filter:
            args['filter'] = request.filter
        if request.next_token:
            args['nextToken'] = request.next_token
        
        response = agentcore_client.list_events(**args)['events']
        events = []
        for evt in response:
            events.append(MemoryEvent(
                memory_id=evt['memoryId'],
                actor_id=evt['actorId'],
                session_id=evt['sessionId'],
                event_id=evt['eventId'],
                event_timestamp=evt['eventTimestamp'].isoformat(),
                payload=evt['payload'],
                branch=evt['branch']
            ))
        return ListEventsResponse(
            events=events
        )

    @staticmethod
    def list_memory_records(
        request: ListMemoryRecordsRequest
    )->ListMemoryRecordsResponse:
        args = {
            'memoryId': request.memory_id,
            'namespace': request.namespace,
            'maxResults': request.max_results
        }
        if request.memory_strategy_id:
            args['memoryStrategyId'] = request.memory_strategy_id

        if request.next_token:
            args['nextToken'] = request.next_token

        response = agentcore_client.list_memory_records(**args)
        memory_records = []

        for rec in response['memoryRecordSummaries']:
            logger.info(f"Got response record {rec}")
            memory_records.append(MemoryRecordSummary(
                memory_record_id=rec['memoryRecordId'],
                content=rec['content'],
                memory_strategy_id=rec['memoryStrategyId'],
                namespaces=rec['namespaces'],
                created_at=rec['createdAt'].isoformat(),
            ))

        return ListMemoryRecordsResponse(
            memory_record_summaries=memory_records,
            next_token= None if 'nextToken' not in response else response['nextToken']
        )

    @staticmethod
    def retrieve_memory_records(
        request: RetrieveMemoryRecordsRequest
    ) -> RetrieveMemoryRecordsResponse:
        """
        Retrieve memory records using semantic search.
        
        Args:
            request: RetrieveMemoryRecordsRequest containing search parameters
            
        Returns:
            RetrieveMemoryRecordsResponse with matching memory records
        """
        logger.info(f"retrieve_memory_records got request {request}")
        try:
            # Get memory provider details to resolve namespace
            memory_provider = agentcore_control_client.get_memory(
                memoryId=request.memory_id
            )['memory']
            
            # Find the namespace for the given memory strategy
            namespace = ''
            for strategy in memory_provider['strategies']:
                if strategy['strategyId'] == request.memory_strategy_id:
                    namespace = strategy['namespaces'][0]
                    # Replace placeholders in namespace
                    namespace = namespace.replace('{actorId}', request.actor_id)
                    namespace = namespace.replace('{memoryStrategyId}', request.memory_strategy_id)
                    
                    # Handle session ID placeholder if present
                    if '{sessionId}' in namespace:
                        if request.session_id is not None:
                            namespace = namespace.replace('{sessionId}', request.session_id)
                        else:
                            # Remove the session ID part if no session ID provided
                            namespace = namespace.replace('/{sessionId}', '')
                    break
            
            if not namespace:
                raise ValueError(f"Could not find namespace for memory strategy ID: {request.memory_strategy_id}")
            
            logger.info(f'Using namespace: {namespace}')
            
            # Call the AWS API to retrieve memory records
            response = agentcore_client.retrieve_memory_records(
                memoryId=request.memory_id,
                namespace=namespace,
                searchCriteria={
                    'searchQuery': request.query
                },
                maxResults=request.max_results
            )
            # logger.info(f"Got response from retrieve_memory_records: {response}")
            # Process the response
            memory_records = []
            for rec in response.get('memoryRecordSummaries', []):
                # logger.info(f"Got response record {rec}")
                memory_record = MemoryRecordSummary(
                    memory_record_id=rec['memoryRecordId'],
                    content=rec['content'],
                    memory_strategy_id=rec['memoryStrategyId'],
                    namespaces=rec['namespaces'],
                    created_at=rec['createdAt'].isoformat(),
                    score=rec.get('score')  # Include score for semantic search results
                )
                memory_records.append(memory_record)
            
            logger.info(f"Retrieved {len(memory_records)} memory records for query: {request.query[:50]}...")
            
            return RetrieveMemoryRecordsResponse(
                memory_record_summaries=memory_records,
                next_token=response.get('nextToken')
            )
            
        except Exception as e:
            logger.error(f"Error retrieving memory records: {str(e)}")
            logger.error(f"Request details - memory_id: {request.memory_id}, query: {request.query[:100]}")
            raise e
    
    @staticmethod
    def list_memory_providers(
        request: ListMemoryProvidersRequest
    ) -> ListMemoryProvidersResponse:
        """
        List  Memory resources.
        
        Args:
            request: ListMemoryProvidersRequest with max_results and next_token
            
        Returns:
            ListMemoryProvidersResponse with a list of  Memory Providers
        """
        # logger.info(f"list_memory_providers got request {request}")
        try:
            # Prepare parameters for list_memories call
            list_params = {}
            if request.max_results:
                list_params['maxResults'] = request.max_results
            if request.next_token:
                list_params['nextToken'] = request.next_token
                
            # logger.info(f"Listing memories with params: {list_params}")
            
            # List all memory resources
            response = agentcore_control_client.list_memories(**list_params)
            memories = response.get('memories', [])
            
            logger.info(f"Successfully retrieved {len(memories)} memory resources")
            
            memory_entries = []
            for memory in memories:
                logger.debug(f"Got memory: {memory}")
                entry = ListMemoryProvidersResponseEntry(
                    arn=memory['arn'],
                    memory_id=memory['id'],
                    status=memory['status'],
                    created_at=memory['createdAt'].isoformat(),
                    updated_at=memory['updatedAt'].isoformat()
                ).to_dict()
                memory_entries.append(entry)
            logger.info(f"list_memory_providers returning memories {memory_entries}")
            return ListMemoryProvidersResponse(
                memories=memory_entries
            ).to_dict()
            
        except Exception as e:
            logger.error(f"Error listing  Memory resources: {str(e)}")
            raise e

    @staticmethod
    def update_memory_provider(
        request: UpdateMemoryProviderRequest
    ) -> UpdateMemoryProviderResponse:
        """
        Update a Bedrock  Memory resource.
        
        Args:
            agentcore_control_client: Boto3 client for  Control
            memory_id: ID of the memory resource to update
            description: Optional new description for the memory
            event_expiry_duration: Optional new retention period in days
            memory_strategies: Optional list of new memory strategies
            
        Returns:
            Updated memory details
        """
        logger.info(f"Updating  Memory resource with ID: {request.memory_id}")
        try:
            # First get current memory details to only update what's provided
            current_memory = agentcore_control_client.get_memory(
                memoryId=request.memory_id
            )['memory']
            
            # Prepare update parameters
            update_params = {
                'memoryId': request.memory_id
            }
            
            # Only add parameters that are provided
            if request.description is not None:
                update_params['description'] = request.description
                logger.info(f"Updating description to: {request.description}")
            else: 
                update_params['description'] = current_memory['description']

            if request.event_expiry_duration is not None:
                update_params['eventExpiryDuration'] = request.event_expiry_duration
                logger.info(f"Updating event expiry duration to: {request.event_expiry_duration} days")
            else: 
                update_params['eventExpiryDuration'] = current_memory['eventExpiryDuration']

            if request.memory_strategies is not None:
                update_params['memoryStrategies'] = request.memory_strategies
                logger.info(f"Updating memory strategies")
            else:
                update_params['memoryStrategies'] = current_memory['strategies']
                
            # Only perform update if we have parameters to update
            if len(update_params) > 1:  # more than just memoryId
                # Update the memory resource
                response = agentcore_control_client.update_memory(**update_params)['memory']
                logger.info(f"Successfully updated memory resource with ID: {response['id']}")
                logger.info(f"update_memory response {response}")
                strategies_returned = response['strategies']
                logger.info(f"strategies returned: {strategies_returned}")
                memory_provider = UpdateMemoryProviderResponse(
                    memory_id=response['id'],
                    name=response['name'],
                    description=response['description'],
                    event_expiry_duration=response['eventExpiryDuration'],
                    strategies=strategies_returned
                )
                result = AgentCoreMemoryClient.dates_to_strings(memory_provider)
                logger.info(f"Update memory_provider returning result {result}")
                return result
            else:
                logger.info(f"No updates provided for memory ID: {request.memory_id}")
                return current_memory
            
        except Exception as e:
            logger.error(f"Error updating Memory resource: {str(e)}")
            raise e

    @staticmethod
    def wait_for_memory_provider_creation(
        memory_id: str,
        max_attempts: int = 20,
        delay_seconds: int = 30
    ) -> Dict[str, Any]:
        
        logger.info(f"Called wait_for_memory_provider_creation for memory {memory_id}")
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
                logger.debug(f"Attempt {attempt}")
                # Try to get the memory details
                memory_details = agentcore_control_client.get_memory(
                    memoryId=memory_id
                )['memory']
                logger.debug(f"Got memory details {memory_details}")

                status = memory_details['status']
                # Check if the memory exists and has all expected attributes
                if status == 'ACTIVE':
                    logger.info(f"Memory {memory_id} is now available after {attempt} attempts")
                    logger.info(f"wait_for_memory_provider_creation returning memory_details {memory_details}")
                    return AgentCoreMemoryClient.dates_to_strings(memory_details)
                else:
                    logger.debug(f"Memory status: {status} (waiting {delay_seconds} seconds to check again)")
                    
            except Exception as e:
                if "Memory not found" in str(e) or "does not exist" in str(e):
                    logger.info(f"Attempt {attempt}/{max_attempts}: Memory {memory_id} not yet available")
                else:
                    logger.warning(f"Unexpected error checking memory: {str(e)}")
            
            # Wait before the next attempt
            if attempt < max_attempts:
                for t in range(1,30):
                    logger.debug('.', end='')
                time.sleep(delay_seconds)
        
        raise TimeoutError(f"Memory {memory_id} did not become available within the timeout period")

    
    def wait_for_memory_provider_deletion(
        agentcore_control_client,
        memory_id: str,
        max_attempts: int=20,
        delay_seconds: int=10
    ) -> bool:
        """
        Wait for memory deletion to complete.
        
        Args:
            agentcore_control_client: Boto3 client for  Control
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
    
    @staticmethod
    def create_event(request: CreateEventRequest) -> CreateEventResponse:
        logger.info(f"Sending payload for create_memory: {request.payload}")
        response: Dict[str, Any] = agentcore_client.create_event(
            memoryId=request.memory_id,
            sessionId=request.session_id,
            actorId=request.actor_id,
            eventTimestamp=request.event_timestamp,
            payload=request.payload
        )['event']

        logger.info(f"Response from create_event: {response}")

        memory_event = MemoryEvent(
            memory_id=response['memoryId'],
            actor_id=response['actorId'],
            session_id=response['sessionId'],
            event_id=response['eventId'],
            event_timestamp=response['eventTimestamp'].isoformat(),
            payload=request.payload,
            branch=response['branch']
        )

        logger.info(f"Created memory event {memory_event}")
        return memory_event

    @staticmethod
    def _save_agentcore_memory_id(memory_id, memory_name):
        ssm_client.put_parameter(
            Name=f"/{memory_name}/agentcore_memory_id",
            Value=memory_id,
            Type="String",
            Overwrite=True
        )
