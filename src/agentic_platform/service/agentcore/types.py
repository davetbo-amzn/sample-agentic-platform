from typing import Dict, Any, Optional, List, Literal, Union, Annotated
from pydantic import BaseModel, Field, field_validator, Discriminator
from uuid import uuid4
from datetime import datetime, timezone
import boto3
from enum import Enum

class AgentRuntimeOperation(Enum):
    CREATE='create-agent-runtime'
    DELETE='delete-agent-runtime'
    GET='get-agent-runtime'
    INVOKE='invoke-agent-runtime'
    LIST='list-agent-runtimes'

class AgentRuntimeRequest(BaseModel):
    operation: AgentRuntimeOperation
    input: Dict[str, Any]

class AgentRuntimeResponse(BaseModel):
    status_code: int
    result: Any

#  Memory Provider Types
class MemoryEvent(BaseModel):
    memory_id: str
    actor_id: str
    session_id: str
    event_id: str
    event_timestamp: str
    payload: List[Dict[str, Any]]
    branch: Dict[str, str]

class MemoryRecordSummary(BaseModel):
    memory_record_id: str
    content: Dict[str, str]
    memory_strategy_id: str
    namespaces: List[str]
    created_at: str
    score: Optional[float] = None

class MemoryProviderOperation(Enum):
    CREATE = 'create-memory-provider'
    CREATE_EVENT = 'create-event' # this is an agentpath memory == agentcore event
    DELETE = 'delete-memory-provider'
    GET = 'get-memory-provider'
    LIST_EVENTS = 'list-events' # note this is AgentPath memories, which are like agentcore events
    LIST_MEMORY_PROVIDERS = 'list-memory-providers'
    LIST_MEMORY_RECORDS = 'list-memory-records'
    UPDATE = 'update-memory-provider'
    WAIT_FOR_CREATE = 'wait-for-memory-provider-creation'
    WAIT_FOR_DELETE = 'wait-for-memory-provider-deletion'

class MemoryProviderRequest(BaseModel):
    input: Dict[str, Any]
    operation: MemoryProviderOperation

class MemoryProviderResponse(BaseModel):
    statusCode: int
    result: Any

class CreateMemoryProviderRequest(BaseModel):
    environment: str="-AgentPath"
    retention_days: int=30,

class CreateMemoryProviderResponse(BaseModel):
    memory_id: str
    name: str
    status: str


class CreateEventRequest(BaseModel):
    memory_id: str
    actor_id: str
    session_id: str
    event_timestamp: str = datetime.now(timezone.utc).isoformat()
    payload: List[Dict[str, Any]]
    branch: Optional[Dict[str, str]] = None
    client_token: Optional[str] = uuid4().hex

class CreateEventResponse(BaseModel):
    memory_id: str
    actor_id: str
    session_id: str
    event_id: str
    event_timestamp: str
    payload: Dict[str, Any]
    branch: Dict[str, str]

class CreateAgentRuntimeRequest(BaseModel):
    s3_zip_path: str
    name: str
    ecr_repo_uri: Optional[str] = None
    entrypoint: Optional[str] = 'entrypoint.py'
    execution_role_arn: Optional[str] = None
    protocol: Optional[str] = 'HTTP'
    update_on_conflict: Optional[bool] = False

class AgentRuntimeStatus(Enum):
    CREATING='CREATING'
    CREATE_FAILED='CREATE_FAILED'
    UPDATING='UPDATING'
    UPDATE_FAILED='UPDATE_FAILED'
    READY='READY'
    DELETING='DELETING'

class AgentRuntime(BaseModel):
    agent_runtime_arn: str
    agent_runtime_id: str
    agent_runtime_version: str
    agent_runtime_name: str
    # description: Ostr
    status: AgentRuntimeStatus
    created_at: Optional[str] = None
    last_updated_at: Optional[str] = None
    workload_identity_details: Optional[Dict[str, str]] = None
    # last_updated_at: Optional[str] = None
    # role_arn: Optional[str] = None
    # agent_runtime_artifact: Optional[Dict[str, Any]] = None
    # network_configuration: Optional[Dict[str, str]] = None
    # protocol_configuration: Optional[Dict[str, str]] = None
    # environment_variables: Optional[Dict[str, str]] = None
    # authorizer_configuration: Optional[Dict[str, Any]] = None
    
class CreateAgentRuntimeResponse(BaseModel):
    agent_runtime_arn: str
    agent_runtime_id: str
    agent_runtime_version: str
    created_at: str
    status: AgentRuntimeStatus
    workload_identity_details: Dict[str, str]

class DeleteAgentRuntimeRequest(BaseModel):
    agent_runtime_id: str

class DeleteAgentRuntimeResponse(BaseModel):
    status: AgentRuntimeStatus

class DeleteMemoryProviderRequest(BaseModel):
    memory_id: str

class DeleteMemoryProviderResponse(BaseModel):
    memory_id: str

class GetAgentRuntimeRequest(BaseModel):
    agent_runtime_id: str
    agent_runtime_version: str=None
    
class GetAgentRuntimeResponse(BaseModel):
    agent_runtime_arn: str
    agent_runtime_id: str
    agent_runtime_version: str
    agent_runtime_name: str
    status: AgentRuntimeStatus
    workload_identity_details: Dict[str, str] = None
    created_at: str = None
    last_updated_at: str = None
    role_arn: str = None
    agent_runtime_artifact:Dict[str, Any] = None
    network_configuration: Dict[str, str] = None
    protocol_configuration: Dict[str, str] = None
    environment_variables: Dict[str, str] = None
    authorizer_configuration: Dict[str, Any] = None
    

class GetMemoryProviderRequest(BaseModel):
    memory_id: str 

class GetMemoryProviderResponse(BaseModel):
    arn: str
    memory_id: str
    name: str
    status: str

class ListEventsRequest(BaseModel):
    memory_id: str
    session_id: str
    actor_id: str
    include_payloads: Optional[bool] = True
    filter: Optional[Dict[str, Dict[str, str]]] = None
    max_results: Optional[int] = 20
    next_token: Optional[str] = None

class ListEventsResponse(BaseModel):
    events: List[MemoryEvent]
    next_token: Optional[str] = None

class ListMemoryRecordsRequest(BaseModel):
    memory_id: str
    namespace: str
    memory_strategy_id: Optional[str] = None
    max_results: int = 20
    next_token: Optional[str] = None

class ListMemoryRecordsResponse(BaseModel):
    memory_record_summaries: List[MemoryRecordSummary]
    next_token: Optional[str] = None

class ListMemoryProvidersRequest(BaseModel):
    max_results: int = 20
    next_token: Optional[str] = None 

class ListMemoryProvidersResponseEntry(BaseModel):
    arn: str
    memory_id: str
    status: str
    created_at: str
    updated_at: str
    def to_dict(item):
        return {
            'arn': item.arn,
            'memory_id': item.memory_id,
            'status': item.status,
            'created_at': item.created_at,
            'updated_at': item.updated_at
        }
    
class ListMemoryProvidersResponse(BaseModel):
    memories: List[ListMemoryProvidersResponseEntry]
    def to_dict(item): 
        mems = []
        for mem in item.memories:
            mems.append(mem.to_dict())
        return {
            'memories': mems
        }

class ListAgentRuntimesRequest(BaseModel):
    max_results: int=20
    next_token: str=None

class ListAgentRuntimesResponse(BaseModel):
    agent_runtimes: List[AgentRuntime]
    next_token: str = None

class UpdateMemoryProviderRequest(BaseModel):
    memory_id: str
    description: str
    event_expiry_duration: int=30
    memory_strategies: Optional[Dict[str, List[Dict[str, Any]]]] = {}

class UpdateMemoryProviderResponse(BaseModel):
    memory_id: str
    name: str
    description: str
    event_expiry_duration: int
    strategies: List[Dict[str, Any]]

class ListAgentRuntimesRequest(BaseModel):
    max_results: Optional[int] = 20
    next_token: Optional[str] = None

class ListRuntimesResponse(BaseModel):
    runtimes: List[Dict[str, Any]]
    next_token: Optional[str]

class UpdateAgentRuntimeRequest(BaseModel):
    agent_runtime_id: str
    agent_runtime_artifact: Dict[str, Dict[str, str]]
    roleArn: str
    network_configuration: Dict[str, str]
    protocol_configuration: Dict[str, str]
    authorizer_configuration: Dict[str, Dict[str, Any]]
    client_token: Optional[str]
    description: Optional[str]
    environment_variables: Optional[Dict[str, str]] = {}

class UpdateAgentRuntimeResponse(BaseModel):
    agent_runtime_arn: str
    agent_runtime_id: str
    workload_identity_details: Dict[str, Dict[str, str]]
    agent_runtime_version: str
    created_at: str
    last_updated_at: str
    status: str
