from agentic_platform.core.models.memory_models import (
    GetSessionContextRequest,
    GetSessionContextResponse,
    UpsertSessionContextRequest,
    UpsertSessionContextResponse,
    GetMemoriesRequest,
    GetMemoriesResponse,
    CreateMemoryRequest,
    CreateMemoryResponse
)

import os

from agentic_platform.core.models.memory_models import MemoryProviderType

memory_provider_env = os.getenv('MEMORY_PROVIDER') # POSTGRESQL or AGENTCORE
MEMORY_PROVIDER = MemoryProviderType.AGENTCORE if memory_provider_env == 'AGENTCORE' else MemoryProviderType.POSTGRESQL


class MemoryClient:

    @classmethod
    def get_session_context(cls, request: GetSessionContextRequest) -> GetSessionContextResponse:
        return PGMemoryClient.get_session_context(request)
    
    @classmethod
    def upsert_session_context(cls, request: UpsertSessionContextRequest) -> UpsertSessionContextResponse:
        return PGMemoryClient.upsert_session_context(request)
    
    @classmethod
    def get_memories(cls, request: GetMemoriesRequest) -> GetMemoriesResponse:
        return PGMemoryClient.get_memories(request)
    
    @classmethod
    def create_memory(cls, request: CreateMemoryRequest) -> CreateMemoryResponse:
        return PGMemoryClient.create_memory(request)
