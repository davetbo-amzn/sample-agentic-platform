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
import zipfile

from urllib.parse import quote
from shutil import rmtree
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agentic_platform.service.agentcore.types import (
    AgentRuntime,
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

S3_ZIPS_BUCKET = os.getenv('S3_ZIPS_BUCKET')


# Initialize AWS clients
agentcore_control_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
agentcore_data_client = boto3.client('bedrock-agentcore', region_name=REGION)
s3_client = boto3.client('s3', region_name=REGION)

print(f"os.getcwd() = {os.getcwd()}")
print(f"os.path.abspath(__file__) = {os.path.abspath(__file__)}")
parent_dir = os.path.dirname(os.path.abspath(__file__))

# agentcore_deploy_template_path = f'{parent_dir}/.bedrock_agentcore.yaml.template'
# print(f"agentcore_deploy_template_path = {agentcore_deploy_template_path}")


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
        local_agent_dir = AgentCoreRuntimeClient.download_zip_from_s3(request.s3_zip_path)
        # new_template_file = agentcore_deploy_template_path.split(os.sep)[-1].replace('.template', '')
        # target_file = f"{local_agent_dir}/{new_template_file}"
        
        account = os.getenv('AWS_ACCOUNT', None)
        if not account: 
            raise Exception('Account must be set in the environment variables for agentcore runtime client.')
        
        region = os.getenv('REGION', os.getenv('AWS_REGION', os.getenv("AWS_DEFAULT_REGION", None)))
        if not region:
            raise Exception('At least one of REGION or AWS_REGION or AWS_DEFAULT_REGION must be set in the environment variables for agentcore runtime client.')
        
        print(f"extracted zip file to {local_agent_dir}")
        os.chdir(local_agent_dir)
        if request.execution_role_arn == None:
            request.execution_role_arn = 'None'
        
        if request.ecr_repo_uri == None:
            request.ecr_repo_uri = 'None'

        args = [
            'agentcore', 'configure', 
            '--name', request.name,
            '--execution-role', request.execution_role_arn, 
            '--ecr', request.ecr_repo_uri, 
            '--entrypoint', request.entrypoint,
            '--requirements-file', 'requirements.txt',
            '--disable-otel',
            '--protocol', request.protocol,
            '--region', REGION,
            '--authorizer-config', f"{json.dumps({'customJWTAuthorizer': {'discoveryUrl': COGNITO_DISCOVERY_URL,'allowedClients': [USER_POOL_CLIENT_ID]}})}",
        ]

        print(f"Running command {' '.join(args)}.\nPlease wait...")
        result: subprocess.CompletedProcess = subprocess.run(args, capture_output=True)
        print(f'Completed command. {result}')
        if not result.returncode == 0:
            raise Exception(f"Error during agentcore configure.\nstdout: {result.stdout}\nstderr: {result.stderr}")
        else:
            print('agentcore configure completed successfully.')

        with open(f"{local_agent_dir}/.bedrock_agentcore.yaml", 'r') as config_in:
            config_lines = config_in.readlines()
            print(f'Got config lines {''.join(config_lines)}')
            final_config_lines = ''
            for line in config_lines:
                if 'execution_role: ' in line:
                    if not line.strip().endswith('None'):
                        final_config_lines += line
                    else:
                        print(f"Skipping execution role None")
                elif 'execution_role_auto_create: ' in line:
                    print(f"execution role arn is {request.execution_role_arn}, type {type(request.execution_role_arn)}")
                    if request.execution_role_arn == 'None':
                        line = line.replace('false', 'true')
                    final_config_lines += line
                elif 'ecr_repository: ' in line:
                    if not line.strip().endswith('None'):
                        final_config_lines += line
                elif 'ecr_auto_create: ' in line:
                    print(f"ecr_repo_uri == {request.ecr_repo_uri}, type {type(request.ecr_repo_uri)}")
                    if request.ecr_repo_uri == 'None':
                        line = line.replace('false', 'true')
                    final_config_lines += line
                else:
                    final_config_lines += line

        print(f"Final config lines before running agentcore launch: {final_config_lines}")
        with open(f"{local_agent_dir}/.bedrock_agentcore.yaml", 'w') as config_out:
            config_out.write(final_config_lines)
            
        args = ['agentcore', 'launch']
        if request.update_on_conflict:
            args.append('--auto-update-on-conflict')
        print(f"Running command {' '.join(args)}.\nPlease wait...")
        result: subprocess.CompletedProcess = subprocess.run(args, capture_output=True)
        print(f'Completed command.')
        if not result.returncode == 0:
            raise Exception(f"Error during agentcore launch.\nstdout: {result.stdout}\nstderr: {result.stderr}")

        agent_arn = None
        lines = result.stderr.decode('utf-8').split('\n')
        for line in lines:
            if 'Deployment completed successfully - Agent: ' in line:
                print(f"Found agent line {line}")
                agent_arn = line.split(' Agent: ')[1]
        agent_runtime_id = agent_arn.split('/')[-1]
        print(f'Created agent with runtime id {agent_runtime_id}')
        return AgentCoreRuntimeClient.get_agentcore_runtime(
            GetAgentRuntimeRequest(
                agent_runtime_id=agent_runtime_id
            )
        )

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
    def download_zip_from_s3(s3_zip_path: str) -> str: 
        # returns the path to the local tmpdir
        # takes the full s3 URI and path
        tmpdir = AgentCoreRuntimeClient.get_tmpdir()
        extraction_dir = f"{tmpdir}/extracted"
        os.makedirs(extraction_dir)
        parts = s3_zip_path.split('/')
        bucket = parts[2]
        s3_key = '/'.join(parts[3:])
        filename = parts[-1]
        local_path = f"{tmpdir}/{filename}"
        s3_client.download_file(bucket, s3_key, local_path)
        with zipfile.ZipFile(local_path, 'r') as zip_ref:
            # Extract all contents to the specified output directory
            zip_ref.extractall(extraction_dir)
        return extraction_dir
    
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
            
            logging.info(f"get_agent_runtime response {response}")

            response['createdAt'] = response['createdAt'].isoformat()
            response['lastUpdatedAt'] = response['lastUpdatedAt'].isoformat()
            del response['ResponseMetadata']
            print(f"Response is now {response}")
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
    #     print("Using JWT token authentication for AgentCore Runtime invocation")

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
    #         print(f"about to call _invoke_with_jwt with request {request} ")
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
        print(f"Listing AgentCore Runtimes got request {request}")
        
        try:
            # Prepare list parameters
            list_params = {}
            
            if request.max_results:
                list_params['maxResults'] = request.max_results
                
            if hasattr(request, 'next_token') and request.next_token:
                list_params['nextToken'] = request.next_token
            
            # List the agent runtimes
            response = agentcore_control_client.list_agent_runtimes(**list_params)
            print(f"response: {response}")
            del response['ResponseMetadata']
            runtimes = []
            for runtime in response['agentRuntimes']:
                print(f"Got runtime {runtime}")
                args = {
                    "agent_runtime_arn": runtime['agentRuntimeArn'],
                    "agent_runtime_id": runtime['agentRuntimeId'],
                    "agent_runtime_version": runtime['agentRuntimeVersion'],
                    "agent_runtime_name": runtime['agentRuntimeName'],
                    "status": runtime['status'],
                }
                if hasattr(runtime,'lastUpdatedAt') and runtime.lastUpdatedAt:
                    args['last_updated_at'] = runtime.lastUpdatedAt.isoformat()
                
                runtimes.append(AgentRuntime(**args).__dict__)
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
            print(f"Got old runtime {old_runtime}")
        except Exception as e:
            print(f"Error updating runtime: {str(e)}")
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

            print(f"Update params currently {update_request_params}")
            # Update the agent runtime
            response = agentcore_control_client.update_agent_runtime(**update_request_params)
            response['createdAt'] = response['createdAt'].isoformat()
            response['lastUpdatedAt'] = response['lastUpdatedAt'].isoformat()
            print(f"Successfully updated AgentCore Runtime with ID: {request.agent_runtime_id}")
            print(response)
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
        creating_states = {'CREATING', 'UPDATING'}
        ready_states = {'READY'}
        failed_states = {'FAILED', 'FAILED_ROLLBACK'}
        
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
