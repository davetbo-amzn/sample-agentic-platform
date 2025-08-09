from agentic_platform.core.models.memory_models import (
    GetMemoriesRequest,
    GetMemoriesResponse
)
from agentic_platform.service.memory_gateway.client.memory.memory_client import MemoryClient
from agentic_platform.service.memory_gateway.client.memory.memory_client_factory import MemoryClientClientFactory

memory_client: MemoryClient = MemoryClientClientFactory.get_memory_client()

class GetMemoriesController:
    @staticmethod
    def get_memories(request: GetMemoriesRequest) -> GetMemoriesResponse:
        return memory_client.get_memories(request)
