# AgentCore Runtime Streaming Implementation

This implementation provides streaming functionality for AgentCore runtimes in the sample-agentic-platform project, enabling real-time visibility into multi-agent interactions and response generation.

## Overview

The streaming implementation consists of three main components:

1. **JWT AgentCore Client** - Direct runtime invocation with JWT authentication
2. **Stream Parser** - Event processing and analysis utilities  
3. **Streaming Tests** - Comprehensive test suite for streaming functionality

## Key Features

- ✅ **Direct Runtime Invocation** - Bypass runtime controller for production-like testing
- ✅ **JWT Authentication** - Support for OAuth from third-party providers
- ✅ **Real-time Streaming** - JSON lines event format with live event processing
- ✅ **Multi-Agent Visibility** - Track interactions between specialized agents
- ✅ **Event Analysis** - Parse and analyze streaming events with rich metadata
- ✅ **Session Management** - Track multiple concurrent streaming sessions

## Architecture

```
Client Request → JWT Auth → AgentCore Runtime → Streaming Response → Event Parser → Structured Events
```

The implementation follows the existing streaming pattern in `multi_entrypoint.py` which already provides sophisticated streaming capabilities for deployed AgentCore runtimes.

## Files Added

### Core Utilities

- `tests-agentcore/utils/jwt_agentcore_client.py` - JWT-authenticated client for direct runtime invocation
- `tests-agentcore/utils/stream_parser.py` - Event parsing and analysis utilities
- `tests-agentcore/utils/__init__.py` - Package initialization

### Tests and Demos  

- `tests-agentcore/test_agentcore_streaming.py` - Comprehensive streaming test suite
- `test_agentcore_streaming_demo.py` - Interactive demonstration script

## Event Types

The streaming implementation supports these event types (defined in `multi_entrypoint.py`):

- **INPUT_CAPTURE** - User input and prompts
- **THOUGHT_CAPTURE** - Agent reasoning and decision-making
- **TOOL_EXECUTION** - Tool invocations and function calls  
- **AGENT_SWITCH** - Multi-agent coordination and routing
- **OUTPUT_CAPTURE** - Generated responses and outputs
- **ERROR** - Error conditions and exceptions
- **DONE** - Completion notifications

## Usage Examples

### JWT AgentCore Client

```python
from tests_agentcore.utils.jwt_agentcore_client import JWTAgentCoreClient

client = JWTAgentCoreClient()

# Non-streaming invocation
response = client.invoke_runtime(
    agent_runtime_arn="arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/my-runtime",
    payload={"prompt": "Hello, world!", "session_id": "test-123"},
    stream=False
)

# Streaming invocation
streaming_response = client.invoke_runtime(
    agent_runtime_arn="arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/my-runtime", 
    payload={"prompt": "Complex multi-agent task", "session_id": "test-123"},
    stream=True
)

# Real-time streaming with generator
for event in client.invoke_runtime_streaming_generator(
    agent_runtime_arn="arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/my-runtime",
    payload={"prompt": "Streaming task", "session_id": "test-123"}
):
    print(f"Event: {event['event']} - {event['data']}")
```

### Stream Parser

```python
from tests_agentcore.utils.stream_parser import parse_streaming_response, StreamEventType

# Parse streaming response
parser = parse_streaming_response(streaming_response)

# Analyze events
input_events = parser.get_events_by_type(StreamEventType.INPUT_CAPTURE)
output_events = parser.get_events_by_type(StreamEventType.OUTPUT_CAPTURE)

# Extract multi-agent interactions
agent_interactions = parser.extract_multi_agent_interactions("session-id")

# Print summary
parser.print_streaming_summary("session-id")
```

## Running Tests

### Pytest Tests

```bash
# Run all streaming tests
pytest tests-agentcore/test_agentcore_streaming.py -v

# Run specific test
pytest tests-agentcore/test_agentcore_streaming.py::test_stream_parser_functionality -v

# Run with streaming marker
pytest -m agentcore_streaming -v
```

### Interactive Demo

```bash
# Run full demo (will prompt for runtime ARN)
python test_agentcore_streaming_demo.py

# Run with specific runtime
python test_agentcore_streaming_demo.py --runtime-arn arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/my-runtime

# Run specific demo
python test_agentcore_streaming_demo.py --demo streaming --runtime-arn <your-arn>
python test_agentcore_streaming_demo.py --demo generator --runtime-arn <your-arn>
```

## Environment Setup

### Required Environment Variables

```bash
# AWS Configuration
export REGION=us-west-2
export USER_POOL_ID=us-west-2_xxxxxxxxx
export USER_POOL_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Default runtime for demos
export AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/my-runtime
```

### Dependencies

The implementation uses:
- `requests` - HTTP client for runtime invocation
- `boto3` - AWS SDK for authentication
- `pytest` - Testing framework
- JWT token generation via existing `get_auth_token.py`

## Multi-Agent Streaming

The `multi_entrypoint.py` template already implements sophisticated multi-agent streaming:

### Specialist Agents
- **Code Assistant** - Programming and debugging tasks
- **Research Assistant** - Factual information and research
- **Data Analysis Assistant** - Statistics and mathematical computations  
- **Documentation Assistant** - Technical writing and explanations

### Orchestrator Agent
- Routes queries to appropriate specialists
- Coordinates multi-agent interactions
- Streams decision-making process in real-time

## Streaming Event Format

Events follow JSON lines format:

```json
{
  "event": "input_capture",
  "data": {
    "prompt": "User input text",
    "type": "user_input"
  },
  "timestamp": "2024-01-01T10:00:00Z",
  "session_id": "session-123",
  "metadata": {
    "source": "user"
  }
}
```

## Integration with Existing Tests

The streaming implementation integrates with existing test fixtures:

- Uses `session_runtime` fixture for deployed runtime testing
- Compatible with existing AgentCore infrastructure
- Follows established JWT authentication patterns

## Benefits

### Real-time Visibility
- See agent reasoning and decision-making as it happens
- Track tool executions and multi-agent coordination
- Monitor response generation progress

### Production-Ready Testing  
- Direct runtime invocation bypasses controller overhead
- JWT authentication supports OAuth integration
- Realistic load testing with concurrent sessions

### Multi-Agent Insights
- Understand how different specialists collaborate
- Analyze agent routing and task distribution
- Debug multi-agent coordination issues

## Future Enhancements

Potential improvements:
- WebSocket streaming support for web applications
- Event filtering and subscription patterns
- Streaming metrics and performance monitoring
- Integration with observability platforms

## Troubleshooting

### Common Issues

**JWT Token Errors**
- Ensure `USER_POOL_ID` and `USER_POOL_CLIENT_ID` are set
- Check that `get_auth_token.py` is accessible
- Verify AWS credentials are configured

**Runtime Connectivity**
- Confirm runtime is in `READY` state
- Verify runtime ARN format
- Check network connectivity to AWS

**Streaming Timeouts**
- Increase timeout values for complex requests
- Monitor runtime resource utilization
- Check for network latency issues

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Conclusion

This streaming implementation enables comprehensive testing and monitoring of AgentCore runtime behavior, providing visibility into multi-agent interactions and real-time response generation that wasn't previously available in the platform.
