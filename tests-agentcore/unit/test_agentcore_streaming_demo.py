#!/usr/bin/env python3
"""
Demonstration script for AgentCore runtime streaming functionality.

This script shows how to use the JWT AgentCore client to invoke deployed
runtimes with streaming responses and parse the multi-agent interactions.

Usage:
    python test_agentcore_streaming_demo.py
    python test_agentcore_streaming_demo.py --runtime-arn <your-runtime-arn>
"""

import argparse
import json
import logging
import os
import sys
import time
from uuid import uuid4

# Add the tests directory to the path for imports
tests_dir = os.path.join(os.path.dirname(__file__), "tests-agentcore")
sys.path.append(tests_dir)
from utils.jwt_agentcore_client import JWTAgentCoreClient
from utils.stream_parser import parse_streaming_response, StreamEventType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def demo_non_streaming_invocation(client: JWTAgentCoreClient, runtime_arn: str):
    """Demonstrate non-streaming invocation."""
    print("\n" + "="*60)
    print("NON-STREAMING INVOCATION DEMO")
    print("="*60)
    
    session_id = f"demo-non-streaming-{uuid4().hex[:8]}"
    
    test_payload = {
        "prompt": "Explain the difference between machine learning and artificial intelligence in simple terms.",
        "session_id": session_id
    }
    
    print(f"Session ID: {session_id}")
    print(f"Request: {json.dumps(test_payload, indent=2)}")
    print(f"Runtime ARN: {runtime_arn}")
    
    try:
        print("\n⏳ Sending request...")
        start_time = time.time()
        
        response = client.invoke_runtime(
            agent_runtime_arn=runtime_arn,
            payload=test_payload,
            stream=False,
            session_id=session_id,
            timeout=30
        )
        
        end_time = time.time()
        
        print(f"✅ Response received in {end_time - start_time:.2f} seconds")
        print(f"\nResponse structure: {list(response.keys()) if isinstance(response, dict) else type(response)}")
        
        # Extract and display content
        if isinstance(response, dict):
            if "result" in response:
                print(f"\n📄 Result:\n{response['result']}")
            elif "response" in response:
                print(f"\n📄 Response:\n{response['response']}")
            else:
                print(f"\n📄 Full Response:\n{json.dumps(response, indent=2)}")
        else:
            print(f"\n📄 Response:\n{response}")
            
    except Exception as e:
        print(f"❌ Non-streaming invocation failed: {e}")

def demo_streaming_invocation(client: JWTAgentCoreClient, runtime_arn: str):
    """Demonstrate streaming invocation with real-time event display."""
    print("\n" + "="*60)
    print("STREAMING INVOCATION DEMO")
    print("="*60)
    
    session_id = f"demo-streaming-{uuid4().hex[:8]}"
    
    test_payload = {
        "prompt": "Can you help me write a Python function to sort a list of dictionaries by multiple keys, and also explain how the sorting algorithm works?",
        "session_id": session_id
    }
    
    print(f"Session ID: {session_id}")
    print(f"Request: {json.dumps(test_payload, indent=2)}")
    print(f"Runtime ARN: {runtime_arn}")
    
    try:
        print("\n🔄 Starting streaming invocation...")
        
        streaming_response = client.invoke_runtime(
            agent_runtime_arn=runtime_arn,
            payload=test_payload,
            stream=True,
            session_id=session_id,
            timeout=60
        )
        
        print(f"✅ Streaming completed with {streaming_response.get('total_events', 0)} events")
        
        # Parse the streaming events
        parser = parse_streaming_response(streaming_response)
        
        print(f"\n📊 Event Analysis:")
        print(f"Total events parsed: {len(parser.events)}")
        
        # Show event breakdown
        event_counts = {}
        for event in parser.events:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        for event_type, count in event_counts.items():
            print(f"  {event_type}: {count}")
        
        # Show agent interactions
        agent_interactions = parser.extract_multi_agent_interactions(session_id)
        if agent_interactions:
            print(f"\n🤖 Multi-Agent Interactions:")
            for agent_name, interactions in agent_interactions.items():
                print(f"\n  Agent: {agent_name}")
                for i, interaction in enumerate(interactions[:3], 1):  # Show first 3 interactions
                    interaction_preview = interaction[:100] + "..." if len(interaction) > 100 else interaction
                    print(f"    {i}. {interaction_preview}")
                if len(interactions) > 3:
                    print(f"    ... and {len(interactions) - 3} more interactions")
        
        # Show conversation flow
        conversation_flow = parser.get_conversation_flow(session_id)
        if conversation_flow:
            print(f"\n💬 Conversation Flow:")
            for i, (event_type, content) in enumerate(conversation_flow[:5], 1):  # Show first 5
                content_preview = content[:80] + "..." if len(content) > 80 else content
                print(f"  {i}. [{event_type}] {content_preview}")
            if len(conversation_flow) > 5:
                print(f"  ... and {len(conversation_flow) - 5} more events")
        
        # Print detailed summary
        parser.print_streaming_summary(session_id)
        
    except Exception as e:
        print(f"❌ Streaming invocation failed: {e}")

def demo_streaming_generator(client: JWTAgentCoreClient, runtime_arn: str):
    """Demonstrate real-time streaming with generator interface."""
    print("\n" + "="*60)
    print("REAL-TIME STREAMING GENERATOR DEMO")
    print("="*60)
    
    session_id = f"demo-generator-{uuid4().hex[:8]}"
    
    test_payload = {
        "prompt": "Debug this Python code and suggest improvements: def calculate_average(numbers): total = 0; for num in numbers: total += num; return total / len(numbers)",
        "session_id": session_id
    }
    
    print(f"Session ID: {session_id}")
    print(f"Request: {json.dumps(test_payload, indent=2)}")
    print(f"Runtime ARN: {runtime_arn}")
    
    try:
        print("\n🔄 Starting real-time streaming...")
        print("Events will be displayed as they arrive:")
        print("-" * 40)
        
        events_received = []
        
        for event in client.invoke_runtime_streaming_generator(
            agent_runtime_arn=runtime_arn,
            payload=test_payload,
            session_id=session_id,
            timeout=60
        ):
            events_received.append(event)
            
            # Display event in real-time
            event_type = event.get("event", "unknown")
            timestamp = event.get("timestamp", "")
            data = event.get("data", {})
            
            # Color coding for different event types
            if event_type == "input_capture":
                print(f"🔵 [{timestamp}] INPUT: {data.get('prompt', data.get('content', ''))[:60]}...")
            elif event_type == "thought_capture":
                agent = data.get('agent', 'unknown')
                thinking = data.get('thinking', data.get('content', ''))
                print(f"🧠 [{timestamp}] THOUGHT ({agent}): {thinking[:60]}...")
            elif event_type == "tool_execution":
                tool_info = data.get('tool_info', data.get('content', ''))
                print(f"🔧 [{timestamp}] TOOL: {tool_info[:60]}...")
            elif event_type == "agent_switch":
                decision = data.get('decision', data.get('content', ''))
                print(f"🔄 [{timestamp}] SWITCH: {decision[:60]}...")
            elif event_type == "output_capture":
                content = data.get('content', '')
                print(f"📤 [{timestamp}] OUTPUT: {content[:60]}...")
            elif event_type == "done":
                print(f"✅ [{timestamp}] DONE: {data.get('message', 'Completed')}")
            elif event_type == "error":
                error = data.get('error', '')
                print(f"❌ [{timestamp}] ERROR: {error[:60]}...")
            else:
                print(f"❓ [{timestamp}] {event_type.upper()}: {str(data)[:60]}...")
        
        print("-" * 40)
        print(f"✅ Real-time streaming completed with {len(events_received)} events")
        
    except Exception as e:
        print(f"❌ Real-time streaming failed: {e}")

def demo_connectivity_test(client: JWTAgentCoreClient, runtime_arn: str):
    """Demonstrate runtime connectivity testing."""
    print("\n" + "="*60)
    print("CONNECTIVITY TEST DEMO")
    print("="*60)
    
    print(f"Testing connectivity to runtime: {runtime_arn}")
    
    connectivity_result = client.test_runtime_connectivity(runtime_arn)
    
    print(f"\nConnectivity Result:")
    print(json.dumps(connectivity_result, indent=2))
    
    if connectivity_result.get("connectivity") == "success":
        print(f"\n✅ Runtime is accessible and responsive")
        print(f"Response time: {connectivity_result.get('response_time_ms', 0)}ms")
    else:
        print(f"\n❌ Runtime connectivity failed: {connectivity_result.get('error', 'Unknown error')}")

def get_runtime_arn_from_user():
    """Get runtime ARN from user input or environment."""
    import os
    
    # Check environment variable first
    runtime_arn = os.getenv('AGENTCORE_RUNTIME_ARN')
    if runtime_arn:
        print(f"Using runtime ARN from environment: {runtime_arn}")
        return runtime_arn
    
    # Get from user input
    print("\nNo runtime ARN provided. Please enter the ARN of your deployed AgentCore runtime:")
    print("(Format: arn:aws:bedrock-agentcore:region:account:runtime/runtime-name)")
    runtime_arn = input("Runtime ARN: ").strip()
    
    if not runtime_arn or not runtime_arn.startswith("arn:aws:bedrock-agentcore:"):
        print("❌ Invalid runtime ARN format")
        sys.exit(1)
    
    return runtime_arn

def main():
    """Main demonstration function."""
    parser = argparse.ArgumentParser(description="AgentCore Streaming Demo")
    parser.add_argument(
        "--runtime-arn",
        help="ARN of the AgentCore runtime to test"
    )
    parser.add_argument(
        "--demo",
        choices=["all", "connectivity", "non-streaming", "streaming", "generator"],
        default="all",
        help="Which demo to run"
    )
    
    args = parser.parse_args()
    
    print("🚀 AgentCore Runtime Streaming Demo")
    print("="*60)
    
    # Get runtime ARN
    runtime_arn = args.runtime_arn
    if not runtime_arn:
        runtime_arn = get_runtime_arn_from_user()
    
    # Initialize JWT client
    try:
        print(f"\n🔐 Initializing JWT AgentCore client...")
        client = JWTAgentCoreClient()
        
        # Test token generation
        token = client._get_jwt_token()
        print(f"✅ JWT token generated successfully (length: {len(token)})")
        
    except Exception as e:
        print(f"❌ Failed to initialize JWT client: {e}")
        sys.exit(1)
    
    # Run demos based on selection
    try:
        if args.demo in ["all", "connectivity"]:
            demo_connectivity_test(client, runtime_arn)
        
        if args.demo in ["all", "non-streaming"]:
            demo_non_streaming_invocation(client, runtime_arn)
        
        if args.demo in ["all", "streaming"]:
            demo_streaming_invocation(client, runtime_arn)
        
        if args.demo in ["all", "generator"]:
            demo_streaming_generator(client, runtime_arn)
        
        print(f"\n🎉 Demo completed successfully!")
        print(f"\nTo run specific demos:")
        print(f"  python {sys.argv[0]} --demo connectivity --runtime-arn {runtime_arn}")
        print(f"  python {sys.argv[0]} --demo streaming --runtime-arn {runtime_arn}")
        print(f"  python {sys.argv[0]} --demo generator --runtime-arn {runtime_arn}")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
