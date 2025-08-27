import os
import logging
from pydantic import BaseModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.session.s3_session_manager import S3SessionManager

from uuid import uuid4

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Environment: {os.environ}")

app = BedrockAgentCoreApp()
agent = Agent()


class HandlerRequest(BaseModel):
    prompt: str

class HandlerResponse(BaseModel):
    statusCode: int
    result: str

@app.entrypoint
def handler(evt) -> HandlerResponse:
    # Create a session manager that stores data in S3
    logger.info(f"handler received request {evt}, type {type(evt)}")
    request = evt
    if isinstance(request, dict):
        # not sure why it was coming in as a dict...
        logger.info(f"Converting request to HandlerRequest")
        request = HandlerRequest(prompt=request['prompt'])
        logger.info(f"Type is now {type(request)}")
    logger.info(f"Handler got request {request}")
    result = agent(request.prompt, session_id=uuid4().hex)
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
