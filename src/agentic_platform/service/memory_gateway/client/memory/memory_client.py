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

from .memory_client_factory import MemoryClientClientFactory
memory_client_class = MemoryClientClientFactory.get_memory_client()

class MemoryClient:
    @classmethod
    def get_session_context(cls, request: GetSessionContextRequest) -> GetSessionContextResponse:
       return memory_client_class.get_session_context(request)
    
    @classmethod
    def upsert_session_context(cls, request: UpsertSessionContextRequest) -> UpsertSessionContextResponse:
       return memory_client_class.upsert_session_context(request)
    
    @classmethod
    def get_memories(cls, request: GetMemoriesRequest) -> GetMemoriesResponse:
       return memory_client_class.get_memories(request)
    
    @classmethod
    def create_memory(cls, request: CreateMemoryRequest) -> CreateMemoryResponse:
        return memory_client_class.create_memory(request)
