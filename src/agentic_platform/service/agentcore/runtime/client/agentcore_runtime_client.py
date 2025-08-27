"""
AgentCore Runtime Client for managing AWS Bedrock AgentCore Runtime resources.

This client provides methods to create, retrieve, update, delete, and list
AgentCore Runtime resources using the AWS Bedrock AgentCore Control Plane API.

Usage:
  - Create agent runtimes for hosting agent workloads
  - Manage runtime lifecycle and configuration
  - Handle runtime endpoints and versioning

Environment Variables:
  - REGION: AWS region for Bedrock AgentCore resources (default: us-west-2)
"""

import boto3
import json
import logging
import os
import requests
import subprocess
import time

from urllib.parse import quote
from shutil import rmtree
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agentic_platform.service.agentcore.types import (
    AgentRuntime,
    AgentRuntimeStatus,
    CreateAgentRuntimeRequest,
    # CreateAgentRuntimeResponse,
    DeleteAgentRuntimeRequest,
    DeleteAgentRuntimeResponse,
    GetAgentRuntimeRequest,
    GetAgentRuntimeResponse,
    ListAgentRuntimesRequest,
    ListAgentRuntimesResponse,
    UpdateAgentRuntimeRequest,
    UpdateAgentRuntimeResponse
)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Get environment variables
REGION = os.getenv('REGION', 'us-west-2')
USER_POOL_CLIENT_ID = os.getenv('USER_POOL_CLIENT_ID', None)
USER_POOL_ID = os.getenv('USER_POOL_ID', None)
if not (USER_POOL_CLIENT_ID and USER_POOL_ID):
    raise Exception('USER_POOL_ID and USER_POOL_CLIENT_ID environment variables must be set')

COGNITO_DISCOVERY_URL = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/openid-configuration"

# Initialize AWS clients
agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
agentcore_data_client = boto3.client('bedrock-agentcore', region_name=REGION)
bedrock_runtime_client = boto3.client('bedrock-runtime', region_name=REGION)

logger.info(f"os.getcwd() = {os.getcwd()}")
logger.info(f"os.path.abspath(__file__) = {os.path.abspath(__file__)}")
parent_dir = os.path.dirname(os.path.abspath(__file__))

# agentcore_deploy_template_path = f'{parent_dir}/.bedrock_agentcore.yaml.template'
# logger.info(f"agentcore_deploy_template_path = {agentcore_deploy_template_path}")


class AgentCoreRuntimeClient:
    # COMMENTED OUT - Not using create_agentcore_runtime_by_boto method
    # We use JWT authentication with requests.post instead
    # @staticmethod
    # def create_agentcore_runtime_by_boto(
    #     request: CreateAgentRuntimeRequest
    # ) -> Any:
    #     """
    #     Create a new AgentCore Runtime resource using direct boto3 API calls.
    #     DEPRECATED: Not used - we use JWT authentication with requests.post instead
    #     """
    #     pass

    @staticmethod 
    def create_agentcore_runtime(
        request: CreateAgentRuntimeRequest
    ) -> Any:
        """Create an Amazon Secure Agent Runtime using intelligent template selection.
        
        This method creates agent deployments by:
        1. Copying templates from local agent_deployment_template directory to unique deployment directory
        2. Using Bedrock to intelligently select single vs multi-agent templates based on agent_description
        3. Optionally moving multi_entrypoint.py to entrypoint.py based on selection
        4. Running agentcore configure and launch with JWT authentication
        
        Args:
            request: CreateAgentRuntimeRequest containing agent_description, name, and other deployment parameters
            
        Returns:
            GetAgentRuntimeResponse with deployment details
        """
        try:
            # Sanitize the agent name to meet AgentCore requirements
            name = AgentCoreRuntimeClient.sanitize_name(request.name)
            logger.info(f"Creating agent runtime '{name}': {request.agent_description[:100]}...")
            
            # Step 1: Create deployment from local templates
            current_file_path = os.path.abspath(__file__)
            service_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
            source_dir = os.path.join(service_root, "runtime", "agent_deployment_template")
            
            # Step 2: Generate unique deployment directory under agent_deployments
            unique_suffix = uuid4().hex[:8]  # Shorter suffix for cleaner names
            unique_dir = f"deployment_{unique_suffix}"
            agent_deployments_dir = os.path.join(service_root, "runtime", "agent_deployments")
            os.makedirs(agent_deployments_dir, exist_ok=True)

            deployment_dir = f"{agent_deployments_dir}/{unique_dir}"
            logger.info(f"Deploying from {deployment_dir}")
            try:
                # Copy template to deployment directory
                import shutil
                shutil.copytree(source_dir, deployment_dir)
                logger.info(f"Copied agent files from {source_dir} to {deployment_dir}")
                
                # Step 3: Intelligently select entrypoint template
                template_selection = AgentCoreRuntimeClient.select_entrypoint_template(request.agent_description)
                if template_selection == 'MULTI':
                    shutil.move(os.path.join(deployment_dir, "multi_entrypoint.py"), 
                               os.path.join(deployment_dir, "entrypoint.py"))
                    logger.info("Selected multi-agent template")
                else:
                    logger.info("Selected single-agent template")
                
                # Step 4: Deploy using agentcore CLI
                account = os.getenv('AWS_ACCOUNT', None)
                if not account:
                    # Try to get account from STS
                    try:
                        sts_client = boto3.client('sts')
                        account = sts_client.get_caller_identity()['Account']
                    except Exception:
                        raise Exception('AWS_ACCOUNT must be set in environment variables or AWS credentials must be available for STS.')
                
                region = os.getenv('REGION', os.getenv('AWS_REGION', os.getenv("AWS_DEFAULT_REGION", 'us-west-2')))
                
                # Change to the deployment directory
                original_cwd = os.getcwd()
                os.chdir(deployment_dir)
                
                try:
                    # Handle None values for CLI
                    execution_role_arn = request.execution_role_arn if request.execution_role_arn else 'None'
                    ecr_repo_uri = request.ecr_repo_uri if request.ecr_repo_uri else 'None'

                    # Configure agentcore with JWT authentication
                    args = [
                        'agentcore', 'configure', 
                        '--name', name,
                        '--execution-role', execution_role_arn, 
                        '--ecr', ecr_repo_uri, 
                        '--entrypoint', request.entrypoint,
                        '--requirements-file', 'requirements.txt',
                        '--disable-otel',
                        '--protocol', request.protocol,
                        '--region', region,
                        '--authorizer-config', f"{json.dumps({'customJWTAuthorizer': {'discoveryUrl': COGNITO_DISCOVERY_URL,'allowedClients': [USER_POOL_CLIENT_ID]}})}",
                    ]

                    logger.info(f"Running agentcore configure command: {' '.join(args)}")
                    result = subprocess.run(args, capture_output=True, text=True)
                    logger.info(f'Agentcore configure completed with return code {result.returncode}')
                    
                    if result.returncode != 0:
                        raise Exception(f"Error during agentcore configure.\nstdout: {result.stdout}\nstderr: {result.stderr}")
                    else:
                        logger.info('agentcore configure completed successfully.')

                    # Modify .bedrock_agentcore.yaml configuration
                    config_file = os.path.join(deployment_dir, '.bedrock_agentcore.yaml')
                    
                    with open(config_file, 'r') as config_in:
                        config_lines = config_in.readlines()
                        logger.info(f'Got config lines: {"".join(config_lines)}')
                        
                        final_config_lines = ''
                        for line in config_lines:
                            if 'execution_role: ' in line:
                                if not line.strip().endswith('None'):
                                    final_config_lines += line
                                else:
                                    logger.info(f"Skipping execution role None")
                            elif 'execution_role_auto_create: ' in line:
                                if execution_role_arn == 'None':
                                    line = line.replace('false', 'true')
                                final_config_lines += line
                            elif 'ecr_repository: ' in line:
                                if not line.strip().endswith('None'):
                                    final_config_lines += line
                            elif 'ecr_auto_create: ' in line:
                                if ecr_repo_uri == 'None':
                                    line = line.replace('false', 'true')
                                final_config_lines += line
                            else:
                                final_config_lines += line

                    logger.info(f"Final config lines before running agentcore launch: {final_config_lines}")
                    
                    with open(config_file, 'w') as config_out:
                        config_out.write(final_config_lines)
                        
                    # Run agentcore launch
                    launch_args = ['agentcore', 'launch']
                    if request.update_on_conflict:
                        launch_args.append('--auto-update-on-conflict')
                        
                    logger.info(f"Running agentcore launch command: {' '.join(launch_args)}")
                    result = subprocess.run(launch_args, capture_output=True, text=True)
                    logger.info(f'Agentcore launch completed with return code {result.returncode}')
                    
                    if result.returncode != 0:
                        raise Exception(f"Error during agentcore launch.\nstdout: {result.stdout}\nstderr: {result.stderr}")

                    # Extract agent ARN from result
                    agent_arn = None
                    lines = result.stderr.split('\n')
                    for line in lines:
                        if 'Deployment completed successfully - Agent: ' in line:
                            logger.info(f"Found agent line: {line}")
                            agent_arn = line.split(' Agent: ')[1]
                            break
                            
                    if not agent_arn:
                        # Try stdout as well
                        lines = result.stdout.split('\n') 
                        for line in lines:
                            if 'Agent: arn:' in line:
                                logger.info(f"Found agent ARN in stdout: {line}")
                                agent_arn = line.split('Agent: ')[1].strip()
                                break
                    
                    if not agent_arn:
                        logger.warning("Could not extract agent ARN from agentcore launch output")
                        agent_arn = f"arn:aws:bedrock-agentcore:{region}:{account}:runtime/{name}"
                        
                    agent_runtime_id = agent_arn.split('/')[-1]
                    logger.info(f'Created agent runtime with ARN: {agent_arn}, ID: {agent_runtime_id}')
                    
                    return AgentCoreRuntimeClient.get_agentcore_runtime(
                        GetAgentRuntimeRequest(
                            agent_runtime_id=agent_runtime_id
                        )
                    )
                    
                finally:
                    # Return to original directory
                    os.chdir(original_cwd)
                
            except Exception as e:
                # Clean up deployment directory on error
                try:
                    if os.path.exists(deployment_dir):
                        import shutil
                        shutil.rmtree(deployment_dir)
                        logger.info(f"Cleaned up deployment directory on error: {deployment_dir}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to cleanup deployment directory on error: {cleanup_err}")
                raise
            
        except Exception as e:
            logger.error(f"Error creating agent runtime: {str(e)}")
            raise Exception(f"Failed to create agent runtime: {str(e)}")

    @staticmethod
    def delete_agentcore_runtime(
        request: DeleteAgentRuntimeRequest
    ) -> DeleteAgentRuntimeResponse:
        """
        Delete an AgentCore Runtime resource.
        
        Args:
            request: DeleteAgentRuntimeRequest containing runtime ID
            
        Returns:
            DeleteAgentRuntimeResponse with deletion status
            
        Raises:
            Exception: If runtime deletion fails
        """
        logger.info(f"Deleting AgentCore Runtime with ID: {request.agent_runtime_id}")
        
        try:
            # Delete the agent runtime
            response = agentcore_control_client.delete_agent_runtime(
                agentRuntimeId=request.agent_runtime_id
            )
            
            logger.info(f"Successfully deleted AgentCore Runtime with ID: {request.agent_runtime_id}")
            
            return DeleteAgentRuntimeResponse(
                agent_runtime_id=request.agent_runtime_id,
                status="DELETING"
            )
            
        except Exception as e:
            logger.error(f"Error deleting AgentCore Runtime: {str(e)}")
            raise e

    @staticmethod
    def delete_tmpdir(tmpdir):
        return rmtree(tmpdir)
    
    @staticmethod
    def get_agentcore_runtime(
        request: GetAgentRuntimeRequest
    ) -> GetAgentRuntimeResponse:
        """
        Retrieve details of an AgentCore Runtime resource.
        
        Args:
            request: GetAgentRuntimeRequest containing runtime ID
            
        Returns:
            GetAgentRuntimeResponse with runtime details
            
        Raises:
            Exception: If runtime retrieval fails
        """
        agent_runtime_id = None
        if not hasattr(request, 'agent_runtime_id') and \
            hasattr(request, 'agent_runtime_arn'):
            agent_runtime_id = request.agent_runtime_arn.split('/')[-1]
        else:
            agent_runtime_id = request.agent_runtime_id

        logger.info(f"Getting AgentCore Runtime with ID: {agent_runtime_id}")
        
        try:
            # Get the agent runtime details
            response = agentcore_control_client.get_agent_runtime(
                agentRuntimeId=agent_runtime_id
            )
            if response['ResponseMetadata']['HTTPStatusCode'] != 200:
                return response
            
            logger.info(f"get_agent_runtime response {response}")

            response['createdAt'] = response['createdAt'].isoformat()
            response['lastUpdatedAt'] = response['lastUpdatedAt'].isoformat()
            del response['ResponseMetadata']
            logger.info(f"Response is now {response}")
            
            logger.info(f"Successfully retrieved AgentCore Runtime with ID: {agent_runtime_id}")
            
            return GetAgentRuntimeResponse(
                agent_runtime_arn=response['agentRuntimeArn'],
                agent_runtime_id=response['agentRuntimeId'],
                agent_runtime_version=response['agentRuntimeVersion'],
                agent_runtime_name=response['agentRuntimeName'],
                status=response['status'],
                workload_identity_details=response['workloadIdentityDetails'],
                created_at=response['createdAt'],
                last_updated_at=response['lastUpdatedAt'],
                role_arn=response['roleArn'],
                agent_runtime_artifact=response['agentRuntimeArtifact'],
                network_configuration=response['networkConfiguration'],
                protocol_configuration=response['protocolConfiguration'],
                authorizer_configuration=response['authorizerConfiguration']
            )
            
        except Exception as e:
            logger.error(f"Error getting AgentCore Runtime: {str(e)}")
            # Check if this is a ResourceNotFoundException that should return 404
            if hasattr(e, 'response') and 'Error' in e.response:
                error_code = e.response['Error'].get('Code', '')
                if error_code == 'ResourceNotFoundException':
                    from fastapi import HTTPException
                    raise HTTPException(status_code=404, detail=f"AgentCore Runtime not found: {agent_runtime_id}")
            raise e

    @staticmethod
    def get_tmpdir():
        tmpdir = f"/tmp/{uuid4().hex[:6]}"
        os.makedirs(tmpdir)
        return tmpdir
        
    # @staticmethod
    # def _invoke_with_jwt(request: InvokeAgentRuntimeRequest) -> InvokeAgentRuntimeResponse:
    #     """
    #     Invoke AgentCore Runtime using JWT authentication via direct HTTP request.
        
    #     Generates fresh JWT token from Cognito credentials, falls back to cached token.
        
    #     Args:
    #         request: InvokeAgentRuntimeRequest containing invocation parameters
            
    #     Returns:
    #         InvokeAgentRuntimeResponse with the agent response
    #     """
    #     logger.info("Using JWT token authentication for AgentCore Runtime invocation")
    #     logger.info("Using JWT token authentication for AgentCore Runtime invocation")

    #     # Construct the URL from the ARN
    #     # ARN format: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id
    #     arn_parts = request.agent_runtime_arn.split(':')
    #     if len(arn_parts) < 6:
    #         raise ValueError(f"Invalid AgentCore Runtime ARN format: {request.agent_runtime_arn}")
        
    #     region = arn_parts[3]
        
    #     # Construct the invoke URL according to AWS documentation:
    #     # POST /runtimes/agentRuntimeArn/invocations?qualifier=qualifier HTTP/1.1
    #     # URL encode the ARN as shown in the OAuth documentation example
    #     # base_url = f"https://bedrock-agentcore.{region}.amazonaws.com"
    #     escaped_agent_arn = quote(request.agent_runtime_arn, safe='')
    #     # invoke_url = f"{base_url}/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"
    #     invoke_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"

    #     # Prepare headers according to AWS documentation
    #     headers = {
    #         'Authorization': f'Bearer {request.token}',
    #         'Content-Type': request.contentType or 'application/json',
    #         'Accept': request.accept or '*/*'
    #     }
        
    #     # Add optional headers with correct header names from AWS documentation
    #     if request.mcpSessionId:
    #         headers['Mcp-Session-Id'] = request.mcpSessionId
            
    #     if request.runtimeSessionId:
    #         headers['X-Amzn-Bedrock-AgentCore-Runtime-Session-Id'] = request.runtimeSessionId
            
    #     if request.mcpProtocolVersion:
    #         headers['Mcp-Protocol-Version'] = request.mcpProtocolVersion
            
    #     if request.runtimeUserId:
    #         headers['X-Amzn-Bedrock-AgentCore-Runtime-User-Id'] = request.runtimeUserId
            
    #     if request.traceId:
    #         headers['X-Amzn-Trace-Id'] = request.traceId
            
    #     if request.traceParent:
    #         headers['traceparent'] = request.traceParent
            
    #     if request.traceState:
    #         headers['tracestate'] = request.traceState
            
    #     if request.baggage:
    #         headers['baggage'] = request.baggage
        
    #     # Prepare query parameters
    #     params = {}
    #     if request.qualifier:
    #         params['qualifier'] = request.qualifier
        
    #     # Prepare payload
    #     payload_data = json.dumps(request.payload)
    #     logger.info(f"Invoking AgentCore at {invoke_url} with params {params},payload data {payload_data}, and headers {headers}")
    #     # Make the HTTP request
    #     try:
    #         response = requests.post(
    #             invoke_url,
    #             headers=headers,
    #             params=params,
    #             data=payload_data,
    #             timeout=30
    #         )
    #         logging.info(f"Cognito JWT response {response}")
    #         # Check for HTTP errors
    #         response.raise_for_status()
            
    #         # Create response object
    #         return InvokeAgentRuntimeResponse(
    #             statusCode=response.status_code,
    #             contentType=response.headers.get('content-type', 'application/json'),
    #             response=response.content  # Raw bytes similar to StreamingBody
    #         )
            
    #     except requests.exceptions.RequestException as e:
    #         logger.error(f"HTTP request failed: {str(e)}")
    #         raise Exception(f"Failed to invoke AgentCore Runtime via JWT: {str(e)}")

    # @staticmethod
    # def invoke_agentcore_runtime(
    #     request: InvokeAgentRuntimeRequest
    # ) -> InvokeAgentRuntimeResponse:
    #     """
    #     Invoke an AgentCore Runtime agent.
        
    #     Sends a request to an agent or tool hosted in an Amazon Bedrock AgentCore Runtime 
    #     and receives responses in real-time.
        
    #     Uses JWT authentication exclusively - AgentCore runtimes configured with JWT
    #     authorization do not support IAM authentication fallback.
        
    #     Args:
    #         request: InvokeAgentRuntimeRequest containing invocation parameters
            
    #     Returns:
    #         InvokeAgentRuntimeResponse with the agent response
            
    #     Raises:
    #         Exception: If JWT authentication or runtime invocation fails
    #     """
    #     logger.info(f"Invoking AgentCore Runtime with ARN: {request.agent_runtime_arn}")
    #     request.jwt = request.headers['Authentication'].split('Bearer ')[1]
    #     logger.info(f"calling _invoke_with_jwt({request})")
    #     try:
    #         # Use JWT authentication exclusively - no IAM fallback
    #         logger.info(f"about to call _invoke_with_jwt with request {request} ")
    #         return AgentCoreRuntimeClient._invoke_with_jwt(request)
                
    #     except Exception as e:
    #         logger.error(f"Error invoking AgentCore Runtime via JWT: {str(e)}")
    #         raise Exception(f"JWT authentication failed for AgentCore Runtime: {str(e)}")

    @staticmethod
    def list_agent_runtimes(
        request: ListAgentRuntimesRequest
    ) -> ListAgentRuntimesResponse:
        """
        List AgentCore Runtime resources.
        
        Args:
            request: ListAgentRuntimesRequest containing listing parameters
            
        Returns:
            ListAgentRuntimesResponse with list of runtimes
            
        Raises:
            Exception: If runtime listing fails
        """
        logger.info(f"Listing AgentCore Runtimes got request {request}")
        
        try:
            # Prepare list parameters
            list_params = {}
            
            if request.max_results:
                list_params['maxResults'] = request.max_results
                
            if hasattr(request, 'next_token') and request.next_token:
                list_params['nextToken'] = request.next_token
            
            # List the agent runtimes
            response = agentcore_control_client.list_agent_runtimes(**list_params)
            logger.info(f"response: {response}")
            del response['ResponseMetadata']
            runtimes = []
            for runtime in response['agentRuntimes']:
                logger.info(f"Got runtime {runtime}")
                args = {
                    "agent_runtime_arn": runtime['agentRuntimeArn'],
                    "agent_runtime_id": runtime['agentRuntimeId'],
                    "agent_runtime_version": runtime['agentRuntimeVersion'],
                    "agent_runtime_name": runtime['agentRuntimeName'],
                    "status": runtime['status'],
                }
                if hasattr(runtime,'lastUpdatedAt') and runtime.lastUpdatedAt:
                    args['last_updated_at'] = runtime.lastUpdatedAt.isoformat()
                
                runtimes.append(AgentRuntime(**args).to_dict())
            logger.info(f"Successfully listed {len(runtimes)} AgentCore Runtimes")
            
            args = {
                "agent_runtimes": runtimes
            }
            if response.get('nextToken'):
                args['next_token'] = response.get('nextToken')

            return ListAgentRuntimesResponse(**args)
            
        except Exception as e:
            logger.error(f"Error listing AgentCore Runtimes: {str(e)}")
            raise e

    @staticmethod
    def update_agentcore_runtime(
        request: UpdateAgentRuntimeRequest
    ) -> UpdateAgentRuntimeResponse:
        """
        Update an AgentCore Runtime resource.
        
        Args:
            request: UpdateAgentRuntimeRequest containing update parameters
            
        Returns:
            UpdateAgentRuntimeResponse with updated runtime details
            
        Raises:
            Exception: If runtime update fails
        """
        logger.info(f"Updating AgentCore Runtime with request: {request}, type {type(request)}")
        # first get the old runtime details:
        old_runtime = None
        # logger.info(f"UpdateAgentRuntimeRequest attrs: {vars(request)}")
        # logger.info(f"Is there an agent_runtime_id property? {hasattr(request, 'agent_runtime_id')}")
        # logger.info(f"how about the vars way? vars(request)['agent_runtime_id'] = {vars(request)['agent_runtime_id']}")
        # logger.info(f"How about the property way? (next line crashes for some reason) request.agent_runtime_id = ")
        # logger.info(request.agent_runtime_id)
        agent_runtime_id = request.agent_runtime_id
        logger.info(f"Got agent_runtime_id {agent_runtime_id}")
        try: 

            old_runtime = AgentCoreRuntimeClient.get_agentcore_runtime(
                GetAgentRuntimeRequest(
                    agent_runtime_id=agent_runtime_id
                )
            )
            logger.info(f"Got old runtime {old_runtime}")
        except Exception as e:
            logger.info(f"Error updating runtime: {str(e)}")
            raise e
        try:
            # Prepare update parameters - only include non-None values
            # Only perform update if we have parameters to update
            update_request_params = {
                "agent_runtime_id": old_runtime.agent_runtime_id,
                "agentRuntimeArtifact": request.agentRuntimeArtifact,
                "roleArn": request.roleArn,
                "networkConfiguration": request.networkConfiguration,
                "protocolConfiguration": request.protocolConfiguration,
                "authorizerConfiguration": request.authorizerConfiguration
            }
            if hasattr(request, 'clientToken') and request.clientToken:
                update_request_params['clientToken'] = request.clientToken
            if hasattr(request, 'description') and request.description:
                update_request_params['description'] = request.description
            else:
                update_request_params['description'] = old_runtime['description']
            if hasattr(request, 'environmentVariables') and request.environmentVariables:
                update_request_params['environmentVariables'] = request.environmentVariables
            else:
                update_request_params['environmentVariables'] = old_runtime.environmentVariables

            logger.info(f"Update params currently {update_request_params}")
            # Update the agent runtime
            response = agentcore_control_client.update_agent_runtime(**update_request_params)
            response['createdAt'] = response['createdAt'].isoformat()
            response['lastUpdatedAt'] = response['lastUpdatedAt'].isoformat()
            logger.info(f"Successfully updated AgentCore Runtime with ID: {request.agent_runtime_id}")
            logger.info(response)
            return response
           
        except Exception as e:
            logger.error(f"Error updating AgentCore Runtime: {str(e)}")
            raise e

    @staticmethod
    def wait_for_runtime_ready(
        agent_runtime_id: str,
        max_wait_time: int = 600,
        poll_interval: int = 10
    ) -> GetAgentRuntimeResponse:
        """
        Wait for an AgentCore Runtime to finish creating and become ready or fail.
        
        Polls the runtime status until it's no longer in 'CREATING' state.
        Returns when status becomes 'READY', or 'FAILED'.
        
        Args:
            agent_runtime_id: The ID of the agent runtime to monitor
            max_wait_time: Maximum time to wait in seconds (default: 600 = 10 minutes)
            poll_interval: Time to wait between status checks in seconds (default: 10)
            
        Returns:
            GetAgentRuntimeResponse with the final runtime details
            
        Raises:
            TimeoutError: If runtime doesn't reach a final state within max_wait_time
            Exception: If runtime retrieval fails
        """
        logger.info(f"Waiting for AgentCore Runtime {agent_runtime_id} to be ready...")
        
        start_time = time.time()
        creating_states = [
            AgentRuntimeStatus.CREATING, 
            AgentRuntimeStatus.UPDATING
        ]
        ready_states = [
            AgentRuntimeStatus.READY,
        ]
        failed_states = [
            AgentRuntimeStatus.CREATE_FAILED, 
            AgentRuntimeStatus.UPDATE_FAILED
        ]
        
        while True:
            try:
                # Get current runtime status
                get_request = GetAgentRuntimeRequest(agent_runtime_id=agent_runtime_id)
                runtime_response = AgentCoreRuntimeClient.get_agentcore_runtime(get_request)
                
                current_status = runtime_response.status
                logger.info(f"Current status for runtime {agent_runtime_id}: {current_status}")
                
                # Check if runtime is ready
                if current_status in ready_states:
                    logger.info(f"AgentCore Runtime {agent_runtime_id} is ready with status: {current_status}")
                    return runtime_response
                
                # Check if runtime failed
                if current_status in failed_states:
                    error_msg = f"AgentCore Runtime {agent_runtime_id} failed with status: {current_status}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                # Check if we've exceeded the maximum wait time
                elapsed_time = time.time() - start_time
                if elapsed_time >= max_wait_time:
                    error_msg = f"Timeout waiting for AgentCore Runtime {agent_runtime_id} to be ready. Current status: {current_status}, elapsed time: {elapsed_time:.1f}s"
                    logger.error(error_msg)
                    raise TimeoutError(error_msg)
                
                # Runtime is still creating/updating, wait before next check
                if current_status in creating_states:
                    logger.info(f"Runtime {agent_runtime_id} still {current_status.lower()}, waiting {poll_interval}s before next check...")
                    time.sleep(poll_interval)
                else:
                    # Unexpected status, log warning but continue waiting
                    logger.warning(f"Runtime {agent_runtime_id} has unexpected status: {current_status}, continuing to wait...")
                    time.sleep(poll_interval)
                    
            except Exception as e:
                # If it's a timeout error we raised, re-raise it
                if isinstance(e, TimeoutError):
                    raise e
                
                # For other exceptions, log and re-raise
                logger.error(f"Error checking runtime status: {str(e)}")
                raise Exception(f"Failed to check runtime status: {str(e)}")

    @staticmethod
    def sanitize_name(original_name: str) -> str:
        """Sanitize agent name to meet AgentCore requirements.
        
        AgentCore agent names must:
        - Start with a letter
        - Contain only letters, numbers, and underscores  
        - Be 1-48 characters long
        
        Args:
            original_name: The original agent name to sanitize
            
        Returns:
            Sanitized agent name that meets AgentCore requirements
        """
        import re
        
        # Replace invalid characters with underscores
        sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '_', original_name)
        
        # Ensure it starts with a letter
        if not sanitized_name or not sanitized_name[0].isalpha():
            sanitized_name = 'agent_' + sanitized_name
        
        # Truncate to 48 characters if needed
        if len(sanitized_name) > 48:
            sanitized_name = sanitized_name[:48]
        
        # Remove trailing underscores that might result from truncation
        sanitized_name = sanitized_name.rstrip('_')
        
        # Ensure it's not empty after sanitization
        if not sanitized_name:
            sanitized_name = 'agent_runtime'
            
        if original_name != sanitized_name:
            logger.info(f"Sanitized agent name from '{original_name}' to '{sanitized_name}'")
        
        return sanitized_name

    @staticmethod
    def select_entrypoint_template(user_description: str) -> str:
        """Given the user's request, decide if the single or multi-agent entrypoint is needed.
        
        Uses Bedrock to analyze the user's description and determine whether a single
        agent or multi-agent orchestration template would be more appropriate.
        
        Args:
            user_description: Natural language description of what the agent should do
            
        Returns:
            'SINGLE' or 'MULTI' indicating which template to use
        """
        try:
            # Construct the prompt for the LLM
            prompt_template = """You're an agentic AI architect. Given the user's request, does it sound like they'll need a single agent or multi-agent template for this project?
            
            <USER_DESCRIPTION>
            {user_description}
            </USER_DESCRIPTION> 

            Return only the word SINGLE or MULTI with no other text or newlines.
            """

            formatted_prompt = prompt_template.format(user_description=user_description)
            
            # Prepare the message for Bedrock Converse API
            messages = [
                {
                    "role": "user",
                    "content": [{"text": formatted_prompt}]
                }
            ]
            logger.info("Sending entrypoint selection prompt to bedrock")
            
            # Call Bedrock Converse API with Nova Micro
            response = bedrock_runtime_client.converse(
                modelId="us.amazon.nova-micro-v1:0",
                messages=messages,
                inferenceConfig={
                    "maxTokens": 50,
                    "temperature": 0.0,  # Lower temperature for more consistent outputs
                    "topP": 0.9,
                    "stopSequences": ["</JSON>"]
                }
            )
            logger.info(f"got response from bedrock {response}")

            # Extract the generated selection
            result = response['output']['message']['content'][0]['text'].strip()
            logger.info(f"entrypoint selection result: {result}")
            
            # Validate result
            if result in ['SINGLE', 'MULTI']:
                return result
            else:
                logger.warning(f"Unexpected template selection result: {result}, defaulting to SINGLE")
                return 'SINGLE'
            
        except Exception as e:
            logger.error(f"Failed to select template via Bedrock: {e}")
            logger.info("Defaulting to SINGLE template")
            return 'SINGLE'
