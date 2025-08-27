import os
import json
import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Environment: {os.environ}")

app = BedrockAgentCoreApp()

# ============================================================================
# Specialized Tool Agents
# ============================================================================

CODE_ASSISTANT_PROMPT = """
You are a specialized code assistant. Focus only on programming-related tasks:
- Code review and debugging
- Writing clean, efficient code
- Explaining programming concepts
- Best practices and design patterns
Always provide practical, actionable coding advice.
"""

@tool
def code_assistant(query: str) -> str:
    """
    Handle programming questions, code review, debugging, and software development tasks.
    
    Args:
        query: A programming-related question or code snippet to analyze
        
    Returns:
        Detailed programming assistance with code examples and best practices
    """
    try:
        code_agent = Agent(
            system_prompt=CODE_ASSISTANT_PROMPT,
            tools=[]  # Add specific coding tools if available
        )
        response = code_agent(query)
        return str(response)
    except Exception as e:
        return f"Error in code assistant: {str(e)}"

RESEARCH_ASSISTANT_PROMPT = """
You are a specialized research assistant. Focus only on providing
factual, well-sourced information in response to research questions.
Always cite your sources when possible and provide comprehensive answers.
"""

@tool
def research_assistant(query: str) -> str:
    """
    Process and respond to research-related queries with factual information.
    
    Args:
        query: A research question requiring factual information
        
    Returns:
        A detailed research answer with citations and sources
    """
    try:
        research_agent = Agent(
            system_prompt=RESEARCH_ASSISTANT_PROMPT,
            tools=[]  # Add research tools like web search if available
        )
        response = research_agent(query)
        return str(response)
    except Exception as e:
        return f"Error in research assistant: {str(e)}"

DATA_ANALYSIS_PROMPT = """
You are a specialized data analysis assistant. Focus on:
- Statistical analysis and interpretation
- Data visualization recommendations
- Mathematical computations
- Data cleaning and preprocessing advice
Provide clear, quantitative insights with explanations.
"""

@tool
def data_analysis_assistant(query: str) -> str:
    """
    Handle data analysis, statistics, and mathematical computation tasks.
    
    Args:
        query: A data analysis or statistical question
        
    Returns:
        Statistical analysis with explanations and recommendations
    """
    try:
        data_agent = Agent(
            system_prompt=DATA_ANALYSIS_PROMPT,
            tools=[]  # Add data analysis tools if available
        )
        response = data_agent(query)
        return str(response)
    except Exception as e:
        return f"Error in data analysis assistant: {str(e)}"

DOCUMENTATION_PROMPT = """
You are a specialized documentation assistant. Focus on:
- Writing clear, comprehensive documentation
- Technical writing best practices
- API documentation and guides
- Explaining complex concepts simply
Always structure information clearly and make it accessible.
"""

@tool
def documentation_assistant(query: str) -> str:
    """
    Help with writing and reviewing documentation, technical writing, and explanations.
    
    Args:
        query: A documentation or technical writing request
        
    Returns:
        Well-structured documentation or writing assistance
    """
    try:
        doc_agent = Agent(
            system_prompt=DOCUMENTATION_PROMPT,
            tools=[]  # Add documentation tools if available
        )
        response = doc_agent(query)
        return str(response)
    except Exception as e:
        return f"Error in documentation assistant: {str(e)}"

# ============================================================================
# Orchestrator Agent
# ============================================================================

ORCHESTRATOR_PROMPT = """
You are an intelligent orchestrator that routes queries to specialized agents:

- For programming, debugging, code review → Use the code_assistant tool
- For research, factual information, general knowledge → Use the research_assistant tool  
- For data analysis, statistics, math → Use the data_analysis_assistant tool
- For documentation, technical writing, explanations → Use the documentation_assistant tool
- For simple greetings or general conversation → Answer directly without tools

Always select the most appropriate specialist based on the user's query. 
If multiple specialists could help, choose the most relevant one.
Be concise in your routing decisions and let the specialists provide detailed responses.
"""

# Create orchestrator with all specialist tools
orchestrator = Agent(
    system_prompt=ORCHESTRATOR_PROMPT,
    tools=[code_assistant, research_assistant, data_analysis_assistant, documentation_assistant]
)

# ============================================================================
# Streaming Event Models
# ============================================================================

class StreamEventType:
    INPUT_CAPTURE = "input_capture"
    THOUGHT_CAPTURE = "thought_capture"
    TOOL_EXECUTION = "tool_execution"
    AGENT_SWITCH = "agent_switch"
    OUTPUT_CAPTURE = "output_capture"
    ERROR = "error"
    DONE = "done"

class StreamEvent(BaseModel):
    event: str
    data: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    session_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

# ============================================================================
# Request/Response Models
# ============================================================================

class HandlerRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    stream: bool = False

class HandlerResponse(BaseModel):
    statusCode: int
    result: str

class StreamingHandlerResponse(BaseModel):
    statusCode: int
    stream: bool = True
    content_type: str = "application/x-ndjson"

# ============================================================================
# Streaming Implementation
# ============================================================================

async def stream_multi_agent_response(
    request: HandlerRequest
) -> AsyncGenerator[str, None]:
    """
    Stream multi-agent responses as JSON lines with real-time capture of inputs, thoughts, and outputs.
    """
    session_id = request.session_id or str(uuid4())
    
    try:
        # Capture initial input
        input_event = StreamEvent(
            event=StreamEventType.INPUT_CAPTURE,
            data={
                "prompt": request.prompt,
                "type": "user_input"
            },
            session_id=session_id,
            metadata={"source": "user"}
        )
        yield f"{input_event.model_dump_json()}\n"
        
        # Capture orchestrator thinking
        thinking_event = StreamEvent(
            event=StreamEventType.THOUGHT_CAPTURE,
            data={
                "thinking": f"Analyzing query: '{request.prompt}' to determine which specialist to route to...",
                "agent": "orchestrator"
            },
            session_id=session_id,
            metadata={"phase": "routing"}
        )
        yield f"{thinking_event.model_dump_json()}\n"
        
        # Use async streaming if available, otherwise fall back to sync
        try:
            # Try to get async streaming from strands
            if hasattr(orchestrator, 'stream_async'):
                async for chunk in orchestrator.stream_async(request.prompt, session_id=session_id):
                    # Capture streaming thoughts and tool executions
                    if isinstance(chunk, dict):
                        # Parse strands streaming event
                        event_type = chunk.get('type', 'unknown')
                        
                        if 'thinking' in str(chunk).lower() or 'reasoning' in str(chunk).lower():
                            thought_event = StreamEvent(
                                event=StreamEventType.THOUGHT_CAPTURE,
                                data={
                                    "thinking": str(chunk),
                                    "agent": "orchestrator",
                                    "raw_chunk": chunk
                                },
                                session_id=session_id,
                                metadata={"phase": "processing"}
                            )
                            yield f"{thought_event.model_dump_json()}\n"
                        elif 'tool' in str(chunk).lower():
                            tool_event = StreamEvent(
                                event=StreamEventType.TOOL_EXECUTION,
                                data={
                                    "tool_info": str(chunk),
                                    "raw_chunk": chunk
                                },
                                session_id=session_id,
                                metadata={"phase": "tool_execution"}
                            )
                            yield f"{tool_event.model_dump_json()}\n"
                        else:
                            # General output capture
                            output_event = StreamEvent(
                                event=StreamEventType.OUTPUT_CAPTURE,
                                data={
                                    "content": str(chunk),
                                    "type": "partial_response"
                                },
                                session_id=session_id,
                                metadata={"phase": "generation"}
                            )
                            yield f"{output_event.model_dump_json()}\n"
            else:
                # Fallback to synchronous processing with simulated streaming
                result = orchestrator(request.prompt, session_id=session_id)
                
                # Simulate agent routing decision
                agent_switch_event = StreamEvent(
                    event=StreamEventType.AGENT_SWITCH,
                    data={
                        "decision": "Routing to appropriate specialist agent",
                        "query_analysis": request.prompt[:100] + "..." if len(request.prompt) > 100 else request.prompt
                    },
                    session_id=session_id,
                    metadata={"phase": "routing"}
                )
                yield f"{agent_switch_event.model_dump_json()}\n"
                
                # Capture final output
                output_event = StreamEvent(
                    event=StreamEventType.OUTPUT_CAPTURE,
                    data={
                        "content": str(result),
                        "type": "final_response",
                        "agent": "multi_agent_system"
                    },
                    session_id=session_id,
                    metadata={"phase": "completion"}
                )
                yield f"{output_event.model_dump_json()}\n"
                
        except Exception as stream_error:
            error_event = StreamEvent(
                event=StreamEventType.ERROR,
                data={
                    "error": f"Streaming error: {str(stream_error)}",
                    "fallback": "Using synchronous processing"
                },
                session_id=session_id,
                metadata={"phase": "error_handling"}
            )
            yield f"{error_event.model_dump_json()}\n"
            
            # Fallback to sync processing
            result = orchestrator(request.prompt, session_id=session_id)
            output_event = StreamEvent(
                event=StreamEventType.OUTPUT_CAPTURE,
                data={
                    "content": str(result),
                    "type": "final_response"
                },
                session_id=session_id,
                metadata={"phase": "fallback_completion"}
            )
            yield f"{output_event.model_dump_json()}\n"
        
        # Stream completion
        done_event = StreamEvent(
            event=StreamEventType.DONE,
            data={
                "message": "Multi-agent response completed",
                "session_id": session_id
            },
            session_id=session_id,
            metadata={"phase": "done"}
        )
        yield f"{done_event.model_dump_json()}\n"
        
    except Exception as e:
        error_event = StreamEvent(
            event=StreamEventType.ERROR,
            data={
                "error": str(e),
                "type": "system_error"
            },
            session_id=session_id,
            metadata={"phase": "error"}
        )
        yield f"{error_event.model_dump_json()}\n"

# ============================================================================
# Main Handler
# ============================================================================

@app.entrypoint
def handler(evt) -> HandlerResponse:
    """
    Main entrypoint for multi-agent system with optional streaming support.
    """
    logger.info(f"handler received request {evt}, type {type(evt)}")
    
    # Parse request
    if isinstance(evt, dict):
        request = HandlerRequest(**evt)
    else:
        request = HandlerRequest(prompt=evt)
    
    logger.info(f"Handler got request {request}")
    
    # Handle streaming requests
    if request.stream:
        logger.info("Streaming request detected - this would require async support in production")
        # In a real implementation, you'd return a streaming response
        # For now, we'll collect all events and return them
        events = []
        async def collect_events():
            async for event_line in stream_multi_agent_response(request):
                events.append(event_line.strip())
        
        # Run async generator synchronously for demo
        asyncio.run(collect_events())
        
        return HandlerResponse(
            statusCode=200,
            result="\n".join(events)
        ).__dict__
    
    # Standard synchronous processing
    session_id = request.session_id or str(uuid4())
    
    try:
        result = orchestrator(request.prompt, session_id=session_id)
        logger.info(f"returning result {result}, type {type(result)}")
        
        # Extract response text based on result type
        if hasattr(result, 'message') and isinstance(result.message, dict):
            response_text = result.message.get('content', [{}])[0].get('text', str(result))
        else:
            response_text = str(result)
        
        return HandlerResponse(
            statusCode=200,
            result=response_text
        ).__dict__
        
    except Exception as e:
        logger.error(f"Error in handler: {e}")
        return HandlerResponse(
            statusCode=500,
            result=f"Error: {str(e)}"
        ).__dict__

# ============================================================================
# Development Server
# ============================================================================

if __name__ == "__main__":
    logger.info('Starting multi-agent streaming app...')
    
    # Test the streaming functionality
    test_request = HandlerRequest(
        prompt="Can you help me debug a Python function that's not working correctly?",
        stream=True
    )
    
    logger.info("\n=== Testing Streaming Functionality ===")
    async def test_streaming():
        async for event_line in stream_multi_agent_response(test_request):
            logger.info(f"STREAM: {event_line.strip()}")
    
    asyncio.run(test_streaming())
    
    logger.info('\n=== Starting BedrockAgentCore App ===')
    app.run()
    logger.info('Exiting')
