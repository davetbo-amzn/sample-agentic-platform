from agentic_platform.core.models.memory_models import (
    GetSessionContextRequest,
    GetSessionContextResponse
)
from agentic_platform.service.memory_gateway.client.memory.memory_client import MemoryClient
from agentic_platform.service.memory_gateway.client.memory.memory_client_factory import MemoryClientClientFactory

memory_client: MemoryClient = MemoryClientClientFactory.get_memory_client()
class GetSessionContextController:
    @staticmethod
    def get_session_context(request: GetSessionContextRequest) -> GetSessionContextResponse:
        return memory_client.get_session_context(request)