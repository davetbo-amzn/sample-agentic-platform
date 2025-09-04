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
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional
from uuid import uuid4

from agentic_platform.service.agentcore.types import (
    AgentRuntime,
    AgentRuntimeStatus,
    DeleteAgentRuntimeRequest,
    DeleteAgentRuntimeResponse,
    GetAgentRuntimeRequest,
    GetAgentRuntimeResponse,
    ListAgentRuntimesRequest,
    ListAgentRuntimesResponse,
    UpdateAgentRuntimeRequest,
    UpdateAgentRuntimeResponse,
)

# Configure logging
logging.basicConfig(
    filename='agentcore_runtime_client.log',
    level=logging.DEBUG,
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    @staticmethod
    def _run_subprocess_with_optional_streaming(args, stream_output=False):
        """
        Run subprocess with optional real-time streaming to stdout.
        
        Args:
            args: Command arguments list
            stream_output: Whether to stream output to stdout in real-time
            
        Returns:
            subprocess.CompletedProcess-like object with returncode, stdout, stderr
        """
        if stream_output:
            # Stream output in real-time while capturing for parsing
            import sys
            
            logger.info(f"Running command with streaming: {' '.join(args)}")
            
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout for unified streaming
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            stdout_lines = []
            
            # Stream output line by line
            for line in process.stdout:
                # Print to stdout for real-time visibility
                print(line.rstrip())
                sys.stdout.flush()
                
                # Also capture for later parsing
                stdout_lines.append(line)
            
            # Wait for process to complete
            return_code = process.wait()
            
            # Reconstruct stdout and stderr for compatibility
            stdout_content = ''.join(stdout_lines)
            
            # Create a result object similar to subprocess.run return
            class StreamedResult:
                def __init__(self, returncode, stdout, stderr=""):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr  # Empty since we merged stderr into stdout
            
            return StreamedResult(return_code, stdout_content, "")
            
        else:
            # Use normal subprocess.run for non-streaming mode
            return subprocess.run(args, capture_output=True, text=True)

    def create_agent_runtime(
        self,
        name: str,
        agent_description: Optional[str] = None,
        entrypoint: Optional[str] = "entrypoint.py",
        ecr_repo_uri: Optional[str] = None,
        execution_role_arn: Optional[str] = None,
        protocol: Optional[str] = "HTTP",
        update_on_conflict: Optional[bool] = False
    ) -> str:
        """Create an Amazon Secure Agent Runtime using agentcore configure and agentcore launch.
        
        This method creates the agent runtime deployment by either:
        1. Using agent_description: Copying template files, customizing business logic using Bedrock
        2. Using ecr_repo_uri: Skipping template creation and using provided ECR repository
        3. Running agentcore configure and launch with streaming output
        
        Args:
            name: The name of the agent runtime (required)
            agent_description: Natural language description (optional, required if ecr_repo_uri not provided)
            entrypoint: Entry point file name (default: entrypoint.py)
            ecr_repo_uri: ECR repository URI (optional, required if agent_description not provided)
            execution_role_arn: IAM role ARN (optional) default None to create one automatically
            protocol: Server protocol - HTTP or MCP (default: HTTP)
            update_on_conflict: Whether to update if runtime already exists (default: false)
        Returns:
            String with deployment details including ARN and runtime ID
        """
        try:
            # Validate that exactly one of agent_description or ecr_repo_uri is provided
            if agent_description and ecr_repo_uri:
                raise ValueError("Cannot provide both agent_description and ecr_repo_uri. Please provide exactly one.")
            if not agent_description and not ecr_repo_uri:
                raise ValueError("Must provide either agent_description or ecr_repo_uri.")
            
            # Sanitize the agent name to meet AgentCore requirements
            name = self.sanitize_name(name)
            
            if agent_description:
                logger.info(f"Creating agent runtime '{name}' from description: {agent_description[:100]}...")
                return self._create_runtime_from_description(
                    name, agent_description, entrypoint, ecr_repo_uri, 
                    execution_role_arn, protocol, update_on_conflict
                )
            else:
                logger.info(f"Creating agent runtime '{name}' from ECR repository: {ecr_repo_uri}")
                return self._create_runtime_from_ecr(
                    name, ecr_repo_uri, entrypoint, execution_role_arn, 
                    protocol, update_on_conflict
                )
            
        except Exception as e:
            logger.error(f"Error creating agent runtime: {str(e)}")
            raise Exception(f"Failed to create agent runtime: {str(e)}")

    def _create_runtime_from_description(
        self,
        name: str,
        agent_description: str,
        entrypoint: str,
        ecr_repo_uri: Optional[str],
        execution_role_arn: Optional[str],
        protocol: str,
        update_on_conflict: bool
    ) -> str:
        """Create agent runtime using agent description (template-based workflow)."""
        # Step 1: Create deployment from existing template code
        project_root = Path(__file__).parent.parent.parent
        source_dir = project_root / "runtime" / "agent_deployment_template"
        
        if not source_dir.exists():
            raise FileNotFoundError(f"Agent templates source directory not found: {source_dir}")
        
        # Step 2: Generate unique deployment directory under agent_deployments
        unique_suffix = uuid4().hex[:8]
        unique_dir = f"deployment_{unique_suffix}"
        deployment_dir = f"{project_root}/agent_deployments/{unique_dir}"

        try:
            # Copy template source to deployment directory
            shutil.copytree(source_dir, deployment_dir)
            logger.info(f"Copied agent files from {source_dir} to {deployment_dir}")
            
            # Step 2.1: Select appropriate template (SINGLE or MULTI)
            template_selection = self.select_entrypoint_template(agent_description)
            logger.info(f"Selected template: {template_selection}")
            
            # Step 2.2: Set up the correct entrypoint file
            if template_selection == 'MULTI':
                shutil.move(f"{deployment_dir}/multi_entrypoint.py", f"{deployment_dir}/entrypoint.py")
                logger.info("Using multi-agent template as entrypoint.py")
            else:
                # SINGLE template is already entrypoint.py, remove multi_entrypoint.py
                os.remove(f"{deployment_dir}/multi_entrypoint.py")
                logger.info("Using single-agent template as entrypoint.py")
            
            # Step 3: Customize business logic using Bedrock
            logger.info("Step 3: Customizing business logic with Bedrock...")
            
            # Read the selected template content
            with open(f"{deployment_dir}/entrypoint.py", 'r') as f:
                template_content = f.read()
            
            # Read the requirements.txt content
            with open(f"{deployment_dir}/requirements.txt", 'r') as f:
                requirements_content = f.read()
            
            # Customize the business logic while preserving architecture
            try:
                customized_entrypoint, updated_requirements = self.customize_business_logic(
                    agent_description, 
                    template_content, 
                    requirements_content
                )
                
                # Write the customized files back
                with open(f"{deployment_dir}/entrypoint.py", 'w') as f:
                    f.write(customized_entrypoint)
                
                with open(f"{deployment_dir}/requirements.txt", 'w') as f:
                    f.write(updated_requirements)
                
                logger.info("Successfully customized entrypoint.py and requirements.txt")
                
            except Exception as customize_error:
                logger.warning(f"Failed to customize business logic: {customize_error}")
                logger.info("Proceeding with original template files")
            
            # Step 4: Deploy using agentcore CLI
            return self._deploy_with_agentcore_cli(
                deployment_dir, name, entrypoint, ecr_repo_uri, 
                execution_role_arn, protocol, update_on_conflict, agent_description
            )
            
        except Exception as e:
            # Clean up deployment directory on error
            try:
                if Path(deployment_dir).exists():
                    shutil.rmtree(deployment_dir)
                    logger.info(f"Cleaned up deployment directory on error: {deployment_dir}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to cleanup deployment directory on error: {cleanup_err}")
            raise

    def _create_runtime_from_ecr(
        self,
        name: str,
        ecr_repo_uri: str,
        entrypoint: str,
        execution_role_arn: Optional[str],
        protocol: str,
        update_on_conflict: bool
    ) -> str:
        """Create agent runtime using ECR repository (direct deployment workflow)."""
        # For ECR-based deployment, we skip template creation and go directly to agentcore CLI
        # Create a minimal deployment directory for agentcore CLI to work in
        project_root = Path(__file__).parent.parent.parent
        unique_suffix = uuid4().hex[:8]
        unique_dir = f"deployment_{unique_suffix}"
        deployment_dir = f"{project_root}/agent_deployments/{unique_dir}"
        
        try:
            # Create minimal deployment directory
            os.makedirs(deployment_dir, exist_ok=True)
            logger.info(f"Created deployment directory for ECR-based runtime: {deployment_dir}")
            
            # Deploy using agentcore CLI with provided ECR repository
            return self._deploy_with_agentcore_cli(
                deployment_dir, name, entrypoint, ecr_repo_uri, 
                execution_role_arn, protocol, update_on_conflict, None
            )
            
        except Exception as e:
            # Clean up deployment directory on error
            try:
                if Path(deployment_dir).exists():
                    shutil.rmtree(deployment_dir)
                    logger.info(f"Cleaned up deployment directory on error: {deployment_dir}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to cleanup deployment directory on error: {cleanup_err}")
            raise

    def _deploy_with_agentcore_cli(
        self,
        deployment_dir: str,
        name: str,
        entrypoint: str,
        ecr_repo_uri: Optional[str],
        execution_role_arn: Optional[str],
        protocol: str,
        update_on_conflict: bool,
        agent_description: Optional[str]
    ) -> str:
        """Common method to deploy using agentcore CLI."""
        # Get environment variables for agentcore CLI
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
        os.chdir(str(deployment_dir))
        
        try:
            # Handle None values for CLI
            if execution_role_arn is None:
                execution_role_arn = 'None'
            
            if ecr_repo_uri is None:
                ecr_repo_uri = 'None'

            # Find the agentcore executable
            import sys
            
            # Try to find the project's virtual environment
            project_root = Path(__file__).parent.parent.parent
            possible_venv_locations = [
                project_root / '.venv' / 'bin',  # Standard .venv location
                Path.cwd() / '.venv' / 'bin',    # Current directory .venv
                Path(sys.executable).parent,     # Current Python bin directory
            ]
            
            agentcore_exe = None
            for venv_path in possible_venv_locations:
                potential_exe = venv_path / 'agentcore'
                if potential_exe.exists():
                    agentcore_exe = potential_exe
                    logger.info(f"Found agentcore executable at {agentcore_exe}")
                    break
            
            if not agentcore_exe:
                # Final fallback - try to use which/where command
                try:
                    which_result = shutil.which('agentcore')
                    if which_result:
                        agentcore_exe = Path(which_result)
                        logger.info(f"Found agentcore using which command: {agentcore_exe}")
                    else:
                        raise Exception(f"Could not find agentcore executable. Tried paths: {[str(p / 'agentcore') for p in possible_venv_locations]}. Also tried 'which agentcore' but not found.")
                except Exception:
                    raise Exception(f"Could not find agentcore executable. Tried paths: {[str(p / 'agentcore') for p in possible_venv_locations]}")
            
            # Run agentcore configure
            args = [
                str(agentcore_exe), 'configure', 
                '--name', name,
                '--execution-role', execution_role_arn, 
                '--ecr', ecr_repo_uri, 
                '--entrypoint', entrypoint,
                '--requirements-file', 'requirements.txt',
                '--protocol', protocol,
                '--region', region
            ]

            logger.info(f"Running agentcore configure command: {' '.join(args)}")
            
            # Use pipes for real-time streaming and provide stdin to answer OAuth prompt
            process = subprocess.Popen(args, 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.STDOUT,
                                      stdin=subprocess.PIPE,
                                      text=True)
            
            # Provide "no" input to the OAuth prompt
            try:
                process.stdin.write("no\n")
                process.stdin.flush()
                process.stdin.close()
            except Exception as e:
                logger.info(f"Failed to write to stdin: {e}")
            
            # Stream output in real-time
            stdout_data = ""
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    stdout_data += output
                    logger.info(f"agentcore configure: {output.strip()}")
            
            returncode = process.poll()
            logger.info(f'Agentcore configure completed with return code {returncode}')
            
            if returncode != 0:
                raise Exception(f"Error during agentcore configure.\noutput: {stdout_data}")
            else:
                logger.info('agentcore configure completed successfully.')

            # Modify .bedrock_agentcore.yaml configuration
            config_file = os.path.join(str(deployment_dir), '.bedrock_agentcore.yaml')
            
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
                        logger.info(f"execution role arn is {execution_role_arn}, type {type(execution_role_arn)}")
                        if execution_role_arn == 'None':
                            line = line.replace('false', 'true')
                        final_config_lines += line
                    elif 'ecr_repository: ' in line:
                        if not line.strip().endswith('None'):
                            final_config_lines += line
                    elif 'ecr_auto_create: ' in line:
                        logger.info(f"ecr_repo_uri == {ecr_repo_uri}, type {type(ecr_repo_uri)}")
                        if ecr_repo_uri == 'None':
                            line = line.replace('false', 'true')
                        final_config_lines += line
                    else:
                        final_config_lines += line

            logger.info(f"Final config lines before running agentcore launch: {final_config_lines}")
            
            with open(config_file, 'w') as config_out:
                config_out.write(final_config_lines)
                
            # Run agentcore launch
            launch_args = [str(agentcore_exe), 'launch']
            if update_on_conflict:
                launch_args.append('--auto-update-on-conflict')
                
            logger.info(f"Running agentcore launch command: {' '.join(launch_args)}")
            
            # Use pipes for real-time streaming
            process = subprocess.Popen(launch_args, 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.STDOUT,
                                      text=True)
            
            # Stream output in real-time
            stdout_data = ""
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    stdout_data += output
                    logger.info(f"agentcore launch: {output.strip()}")
            
            returncode = process.poll()
            logger.info(f'Agentcore launch completed with return code {returncode}')
            
            if returncode != 0:
                raise Exception(f"Error during agentcore launch.\noutput: {stdout_data}")

            # Extract agent ARN from result
            agent_arn = None
            lines = stdout_data.split('\n')
            for line in lines:
                if 'Deployment completed successfully - Agent: ' in line:
                    logger.info(f"Found agent line: {line}")
                    agent_arn = line.split(' Agent: ')[1]
                    break
                    
            if not agent_arn:
                # Try looking for other patterns in output
                for line in lines:
                    if 'Agent: arn:' in line:
                        logger.info(f"Found agent ARN in output: {line}")
                        agent_arn = line.split('Agent: ')[1].strip()
                        break
            
            if not agent_arn:
                logger.warning("Could not extract agent ARN from agentcore launch output")
                agent_arn = f"arn:aws:bedrock-agentcore:{region}:{account}:runtime/{name}"
                
            agent_runtime_id = agent_arn.split('/')[-1]
            logger.info(f'Created agent runtime with ARN: {agent_arn}, ID: {agent_runtime_id}')
            
            # Get runtime details
            try:
                response = agentcore_control_client.get_agent_runtime(agentRuntimeId=agent_runtime_id)
                logger.info(f"Successfully retrieved runtime details for {agent_runtime_id}")
                
                description_info = f"\n\nAgent Description: {agent_description}" if agent_description else f"\n\nECR Repository: {ecr_repo_uri}"
                
                return f"Successfully created agent runtime:\n\nRuntime Name: {name}\nRuntime ID: {agent_runtime_id}\nRuntime ARN: {agent_arn}\nStatus: {response.get('status', 'UNKNOWN')}\n\nDeployment Directory: {deployment_dir}{description_info}\n\nYou can now invoke this runtime using the invoke_agent_runtime tool."
                
            except Exception as e:
                logger.warning(f"Could not retrieve runtime details: {e}")
                description_info = f"\n\nAgent Description: {agent_description}" if agent_description else f"\n\nECR Repository: {ecr_repo_uri}"
                return f"Successfully created agent runtime:\n\nRuntime Name: {name}\nRuntime ID: {agent_runtime_id}\nRuntime ARN: {agent_arn}\n\nDeployment Directory: {deployment_dir}{description_info}"
                
        finally:
            # Return to original directory
            os.chdir(original_cwd)

    def customize_business_logic(
        self, 
        user_description: str, 
        template_content: str, 
        requirements_content: str
    ) -> tuple[str, str]:
        """Customize the business logic in the entrypoint template while preserving architecture.
        
        This is step 3 of the agent runtime creation process. It takes the selected template
        and modifies only the business logic to match the user's requirements while keeping
        the overall code architecture pattern intact.
        
        Args:
            user_description: Natural language description of what the agent should do
            template_content: The content of the selected entrypoint.py template
            requirements_content: The content of the default requirements.txt
            
        Returns:
            Tuple of (modified_entrypoint_content, updated_requirements_content)
        """
        try:
            # Construct the prompt for customizing business logic
            prompt_template = """You are an expert Python developer specializing in AI agent development. Your task is to customize the business logic in an agent entrypoint template while preserving the overall architecture pattern.

# IMPORTANT INSTRUCTIONS:
1. KEEP the overall code structure, imports, app setup, models, and handler function signature EXACTLY as they are
2. ONLY modify the business logic to match the user's requirements using replace-in-file techniques:
      a) Find the blocks of example template code that need replacing.
      b) Replace with your new business logic per the user's requirements.
      c) Output format would be:
            ```
            ------- SEARCH
            [one exact content string (including newlines, whitespace, and punctuation) to find in the file]
            =======
            [one new content block to replace it with]
            +++++++ REPLACE
            ```
3. Preserve all existing architectural patterns (BedrockAgentCoreApp, Pydantic models, etc.)
4. Keep all logging, error handling, and response formatting as-is
5. If you need a web tool use the example at the top of the template as-is and list the agentic_web_browser_tool in the tools for the agent rather than using other web agent strategies.
6. If you need additional Python packages, list them at the end after "REQUIREMENTS_UPDATE:"

USER REQUIREMENTS:
{user_description}

CURRENT ENTRYPOINT TEMPLATE:
{template_content}

CURRENT REQUIREMENTS.TXT:
{requirements_content}


# OUTPUT FORMAT:
<entrypoint_updates>
------- SEARCH
[exact content to find in the file]
=======
[new content to replace it with]
+++++++ REPLACE
------- SEARCH
[next content to find in the file]
=======
[new content to replace it with]
+++++++ REPLACE
</entrypoint_updates>

<requirements_updates>
[list of additional python modules to add at the end of requirements.txt, one per line]
</requirements_updates>
# END OUTPUT FORMAT

Now output the results without further commentary

"""

            formatted_prompt = prompt_template.format(
                user_description=user_description,
                template_content=template_content,
                requirements_content=requirements_content
            )
            
            # Prepare the message for Bedrock Converse API
            messages = [
                {
                    "role": "user",
                    "content": [{"text": formatted_prompt}]
                }
            ]
            
            logger.info(f"Customizing business logic for: {user_description[:100]}...")
            
            response = bedrock_runtime_client.converse(
                modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                messages=messages,
                inferenceConfig={
                    "maxTokens": 4000,
                    "temperature": 0.2,  # Low temperature for consistent, reliable code modification
                    "topP": 0.9
                }
            )
            
            # Extract the response
            response_text = response['output']['message']['content'][0]['text'].strip()
            logger.info(f"Bedrock response: {response_text}")

            entrypoint_updates = response_text.split('<entrypoint_updates>')[1].split('</entrypoint_updates>')[0]
            requirements_updates = response_text.split('<requirements_updates>')[1].split('</requirements_updates>')[0]
            
            new_entrypoint = template_content
            updated_requirements = requirements_content
            logger.info(f"Got entrypoint_updates\n{entrypoint_updates}")
            logger.info(f"STARTING REPLACEMENTS")
            for update in entrypoint_updates.split('+++++++ REPLACE'):
                if update.strip() == '':
                    continue
                logger.info(f"Got update\n{update}...")
                update = update.replace('------- SEARCH', '')
                search, replacement = update.split("=======")
                search = search.strip()
                # replacement = replacement.strip()
                logger.info(f"Replacing\n{search}\nwith \n{replacement} in entrypoint.")
                new_entrypoint = new_entrypoint.replace(search, replacement)
            
            if requirements_content not in requirements_updates:
                updated_requirements = requirements_content + requirements_updates
            else:
                updated_requirements = requirements_updates
            logger.info(f"Returning new entrypoint\n{new_entrypoint} \nand requirements \n{updated_requirements}")
            return new_entrypoint, updated_requirements
            
        except Exception as e:
            logger.error(f"Failed to customize business logic via Bedrock: {e}")
            raise e

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
        return shutil.rmtree(tmpdir)
    
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
                    "status": runtime['status'] if isinstance(runtime['status'], str) else runtime['status'].value,
                }
                if hasattr(runtime,'lastUpdatedAt') and runtime.lastUpdatedAt:
                    args['last_updated_at'] = runtime.lastUpdatedAt.isoformat()
                
                runtimes.append(AgentRuntime(**args))
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
            logger.info(f"Error getting runtime details: {str(e)}")
            raise e
        try:
            # Prepare update parameters - use values from request if provided, otherwise use values from existing runtime
            update_request_params = {
                "agentRuntimeId": old_runtime.agent_runtime_id,
                "agentRuntimeArtifact": request.agent_runtime_artifact if hasattr(request, 'agent_runtime_artifact') and request.agent_runtime_artifact else old_runtime.agent_runtime_artifact,
                "roleArn": request.roleArn if hasattr(request, 'roleArn') and request.roleArn else old_runtime.role_arn,
                "networkConfiguration": request.network_configuration if hasattr(request, 'network_configuration') and request.network_configuration else old_runtime.network_configuration,
                "protocolConfiguration": request.protocol_configuration if hasattr(request, 'protocol_configuration') and request.protocol_configuration else old_runtime.protocol_configuration
            }
            
            # Handle optional fields - skip client token as it's optional and can cause validation errors
            if hasattr(request, 'client_token') and request.client_token and len(request.client_token) >= 33:
                update_request_params['clientToken'] = request.client_token
                
            if hasattr(request, 'description') and request.description and len(request.description) > 0:
                update_request_params['description'] = request.description
            else:
                # Use existing description or default description if none exists (cannot be empty)
                existing_description = getattr(old_runtime, 'description', '')
                if existing_description and len(existing_description) > 0:
                    update_request_params['description'] = existing_description
                else:
                    update_request_params['description'] = f"Updated runtime configuration at {time.strftime('%Y-%m-%d %H:%M:%S')}"
                
            # Handle environment variables if provided
            if hasattr(request, 'environmentVariables') and request.environmentVariables:
                update_request_params['environmentVariables'] = request.environmentVariables
            else:
                # Use existing environment variables if available
                update_request_params['environmentVariables'] = getattr(old_runtime, 'environmentVariables', {})

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
                    logger.info(f"Runtime {agent_runtime_id} still {current_status}, waiting {poll_interval}s before next check...")
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
            
        Raises:
            ValueError: If the name cannot be sanitized to meet requirements
        """
        import re
        
        # Handle empty string case first
        if not original_name:
            raise ValueError("Agent name cannot be empty. Please provide a name that starts with a letter.")
        
        # Replace invalid characters with underscores
        sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '_', original_name)
        
        # Ensure it starts with a letter
        if not sanitized_name or not sanitized_name[0].isalpha():
            raise ValueError(f"Agent name '{original_name}' must start with a letter. Please provide a name that starts with a letter.")
        
        # Truncate to 48 characters if needed
        if len(sanitized_name) > 48:
            sanitized_name = sanitized_name[:48]
        
        # Remove trailing underscores that might result from truncation
        sanitized_name = sanitized_name.rstrip('_')
        
        # Ensure it's not empty after sanitization
        if not sanitized_name:
            raise ValueError(f"Agent name '{original_name}' could not be sanitized to meet requirements. Please provide a name that starts with a letter and contains valid characters.")
            
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
