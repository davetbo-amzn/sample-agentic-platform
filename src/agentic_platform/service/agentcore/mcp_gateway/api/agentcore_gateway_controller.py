"""
AgentCore Gateway Controller for managing AWS Bedrock AgentCore Gateway resources.

This controller provides static methods to create, retrieve, update, delete, and list
AgentCore Gateway resources using the AWS Bedrock AgentCore Gateway Control Plane API.

This controller handles all MCP (Model Context Protocol) gateway operations including:
  - Gateway lifecycle management (create, update, delete, list)
  - Protocol configuration for MCP gateways
  - Authorization configuration management
  - Gateway status monitoring and waiting operations
  - Error handling and validation

Usage:
  - Create and manage MCP gateways with protocol-specific configurations
  - Handle gateway lifecycle (create, update, delete, list)
  - Monitor gateway status and wait for operations to complete
  - Configure authorization mechanisms for gateway access
"""

from agentic_platform.service.agentcore.types import (
    GatewayOperation,
    GatewayRequest,
    GatewayResponse,
    GatewayStatus,
    CreateGatewayRequest,
    CreateGatewayResponse,
    DeleteGatewayRequest,
    DeleteGatewayResponse,
    GetGatewayRequest,
    GetGatewayResponse,
    ListGatewaysRequest,
    ListGatewaysResponse,
    UpdateGatewayRequest,
    UpdateGatewayResponse,
    Gateway
)
from agentic_platform.service.agentcore.mcp_gateway.client.agentcore_gateway_client import AgentCoreGatewayClient


class AgentCoreGatewayController:

    @staticmethod
    def handler(event, context):
        """
        Lambda handler for gateway operations.
        
        Args:
            event: Lambda event containing operation and input data
            context: Lambda context object
            
        Returns:
            Dictionary with status_code and result
        """
        evt = GatewayRequest(**event)
        
        if evt.operation == GatewayOperation.CREATE:
            result = AgentCoreGatewayController.create_gateway(
                CreateGatewayRequest(**evt.input)
            )
        
        elif evt.operation == GatewayOperation.DELETE:
            result = AgentCoreGatewayController.delete_gateway(
                DeleteGatewayRequest(**evt.input)
            )
        
        elif evt.operation == GatewayOperation.GET:
            result = AgentCoreGatewayController.get_gateway(
                GetGatewayRequest(**evt.input)
            )
        
        elif evt.operation == GatewayOperation.LIST:
            result = AgentCoreGatewayController.list_gateways(
                ListGatewaysRequest(**evt.input)
            )
        
        elif evt.operation == GatewayOperation.UPDATE:
            result = AgentCoreGatewayController.update_gateway(
                UpdateGatewayRequest(**evt.input)
            )
        
        elif evt.operation == GatewayOperation.WAIT_FOR_CREATE:
            result = AgentCoreGatewayController.wait_for_gateway_creation(
                evt.input.get('gateway_id'),
                evt.input.get('max_attempts', 20),
                evt.input.get('delay_seconds', 15)
            )
        
        elif evt.operation == GatewayOperation.WAIT_FOR_DELETE:
            result = AgentCoreGatewayController.wait_for_gateway_deletion(
                evt.input.get('gateway_id'),
                evt.input.get('max_attempts', 20),
                evt.input.get('delay_seconds', 15)
            )
        
        else:
            raise Exception(f"Parameter validation exception: operation must be a GatewayOperation (one of {[op.value for op in GatewayOperation]})")
        
        # Handle different result types for the response
        if hasattr(result, 'to_dict'):
            result_dict = result.to_dict()
        elif hasattr(result, '__dict__'):
            result_dict = result.__dict__
        else:
            # For raw data like wait operations that return dictionaries or primitives
            result_dict = result if isinstance(result, dict) else {"result": result}
            
        return GatewayResponse(
            status_code=200,
            result=result_dict
        ).to_dict()
    
    @staticmethod
    def create_gateway(request: CreateGatewayRequest) -> CreateGatewayResponse:
        """
        Create a new AgentCore Gateway.
        
        Args:
            request: CreateGatewayRequest with gateway configuration
            
        Returns:
            CreateGatewayResponse with created gateway details
        """
        result = AgentCoreGatewayClient.create_gateway(
            name=request.name,
            role_arn=request.role_arn,
            protocol_type=request.protocol_type,
            description=request.description,
            protocol_configuration=request.protocol_configuration,
            authorizer_type=request.authorizer_type,
            authorizer_configuration=request.authorizer_configuration,
            kms_key_arn=request.kms_key_arn,
            exception_level=request.exception_level,
            client_token=request.client_token
        )
        
        return CreateGatewayResponse(
            gateway_id=result['gateway_id'],
            gateway_arn=result['gateway_arn'],
            gateway_url=result['gateway_url'],
            name=result['name'],
            status=GatewayStatus(result['status']),
            created_at=result.get('created_at'),
            updated_at=result.get('updated_at')
        )
    
    @staticmethod
    def delete_gateway(request: DeleteGatewayRequest) -> DeleteGatewayResponse:
        """
        Delete an AgentCore Gateway.
        
        Args:
            request: DeleteGatewayRequest with gateway ID
            
        Returns:
            DeleteGatewayResponse with deletion status
        """
        result = AgentCoreGatewayClient.delete_gateway(request.gateway_id)
        
        return DeleteGatewayResponse(
            gateway_id=result['gateway_id'],
            status=GatewayStatus(result['status'])
        )
    
    @staticmethod
    def get_gateway(request: GetGatewayRequest) -> GetGatewayResponse:
        """
        Get details of an AgentCore Gateway.
        
        Args:
            request: GetGatewayRequest with gateway ID
            
        Returns:
            GetGatewayResponse with gateway details
        """
        result = AgentCoreGatewayClient.get_gateway(request.gateway_id)
        
        return GetGatewayResponse(
            gateway_id=result['gateway_id'],
            gateway_arn=result['gateway_arn'],
            gateway_url=result['gateway_url'],
            name=result['name'],
            description=result.get('description'),
            status=GatewayStatus(result['status']),
            role_arn=result['role_arn'],
            protocol_type=result['protocol_type'],
            protocol_configuration=result.get('protocol_configuration'),
            authorizer_type=result['authorizer_type'],
            authorizer_configuration=result.get('authorizer_configuration'),
            created_at=result.get('created_at'),
            updated_at=result.get('updated_at')
        )

    @staticmethod
    def list_gateways(request: ListGatewaysRequest) -> ListGatewaysResponse:
        """
        List AgentCore Gateways.
        
        Args:
            request: ListGatewaysRequest with pagination parameters
            
        Returns:
            ListGatewaysResponse with list of gateways
        """
        result = AgentCoreGatewayClient.list_gateways(
            max_results=request.max_results,
            next_token=request.next_token
        )
        
        gateways = []
        for gateway_data in result['gateways']:
            gateway = Gateway(
                gateway_id=gateway_data['gateway_id'],
                gateway_arn=gateway_data['gateway_arn'],
                gateway_url=gateway_data['gateway_url'],
                name=gateway_data['name'],
                description=gateway_data.get('description'),
                status=GatewayStatus(gateway_data['status']),
                role_arn=gateway_data.get('role_arn', ''),
                protocol_type=gateway_data.get('protocol_type', 'MCP'),
                protocol_configuration=gateway_data.get('protocol_configuration'),
                authorizer_type=gateway_data.get('authorizer_type', 'CUSTOM_JWT'),
                authorizer_configuration=gateway_data.get('authorizer_configuration'),
                created_at=gateway_data.get('created_at'),
                updated_at=gateway_data.get('updated_at')
            )
            gateways.append(gateway)
        
        return ListGatewaysResponse(
            gateways=gateways,
            next_token=result.get('next_token')
        )
    
    @staticmethod
    def update_gateway(request: UpdateGatewayRequest) -> UpdateGatewayResponse:
        """
        Update an AgentCore Gateway.
        
        Args:
            request: UpdateGatewayRequest with gateway ID and update parameters
            
        Returns:
            UpdateGatewayResponse with updated gateway details
        """
        result = AgentCoreGatewayClient.update_gateway(
            gateway_id=request.gateway_id,
            name=request.name,
            description=request.description,
            role_arn=request.role_arn,
            protocol_configuration=request.protocol_configuration,
            authorizer_configuration=request.authorizer_configuration,
            kms_key_arn=request.kms_key_arn,
            exception_level=request.exception_level,
            client_token=request.client_token
        )
        
        return UpdateGatewayResponse(
            gateway_id=result['gateway_id'],
            gateway_arn=result['gateway_arn'],
            gateway_url=result['gateway_url'],
            name=result['name'],
            description=result.get('description'),
            status=GatewayStatus(result['status']),
            role_arn=result['role_arn'],
            protocol_type=result['protocol_type'],
            protocol_configuration=result.get('protocol_configuration'),
            authorizer_type=result['authorizer_type'],
            authorizer_configuration=result.get('authorizer_configuration'),
            created_at=result.get('created_at'),
            updated_at=result.get('updated_at')
        )
    
    @staticmethod
    def wait_for_gateway_creation(gateway_id: str, max_attempts: int = 20, delay_seconds: int = 15):
        """
        Wait for gateway creation to complete.
        
        Args:
            gateway_id: Gateway ID to wait for
            max_attempts: Maximum number of polling attempts
            delay_seconds: Delay between polling attempts in seconds
            
        Returns:
            Gateway details when creation is complete
        """
        return AgentCoreGatewayClient.wait_for_gateway_creation(
            gateway_id, max_attempts, delay_seconds
        )
    
    @staticmethod
    def wait_for_gateway_deletion(gateway_id: str, max_attempts: int = 20, delay_seconds: int = 15):
        """
        Wait for gateway deletion to complete.
        
        Args:
            gateway_id: Gateway ID to wait for deletion
            max_attempts: Maximum number of polling attempts
            delay_seconds: Delay between polling attempts in seconds
            
        Returns:
            Boolean indicating successful deletion
        """
        return AgentCoreGatewayClient.wait_for_gateway_deletion(
            gateway_id, max_attempts, delay_seconds
        )


def handler(event, context):
    """Lambda entry point for gateway operations."""
    return AgentCoreGatewayController.handler(event, context)
