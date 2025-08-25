import os
from pydantic import BaseModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.session.s3_session_manager import S3SessionManager

from uuid import uuid4

print(f"Environment: {os.environ}")

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
    print(f"handler received request {evt}, type {type(evt)}")
    request = evt
    if isinstance(request, dict):
        # not sure why it was coming in as a dict...
        print(f"Converting request to HandlerRequest")
        request = HandlerRequest(prompt=request['prompt'])
        print(f"Type is now {type(request)}")
    print(f"Handler got request {request}")
    result = agent(request.prompt, session_id=uuid4().hex)
    print(f"returning result {result}, type {type(result)}, str {str(result)}, dict {result.__dict__}")
    response_text = result.message['content'][0]['text']
    return HandlerResponse(
        statusCode=200,
        result=response_text
    ).__dict__

if __name__ == "__main__":
    print('starting app')
    app.run()
    print('exiting')
