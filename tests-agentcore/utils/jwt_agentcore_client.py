"""
JWT AgentCore Client for direct runtime invocation with streaming support.

This client provides methods to invoke deployed AgentCore runtimes directly
using JWT authentication, bypassing the runtime controller for production-like testing.
"""

import json
import logging
import os
import requests
import time
from typing import Dict, Any, Optional, Iterator, Generator
from urllib.parse import quote
from uuid import uuid4

# Import JWT token generation utility
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "script"))
from get_auth_token import get_token

logger = logging.getLogger(__name__)

class JWTAgentCoreClient:
    """Client for directly invoking AgentCore runtimes with JWT authentication."""
    
    def __init__(self, region: str = None):
        """Initialize the JWT AgentCore client.
        
        Args:
            region: AWS region (default: from environment)
        """
        self.region = region or os.getenv('REGION', os.getenv('AWS_REGION', 'us-west-2'))
        self._cached_token = None
        self._token_expiry = None
        
    def _get_jwt_token(self, force_refresh: bool = False) -> str:
        """Get a JWT token for AgentCore authentication.
        
        Args:
            force_refresh: Force token refresh even if cached token exists
            
        Returns:
            JWT token string
            
        Raises:
            Exception: If token generation fails
        """
        # Check if we have a valid cached token
        if not force_refresh and self._cached_token and self._token_expiry:
            # Add 60 second buffer before expiry
            if time.time() < (self._token_expiry - 60):
                logger.debug("Using cached JWT token")
                return self._cached_token
        
        try:
            logger.info("Generating fresh JWT token for AgentCore authentication")
            token_data = get_token()
            
            if isinstance(token_data, dict):
                self._cached_token = token_data.get('access_token')
                # Estimate expiry (JWT tokens typically valid for 1 hour)
                self._token_expiry = time.time() + 3600  # 1 hour
            else:
                self._cached_token = str(token_data)
                self._token_expiry = time.time() + 3600
                
            if not self._cached_token:
                raise Exception("Failed to extract access token from JWT response")
                
            logger.info("Successfully generated JWT token")
            return self._cached_token
            
        except Exception as e:
            logger.error(f"Failed to get JWT token: {e}")
            raise Exception(f"JWT token generation failed: {e}")
    
    def _construct_invoke_url(self, agent_runtime_arn: str, qualifier: str = "DEFAULT") -> str:
        """Construct the invoke URL for an AgentCore runtime.
        
        Args:
            agent_runtime_arn: The ARN of the AgentCore runtime
            qualifier: Runtime qualifier (default: DEFAULT)
            
        Returns:
            Complete invoke URL
        """
        # URL encode the ARN as required by AWS AgentCore API
        escaped_agent_arn = quote(agent_runtime_arn, safe='')
        
        # Construct the invoke URL according to AWS documentation
        invoke_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier={qualifier}"
        
        logger.debug(f"Constructed invoke URL: {invoke_url}")
        return invoke_url
    
    def invoke_runtime(
        self,
        agent_runtime_arn: str,
        payload: Dict[str, Any],
        stream: bool = False,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        content_type: str = "application/json",
        qualifier: str = "DEFAULT",
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Invoke an AgentCore runtime with JWT authentication.
        
        Args:
            agent_runtime_arn: ARN of the AgentCore runtime
            payload: Request payload to send to the runtime
            stream: Enable streaming response
            session_id: Optional session ID for conversation tracking
            user_id: Optional user ID for request tracking
            content_type: Request content type
            qualifier: Runtime qualifier
            timeout: Request timeout in seconds
            
        Returns:
            Response data from the runtime
            
        Raises:
            Exception: If invocation fails
        """
        # Get JWT token
        token = self._get_jwt_token()
        
        # Construct URL
        invoke_url = self._construct_invoke_url(agent_runtime_arn, qualifier)
        
        # Prepare headers
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': content_type,
            'Accept': '*/*'
        }
        
        # Add optional headers
        if session_id:
            headers['X-Amzn-Bedrock-AgentCore-Runtime-Session-Id'] = session_id
            
        if user_id:
            headers['X-Amzn-Bedrock-AgentCore-Runtime-User-Id'] = user_id
        
        # Add stream flag to payload if streaming
        if stream:
            payload = {**payload, "stream": True}
        
        logger.info(f"Invoking AgentCore runtime: {agent_runtime_arn}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            # Make the request
            if stream:
                return self._handle_streaming_response(
                    invoke_url, headers, payload, timeout
                )
            else:
                response = requests.post(
                    invoke_url,
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
                response.raise_for_status()
                
                # Try to parse as JSON, fall back to text
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"response": response.text, "content_type": response.headers.get('content-type')}
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"AgentCore runtime invocation failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise Exception(f"Failed to invoke AgentCore runtime: {e}")
    
    def _handle_streaming_response(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        timeout: int
    ) -> Dict[str, Any]:
        """Handle streaming response from AgentCore runtime.
        
        Args:
            url: Invoke URL
            headers: Request headers
            payload: Request payload
            timeout: Request timeout
            
        Returns:
            Dictionary containing streaming events and metadata
        """
        logger.info("Starting streaming request to AgentCore runtime")
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                stream=True,
                timeout=timeout
            )
            response.raise_for_status()
            
            # Collect streaming events
            events = []
            for line in response.iter_lines(decode_unicode=True):
                if line.strip():  # Skip empty lines
                    try:
                        event_data = json.loads(line.strip())
                        events.append(event_data)
                        logger.debug(f"Received streaming event: {event_data.get('event', 'unknown')}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse streaming line as JSON: {line[:100]}...")
                        # Store as raw text event
                        events.append({
                            "event": "raw_text",
                            "data": {"text": line.strip()},
                            "timestamp": time.time()
                        })
            
            logger.info(f"Streaming completed with {len(events)} events")
            
            return {
                "streaming": True,
                "events": events,
                "total_events": len(events),
                "status_code": response.status_code,
                "headers": dict(response.headers)
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Streaming request failed: {e}")
            raise Exception(f"Failed to handle streaming response: {e}")
    
    def invoke_runtime_streaming_generator(
        self,
        agent_runtime_arn: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        qualifier: str = "DEFAULT",
        timeout: int = 30
    ) -> Generator[Dict[str, Any], None, None]:
        """Invoke AgentCore runtime with streaming as a generator.
        
        Args:
            agent_runtime_arn: ARN of the AgentCore runtime
            payload: Request payload to send to the runtime
            session_id: Optional session ID for conversation tracking
            user_id: Optional user ID for request tracking
            qualifier: Runtime qualifier
            timeout: Request timeout in seconds
            
        Yields:
            Individual streaming events as they arrive
            
        Raises:
            Exception: If invocation fails
        """
        # Get JWT token
        token = self._get_jwt_token()
        
        # Construct URL
        invoke_url = self._construct_invoke_url(agent_runtime_arn, qualifier)
        
        # Prepare headers
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': '*/*'
        }
        
        # Add optional headers
        if session_id:
            headers['X-Amzn-Bedrock-AgentCore-Runtime-Session-Id'] = session_id
            
        if user_id:
            headers['X-Amzn-Bedrock-AgentCore-Runtime-User-Id'] = user_id
        
        # Add stream flag to payload
        payload = {**payload, "stream": True}
        
        logger.info(f"Starting streaming generator for AgentCore runtime: {agent_runtime_arn}")
        
        try:
            response = requests.post(
                invoke_url,
                headers=headers,
                json=payload,
                stream=True,
                timeout=timeout
            )
            response.raise_for_status()
            
            for line in response.iter_lines(decode_unicode=True):
                if line.strip():  # Skip empty lines
                    try:
                        event_data = json.loads(line.strip())
                        yield event_data
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse streaming line as JSON: {line[:100]}...")
                        # Yield as raw text event
                        yield {
                            "event": "raw_text",
                            "data": {"text": line.strip()},
                            "timestamp": time.time()
                        }
                        
        except requests.exceptions.RequestException as e:
            logger.error(f"Streaming generator failed: {e}")
            # Yield error event
            yield {
                "event": "error",
                "data": {"error": str(e)},
                "timestamp": time.time()
            }
    
    def test_runtime_connectivity(self, agent_runtime_arn: str) -> Dict[str, Any]:
        """Test connectivity to an AgentCore runtime with a simple request.
        
        Args:
            agent_runtime_arn: ARN of the AgentCore runtime to test
            
        Returns:
            Test results including connectivity status and response info
        """
        test_payload = {
            "prompt": "Hello, can you confirm you're working?",
            "session_id": f"test-connectivity-{uuid4().hex[:8]}"
        }
        
        try:
            logger.info(f"Testing connectivity to AgentCore runtime: {agent_runtime_arn}")
            
            start_time = time.time()
            response = self.invoke_runtime(
                agent_runtime_arn=agent_runtime_arn,
                payload=test_payload,
                stream=False,
                timeout=15
            )
            end_time = time.time()
            
            return {
                "connectivity": "success",
                "runtime_arn": agent_runtime_arn,
                "response_time_ms": round((end_time - start_time) * 1000, 2),
                "response_size": len(str(response)),
                "response_preview": str(response)[:200] + "..." if len(str(response)) > 200 else str(response)
            }
            
        except Exception as e:
            logger.error(f"Connectivity test failed for {agent_runtime_arn}: {e}")
            return {
                "connectivity": "failed",
                "runtime_arn": agent_runtime_arn,
                "error": str(e)
            }
