# Agent Deployment Templates

This directory contains templates for creating AgentCore Runtime deployments.

## Templates

### entrypoint.py
Single agent template using Strands Agent framework. Best for simple, focused tasks that don't require multiple specialized capabilities.

### multi_entrypoint.py  
Multi-agent orchestration template with specialized agents for:
- **Code Assistant**: Programming, debugging, code review
- **Research Assistant**: Factual information, general knowledge
- **Data Analysis Assistant**: Statistics, mathematical computations
- **Documentation Assistant**: Technical writing, explanations

The orchestrator intelligently routes queries to the most appropriate specialist agent.

## Requirements

The `requirements.txt` file includes:
- `bedrock-agentcore-starter-toolkit`: Core AgentCore runtime framework
- `strands-agents`: Strands AI agent framework
- `pydantic`: Data validation and serialization

## Usage

These templates are automatically copied and deployed by the AgentCore Runtime Client based on the user's agent description. The system uses Bedrock to intelligently select between single and multi-agent templates.
