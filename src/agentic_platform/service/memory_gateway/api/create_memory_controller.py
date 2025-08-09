from agentic_platform.core.models.memory_models import (
    CreateMemoryRequest,
    CreateMemoryResponse
)
from agentic_platform.service.memory_gateway.client.memory.memory_client import MemoryClient
from agentic_platform.service.memory_gateway.client.memory.memory_client_factory import MemoryClientClientFactory

memory_client: MemoryClient = MemoryClientClientFactory.get_memory_client()

class CreateMemoryController:
    @staticmethod
    def create_memory(request: CreateMemoryRequest) -> CreateMemoryResponse:
        return memory_client.create_memory(request)