"""
AgentCore Runtime Controller for managing AWS Bedrock AgentCore Runtime resources.

This controller provides static methods to create, retrieve, update, delete, and list
AgentCore Runtime resources using the AWS Bedrock AgentCore Control Plane API.

Usage:
  - Create agent runtimes for hosting agent workloads
  - Manage runtime lifecycle and configuration
  - Handle runtime endpoints and versioning
"""

from agentic_platform.service.agentcore.types import (
    AgentRuntimeOperation,
    AgentRuntimeRequest,
    AgentRuntimeResponse,
    CreateAgentRuntimeRequest,
    CreateAgentRuntimeResponse,
    DeleteAgentRuntimeRequest,
    DeleteAgentRuntimeResponse,
    GetAgentRuntimeRequest,
    GetAgentRuntimeResponse,
    ListAgentRuntimesRequest,
    ListAgentRuntimesResponse,
    UpdateAgentRuntimeRequest,
    UpdateAgentRuntimeResponse
)
from agentic_platform.service.agentcore.runtime.client.agentcore_runtime_client import AgentCoreRuntimeClient


class AgentCoreRuntimeController:

    @staticmethod
    def handler(event, context):
        evt = AgentRuntimeRequest(**event)
        if evt.operation == AgentRuntimeOperation.CREATE:
            result = AgentCoreRuntimeController.create_agentcore_runtime(
                CreateAgentRuntimeRequest(**evt.input)
            )
        
        elif evt.operation == AgentRuntimeOperation.DELETE:
            result = AgentCoreRuntimeController.delete_agentcore_runtime(
                DeleteAgentRuntimeRequest(**evt.input)
            )
        
        elif evt.operation == AgentRuntimeOperation.GET:
            result = AgentCoreRuntimeController.get_agentcore_runtime(
                GetAgentRuntimeRequest(**evt.input)
            )
        
        elif evt.operation == AgentRuntimeOperation.INVOKE:
            raise Exception("Invocations should go directly to the published agentcore runtimes")
        
        elif evt.operation == AgentRuntimeOperation.LIST:
            result = AgentCoreRuntimeController.list_agent_runtimes(
                ListAgentRuntimesRequest(**evt.input)
            )
        
        elif evt.operation == AgentRuntimeOperation.UPDATE:
            result = AgentCoreRuntimeController.update_agentcore_runtime(
                UpdateAgentRuntimeRequest(**evt.input)
            )
        
        else:
            raise Exception(f"Parameter validation exception: operation must be an AgentRuntimeOperation (one of {AgentRuntimeOperation.__dict__})")
        
        return AgentRuntimeResponse(
            status_code=200,
            result=result.__dict__
        ).__dict__
    
    @staticmethod
    def create_agentcore_runtime(request: CreateAgentRuntimeRequest) -> CreateAgentRuntimeResponse:
        return AgentCoreRuntimeClient.create_agentcore_runtime(request)
    
    @staticmethod
    def delete_agentcore_runtime(request: DeleteAgentRuntimeRequest) -> DeleteAgentRuntimeResponse:
        return AgentCoreRuntimeClient.delete_agentcore_runtime(request)
    
    @staticmethod
    def get_agentcore_runtime(request: GetAgentRuntimeRequest) -> GetAgentRuntimeResponse:
        return AgentCoreRuntimeClient.get_agentcore_runtime(request)

    @staticmethod
    def list_agent_runtimes(request: ListAgentRuntimesRequest) -> ListAgentRuntimesResponse:
        return AgentCoreRuntimeClient.list_agent_runtimes(request)
    
    @staticmethod
    def update_agentcore_runtime(request: UpdateAgentRuntimeRequest) -> UpdateAgentRuntimeResponse:
        return AgentCoreRuntimeClient.update_agentcore_runtime(request)

def handler(event, context):
    return AgentCoreRuntimeController.handler(event, context)