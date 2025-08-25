"""
Integration tests for AgentCore Runtime service.

This module tests the AgentCore Runtime service by:
1. Starting the service using multiprocessing
2. Making HTTP requests to verify endpoints
3. Testing CRUD operations for AgentCore Runtimes
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
AGENTCORE_RUNTIME_PORT = 8003
AGENTCORE_RUNTIME_URL = f"http://localhost:{AGENTCORE_RUNTIME_PORT}"
SERVICE_STARTUP_TIMEOUT = 30  # seconds
REQUEST_TIMEOUT = 10  # seconds


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
        # Change to the sample-agentic-platform directory and run make agentcore-runtime
        base_dir = Path(__file__).parent.parent.parent
        print(f"Starting AgentCore Runtime server from {base_dir}")
        
        # Start the process in a new process group so we can kill the entire group
        process = subprocess.Popen(
            ["make", "agentcore-runtime-controller"],
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
            args=(process.stdout, "SERVER-OUT"),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=stream_output, 
            args=(process.stderr, "SERVER-ERR"),
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
            response = requests.get(f"{AGENTCORE_RUNTIME_URL}/ping", timeout=2)
            if response.status_code == 200:
                print("AgentCore Runtime server is ready")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    
    print(f"Server failed to become ready within {timeout} seconds")
    return False


def wait_for_runtime_ready(runtime_id: str, timeout: int = 300) -> bool:
    """Wait for an AgentCore Runtime to be in READY status."""
    print(f"Waiting for runtime {runtime_id} to be READY...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            payload = {"agentRuntimeId": runtime_id}
            response = requests.get(
                f"{AGENTCORE_RUNTIME_URL}/get-agentcore-runtime",
                params=payload,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "UNKNOWN")
                print(f"Runtime {runtime_id} status: {status}")
                
                if status == "READY":
                    print(f"status READY...returning from wait_for_runtime_ready with True")
                    return True
                
                elif status in ["FAILED", "DELETING", "DELETED"]:
                    print(f"Runtime {runtime_id} is in terminal state: {status}")
                    return False
                    
            elif response.status_code == 404:
                print(f"Runtime {runtime_id} not found (may have been deleted)")
                return False
                
        except Exception as e:
            print(f"Error checking runtime status: {e}")
        
        time.sleep(5)  # Check every 5 seconds
    
    print(f"Timeout waiting for runtime {runtime_id} to be READY")
    return False


def concurrent_worker_process(worker_id: int, results):
    """Worker function for concurrent requests."""
    success_count = 0
    for i in range(5):  # Make 5 requests per worker
        try:
            response = requests.get(f"{AGENTCORE_RUNTIME_URL}/ping", timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                success_count += 1
        except Exception:
            pass
        time.sleep(0.1)  # Small delay between requests
    results.append((worker_id, success_count))


@pytest.fixture(scope="session")
def env_setup():
    """Session-scoped fixture to set up environment variables for tests and restore them after."""
    # Environment is already loaded by load_env_file() at module level
    yield
    # No cleanup needed as we're not modifying environment variables


@pytest.fixture(scope="session")
def agentcore_runtime_server(env_setup):
    """Session-scoped fixture to start and manage the AgentCore Runtime server process."""
    print("Starting AgentCore Runtime server...")
    
    # Kill any existing processes on the port first
    kill_processes_on_port(AGENTCORE_RUNTIME_PORT)
    
    # Start server process
    server_process = None
    try:
        server_process = run_server_command()
        if not server_process:
            pytest.fail("Failed to start AgentCore Runtime server process")
        
        print(f"Started AgentCore Runtime server with PID: {server_process.pid}")
        
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
            pytest.fail("Failed to start AgentCore Runtime server")
        
        yield server_process
        
    finally:
        # Cleanup server process
        print("Stopping AgentCore Runtime server...")
        
        # First kill any processes listening on the port
        kill_processes_on_port(AGENTCORE_RUNTIME_PORT)
        
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
        kill_processes_on_port(AGENTCORE_RUNTIME_PORT)
        print("Server stopped")


@pytest.fixture
def cleanup_additional_runtimes():
    """Fixture to clean up any additional runtime resources created during specific tests."""
    created_runtime_ids = []
    
    def track_runtime_id(runtime_id):
        created_runtime_ids.append(runtime_id)
    
    yield track_runtime_id
    
    # Cleanup additional runtimes created during tests
    for runtime_id in created_runtime_ids:
        try:
            print(f"Cleaning up test runtime: {runtime_id}")
            
            # Wait for runtime to be READY before attempting to delete
            if wait_for_runtime_ready(runtime_id, timeout=120):  # Wait up to 2 minutes
                print(f"Runtime {runtime_id} is READY, proceeding with deletion")
                payload = {"agentRuntimeId": runtime_id}
                response = requests.delete(
                    f"{AGENTCORE_RUNTIME_URL}/delete-agentcore-runtime",
                    json=payload,
                    timeout=REQUEST_TIMEOUT
                )
                if response.status_code in [200, 404]:
                    print(f"Successfully cleaned up test runtime: {runtime_id}")
                else:
                    print(f"Cleanup response for {runtime_id}: {response.status_code} - {response.text}")
            else:
                print(f"Runtime {runtime_id} did not become READY within timeout, skipping cleanup")
        except Exception as e:
            print(f"Failed to cleanup additional runtime {runtime_id}: {str(e)}")


def test_ping_endpoint(agentcore_runtime_server):
    """Test the ping/health endpoint."""
    print(f"test_ping_endpoing got agentcore_runtime_server {agentcore_runtime_server}")
    response = requests.get(f"{AGENTCORE_RUNTIME_URL}/ping", timeout=REQUEST_TIMEOUT)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_list_agentcore_runtimes(agentcore_runtime_server):
    """Test listing AgentCore Runtimes."""
    payload = {
        "maxResults": 10
    }
    response = requests.get(
        f"{AGENTCORE_RUNTIME_URL}/list-agentcore-runtimes",
        params=payload,
        timeout=REQUEST_TIMEOUT
    )
    print(f"list_agent_runtimes got response {response}")
    # Should return 200 even if no runtimes exist
    assert response.status_code == 200


def test_create_agentcore_runtime(agentcore_runtime_server, cleanup_additional_runtimes):
    """Test creating an AgentCore Runtime."""
    # Skip if required environment variables are not set
    container_uri = os.getenv("TEST_CONTAINER_URI")
    role_arn = os.getenv("TEST_ROLE_ARN")
    
    if not container_uri or not role_arn:
        pytest.skip("TEST_CONTAINER_URI and TEST_ROLE_ARN environment variables required")
    
    # Generate unique suffix to prevent duplicate name conflicts
    unique_suffix = uuid4().hex[-6:]
    
    payload = {
        "agentRoleArn": role_arn,
        "agentRuntimeName": f"test_runtime_integration_{unique_suffix}",
        "containerUri": container_uri,
        "description": "Integration test runtime",
        "environmentVariables": {
            "TEST_VAR": "test_value"
        }
    }
    
    response = requests.post(
        f"{AGENTCORE_RUNTIME_URL}/create-agentcore-runtime",
        json=payload,
        timeout=REQUEST_TIMEOUT
    )
    
    # Server errors (5xx) should fail the test - they indicate bugs in our code
    if response.status_code >= 500:
        pytest.fail(f"Server error {response.status_code}: {response.text}")
    
    # For this integration test, we expect either success or client errors due to AWS config
    assert response.status_code in [200, 400, 403], f"Unexpected status code {response.status_code}: {response.text}"
    
    if response.status_code == 200:
        data = response.json()
        assert "agentRuntimeArn" in data or "agentRuntimeId" in data
        
        # Track the runtime for cleanup if created successfully
        if "agentRuntimeId" in data:
            cleanup_additional_runtimes(data["agentRuntimeId"])


def test_get_agentcore_runtime(agentcore_runtime_server):
    """Test getting a specific AgentCore Runtime."""
    runtime_id = os.getenv("RUNTIME_ID")
    
    if not runtime_id:
        pytest.skip("RUNTIME_ID environment variable required")
    
    payload = {
        "agentRuntimeId": runtime_id
    }
    
    response = requests.get(
        f"{AGENTCORE_RUNTIME_URL}/get-agentcore-runtime",
        params=payload,
        timeout=REQUEST_TIMEOUT
    )
    
    # Server errors (5xx) should fail the test - they indicate bugs in our code
    if response.status_code >= 500:
        pytest.fail(f"Server error {response.status_code}: {response.text}")
    
    # For this test, we expect either success, not found, or client errors due to AWS config
    assert response.status_code in [200, 404, 400, 403], f"Unexpected status code {response.status_code}: {response.text}"


def test_update_agentcore_runtime(agentcore_runtime_server):
    """Test updating an AgentCore Runtime."""
    runtime_id = os.getenv("RUNTIME_ID")
    role_arn = os.getenv("TEST_ROLE_ARN")
    
    if not runtime_id or not role_arn:
        pytest.skip("RUNTIME_ID and TEST_ROLE_ARN environment variables required")
    
    payload = {
        "agentRuntimeId": runtime_id,
        "agentRuntimeArtifact": {
            "containerConfiguration": {
                "containerUri": os.getenv("TEST_CONTAINER_URI", "")
            }
        },
        "roleArn": role_arn,
        "networkConfiguration": {
            "subnetIds": ["subnet-123"],
            "securityGroupIds": ["sg-123"]
        },
        "protocolConfiguration": {
            "protocol": "HTTP"
        },
        "authorizerConfiguration": {
            "jwtConfiguration": {
                "issuer": "test-issuer",
                "audience": "test-audience"
            }
        },
        "description": "Updated integration test runtime",
        "environmentVariables": {
            "UPDATED_VAR": "updated_value"
        }
    }
    
    response = requests.put(
        f"{AGENTCORE_RUNTIME_URL}/update-agentcore-runtime",
        json=payload,
        timeout=REQUEST_TIMEOUT
    )
    
    # Server errors (5xx) should fail the test - they indicate bugs in our code
    if response.status_code >= 500:
        pytest.fail(f"Server error {response.status_code}: {response.text}")
    
    # For this test, we expect either success, not found, validation errors, or client errors due to AWS config
    assert response.status_code in [200, 404, 400, 403, 422], f"Unexpected status code {response.status_code}: {response.text}"


# def test_delete_agentcore_runtime(agentcore_runtime_server):
#     """Test deleting an AgentCore Runtime."""
#     runtime_id = os.getenv("TEST_DELETE_RUNTIME_ID")  # Use separate env var for delete test
    
#     if not runtime_id:
#         pytest.skip("TEST_DELETE_RUNTIME_ID environment variable required")
    
#     payload = {
#         "agentRuntimeId": runtime_id
#     }
    
#     response = requests.delete(
#         f"{AGENTCORE_RUNTIME_URL}/delete-agentcore-runtime",
#         json=payload,
#         timeout=REQUEST_TIMEOUT
#     )
    
#     # May return 404 if runtime doesn't exist, or 200 if deleted successfully
#     assert response.status_code in [200, 404, 400, 403]


def make_ping_request():
    """Helper function to make a ping request."""
    try:
        response = requests.get(f"{AGENTCORE_RUNTIME_URL}/ping", timeout=REQUEST_TIMEOUT)
        return response.status_code == 200
    except Exception:
        return False


def test_concurrent_requests(agentcore_runtime_server):
    """Test making concurrent requests to the service."""
    # Create multiple processes to make concurrent requests
    processes = []
    manager = multiprocessing.Manager()
    results = manager.list()
    
    # Start 3 worker processes
    for i in range(3):
        process = multiprocessing.Process(target=concurrent_worker_process, args=(i, results))
        process.start()
        processes.append(process)
    
    # Wait for all processes to complete
    for process in processes:
        process.join(timeout=30)
        if process.is_alive():
            process.terminate()
    
    # Verify results
    assert len(results) == 3
    for worker_id, success_count in results:
        assert success_count >= 3, f"Worker {worker_id} had too many failures: {success_count}/5"


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
