from agentic_platform.service.agentcore.types import (
    MemoryProviderOperation,
    MemoryProviderRequest,
    MemoryProviderResponse,
    CreateEventRequest,
    CreateEventResponse,
    CreateMemoryProviderRequest,
    CreateMemoryProviderResponse,
    CreateMemoryProviderRequest,
    CreateMemoryProviderResponse,
    DeleteMemoryProviderRequest,
    DeleteMemoryProviderResponse,
    GetMemoryProviderRequest,
    GetMemoryProviderResponse,
    ListEventsRequest,
    ListEventsResponse,
    ListMemoryProvidersRequest,
    ListMemoryProvidersResponse,
    ListMemoryRecordsRequest,
    ListMemoryRecordsResponse,
    UpdateMemoryProviderRequest,
    UpdateMemoryProviderResponse,
)
from agentic_platform.service.agentcore.memory.client.agentcore_memory_client import AgentCoreMemoryClient


class AgentCoreMemoryProviderController:

    @staticmethod
    def handler(event, context):
        evt = MemoryProviderRequest(**event)
        if evt.operation == MemoryProviderOperation.CREATE:
            result = AgentCoreMemoryProviderController.create_memory_provider(
                CreateMemoryProviderRequest(**evt.input)
            )
        
        elif evt.operation == MemoryProviderOperation.CREATE_EVENT:
            # this is an AgentPath memory which is like an AgentCore event.
            result = AgentCoreMemoryProviderController.create_event(
                CreateEventRequest(**evt.input)
            )
        
        elif evt.operation == MemoryProviderOperation.DELETE:
            result = AgentCoreMemoryProviderController.delete_memory_provider(
                DeleteMemoryProviderRequest(**evt.input)
            )
        
        elif evt.operation == MemoryProviderOperation.GET:
            result = AgentCoreMemoryProviderController.get_memory_provider(
                GetMemoryProviderRequest(**evt.input)
            )
        
        elif evt.operation == MemoryProviderOperation.LIST_EVENTS:
            result = AgentCoreMemoryProviderController.list_events(
                ListEventsRequest(**evt.input)
            )

        elif evt.operation == MemoryProviderOperation.LIST_MEMORY_PROVIDERS:
            result = AgentCoreMemoryProviderController.list_memory_providers(
                ListMemoryProvidersRequest(**evt.input)
            )
        
        elif evt.operation == MemoryProviderOperation.LIST_MEMORY_RECORDS:
            result = AgentCoreMemoryProviderController.list_memory_records(
                ListMemoryRecordsRequest(**evt.input)
            )
        
        elif evt.operation == MemoryProviderOperation.UPDATE:
            result = AgentCoreMemoryProviderController.update_memory_provider(
                UpdateMemoryProviderRequest(**evt.input)
            )
        

        elif evt.operation == MemoryProviderOperation.WAIT_FOR_CREATE:
            result = AgentCoreMemoryProviderController.wait_for_memory_provider_creation(
                evt.input.get('memory_id'),
                evt.input.get('max_attempts', 20),
                evt.input.get('delay_seconds', 30)
            )
        
        elif evt.operation == MemoryProviderOperation.WAIT_FOR_DELETE:
            result = AgentCoreMemoryProviderController.wait_for_memory_provider_deletion(
                evt.input.get('memory_id'), 
                evt.input.get('max_attempts', 20),
                evt.input.get('delay_seconds', 10)
            )
        
        else:
            raise Exception(f"Parameter validation exception: operation must be an MemoryProviderOperation (one of {MemoryProviderOperation.__dict__})")
        
        # Handle different result types for the response
        if hasattr(result, '__dict__'):
            result_dict = result.__dict__
        else:
            # For raw data like wait operations that return dictionaries or primitives
            result_dict = result if isinstance(result, dict) else {"result": result}
            
        return MemoryProviderResponse(
            statusCode=200,
            result=result_dict
        ).__dict__
    
    @staticmethod
    def create_memory_provider(request: CreateMemoryProviderRequest) -> CreateMemoryProviderResponse:
        return AgentCoreMemoryClient.create_memory_provider(request)
    
    @staticmethod
    def delete_memory_provider(request: DeleteMemoryProviderRequest) -> DeleteMemoryProviderResponse:
        return AgentCoreMemoryClient.delete_memory_provider(request)
    
    @staticmethod
    def get_memory_provider(request: GetMemoryProviderRequest) -> GetMemoryProviderResponse:
        return AgentCoreMemoryClient.get_memory_provider(request)
    
    @staticmethod
    def list_memory_providers(request: ListMemoryProvidersRequest) -> ListMemoryProvidersResponse:
        return AgentCoreMemoryClient.list_memory_providers(request)
    
    @staticmethod
    def update_memory_provider(request: UpdateMemoryProviderRequest) -> UpdateMemoryProviderResponse:
        return AgentCoreMemoryClient.update_memory_provider(request)
    
    @staticmethod
    def create_event(request: CreateEventRequest) -> CreateEventResponse:
        return AgentCoreMemoryClient.create_event(request)
    
    @staticmethod
    def list_events(request: ListEventsRequest) -> ListEventsResponse:
        return AgentCoreMemoryClient.list_events(request)
    
    @staticmethod
    def list_memory_records(request: ListMemoryRecordsRequest) -> ListMemoryRecordsResponse:
        return AgentCoreMemoryClient.list_memory_records(request)
    
    @staticmethod
    def wait_for_memory_provider_creation(memory_id: str, max_attempts: int = 20, delay_seconds: int = 30):
        return AgentCoreMemoryClient.wait_for_memory_provider_creation(memory_id, max_attempts, delay_seconds)
    
    @staticmethod
    def wait_for_memory_provider_deletion(memory_id: str, max_attempts: int = 20, delay_seconds: int = 10):
        return AgentCoreMemoryClient.wait_for_memory_provider_deletion(memory_id, max_attempts, delay_seconds)
    
def handler(event, context):
    return AgentCoreMemoryProviderController.handler(event, context)
