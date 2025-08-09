from agentic_platform.core.models.memory_models import (
    CreateMemoryRequest,
    CreateMemoryResponse,
    CreateAgentCoreMemoryProviderRequest,
    CreateAgentCoreMemoryProviderResponse,
    DeleteAgentCoreMemoryProviderRequest,
    DeleteAgentCoreMemoryProviderResponse,
    UpdateAgentCoreMemoryProviderRequest,
    UpdateAgentCoreMemoryProviderResponse
)
from agentic_platform.service.memory_gateway.client.memory.agentcore_memory_client import AgentCoreMemoryClient
from agentic_platform.service.memory_gateway.client.memory.memory_client_factory import MemoryClientClientFactory


class AgentCoreMemoryProviderController:
    @staticmethod
    def create_memory_provider(request: CreateAgentCoreMemoryProviderRequest) -> CreateAgentCoreMemoryProviderResponse:
        return AgentCoreMemoryClient.create_memory_provider(request)
    
    @staticmethod
    def delete_memory_provider(request: DeleteAgentCoreMemoryProviderRequest) -> DeleteAgentCoreMemoryProviderResponse:
        return AgentCoreMemoryClient.delete_memory_provider(request)
    
    @staticmethod
    def update_memory_provider(request: UpdateAgentCoreMemoryProviderRequest) -> UpdateAgentCoreMemoryProviderResponse:
        return AgentCoreMemoryClient.update_memory_provider(request)