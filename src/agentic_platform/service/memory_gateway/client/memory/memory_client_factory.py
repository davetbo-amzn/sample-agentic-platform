import os
from importlib import import_module

from agentic_platform.core.models.memory_models import MemoryClientType
# from agentic_platform.service.memory_gateway.client.memory.memory_client import MemoryClient

class MemoryClientClientFactory: 
    @staticmethod
    def get_memory_client() :
        memory_client_type = MemoryClientType[os.getenv("MEMORY_CLIENT", "POSTGRESQL")]
        py_path = 'agentic_platform.service.memory_gateway.client.memory.pg_memory_client.PGMemoryClient' \
            if memory_client_type == MemoryClientType.POSTGRESQL \
            else 'agentic_platform.service.memory_gateway.client.memory.agentcore_memory_client.AgentCoreMemoryClient'
        parts = py_path.split('.')
        client_file = '.'.join(parts[:-1])
        client_classname = parts[-1]
        client_module = import_module(client_file)
        return getattr(client_module, client_classname)
        