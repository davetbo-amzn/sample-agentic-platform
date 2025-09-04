import os
import logging
from pydantic import BaseModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.hooks import AfterInvocationEvent, HookProvider, HookRegistry, MessageAddedEvent

# Import AgentCore Memory
from bedrock_agentcore.memory import MemoryClient

from uuid import uuid4
import boto3
from boto3.session import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Environment: {os.environ}")

# Initialize boto session and region
boto_session = Session()
REGION = boto_session.region_name

app = BedrockAgentCoreApp()


class AgentMemoryHooks(HookProvider):
    """Memory hooks for agent runtime"""

    def __init__(
        self, memory_id: str, client: MemoryClient, actor_id: str, session_id: str
    ):
        self.memory_id = memory_id
        self.client = client
        self.actor_id = actor_id
        self.session_id = session_id
        self.namespaces = {}
        
        # Get memory strategies and build namespace mapping
        try:
            strategies = self.client.get_memory_strategies(self.memory_id)
            self.namespaces = {
                strategy["type"]: strategy["namespaces"][0]
                for strategy in strategies
            }
        except Exception as e:
            logger.warning(f"Could not retrieve memory strategies: {e}")

    def retrieve_context(self, event: MessageAddedEvent):
        """Retrieve context before processing user query"""
        messages = event.agent.messages
        if (
            messages[-1]["role"] == "user"
            and "toolResult" not in messages[-1]["content"][0]
        ):
            user_query = messages[-1]["content"][0]["text"]

            try:
                all_context = []

                for context_type, namespace in self.namespaces.items():
                    # Retrieve memories from each namespace
                    memories = self.client.retrieve_memories(
                        memory_id=self.memory_id,
                        namespace=namespace.format(actorId=self.actor_id),
                        query=user_query,
                        top_k=3,
                    )
                    # Format memories into context strings
                    for memory in memories:
                        if isinstance(memory, dict):
                            content = memory.get("content", {})
                            if isinstance(content, dict):
                                text = content.get("text", "").strip()
                                if text:
                                    all_context.append(
                                        f"[{context_type.upper()}] {text}"
                                    )

                # Inject context into the query
                if all_context:
                    context_text = "\n".join(all_context)
                    original_text = messages[-1]["content"][0]["text"]
                    messages[-1]["content"][0][
                        "text"
                    ] = f"Context:\n{context_text}\n\n{original_text}"
                    logger.info(f"Retrieved {len(all_context)} context items")

            except Exception as e:
                logger.error(f"Failed to retrieve context: {e}")

    def save_interaction(self, event: AfterInvocationEvent):
        """Save interaction after agent response"""
        try:
            messages = event.agent.messages
            if len(messages) >= 2 and messages[-1]["role"] == "assistant":
                # Get last user query and agent response
                user_query = None
                agent_response = None

                for msg in reversed(messages):
                    if msg["role"] == "assistant" and not agent_response:
                        agent_response = msg["content"][0]["text"]
                    elif (
                        msg["role"] == "user"
                        and not user_query
                        and "toolResult" not in msg["content"][0]
                    ):
                        user_query = msg["content"][0]["text"]
                        break

                if user_query and agent_response:
                    # Save the interaction
                    self.client.create_event(
                        memory_id=self.memory_id,
                        actor_id=self.actor_id,
                        session_id=self.session_id,
                        messages=[
                            (user_query, "USER"),
                            (agent_response, "ASSISTANT"),
                        ],
                    )
                    logger.info("Saved interaction to memory")

        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register memory hooks"""
        registry.add_callback(MessageAddedEvent, self.retrieve_context)
        registry.add_callback(AfterInvocationEvent, self.save_interaction)
        logger.info("Memory hooks registered")


# Initialize memory resources from environment
memory_id = os.environ.get('AGENTCORE_MEMORY_ID')
memory_client = None

if memory_id:
    try:
        memory_client = MemoryClient(region_name=REGION)
        # Verify the memory resource exists
        memory_client.gmcp_client.get_memory(memoryId=memory_id)
        logger.info(f"Using memory resource: {memory_id}")
    except Exception as e:
        logger.error(f"Failed to initialize memory client with ID {memory_id}: {e}")
        memory_id = None
        memory_client = None
else:
    logger.warning("No AGENTCORE_MEMORY_ID environment variable set, running without memory")

# Create base agent
agent = Agent()


class HandlerRequest(BaseModel):
    prompt: str

class HandlerResponse(BaseModel):
    statusCode: int
    result: str

@app.entrypoint
def handler(evt) -> HandlerResponse:
    logger.info(f"handler received request {evt}, type {type(evt)}")
    request = evt
    if isinstance(request, dict):
        # not sure why it was coming in as a dict...
        logger.info(f"Converting request to HandlerRequest")
        request = HandlerRequest(prompt=request['prompt'])
        logger.info(f"Type is now {type(request)}")
    logger.info(f"Handler got request {request}")
    
    # Generate session and actor IDs for this request
    session_id = uuid4().hex
    actor_id = getattr(request, 'actor_id', 'default_user')  # Use actor_id from request or default
    
    # Create agent with memory hooks for this request
    current_agent = agent
    if memory_id and memory_client:
        try:
            # Create memory hooks for this specific request
            memory_hooks = AgentMemoryHooks(
                memory_id=memory_id,
                client=memory_client,
                actor_id=actor_id,
                session_id=session_id
            )
            
            # Create agent with memory hooks
            current_agent = Agent(hooks=[memory_hooks])
            logger.info(f"Created agent with memory hooks for actor: {actor_id}, session: {session_id}")
        except Exception as e:
            logger.error(f"Failed to create memory hooks, using agent without memory: {e}")
            current_agent = agent
    
    result = current_agent(request.prompt, session_id=session_id)
    logger.info(f"returning result {result}, type {type(result)}, str {str(result)}, dict {result.__dict__}")
    response_text = result.message['content'][0]['text']
    return HandlerResponse(
        statusCode=200,
        result=response_text
    ).__dict__

if __name__ == "__main__":
    logger.info('starting app')
    app.run()
    logger.info('exiting')
