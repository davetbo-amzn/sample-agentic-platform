# Module 6: AgentCore Integration with AgentPath

## Overview

Module 6 is an advanced lab that demonstrates the **AgentPath support for Amazon Bedrock AgentCore**. This module shows how to integrate with AgentCore's memory and runtime management capabilities through our AgentPath sample agentic platform.

## What You'll Learn

This lab demonstrates:

1. **AgentCore Memory CRUD Operations**
   - Create AgentCore memory providers
   - Read/Get memory provider configurations  
   - Update memory provider settings
   - Delete memory providers
   - Manage memory events and sessions

2. **AgentCore Runtime CRUD Operations**
   - Create AgentCore runtimes from container images
   - List and get runtime details
   - Update runtime configurations
   - Delete runtimes
   - Monitor runtime status and health

3. **AgentCore Runtime Invocation with Memory**
   - Invoke AgentCore runtimes with integrated memory
   - Pass context between memory and runtime operations
   - Handle agent conversations with persistent memory
   - Demonstrate end-to-end agentic workflows

4. **Production Integration Patterns**
   - Service authentication and authorization
   - Error handling and retry strategies
   - Resource lifecycle management
   - Observability and monitoring

## Architecture

Module 6 integrates with the AgentCore components organized under the new business logic structure:

```
┌─────────────────┐    ┌──────────────────────────────────────┐    ┌─────────────────────┐
│   Lab Notebook  │───▶│  AgentCore Service                   │───▶│  AgentCore Memory   │
│                 │    │  (src/agentic_platform/service/      │    │                     │
└─────────────────┘    │   agentcore/)                        │    └─────────────────────┘
         │             │                                      │
         ▼             │   ┌─────────────┐ ┌──────────────┐   │
┌───────────────────── │  │   Memory    │ │   Runtime    │   │    ┌──────────────────────┐
│ AgentCore Runtime   │─┤  │   Module    │ │   Module     │   ├───▶│  AgentCore Runtime   │
│ Gateway (Port 8003) │ │  │             │ │              │   │    │                      │
└─────────────────────┘ │  └─────────────┘ └──────────────┘   │    └──────────────────────┘
                        └──────────────────────────────────────┘
```

### AgentCore Business Logic Structure

The AgentCore business logic is now organized under `src/agentic_platform/service/agentcore/` with the following modular structure:

#### Memory Module (`memory/`)
- **API Layer** (`api/agentcore_memory_provider_controller.py`): Controller handling memory provider operations
- **Client Layer** (`client/agentcore_memory_client.py`): Client for AWS Bedrock AgentCore Memory API calls
- **Operations Supported**:
  - Create/Delete memory providers
  - Get/List memory providers and configurations
  - Create memory events (AgentPath memories → AgentCore events)
  - List events and manage sessions
  - Wait operations for async provider lifecycle

#### Runtime Module (`runtime/`)
- **API Layer** (`api/agentcore_runtime_controller.py`): Controller managing runtime lifecycle
- **Client Layer** (`client/agentcore_runtime_client.py`): Client for AWS Bedrock AgentCore Runtime API calls
- **Example Deployment** (`example_agent_deployment/`): Complete containerized agent example
- **Operations Supported**:
  - Create/Delete AgentCore runtimes from container images
  - Get/List runtime details and status
  - Update runtime configurations
  - Monitor runtime health and readiness

### Key Components

- **AgentCore Memory Module**: Provides CRUD operations for AgentCore memory providers and events
- **AgentCore Runtime Module**: Manages AgentCore runtime lifecycle and invocation
- **Modular Architecture**: Clean separation between API controllers and service clients
- **AgentPath Deployment**: Isolated Terraform deployment for AgentCore infrastructure
- **Integration Tests**: Comprehensive test suite demonstrating all operations

## Prerequisites

Before starting this lab, you should have completed:

- **Modules 1-5**: Understanding of agentic patterns, frameworks, and deployment
- **AWS Account**: With access to AWS Bedrock AgentCore services
- **AgentPath Deployment**: The isolated AgentCore infrastructure should be deployed

### Required AWS Permissions

Your AWS credentials need permissions for:
- `bedrock-agentcore:*` (AgentCore data plane operations)
- `bedrock-agentcore-control:*` (AgentCore control plane operations) 
- IAM role access for runtime execution
- ECR access for container images

### Environment Setup

1. **AgentPath Infrastructure**: Deploy the isolated AgentCore components:
   ```bash
   cd ../../agentcore-agentpath
   ./docker_package_lambda.sh  # Package the Lambda function
   terraform init
   terraform apply
   ```

2. **Environment Variables**: Configure your test environment:
   ```bash
   # Copy the environment template
   cp ../../tests-agentcore/.env.example ../../tests-agentcore/.env
   
   # Edit with your AWS configuration
   # TEST_CONTAINER_URI=your-ecr-uri
   # TEST_ROLE_ARN=your-iam-role-arn
   # REGION=us-west-2
   ```

3. **Dependencies**: Ensure required packages are installed:
   ```bash
   uv sync  # Install all project dependencies
   ```

## Lab Structure

### Part 1: AgentCore Memory Management
- Create and configure memory providers
- Understand memory retention and event expiry
- Perform CRUD operations on memory resources
- Work with memory events and sessions

### Part 2: AgentCore Runtime Management  
- Create runtimes from container images
- Configure runtime parameters and roles
- Monitor runtime status and readiness
- Update and delete runtime resources

### Part 3: Integrated Agent Workflows
- Invoke runtimes with memory context
- Build conversational agents with persistent memory
- Handle multi-turn interactions
- Implement error handling and recovery

### Part 4: Production Considerations
- Authentication and security patterns
- Monitoring and observability
- Resource optimization
- Scaling considerations

## Running the Lab

Start the Jupyter Lab environment:

```bash
# From the project root directory
uv run jupyter lab
```

Then open and run through the lab notebook: `module6_agentcore_integration.ipynb`

## Key Concepts

### AgentCore Memory vs Platform Memory Gateway

**AgentCore Memory** (AWS Bedrock):
- `create_memory()` creates a memory *provider* resource in AWS
- Supports backend memory strategies for multiple agents and users
- Events have configurable expiry (minimum 7 days)
- Designed for production multi-tenant scenarios

**Platform Memory Gateway** (Local):
- `create_memory()` stores a single payload/event
- Equivalent to AgentCore's `create_event()` call  
- Simpler model for development and testing
- Bridges to AgentCore when `MEMORY_CLIENT=AGENTCORE`

### Runtime Lifecycle Management

AgentCore runtimes go through these states:
- `CREATING` → `READY` (success)
- `CREATING` → `FAILED` (failure)
- `UPDATING` → `READY` (success)  
- `UPDATING` → `FAILED_ROLLBACK` (failure)

The lab demonstrates proper waiter patterns for handling async operations.

### Authentication Patterns

AgentCore uses **opaque tokens** (not JWTs like Cognito):
- `get_workload_access_token()` - For service-to-service calls
- `get_workload_access_token_for_jwt()` - For user-based workloads
- `get_workload_access_token_for_user_id()` - For specific users

## Integration with Previous Modules

Module 6 builds on concepts from previous labs:

- **Module 1**: Prompt engineering techniques now applied in AgentCore runtimes
- **Module 2**: Agentic patterns implemented using AgentCore infrastructure  
- **Module 3**: Agent applications now deployed as AgentCore runtimes
- **Module 4**: Multi-agent systems coordinated through AgentCore memory
- **Module 5**: Production deployment patterns extended to AgentCore

## Success Criteria

By the end of this lab, you should be able to:

1. ✅ Create and manage AgentCore memory providers
2. ✅ Deploy and manage AgentCore runtimes  
3. ✅ Invoke runtimes with integrated memory context
4. ✅ Handle the full lifecycle of AgentCore resources
5. ✅ Implement production-ready error handling
6. ✅ Understand the integration between AgentPath and the broader platform

## Troubleshooting

### Common Issues

**Service Connection Errors**: 
- Verify AgentPath infrastructure is deployed
- Check AWS credentials and permissions
- Ensure services are running on correct ports (8003, 8004)

**Memory Provider Creation Failures**:
- Validate `eventExpiryDuration` is ≥ 7 days
- Check IAM role permissions for AgentCore
- Verify AWS region configuration

**Runtime Deployment Issues**:
- Confirm ECR container URI is accessible
- Validate IAM execution role exists
- Check container image compatibility

**Token Authentication Errors**:
- AgentCore tokens are opaque, not JWTs
- Use proper token acquisition methods
- Handle token refresh and expiry

### Getting Help

If you encounter issues:
1. Review the integration test files in `../../tests-agentcore/integration/`
2. Check the AgentPath deployment logs
3. Verify environment variable configuration
4. Consult the AgentCore API documentation

## Next Steps

After completing Module 6:

- **Deploy Full Platform**: Try deploying the complete Sample Agentic Platform
- **Build Custom Agents**: Create your own AgentCore-powered applications
- **Extend Integration**: Add new services that integrate with AgentCore
- **Production Deployment**: Deploy AgentCore applications to production AWS environments

## Resources

- **AgentPath Deployment Guide**: `../../agentcore-agentpath/README.md`
- **Integration Tests**: `../../tests-agentcore/integration/`
- **Platform Architecture**: `../../media/highlevel-architecture.png`
- **AWS Bedrock AgentCore Documentation**: [AWS Docs](https://docs.aws.amazon.com/bedrock/)

---

**Welcome to the advanced world of production-ready agentic applications with AWS Bedrock AgentCore!** 🚀
