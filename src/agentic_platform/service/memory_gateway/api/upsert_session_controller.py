from agentic_platform.core.models.memory_models import (
    UpsertSessionContextRequest,
    UpsertSessionContextResponse
)
from agentic_platform.service.memory_gateway.client.memory.memory_client import MemoryClient
from agentic_platform.service.memory_gateway.client.memory.memory_client_factory import MemoryClientClientFactory

memory_client = MemoryClientClientFactory.get_memory_client()
class UpsertSessionContextController:
    @staticmethod
    def upsert_session_context(request: UpsertSessionContextRequest) -> UpsertSessionContextResponse:
        return memory_client.upsert_session_context(request)