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
    UPDATE='update-agent-runtime'

class AgentRuntimeRequest(BaseModel):
    operation: AgentRuntimeOperation
    input: Dict[str, Any]

class AgentRuntimeResponse(BaseModel):
    status_code: int
    result: Any
    
    def to_dict(self):
        return {
            'status_code': self.status_code,
            'result': self.result
        }

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
    def to_dict(item):
        return {
            "memory_record_id": item.memory_record_id,
            "content": item.content,
            "memory_strategy_id": item.memory_strategy_id,
            "namespaces": item.namespaces,
            "created_at": item.created_at,
            "score": item.score
        }

class MemoryProviderOperation(Enum):
    CREATE = 'create-memory-provider'
    CREATE_EVENT = 'create-event' # this is an agentpath memory == agentcore event
    DELETE = 'delete-memory-provider'
    DELETE_MEMORY_RECORD = 'delete-memory-record'
    GET = 'get-memory-provider'
    LIST_EVENTS = 'list-events' # note this is AgentPath memories, which are like agentcore events
    LIST_MEMORY_PROVIDERS = 'list-memory-providers'
    LIST_MEMORY_RECORDS = 'list-memory-records'
    RETRIEVE_MEMORY_RECORDS = 'retrieve-memory-records'
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
    name: str
    retention_days: int=30

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
    agent_description: Optional[str] = None
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
    def __str__(item):
        return item.value

class AgentRuntime(BaseModel):
    agent_runtime_arn: str
    agent_runtime_id: str
    agent_runtime_version: str
    agent_runtime_name: str
    # description: Ostr
    status: AgentRuntimeStatus
    # created_at: Optional[str] = None
    # last_updated_at: Optional[str] = None
    created_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    workload_identity_details: Optional[Dict[str, str]] = None
    def to_dict(self):
        return {
            "agent_runtime_arn": self.agent_runtime_arn,
            "agent_runtime_id": self.agent_runtime_id,
            "agent_runtime_version": self.agent_runtime_version,
            "agent_runtime_name": self.agent_runtime_name,
            "status": self.status.value,
            "created_at": None if not self.created_at else self.created_at.isoformat(),
            "last_updated_at": None if not self.last_updated_at else self.last_updated_at.isoformat(),
            "workload_identity_details": self.workload_identity_details
        }
    
class CreateAgentRuntimeResponse(BaseModel):
    agent_runtime_arn: str
    agent_runtime_id: str
    agent_runtime_version: str
    created_at: str
    status: AgentRuntimeStatus
    workload_identity_details: Dict[str, str]
    
    def to_dict(self):
        return {
            'agent_runtime_arn': self.agent_runtime_arn,
            'agent_runtime_id': self.agent_runtime_id,
            'agent_runtime_version': self.agent_runtime_version,
            'created_at': self.created_at,
            'status': self.status.value if isinstance(self.status, AgentRuntimeStatus) else self.status,
            'workload_identity_details': self.workload_identity_details
        }

class DeleteAgentRuntimeRequest(BaseModel):
    agent_runtime_id: str

class DeleteAgentRuntimeResponse(BaseModel):
    status: AgentRuntimeStatus
    agent_runtime_id: str
    def to_dict(self):
        return {
            "agent_runtime_id": self.agent_runtime_id,
            'status': self.status.value if isinstance(self.status, AgentRuntimeStatus) else self.status
        }

class DeleteMemoryProviderRequest(BaseModel):
    memory_id: str

class DeleteMemoryProviderResponse(BaseModel):
    memory_id: str

class DeleteMemoryRecordRequest(BaseModel):
    memory_id: str
    memory_record_id: str

class DeleteMemoryRecordResponse(BaseModel):
    memory_record_id: str

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
    def to_dict(self):
        return {
            'agent_runtime_arn': self.agent_runtime_arn,
            'agent_runtime_id': self.agent_runtime_id,
            'agent_runtime_version': self.agent_runtime_version,
            'agent_runtime_name': self.agent_runtime_name,
            'status': self.status.value if isinstance(self.status, AgentRuntimeStatus) else self.status,
            'workload_identity_details': self.workload_identity_details,
            'created_at': self.created_at,
            'last_updated_at': self.last_updated_at,
            'role_arn': self.role_arn,
            'agent_runtime_artifact': self.agent_runtime_artifact,
            'network_configuration': self.network_configuration,
            'protocol_configuration': self.protocol_configuration,
        }
    

class GetMemoryProviderRequest(BaseModel):
    memory_id: str 


class MemoryStrategy(BaseModel):
    strategy_id: str
    name: str
    description: str
    memory_type: str
    namespaces: List[str]
    created_at: datetime
    updated_at: datetime
    status: str
    def to_dict(item): 
        return {
            "strategy_id": item.strategy_id,
            "name": item.name,
            "description": item.description,
            "memory_type": item.memory_type,
            "namespaces": item.namespaces,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat()
        }
    
class GetMemoryProviderResponse(BaseModel):
    arn: str
    memory_id: str
    name: str
    description: str
    event_expiry_duration: int
    status: str
    failure_reason: str=''
    created_at: datetime
    updated_at: datetime
    strategies: List[MemoryStrategy]
    def to_dict(item):
        strats = []
        for strat in item.strategies:
            strats.append(strat.to_dict())
        return {
            "arn": item.arn,
            "memory_id": item.memory_id,
            "description": item.description,
            "event_expiry_duration": item.event_expiry_duration,
            "status": item.status,
            "failure_reason": item.failure_reason,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
            "strategies": strats
        }

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

class RetrieveMemoryRecordsRequest(BaseModel):
    memory_id: str
    query: str
    memory_strategy_id: str
    actor_id: str
    max_results: int = 5
    session_id: Optional[str] = None

class RetrieveMemoryRecordsResponse(BaseModel):
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
    
    def to_dict(self):
        return {
            'agent_runtimes': [runtime.to_dict() for runtime in self.agent_runtimes],
            'next_token': self.next_token
        }

class UpdateMemoryProviderRequest(BaseModel):
    memory_id: str
    description: str
    event_expiry_duration: Optional[int]=None
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
    agent_runtime_artifact: Optional[Dict[str, Dict[str, str]]] = None
    roleArn: Optional[str] = None
    network_configuration: Optional[Dict[str, str]] = None
    protocol_configuration: Optional[Dict[str, str]] = None
    client_token: Optional[str] = None
    description: Optional[str] = None
    environmentVariables: Optional[Dict[str, str]] = None

class UpdateAgentRuntimeResponse(BaseModel):
    agent_runtime_arn: str
    agent_runtime_id: str
    workload_identity_details: Dict[str, Dict[str, str]]
    agent_runtime_version: str
    created_at: str
    last_updated_at: str
    status: str
    
    def to_dict(self):
        return {
            'agent_runtime_arn': self.agent_runtime_arn,
            'agent_runtime_id': self.agent_runtime_id,
            'workload_identity_details': self.workload_identity_details,
            'agent_runtime_version': self.agent_runtime_version,
            'created_at': self.created_at,
            'last_updated_at': self.last_updated_at,
            'status': self.status
        }

# OAuth2 Credential Provider Types
class OAuth2CredentialProviderOperation(Enum):
    CREATE='create-oauth2-credential-provider'
    DELETE='delete-oauth2-credential-provider'
    GET='get-oauth2-credential-provider'
    LIST='list-oauth2-credential-providers'
    UPDATE='update-oauth2-credential-provider'

class OAuth2CredentialProviderRequest(BaseModel):
    operation: OAuth2CredentialProviderOperation
    input: Dict[str, Any]

class OAuth2CredentialProviderResponse(BaseModel):
    status_code: int
    result: Any
    
    def to_dict(self):
        return {
            'status_code': self.status_code,
            'result': self.result
        }

class OAuth2CredentialProviderStatus(Enum):
    CREATING='CREATING'
    CREATE_FAILED='CREATE_FAILED'
    UPDATING='UPDATING'
    UPDATE_FAILED='UPDATE_FAILED'
    READY='READY'
    DELETING='DELETING'
    
    def __str__(self):
        return self.value

class GoogleOAuth2Config(BaseModel):
    client_id: str
    client_secret: str

class CreateOauth2CredentialProviderRequest(BaseModel):
    name: str
    provider_type: Literal['google'] = 'google'
    scopes: List[str]
    google_config: Optional[GoogleOAuth2Config] = None
    client_token: Optional[str] = Field(default_factory=lambda: uuid4().hex)

class OAuth2CredentialProvider(BaseModel):
    arn: str
    credential_provider_id: str
    name: str
    provider_type: str
    status: OAuth2CredentialProviderStatus
    scopes: List[str]
    created_at: Optional[str] = None
    last_updated_at: Optional[str] = None
    
    def to_dict(self):
        return {
            'arn': self.arn,
            'credential_provider_id': self.credential_provider_id,
            'name': self.name,
            'provider_type': self.provider_type,
            'status': self.status.value if isinstance(self.status, OAuth2CredentialProviderStatus) else self.status,
            'scopes': self.scopes,
            'created_at': self.created_at,
            'last_updated_at': self.last_updated_at
        }

class CreateOauth2CredentialProviderResponse(BaseModel):
    arn: str
    credential_provider_id: str
    name: str
    provider_type: str
    status: OAuth2CredentialProviderStatus
    scopes: List[str]
    created_at: str
    
    def to_dict(self):
        return {
            'arn': self.arn,
            'credential_provider_id': self.credential_provider_id,
            'name': self.name,
            'provider_type': self.provider_type,
            'status': self.status.value if isinstance(self.status, OAuth2CredentialProviderStatus) else self.status,
            'scopes': self.scopes,
            'created_at': self.created_at
        }

class DeleteOauth2CredentialProviderRequest(BaseModel):
    credential_provider_id: str

class DeleteOauth2CredentialProviderResponse(BaseModel):
    status: OAuth2CredentialProviderStatus
    
    def to_dict(self):
        return {
            'status': self.status.value if isinstance(self.status, OAuth2CredentialProviderStatus) else self.status
        }

class GetOauth2CredentialProviderRequest(BaseModel):
    credential_provider_id: str

class GetOauth2CredentialProviderResponse(BaseModel):
    arn: str
    credential_provider_id: str
    name: str
    provider_type: str
    status: OAuth2CredentialProviderStatus
    scopes: List[str]
    created_at: str
    last_updated_at: str
    
    def to_dict(self):
        return {
            'arn': self.arn,
            'credential_provider_id': self.credential_provider_id,
            'name': self.name,
            'provider_type': self.provider_type,
            'status': self.status.value if isinstance(self.status, OAuth2CredentialProviderStatus) else self.status,
            'scopes': self.scopes,
            'created_at': self.created_at,
            'last_updated_at': self.last_updated_at
        }

class ListOauth2CredentialProvidersRequest(BaseModel):
    max_results: Optional[int] = 20
    next_token: Optional[str] = None

class ListOauth2CredentialProvidersResponse(BaseModel):
    oauth2_credential_providers: List[OAuth2CredentialProvider]
    next_token: Optional[str] = None
    
    def to_dict(self):
        return {
            'oauth2_credential_providers': [provider.to_dict() for provider in self.oauth2_credential_providers],
            'next_token': self.next_token
        }

class UpdateOauth2CredentialProviderRequest(BaseModel):
    credential_provider_id: str
    name: Optional[str] = None
    scopes: Optional[List[str]] = None
    google_config: Optional[GoogleOAuth2Config] = None
    client_token: Optional[str] = Field(default_factory=lambda: uuid4().hex)

class UpdateOauth2CredentialProviderResponse(BaseModel):
    arn: str
    credential_provider_id: str
    name: str
    provider_type: str
    status: OAuth2CredentialProviderStatus
    scopes: List[str]
    created_at: str
    last_updated_at: str
    
    def to_dict(self):
        return {
            'arn': self.arn,
            'credential_provider_id': self.credential_provider_id,
            'name': self.name,
            'provider_type': self.provider_type,
            'status': self.status.value if isinstance(self.status, OAuth2CredentialProviderStatus) else self.status,
            'scopes': self.scopes,
            'created_at': self.created_at,
            'last_updated_at': self.last_updated_at
        }

# Gateway Types
class GatewayOperation(Enum):
    CREATE = 'create-gateway'
    DELETE = 'delete-gateway'
    GET = 'get-gateway'
    LIST = 'list-gateways'
    UPDATE = 'update-gateway'
    WAIT_FOR_CREATE = 'wait-for-gateway-creation'
    WAIT_FOR_DELETE = 'wait-for-gateway-deletion'

class GatewayRequest(BaseModel):
    operation: GatewayOperation
    input: Dict[str, Any]

class GatewayResponse(BaseModel):
    status_code: int
    result: Any
    
    def to_dict(self):
        return {
            'status_code': self.status_code,
            'result': self.result
        }

class GatewayStatus(Enum):
    CREATING = 'CREATING'
    CREATE_FAILED = 'CREATE_FAILED'
    UPDATING = 'UPDATING'
    UPDATE_FAILED = 'UPDATE_FAILED'
    READY = 'READY'
    DELETING = 'DELETING'
    
    def __str__(self):
        return self.value

class CreateGatewayRequest(BaseModel):
    name: str
    role_arn: str
    protocol_type: str = 'MCP'
    description: Optional[str] = None
    protocol_configuration: Optional[Dict[str, Any]] = None
    authorizer_type: str = 'CUSTOM_JWT'
    authorizer_configuration: Optional[Dict[str, Any]] = None
    kms_key_arn: Optional[str] = None
    exception_level: Optional[str] = None
    client_token: Optional[str] = Field(default_factory=lambda: uuid4().hex)

class Gateway(BaseModel):
    gateway_id: str
    gateway_arn: str
    gateway_url: str
    name: str
    description: Optional[str] = None
    status: GatewayStatus
    role_arn: str
    protocol_type: str
    protocol_configuration: Optional[Dict[str, Any]] = None
    authorizer_type: str
    authorizer_configuration: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self):
        return {
            'gateway_id': self.gateway_id,
            'gateway_arn': self.gateway_arn,
            'gateway_url': self.gateway_url,
            'name': self.name,
            'description': self.description,
            'status': self.status.value if isinstance(self.status, GatewayStatus) else self.status,
            'role_arn': self.role_arn,
            'protocol_type': self.protocol_type,
            'protocol_configuration': self.protocol_configuration,
            'authorizer_type': self.authorizer_type,
            'authorizer_configuration': self.authorizer_configuration,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class CreateGatewayResponse(BaseModel):
    gateway_id: str
    gateway_arn: str
    gateway_url: str
    name: str
    status: GatewayStatus
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self):
        return {
            'gateway_id': self.gateway_id,
            'gateway_arn': self.gateway_arn,
            'gateway_url': self.gateway_url,
            'name': self.name,
            'status': self.status.value if isinstance(self.status, GatewayStatus) else self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class DeleteGatewayRequest(BaseModel):
    gateway_id: str

class DeleteGatewayResponse(BaseModel):
    gateway_id: str
    status: GatewayStatus
    
    def to_dict(self):
        return {
            'gateway_id': self.gateway_id,
            'status': self.status.value if isinstance(self.status, GatewayStatus) else self.status
        }

class GetGatewayRequest(BaseModel):
    gateway_id: str

class GetGatewayResponse(BaseModel):
    gateway_id: str
    gateway_arn: str
    gateway_url: str
    name: str
    description: Optional[str] = None
    status: GatewayStatus
    role_arn: str
    protocol_type: str
    protocol_configuration: Optional[Dict[str, Any]] = None
    authorizer_type: str
    authorizer_configuration: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self):
        return {
            'gateway_id': self.gateway_id,
            'gateway_arn': self.gateway_arn,
            'gateway_url': self.gateway_url,
            'name': self.name,
            'description': self.description,
            'status': self.status.value if isinstance(self.status, GatewayStatus) else self.status,
            'role_arn': self.role_arn,
            'protocol_type': self.protocol_type,
            'protocol_configuration': self.protocol_configuration,
            'authorizer_type': self.authorizer_type,
            'authorizer_configuration': self.authorizer_configuration,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class ListGatewaysRequest(BaseModel):
    max_results: Optional[int] = 20
    next_token: Optional[str] = None

class ListGatewaysResponse(BaseModel):
    gateways: List[Gateway]
    next_token: Optional[str] = None
    
    def to_dict(self):
        return {
            'gateways': [gateway.to_dict() for gateway in self.gateways],
            'next_token': self.next_token
        }

class UpdateGatewayRequest(BaseModel):
    gateway_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    role_arn: Optional[str] = None
    protocol_configuration: Optional[Dict[str, Any]] = None
    authorizer_configuration: Optional[Dict[str, Any]] = None
    kms_key_arn: Optional[str] = None
    exception_level: Optional[str] = None
    client_token: Optional[str] = Field(default_factory=lambda: uuid4().hex)

class UpdateGatewayResponse(BaseModel):
    gateway_id: str
    gateway_arn: str
    gateway_url: str
    name: str
    description: Optional[str] = None
    status: GatewayStatus
    role_arn: str
    protocol_type: str
    protocol_configuration: Optional[Dict[str, Any]] = None
    authorizer_type: str
    authorizer_configuration: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self):
        return {
            'gateway_id': self.gateway_id,
            'gateway_arn': self.gateway_arn,
            'gateway_url': self.gateway_url,
            'name': self.name,
            'description': self.description,
            'status': self.status.value if isinstance(self.status, GatewayStatus) else self.status,
            'role_arn': self.role_arn,
            'protocol_type': self.protocol_type,
            'protocol_configuration': self.protocol_configuration,
            'authorizer_type': self.authorizer_type,
            'authorizer_configuration': self.authorizer_configuration,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
