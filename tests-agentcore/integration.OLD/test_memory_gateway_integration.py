"""
Integration tests for Memory Gateway service.

This module tests the Memory Gateway service by:
1. Starting the service using subprocess
2. Making HTTP requests to verify endpoints
3. Testing memory operations and session context management
"""

import json
import multiprocessing
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any
from uuid import uuid4
import boto3
import hmac
import hashlib
import base64

import pytest
import requests
from dotenv import load_dotenv

# Load environment variables from the .env file
def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_path = Path(__file__).parent.parent / ".env"
    print(f"loading env_path: {env_path}")
    
    if env_path.exists():
        load_dotenv(env_path)

# Load .env file at module import time
load_env_file()

# Test configuration
MEMORY_GATEWAY_PORT = 8004
MEMORY_GATEWAY_URL = f"http://localhost:{MEMORY_GATEWAY_PORT}"
SERVICE_STARTUP_TIMEOUT = 30  # seconds
REQUEST_TIMEOUT = 10  # seconds


def calculate_secret_hash(username, client_id, client_secret):
    """Calculate the SECRET_HASH for Cognito authentication"""
    message = bytes(username + client_id, 'utf-8')
    key = bytes(client_secret, 'utf-8')
    secret_hash = base64.b64encode(hmac.new(key, message, digestmod=hashlib.sha256).digest()).decode()
    return secret_hash


def get_jwt_token():
    """Get JWT token from Cognito for authentication"""
    try:
        # Get Cognito credentials from environment
        client_id = os.getenv("COGNITO_USER_CLIENT_ID") or os.getenv("USER_POOL_CLIENT_ID")
        username = os.getenv("COGNITO_USERNAME")
        password = os.getenv("COGNITO_PASSWORD")
        client_secret = os.getenv("COGNITO_CLIENT_SECRET")
        region = os.getenv("REGION", "us-west-2")
        
        if not all([client_id, username, password]):
            print("Warning: Missing Cognito credentials, requests will fail with 401")
            return None
        
        # Create Cognito client
        client = boto3.client('cognito-idp', region_name=region)
        
        # Prepare authentication parameters
        auth_parameters = {
            'USERNAME': username,
            'PASSWORD': password
        }
        
        # Add SECRET_HASH if client secret is provided
        if client_secret:
            secret_hash = calculate_secret_hash(username, client_id, client_secret)
            auth_parameters['SECRET_HASH'] = secret_hash
        
        # Authenticate with Cognito
        response = client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters=auth_parameters
        )
        
        # Extract and return the token
        token = response['AuthenticationResult']['AccessToken']
        return token
        
    except Exception as e:
        print(f"Error getting JWT token: {str(e)}")
        return None


def get_auth_headers():
    """Get authentication headers with JWT token"""
    token = get_jwt_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    else:
        return {}


def stream_output(stream, prefix):
    """Stream output from subprocess to stdout with prefix."""
    try:
        for line in iter(stream.readline, ''):
            if line:
                print(f"{prefix}: {line.rstrip()}", flush=True)
    except Exception as e:
        print(f"Error streaming {prefix}: {e}")
    finally:
        stream.close()


def run_server_command():
    """Run the server command in subprocess."""
    try:
        # Change to the sample-agentic-platform directory and run make memory-gateway
        base_dir = Path(__file__).parent.parent.parent
        print(f"Starting Memory Gateway server from {base_dir}")
        
        # Start the process in a new process group so we can kill the entire group
        process = subprocess.Popen(
            ["make", "memory-gateway"],
            cwd=base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            preexec_fn=os.setsid  # Create new process group
        )
        
        # Start threads to stream stdout and stderr
        stdout_thread = threading.Thread(
            target=stream_output, 
            args=(process.stdout, "MEMORY-OUT"),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=stream_output, 
            args=(process.stderr, "MEMORY-ERR"),
            daemon=True
        )
        
        stdout_thread.start()
        stderr_thread.start()
        
        # Store threads on the process for cleanup
        process.output_threads = (stdout_thread, stderr_thread)
        
        return process
    except Exception as e:
        print(f"Error running server command: {e}")
        return None


def kill_processes_on_port(port):
    """Kill any processes listening on the specified port."""
    try:
        # Find processes listening on the port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True
        )
        output = result.stdout.strip()
        if result.returncode == 0 and output:
            print(f'Output from lsof: {output}')
            pids = output.split('\n')
            for pid in pids:
                if pid:
                    try:
                        print(f"Killing process {pid} listening on port {port}")
                        os.kill(int(pid), signal.SIGTERM)
                        time.sleep(1)
                        # Force kill if still running
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass  # Process already dead
                    except (ValueError, ProcessLookupError) as e:
                        print(f"Failed to kill process {pid}: {e}")
        else:
            print(f"No processes found listening on port {port}")
    except FileNotFoundError:
        # lsof not available, try alternative approach
        print("lsof not available, trying alternative cleanup...")
        kill_processes_on_port_alternative(port)
    except Exception as e:
        print(f"Error killing processes on port {port}: {e}")


def kill_processes_on_port_alternative(port):
    """Alternative method to kill processes on port using netstat."""
    try:
        # Use netstat to find processes
        result = subprocess.run(
            ["netstat", "-tulpn"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if f":{port}" in line and "LISTEN" in line:
                    # Extract PID from netstat output
                    parts = line.split()
                    for part in parts:
                        if "/" in part:
                            try:
                                pid = int(part.split("/")[0])
                                print(f"Killing process {pid} listening on port {port}")
                                os.kill(pid, signal.SIGTERM)
                                time.sleep(1)
                                try:
                                    os.kill(pid, signal.SIGKILL)
                                except ProcessLookupError:
                                    pass
                            except (ValueError, ProcessLookupError):
                                pass
    except Exception as e:
        print(f"Alternative port cleanup failed: {e}")


def wait_for_server_ready(timeout: int = SERVICE_STARTUP_TIMEOUT) -> bool:
    """Wait for the server to be ready to accept requests."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{MEMORY_GATEWAY_URL}/health", timeout=2)
            if response.status_code == 200:
                print("Memory Gateway server is ready")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    
    print(f"Server failed to become ready within {timeout} seconds")
    return False


def concurrent_worker_process(worker_id: int, results):
    """Worker function for concurrent requests."""
    success_count = 0
    for i in range(5):  # Make 5 requests per worker
        try:
            response = requests.get(f"{MEMORY_GATEWAY_URL}/health", timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                success_count += 1
        except Exception:
            pass
        time.sleep(0.1)  # Small delay between requests
    results.append((worker_id, success_count))


def make_get_session_request(user_id: str):
    """Helper function to make a get session context request."""
    try:
        payload = {
            "user_id": user_id,
            "max_results": 5
        }
        headers = get_auth_headers()
        response = requests.post(
            f"{MEMORY_GATEWAY_URL}/get-session-context",
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        return response.status_code in [200, 404]
    except Exception:
        return False


def concurrent_session_worker_process(worker_id: int, results):
    """Worker function for concurrent session requests."""
    success_count = 0
    user_id = f"concurrent-test-user-{worker_id}"
    
    for i in range(3):  # Make 3 requests per worker
        if make_get_session_request(user_id):
            success_count += 1
        time.sleep(0.2)  # Small delay between requests
    results.append((worker_id, success_count))


@pytest.fixture(scope="session")
def env_setup():
    """Session-scoped fixture to set up environment variables for tests and restore them after."""
    # Environment is already loaded by load_env_file() at module level
    yield
    # No cleanup needed as we're not modifying environment variables


@pytest.fixture(scope="session")
def memory_gateway_server(env_setup):
    """Session-scoped fixture to start and manage the Memory Gateway server process."""
    print("Starting Memory Gateway server...")
    
    # Kill any existing processes on the port first
    kill_processes_on_port(MEMORY_GATEWAY_PORT)
    
    # Start server process
    server_process = None
    try:
        server_process = run_server_command()
        if not server_process:
            pytest.fail("Failed to start Memory Gateway server process")
        
        print(f"Started Memory Gateway server with PID: {server_process.pid}")
        
        # Wait for server to be ready
        if not wait_for_server_ready():
            if server_process and server_process.poll() is None:
                # Kill the process group
                try:
                    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
                    time.sleep(2)
                    os.killpg(os.getpgid(server_process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            pytest.fail("Failed to start Memory Gateway server")
        
        yield server_process
        
    finally:
        # Cleanup server process
        print("Stopping Memory Gateway server...")
        
        # First kill any processes listening on the port
        kill_processes_on_port(MEMORY_GATEWAY_PORT)
        
        # Then terminate the server process
        if server_process and server_process.poll() is None:
            try:
                # Kill the process group
                os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
                time.sleep(2)
                # Force kill if still running
                try:
                    os.killpg(os.getpgid(server_process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Process already dead
            except (ProcessLookupError, OSError) as e:
                print(f"Process group cleanup failed: {e}")
        
        # Double-check that port is free
        kill_processes_on_port(MEMORY_GATEWAY_PORT)
        print("Memory Gateway server stopped")


def test_health_endpoint(memory_gateway_server):
    """Test the health endpoint."""
    print(f"test_health_endpoint got memory_gateway_server {memory_gateway_server}")
    response = requests.get(f"{MEMORY_GATEWAY_URL}/health", timeout=REQUEST_TIMEOUT)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_upsert_session_context(memory_gateway_server):
    """Test upserting a session context."""
    session_id = str(uuid4())
    user_id = "test-user-" + str(uuid4())[:8]
    
    session_context = {
        "session_id": session_id,
        "user_id": user_id,
        "agent_id": "test-agent-123",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Hello, this is a test message"
                    }
                ],
                "tool_calls": [],
                "tool_results": [],
                "timestamp": time.time()
            }
        ],
        "system_prompt": "You are a helpful assistant.",
        "session_metadata": {
            "test_metadata": "test_value"
        }
    }
    
    payload = {
        "session_context": session_context
    }
    
    headers = get_auth_headers()
    response = requests.post(
        f"{MEMORY_GATEWAY_URL}/upsert-session-context",
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    print(f"response from POST /upsert-session-context")
    # Server errors (5xx) should fail the test - they indicate bugs in our code
    if response.status_code >= 500:
        pytest.fail(f"Server error {response.status_code}: {response.text}")
    
    # Should return 200 or appropriate status code
    assert response.status_code in [200, 201, 400, 401, 403, 422], f"Unexpected status code {response.status_code}: {response.text}"
    
    if response.status_code in [200, 201]:
        data = response.json()
        assert "session_context" in data
        assert data["session_context"]["session_id"] == session_id

def test_create_memory(memory_gateway_server):
    """Test creating a memory."""
    session_id = str(uuid4())
    user_id = "test-user-" + str(uuid4())[:8]
    agent_id = "test-agent-" + str(uuid4())[:8]    
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "agent_id": agent_id,
        "content": 'This is a memory creation test',
        'embedding_model': 'N/A'
    }
    
    headers = get_auth_headers()
    response = requests.post(
        f"{MEMORY_GATEWAY_URL}/create-memory",
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    # Server errors (5xx) should fail the test - they indicate bugs in our code
    if response.status_code >= 500:
        pytest.fail(f"Server error {response}")
    
    # Should return 200 or appropriate status code
    assert response.status_code in [200, 201, 400, 401, 403, 422], f"Unexpected status code {response.status_code}: {response.text}"
    
    if response.status_code in [200, 201]:
        data = response.json()
        assert "memory" in data
        memory = data["memory"]
        assert memory["session_id"] == session_id
        assert memory["user_id"] == user_id
        assert memory["agent_id"] == agent_id

def test_create_update_delete_agentcore_memory_provider(memory_gateway_server):
    """Test creating an AgentCore memory provider."""
    # Skip if MEMORY_CLIENT is not set to AGENTCORE
    memory_client = os.getenv("MEMORY_CLIENT", "").upper()
    if memory_client != "AGENTCORE":
        pytest.skip("MEMORY_CLIENT must be set to AGENTCORE for this test")
    
    payload = {
        "environment": f"test-environment-{uuid4().hex[-4:]}",
        "retention_days": 30
    }
    
    headers = get_auth_headers()
    response = requests.post(
        f"{MEMORY_GATEWAY_URL}/create-agentcore-memory-provider",
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    result = response.json()
    print(f"Got create result {result}")
    assert result['memory_id'] is not None
    status = result['status']
    updated_result = None
    if status == 'CREATING':
        print(f"Waiting for memory to finish creating. It takes about 3.5 minutes.")
        while status == 'CREATING':
            response = requests.get(
                f"{MEMORY_GATEWAY_URL}/get-memory-provider/?memory_id={result['memory_id']}",
                headers=headers
            )
            updated_result = response.json()
            print(f"Got agentcore memory {updated_result}")
            status = updated_result['status']
            if status == 'CREATING': 
                print(f"Waiting 30 seconds...status is still CREATING")
                time.sleep(30)

    print(f"Create result: {updated_result}")

    """Test updating an AgentCore memory provider.""" 
    memory_id = result['memory_id']
    updated_description = "Updated test memory provider"
    payload = {
        "memory_id": memory_id,
        "description": updated_description,
        "event_expiry_duration": 7 # in days
    }
    
    headers = get_auth_headers()
    print(f"Calling /update-memory-provider with payload {payload}")
    response = requests.post(
        f"{MEMORY_GATEWAY_URL}/update-memory-provider",
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    result = response.json()
    print(f"Got response from update: {result}")
    assert result['description'] == updated_description
   
    """Test deleting an AgentCore memory provider."""    
    payload = {
        "memory_id": result['memory_id']
    }
    
    headers = get_auth_headers()
    print(f"Calling delete memo")
    response = requests.delete(
        f"{MEMORY_GATEWAY_URL}/delete-memory-provider",
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    result = response.json()
    print(f"Got delete response {result}")
    # assert response.status_code == 200
    assert result['memory_id'] == memory_id


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
