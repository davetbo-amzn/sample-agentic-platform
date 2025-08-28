# Continue with regular imports.
from typing import Dict, Any
from fastapi import FastAPI, Request

from .types import (
    AgentRuntimeRequest as acrReq,
    AgentRuntimeResponse as acrResp,
    AgentCoreRuntimeOperation as acrOperation,
    CreateAgentRuntimeRequest as createAcrReq,
    CreateAgentRuntimeResponse as createAcrResp,
    DeleteAgentRuntimeRequest as deleteAcrReq,
    DeleteAgentRuntimeResponse as deleteAcrResp,
    GetAgentRuntimeRequest as getAcrReq,
    GetAgentRuntimeResponse as getAcrResp,
    ListAgentRuntimesRequest as listAcrReq,
    ListAgentRuntimesResponse as listAcrResp,
    UpdateAgentRuntimeRequest as updateAcrReq,
    UpdateAgentRuntimeResponse as updateAcrResp
)

# from agentic_platform.core.middleware.configure_middleware import configuration_server_middleware
from agentic_platform.service.agentcore.runtime.api.agentcore_runtime_controller import AgentCoreRuntimeController
import os

app = FastAPI()

# Configure middleware that's common to all servers.
# configuration_server_middleware(app, path_prefix="/api/agentcore-runtime")

# @app.post('/invocations')
# def invocations(request: Request) -> acrResp:
#     print(f"handler received request {request}")
#     if isinstance(request, dict):
#         print(f"Converting request to acrReq")
#         request = acrReq(
#             input=request['input'],
#             operation=request['operation'],
#         )
#         print(f"Type is now {type(request)}")

#     print(f"Handler got request {request}")
#     operation: acrOperation = acrOperation(request.operation)
#     print(f'Got operation {operation}')
#     result = None
#     if operation == acrOperation.CREATE:
#         result: createAcrResp = create_agent_runtime(createAcrReq(**request.input))

#     elif operation == acrOperation.DELETE:
#         print(f"Calling delete_agentcore_runtime with request input {request.input}")
#         delete_req = deleteAcrReq(**request.input)
#         print(f"delete_req = {delete_req}")
#         result: deleteAcrResp = delete_agentcore_runtime(delete_req)
#         print(f"delete result {result.__dict__}")

#     elif operation == acrOperation.GET:
#         result: getAcrResp = get_agentcore_runtime(getAcrReq(**request.input))

#     # elif operation == acrOperation.INVOKE:
#     #     print(f"Got request headers {request.headers}")
#     #     invoke_req = invokeAcrReq(
#     #         agentRuntimeArn=request.input['agentRuntimeArn'],
#     #         jwt=request.headers['Authorization'].split('Bearer ')[1],
#     #         payload = request.input['payload']
#     #     )
#     #     print(f"invoking agentcore runtime with request {request.input}, headers {request.headers}")
#     #     result: invokeAcrResp = invoke_agentcore_runtime(request=invokeAcrReq(**request.input))
#     #     user_message = request.input['payload']['prompt']
#     #     result = agent(user_message)

#     elif operation == acrOperation.LIST:
#         result: listAcrResp = list_agentcore_runtimes(listAcrReq(**request.input))

#     elif operation == acrOperation.UPDATE:
#         result: updateAcrResp = update_agentcore_runtime(updateAcrReq(**request.input))
#     else: 
#         raise Exception(f"Invalid AgentCoreRuntimeOperation provided {operation}")
    
#     print(f"returning result {result}")
#     return acrResp(
#         statusCode=200,
#         result=result
#     )

@app.post("/create-agentcore-runtime")
def create_agent_runtime(request: createAcrReq) -> createAcrResp:
    # print(f"Got request {request}")
    """Create a new AgentCore Runtime from S3 zip package."""
    return AgentCoreRuntimeController.create_agent_runtime(request)

@app.delete("/delete-agentcore-runtime")
def delete_agentcore_runtime(request: deleteAcrReq) -> deleteAcrResp:
    """Delete an existing AgentCore Runtime."""
    # print(f"Got DeleteAgentRuntimeRequest {request}")
    return AgentCoreRuntimeController.delete_agentcore_runtime(request)

@app.get("/get-agentcore-runtime")
def get_agentcore_runtime(agent_runtime_id: str) -> getAcrResp:
    """Get details of a specific AgentCore Runtime."""
    request = getAcrReq(agent_runtime_id=agent_runtime_id)
    return AgentCoreRuntimeController.get_agentcore_runtime(request)

@app.get("/list-agentcore-runtimes")
def list_agentcore_runtimes(maxResults: int = 20, nextToken: str = None) -> listAcrResp:
    """List all AgentCore Runtimes."""
    request = listAcrReq(maxResults=maxResults, nextToken=nextToken)
    return AgentCoreRuntimeController.list_agentcore_runtimes(request)

@app.put("/update-agentcore-runtime")
def update_agentcore_runtime(request: updateAcrReq) -> updateAcrResp:
    """Update an existing AgentCore Runtime."""
    return AgentCoreRuntimeController.update_agentcore_runtime(request)

@app.get("/ping")
async def health():
    """
    Health check endpoint for Kubernetes probes.
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)  # nosec B104 - Binding to all interfaces within container is intended
