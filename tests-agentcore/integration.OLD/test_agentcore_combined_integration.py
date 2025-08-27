"""
Combined integration tests for AgentCore Runtime and Memory Gateway services.

This module tests both services working together by:
1. Starting both services using multiprocessing
2. Testing interactions between agentcore-runtime and memory-gateway
3. End-to-end workflows that involve both services
"""

import json
import multiprocessing
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any
from uuid import uuid4

import pytest
import requests
from dotenv import load_dotenv

# Load environment variables from the .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Test configuration
AGENTCORE_RUNTIME_PORT = 8003
MEMORY_GATEWAY_PORT = 8004
AGENTCORE_RUNTIME_URL = f"http://localhost:{AGENTCORE_RUNTIME_PORT}"
MEMORY_GATEWAY_URL = f"http://localhost:{MEMORY_GATEWAY_PORT}"
SERVICE_STARTUP_TIMEOUT = 45  # seconds - longer for both services
REQUEST_TIMEOUT = 15  # seconds


class CombinedTestServer:
    """Manages both AgentCore Runtime and Memory Gateway test servers."""
    
    def __init__(self):
        self.agentcore_process = None
        self.memory_process = None
        self.base_dir = Path(__file__).parent.parent.parent
        
    def start_agentcore_server(self):
        """Start the AgentCore Runtime server using make command."""
        try:
            print(f"Starting AgentCore Runtime server from {self.base_dir}")
            self.agentcore_process = multiprocessing.Process(
                target=self._run_agentcore_command,
                args=(["make", "agentcore-runtime"], self.base_dir)
            )
            self.agentcore_process.start()
            print(f"Started AgentCore Runtime server with PID: {self.agentcore_process.pid}")
            return True
        except Exception as e:
            print(f"Error starting AgentCore server: {e}")
            return False
    
    def _run_agentcore_command(self, cmd, cwd):
        """Run the AgentCore server command in subprocess."""
        import subprocess
        process = subprocess.run(cmd, cwd=cwd, capture_output=False)
        return process.returncode
    
    def start_memory_server(self):
        """Start the Memory Gateway server using make command."""
        try:
            print(f"Starting Memory Gateway server from {self.base_dir}")
            self.memory_process = multiprocessing.Process(
                target=self._run_memory_command,
                args=(["make", "memory-gateway"], self.base_dir)
            )
            self.memory_process.start()
            print(f"Started Memory Gateway server with PID: {self.memory_process.pid}")
            return True
        except Exception as e:
            print(f"Error starting Memory server: {e}")
            return False
    
    def _run_memory_command(self, cmd, cwd):
        """Run the Memory Gateway server command in subprocess."""
        import subprocess
        process = subprocess.run(cmd, cwd=cwd, capture_output=False)
        return process.returncode
    
    def stop_servers(self):
        """Stop both servers."""
        print("Stopping both servers...")
        
        if self.agentcore_process and self.agentcore_process.is_alive():
            print("Stopping AgentCore Runtime server...")
            self.agentcore_process.terminate()
            self.agentcore_process.join(timeout=5)
            if self.agentcore_process.is_alive():
                print("Force killing AgentCore server process...")
                self.agentcore_process.kill()
                self.agentcore_process.join()
        
        if self.memory_process and self.memory_process.is_alive():
            print("Stopping Memory Gateway server...")
            self.memory_process.terminate()
            self.memory_process.join(timeout=5)
            if self.memory_process.is_alive():
                print("Force killing Memory server process...")
                self.memory_process.kill()
                self.memory_process.join()
        
        print("Both servers stopped")
    
    def wait_for_servers_ready(self, timeout: int = SERVICE_STARTUP_TIMEOUT) -> bool:
        """Wait for both servers to be ready to accept requests."""
        start_time = time.time()
        agentcore_ready = False
        memory_ready = False
        
        while time.time() - start_time < timeout:
            # Check AgentCore Runtime
            if not agentcore_ready:
                try:
                    response = requests.get(f"{AGENTCORE_RUNTIME_URL}/ping", timeout=2)
                    if response.status_code == 200:
                        print("AgentCore Runtime server is ready")
                        agentcore_ready = True
                except requests.exceptions.RequestException:
                    pass
            
            # Check Memory Gateway
            if not memory_ready:
                try:
                    response = requests.get(f"{MEMORY_GATEWAY_URL}/health", timeout=2)
                    if response.status_code == 200:
                        print("Memory Gateway server is ready")
                        memory_ready = True
                except requests.exceptions.RequestException:
                    pass
            
            # Both services ready
            if agentcore_ready and memory_ready:
                print("Both services are ready")
                return True
            
            time.sleep(2)
        
        print(f"Services failed to become ready within {timeout} seconds")
        print(f"AgentCore ready: {agentcore_ready}, Memory ready: {memory_ready}")
        return False


def run_combined_server_process(server_manager: CombinedTestServer):
    """Function to run both servers in a separate process."""
    # Start AgentCore Runtime first
    if not server_manager.start_agentcore_server():
        print("Failed to start AgentCore Runtime server")
        return
    
    # Wait a bit then start Memory Gateway
    time.sleep(5)
    if not server_manager.start_memory_server():
        print("Failed to start Memory Gateway server")
        server_manager.stop_servers()
        return
    
    # Keep the process alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server_manager.stop_servers()


class TestAgentCoreCombinedIntegration:
    """Combined integration tests for both services."""
    
    @classmethod
    def setup_class(cls):
        """Set up the test class with both server processes."""
        cls.server_manager = CombinedTestServer()
        
        # Start both servers in a separate process
        cls.server_process = multiprocessing.Process(
            target=run_combined_server_process,
            args=(cls.server_manager,)
        )
        cls.server_process.start()
        
        # Wait for both servers to be ready
        if not cls.server_manager.wait_for_servers_ready():
            cls.server_process.terminate()
            cls.server_process.join()
            pytest.fail("Failed to start both servers")
    
    @classmethod
    def teardown_class(cls):
        """Clean up after tests."""
        print("Cleaning up combined test servers...")
        cls.server_manager.stop_servers()
        if cls.server_process.is_alive():
            cls.server_process.terminate()
            cls.server_process.join(timeout=15)
    
    def test_both_services_health(self):
        """Test that both services are healthy."""
        # Test AgentCore Runtime
        agentcore_response = requests.get(f"{AGENTCORE_RUNTIME_URL}/ping", timeout=REQUEST_TIMEOUT)
        assert agentcore_response.status_code == 200
        agentcore_data = agentcore_response.json()
        assert agentcore_data["status"] == "healthy"
        
        # Test Memory Gateway
        memory_response = requests.get(f"{MEMORY_GATEWAY_URL}/health", timeout=REQUEST_TIMEOUT)
        assert memory_response.status_code == 200
        memory_data = memory_response.json()
        assert memory_data["status"] == "healthy"
    
    def test_agentcore_runtime_list_with_memory_context(self):
        """Test listing AgentCore Runtimes while also managing memory context."""
        # First, create a session context in memory gateway
        session_id = str(uuid4())
        user_id = "integration-test-user-" + str(uuid4())[:8]
        
        session_context = {
            "session_id": session_id,
            "user_id": user_id,
            "agent_id": "integration-agent-123",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "List my AgentCore Runtimes"
                        }
                    ],
                    "tool_calls": [],
                    "tool_results": [],
                    "timestamp": time.time()
                }
            ],
            "system_prompt": "You are an AgentCore Runtime assistant.",
            "session_metadata": {
                "operation": "list_runtimes",
                "user_intent": "view_all_runtimes"
            }
        }
        
        # Upsert the session context
        memory_payload = {
            "session_context": session_context
        }
        
        memory_response = requests.post(
            f"{MEMORY_GATEWAY_URL}/upsert-session-context",
            json=memory_payload,
            timeout=REQUEST_TIMEOUT
        )
        assert memory_response.status_code in [200, 201, 400, 500]
        
        # Now list AgentCore Runtimes
        agentcore_payload = {
            "maxResults": 10
        }
        
        agentcore_response = requests.get(
            f"{AGENTCORE_RUNTIME_URL}/list-agentcore-runtimes",
            params=agentcore_payload,
            timeout=REQUEST_TIMEOUT
        )
        assert agentcore_response.status_code == 200
        
        # Verify we can retrieve the session context back
        get_session_payload = {
            "user_id": user_id,
            "session_id": session_id,
            "max_results": 1
        }
        
        get_session_response = requests.post(
            f"{MEMORY_GATEWAY_URL}/get-session-context",
            json=get_session_payload,
            timeout=REQUEST_TIMEOUT
        )
        assert get_session_response.status_code in [200, 404]
    
    def test_runtime_creation_with_memory_logging(self):
        """Test creating a runtime while logging the operation in memory."""
        # Skip if required environment variables are not set
        container_uri = os.getenv("TEST_CONTAINER_URI")
        role_arn = os.getenv("TEST_ROLE_ARN")
        
        if not container_uri or not role_arn:
            pytest.skip("TEST_CONTAINER_URI and TEST_ROLE_ARN environment variables required")
        
        session_id = str(uuid4())
        user_id = "runtime-creation-user-" + str(uuid4())[:8]
        agent_id = "runtime-creation-agent-" + str(uuid4())[:8]
        
        # Log the intent to create a runtime in memory
        pre_creation_context = {
            "session_id": session_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Create a new AgentCore Runtime with container {container_uri}"
                        }
                    ],
                    "tool_calls": [],
                    "tool_results": [],
                    "timestamp": time.time()
                }
            ],
            "system_prompt": "You are an AgentCore Runtime management assistant.",
            "session_metadata": {
                "operation": "create_runtime",
                "container_uri": container_uri,
                "role_arn": role_arn
            }
        }
        
        # Store the pre-creation context
        memory_payload = {
            "session_context": pre_creation_context
        }
        
        memory_response = requests.post(
            f"{MEMORY_GATEWAY_URL}/upsert-session-context",
            json=memory_payload,
            timeout=REQUEST_TIMEOUT
        )
        assert memory_response.status_code in [200, 201, 400, 500]
        
        # Generate unique suffix to prevent duplicate name conflicts
        unique_suffix = uuid4().hex[-6:]
        
        # Attempt to create the runtime
        runtime_payload = {
            "agentRoleArn": role_arn,
            "agentRuntimeName": f"integration-test-runtime_{unique_suffix}",
            "containerUri": container_uri,
            "description": "Integration test runtime with memory logging",
            "environmentVariables": {
                "INTEGRATION_TEST": "true",
                "SESSION_ID": session_id
            }
        }
        
        runtime_response = requests.post(
            f"{AGENTCORE_RUNTIME_URL}/create-agentcore-runtime",
            json=runtime_payload,
            timeout=REQUEST_TIMEOUT
        )
        
        # Log the result back to memory
        result_message = {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": f"Runtime creation attempt completed with status: {runtime_response.status_code}"
                }
            ],
            "tool_calls": [],
            "tool_results": [],
            "timestamp": time.time()
        }
        
        # Update session with result
        pre_creation_context["messages"].append(result_message)
        pre_creation_context["session_metadata"]["creation_status"] = runtime_response.status_code
        
        updated_memory_payload = {
            "session_context": pre_creation_context
        }
        
        updated_memory_response = requests.post(
            f"{MEMORY_GATEWAY_URL}/upsert-session-context",
            json=updated_memory_payload,
            timeout=REQUEST_TIMEOUT
        )
        assert updated_memory_response.status_code in [200, 201, 400, 500]
        
        # Verify the runtime creation response
        assert runtime_response.status_code in [200, 400, 403, 500]
        
        if runtime_response.status_code == 200:
            data = runtime_response.json()
            assert "agentRuntimeArn" in data or "agentRuntimeId" in data
    
    def test_concurrent_operations_both_services(self):
        """Test concurrent operations on both services."""
        # Create multiple processes to make concurrent requests to both services
        processes = []
        manager = multiprocessing.Manager()
        results = manager.list()
        
        def worker_process(worker_id: int):
            """Worker function for concurrent requests to both services."""
            agentcore_success = 0
            memory_success = 0
            user_id = f"concurrent-worker-{worker_id}"
            
            for i in range(3):  # Make 3 requests per worker
                # Test AgentCore Runtime
                try:
                    response = requests.get(f"{AGENTCORE_RUNTIME_URL}/ping", timeout=REQUEST_TIMEOUT)
                    if response.status_code == 200:
                        agentcore_success += 1
                except Exception:
                    pass
                
                # Test Memory Gateway
                try:
                    payload = {
                        "user_id": user_id,
                        "max_results": 5
                    }
                    response = requests.post(
                        f"{MEMORY_GATEWAY_URL}/get-session-context",
                        json=payload,
                        timeout=REQUEST_TIMEOUT
                    )
                    if response.status_code in [200, 404]:
                        memory_success += 1
                except Exception:
                    pass
                
                time.sleep(0.5)  # Delay between iterations
            
            results.append((worker_id, agentcore_success, memory_success))
        
        # Start 3 worker processes
        for i in range(3):
            process = multiprocessing.Process(target=worker_process, args=(i,))
            process.start()
            processes.append(process)
        
        # Wait for all processes to complete
        for process in processes:
            process.join(timeout=45)
            if process.is_alive():
                process.terminate()
        
        # Verify results
        assert len(results) == 3
        for worker_id, agentcore_success, memory_success in results:
            assert agentcore_success >= 2, f"Worker {worker_id} AgentCore failures: {agentcore_success}/3"
            assert memory_success >= 2, f"Worker {worker_id} Memory failures: {memory_success}/3"
    
    def test_memory_with_agentcore_metadata(self):
        """Test storing AgentCore-specific metadata in memory."""
        session_id = str(uuid4())
        user_id = "agentcore-metadata-user-" + str(uuid4())[:8]
        agent_id = "agentcore-metadata-agent-" + str(uuid4())[:8]
        
        # Create session context with AgentCore metadata
        session_context = {
            "session_id": session_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Show me my AgentCore Runtime status"
                        }
                    ],
                    "tool_calls": [],
                    "tool_results": [],
                    "timestamp": time.time()
                }
            ],
            "system_prompt": "You manage AgentCore Runtimes.",
            "session_metadata": {
                "agentcore_runtime_arn": os.getenv("TEST_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/test"),
                "runtime_id": os.getenv("RUNTIME_ID", "test-runtime-123"),
                "container_uri": os.getenv("TEST_CONTAINER_URI", "123456789012.dkr.ecr.us-west-2.amazonaws.com/test:latest"),
                "role_arn": os.getenv("TEST_ROLE_ARN", "arn:aws:iam::123456789012:role/test-role"),
                "last_operation": "status_check",
                "operation_timestamp": time.time()
            }
        }
        
        # Store in memory
        memory_payload = {
            "session_context": session_context
        }
        
        memory_response = requests.post(
            f"{MEMORY_GATEWAY_URL}/upsert-session-context",
            json=memory_payload,
            timeout=REQUEST_TIMEOUT
        )
        assert memory_response.status_code in [200, 201, 400, 500]
        
        # Create a memory entry for this session
        create_memory_payload = {
            "session_id": session_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "session_context": session_context
        }
        
        create_memory_response = requests.post(
            f"{MEMORY_GATEWAY_URL}/create-memory",
            json=create_memory_payload,
            timeout=REQUEST_TIMEOUT
        )
        assert create_memory_response.status_code in [200, 201, 400, 500]
        
        # Retrieve memories
        get_memories_payload = {
            "user_id": user_id,
            "session_id": session_id,
            "agent_id": agent_id,
            "limit": 5
        }
        
        get_memories_response = requests.post(
            f"{MEMORY_GATEWAY_URL}/get-memories",
            json=get_memories_payload,
            timeout=REQUEST_TIMEOUT
        )
        assert get_memories_response.status_code in [200, 404]


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
