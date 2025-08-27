import sys
import boto3


if not len(sys.argv) > 1:
    sys.exit("\nERROR: Must provide agent id prefix for deletions\n")

delete_prefix = sys.argv[1]

ac_control_client = boto3.client('bedrock-agentcore-control', region_name='us-west-2')

next_token = None

while True:
    args = {
        "maxResults": 100
    }
    if next_token:
        args['nextToken'] = next_token
    
    response = ac_control_client.list_agent_runtimes(**args)
    
    for runtime in response['agentRuntimes']:
        if runtime['agent_runtime_name'].startswith(delete_prefix):
            print(f"Deleting runtime {runtime['agent_runtime_id']}")
            ac_control_client.delete_agent_runtime(
                agentRuntimeId=runtime['agentRuntimeId']
            )

    if 'nextToken' in response:
        next_token = response['nextToken']
    else:
        break

