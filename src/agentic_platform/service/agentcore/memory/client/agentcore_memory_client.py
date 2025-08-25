"""
AWS Lambda function to provision and manage Bedrock  Memory resources.

This function is used by Terraform to create and update Bedrock  memory
capabilities for the Agentic Platform.

Usage:
  - The function is invoked by Terraform with appropriate configuration parameters
  - It creates or updates  resources using the boto3 SDK
  - It handles provision action for now

Environment Variables:
  - MEMORY_RETENTION_PERIOD: Number of days to retain memory (default: 30)
  - ENVIRONMENT: Deployment environment (e.g., dev, prod)
  - REGION: AWS region for Bedrock  resources
"""

import boto3
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict

from agentic_platform.service.agentcore.types import (
    MemoryEvent,
    CreateMemoryProviderRequest,
    CreateMemoryProviderResponse,
    CreateEventRequest,
    CreateEventResponse,
    DeleteMemoryProviderRequest,
    DeleteMemoryProviderResponse,
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
    UpdateMemoryProviderRequest,
    UpdateMemoryProviderResponse
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get environment variables
MEMORY_RETENTION_DAYS = int(os.environ.get('MEMORY_RETENTION_PERIOD', 30))
ENVIRONMENT = os.environ.get('ENVIRONMENT', '-AgentPath')
REGION = os.environ.get('REGION', 'us-west-2')

agentcore_client = boto3.client('bedrock-agentcore', region_name=REGION)
agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
ssm_client = boto3.client('ssm', region_name=REGION)
agentcore_memory_id = None

class AgentCoreMemoryClient:

    @staticmethod
    def _get_agentcore_memory_id():
        global agentcore_memory_id
        if not agentcore_memory_id:
            try:
                param_name = f"/{ENVIRONMENT}/agentcore_memory_id"
                # print(f"Checking for ssm param {param_name}")
                parameters = ssm_client.get_parameters_by_path(
                    Path=param_name
                )['Parameters']
                if len(parameters) > 0:
                    agentcore_memory_id = parameters[0]['Value']
                else:
                    print(f"Creating agentcore model {ENVIRONMENT}")
                    # Create a proper CreateMemoryProviderRequest with default values
                    create_request = CreateMemoryProviderRequest(
                        environment=ENVIRONMENT,
                        retention_days=MEMORY_RETENTION_DAYS
                    )
                    response = AgentCoreMemoryClient.create_memory_provider(create_request)
                    print(f"response from create_model_provider {response}")

                    AgentCoreMemoryClient.wait_for_memory_provider_creation(
                        response.memory_id
                    )
                    agentcore_memory_id = response.memory_id
                    ssm_client.put_parameter(
                        Name=param_name,
                        Value=agentcore_memory_id,
                        Type='String',
                        Overwrite=True
                    )

            except Exception as e:
                raise e
        return agentcore_memory_id

    @staticmethod
    def dates_to_strings(agentcore_memory):
        # print(f"dates_to_strings received agentcore_memory {agentcore_memory}")
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

        print(f"Provisioning  Memory {ENVIRONMENT} with {request.retention_days} day retention for environment {ENVIRONMENT}")
        try:
            # Create a unique resource name and namespace for this environment            
            # Create memory configuration using the control plane client
            memory_name = ENVIRONMENT.replace('-','_')
            print(f"creating memory name {memory_name}")
            create_response = agentcore_control_client.create_memory(
                name=memory_name,
                description=f" memory for {ENVIRONMENT} environment",
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
            print(f"Got create response {create_response}")
            memory_id = create_response['id']
            print(f"Creating agentcore memory resource with ID: {memory_id}")
            print("Waiting for memory creation to complete.")
            result = AgentCoreMemoryClient.wait_for_memory_provider_creation(memory_id)
            print(f"Memory creation result: {result}")
            status = agentcore_control_client.get_memory(
                memoryId=memory_id
            )['memory']['status']

            print(f"memory {memory_id} status {status}")
            if not status == 'READY':
                raise Exception(f'Failed to create memory {memory_name}')
            
            AgentCoreMemoryClient._save_agentcore_memory_id(memory_id)
            logger.info(" Memory provisioning completed successfully")
            agentcore_memory_id = memory_id
            return CreateMemoryProviderResponse(
                memory_id=agentcore_memory_id,
                name=memory_name,
                status=create_response['status'],
            )
        
        except Exception as create_error:
            print(f"ERROR: {str(create_error)}")
            if "already exists" in str(create_error):
                print(f"Memory {memory_name} already exists")
                memories = agentcore_control_client.list_memories()['memories']
                for mem in memories:
                    if mem['id'].split('-')[0] == memory_name:
                        print(f"Found memory {mem}")
                        agentcore_memory_id = mem['id']
                        AgentCoreMemoryClient._save_agentcore_memory_id(agentcore_memory_id)
                        print(f"Returning existing agentcore_memory_id {agentcore_memory_id}")
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
        print(f"delete_memory_provider got request {request}")
        try:
            memory_id = request.memory_id
            print(f"Deleting memory with id {memory_id}")
            # Delete the memory resource 
            agentcore_control_client.delete_memory(
                memoryId=memory_id
            )
            
            print(f"Successfully deleted memory resource with ID: {memory_id}")
            return DeleteMemoryProviderResponse(memory_id=memory_id)
            
        except Exception as e:
            logger.error(f"Error deleting  Memory resource: {str(e)}")
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
        print(f"get_memory_provider got request {request}")
        try:
            memory_id = request.memory_id
            print(f"Retrieving memory with id {memory_id}")
            # Get the memory resource 
            response = agentcore_control_client.get_memory(
                memoryId=memory_id
            )['memory']
            
            print(f"Successfully retrieved memory resource with ID: {memory_id}")
            return GetMemoryProviderResponse(
                memory_id=response['id'],
                arn=response['arn'],
                name=response['name'],
                status=response['status'],
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
            print(f"Got response record {rec}")
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
        print(f"list_memory_providers got request {request}")
        try:
            # Prepare parameters for list_memories call
            list_params = {}
            if request.max_results:
                list_params['maxResults'] = request.max_results
            if request.next_token:
                list_params['nextToken'] = request.next_token
                
            print(f"Listing memories with params: {list_params}")
            
            # List all memory resources
            response = agentcore_control_client.list_memories(**list_params)
            memories = response.get('memories', [])
            
            print(f"Successfully retrieved {len(memories)} memory resources")
            
            memory_entries = []
            for memory in memories:
                print(f"Got memory: {memory}")
                entry = ListMemoryProvidersResponseEntry(
                    arn=memory['arn'],
                    memory_id=memory['id'],
                    status=memory['status'],
                    created_at=memory['createdAt'].isoformat(),
                    updated_at=memory['updatedAt'].isoformat()
                ).to_dict()
                memory_entries.append(entry)
            print(f"list_memory_providers returning memories {memory_entries}")
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
        print(f"Updating  Memory resource with ID: {request.memory_id}")
        try:
            # First get current memory details to only update what's provided
            current_memory = agentcore_control_client.get_memory(
                memoryId=request.memory_id
            )
            
            # Prepare update parameters
            update_params = {
                'memoryId': request.memory_id
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
                response = agentcore_control_client.update_memory(**update_params)['memory']
                logger.info(f"Successfully updated memory resource with ID: {response['id']}")
                print(f"update_memory response {response}")
                strategies_returned = response['strategies']
                print(f"strategies returned: {strategies_returned}")
                memory_provider = UpdateMemoryProviderResponse(
                    memory_id=response['id'],
                    name=response['name'],
                    description=response['description'],
                    event_expiry_duration=response['eventExpiryDuration'],
                    strategies=strategies_returned
                )
                result = AgentCoreMemoryClient.dates_to_strings(memory_provider)
                print(f"Update memory_provider returning result {result}")
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
        
        print(f"Called wait_for_memory_provider_creation for memory {memory_id}")
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
                print(f"Got memory details {memory_details}")

                status = memory_details['status']
                # Check if the memory exists and has all expected attributes
                if status == 'ACTIVE':
                    logger.info(f"Memory {memory_id} is now available after {attempt} attempts")
                    # if 'createdAt' in memory_details:
                    #     print('Updating createdAt field to iso string')
                    #     memory_details['createdAt'] = memory_details['createdAt'].isoformat()
                    # if 'updatedAt' in memory_details:
                    #     print('Updating updatedAt field to iso string')
                    #     memory_details['updatedAt'] = memory_details['updatedAt'].isoformat()
                    print(f"wait_for_memory_provider_creation returning memory_details {memory_details}")
                    return AgentCoreMemoryClient.dates_to_strings(memory_details)
                else:
                    print(f"Memory status: {status} (waiting {delay_seconds} seconds to check again)")
                    
            except Exception as e:
                if "Memory not found" in str(e) or "does not exist" in str(e):
                    logger.info(f"Attempt {attempt}/{max_attempts}: Memory {memory_id} not yet available")
                else:
                    logger.warning(f"Unexpected error checking memory: {str(e)}")
            
            # Wait before the next attempt
            if attempt < max_attempts:
                for t in range(1,30):
                    print('.', end='')
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

    # @staticmethod
    # def _events_to_messages(events):
    #     msgs = []
    #     for evt in events:
    #         print(f"Got event {evt}")
    #         msgs.append(Message(
    #             role=evt['payload'][0]['conversational']['role'],
    #             content=[{
    #                 "type": "text",
    #                 "text": evt['payload'][0]['conversational']['content']['text']
    #             }],
    #             tool_calls=[],
    #             tool_results=[]

    #         ))
    #     return msgs
    
    # @staticmethod
    # def _events_to_memories(events):
    #     mems = []
    #     memory_id = AgentCoreMemoryClient._get_agentcore_memory_id()
    #     for evt in events:
    #         mems.append(MemoryEvent(
    #             event_id=evt['eventId'],
    #             memory_id=evt['memoryId'],
    #             session_id=evt['sessionId'],
    #             actor_id=evt['actorId'],
    #             event_timestamp=evt['eventTimestamp'],
    #             payload=evt['payload'],
    #             branch=evt['branch']
    #         ))
    #     return mems
        
    # @staticmethod
    # def _initialize_session(actor_id):
    #     payload = [{
    #         "conversational": {
    #             "content": {
    #                 "text": "Initializing new  memory session."
    #             },
    #             "role": "ASSISTANT"
    #         }
    #     }]
    #     event = agentcore_client.create_event(
    #         memoryId=agentcore_memory_id,
    #         actorId=actor_id,
    #         eventTimestamp=datetime.now(),
    #         payload=payload
    #     )['event']
    #     print(f"Got event response {event}")
        
        
    #     session_ctx = SessionContext(
    #         session_id=event['sessionId'],
    #         user_id=event['actorId'],
    #         messages=[Message(
    #             role='assistant',
    #             content=[{
    #                 "type": "text",
    #                 "text": payload[0]['conversational']['content']['text']
    #             }]
    #         )]
    #     )
    
    #     return session_ctx
    
    # @staticmethod
    # def get_memories(request: GetMemoryEventsRequest) -> GetMemoriesResponse:
    #     # memories in AgentPath are equivalent to events in .
    #     print(f"get_memories got request {request}, of type {type(request)}")
    #     args = {
    #         "sessionId": request.session_id,
    #         "actorId": request.user_id,
    #         "maxResults": request.limit,
    #         "memoryId": AgentCoreMemoryClient._get_agentcore_memory_id()
    #     }
    #     if request.next_token:
    #         args['nextToken'] = request.next_token
    #     print(f"invoking list_events with args {args}")
    #     events = agentcore_client.list_events(**args)['events']
    #     print(f"Got events: {events}")
    #     memories = AgentCoreMemoryClient._events_to_memories(events)
    #     print(f"Converted events to memories: {memories}")
    #     # for evt in events:
    #     #     del evt['memoryId']
    #     #     del evt['actorId']
    #     #     memories.append(evt)
    #     # if memories == []:
    #     #     print(f"Creating default initial memory.")
    #     #     if not hasattr(request, 'agent_id') or not request.agent_id:
    #     #         request.agent_id='not submitted with request'

    #     #     mem = Memory(
    #     #         session_id=request.session_id,
    #     #         user_id=request.user_id,
    #     #         agent_id=request.agent_id,
    #     #         content="No memories yet.",
    #     #         embedding_model="embedding model n/a with Bedrock ",
    #     #     )
    #     #     print(f"Returning initial mem {mem}")
    #     #     memories = [mem]
    #     print(f"returning context: {memories}")
    #     return GetMemoriesResponse(
    #         memories=memories
    #     )
    
    
    @staticmethod
    def create_event(request: CreateEventRequest) -> CreateEventResponse:
        print(f"Sending payload for create_memory: {request.payload}")
        response: Dict[str, Any] = agentcore_client.create_event(
            memoryId=request.memory_id,
            sessionId=request.session_id,
            actorId=request.actor_id,
            eventTimestamp=request.event_timestamp,
            payload=request.payload
        )['event']

        print(f"Response from create_event: {response}")

        memory_event = MemoryEvent(
            memory_id=response['memoryId'],
            actor_id=response['actorId'],
            session_id=response['sessionId'],
            event_id=response['eventId'],
            event_timestamp=response['eventTimestamp'].isoformat(),
            payload=request.payload,
            branch=response['branch']
        )

        print(f"Created memory event {memory_event}")
        return memory_event

    @staticmethod
    def _save_agentcore_memory_id(memory_id):
        ssm_client.put_parameter(
            Name=f"/{ENVIRONMENT}/agentcore_memory_id",
            Value=memory_id,
            Type="String",
            Overwrite=True
        )
