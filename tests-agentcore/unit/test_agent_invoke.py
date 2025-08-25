import requests
import boto3
import urllib.parse
import json
import os
from uuid import uuid4

# Configuration Constants
REGION_NAME = "us-west-2"
ac_client = boto3.client('bedrock-agentcore', region_name=REGION_NAME)

# === Agent Invocation Demo ===
invoke_agent_arn = "arn:aws:bedrock-agentcore:us-west-2:165361166149:runtime/entrypoint-6jqVTrA50d"
agent_runtime_id = invoke_agent_arn.split('/')[-1]

# Try to get auth token from environment, fallback to generating fresh token
auth_token = os.getenv('TOKEN')
# if not auth_token:
#     try:
#         print("No TOKEN environment variable found, generating fresh JWT token...")
#         auth_token = JWTTestUtils.generate_fresh_jwt_token()
#         print("Successfully generated fresh JWT token for testing")
#     except Exception as e:
#         print(f"Failed to generate fresh JWT token: {e}")
#         raise Exception("No authentication token available - set TOKEN environment variable or provide Cognito credentials")
print(f"Using Agent ARN from environment: {invoke_agent_arn}")

# URL encode the agent ARN
escaped_agent_arn = urllib.parse.quote(invoke_agent_arn, safe='')
print(f"Got escaped agent arn {escaped_agent_arn}", flush=True)
# Construct the URL
url = f"https://bedrock-agentcore.{REGION_NAME}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"
# url = "http://127.0.0.1:8080/invocations"
print(f"Using url: {url}")

session_id = "session-" + uuid4().hex
print(f"\n\ninvoking with session ID {session_id}\n\n")

# Set up headers
headers = {
    "Authorization": f"Bearer {auth_token}",
    # "X-Amzn-Trace-Id": "your-trace-id", 
    "Content-Type": "application/json",
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    # "X-Amzn-Bedrock-AgentCore-Runtime-User-Id": "user-" + uuid4().hex
}
print(f"Got headers for call: {headers}")
print(f"Invoking {url}")

data = {
    "prompt": "What is your name? \n" 
}

print(f'sending data {data}')
invoke_response = requests.post(
    url,
    headers=headers,
    data=json.dumps(data)
)
print(f"Got response: {invoke_response}")
# Print response in a safe manner
# print(f"Status Code: {invoke_response.status_code}")
# print(f"Response Headers: {dict(invoke_response.headers)}")

# Handle response based on status code
if invoke_response.status_code == 200:
    answer = invoke_response.json()
    print(f"got response json {answer}")
    print(f"answer: {answer}")
    
elif invoke_response.status_code >= 400:
    print(f"Error Response ({invoke_response.status_code}):")
    error_data = invoke_response.json()
    print(json.dumps(error_data, indent=2))
    
else:
    print(f"Unexpected status code: {invoke_response.status_code}")
    print("Response text:")
    print(invoke_response.text[:500])
