"""
Unit tests for the wait functions in AgentCoreMemoryClient.

These tests focus on the _wait_for_memory_provider_creation and 
_wait_for_memory_provider_deletion methods, testing various timing
and response patterns.
"""

import pytest
import time
from unittest import mock

from agentic_platform.service.memory_gateway.client.memory.agentcore_memory_client import AgentCoreMemoryClient


class TestAgentCoreMemoryWaitFunctions:
    """Test suite specifically for the wait functions in AgentCoreMemoryClient."""

    def test_wait_for_memory_provider_creation_immediate_success(self):
        """Test wait_for_memory_provider_creation when memory is immediately available."""
        # Arrange
        mock_control_client = mock.MagicMock()
        mock_control_client.get_memory.return_value = {
            'memory': {'id': 'test-memory-id', 'status': 'ACTIVE'}
        }
        
        # Act
        result = AgentCoreMemoryClient._wait_for_memory_provider_creation(
            mock_control_client,
            'test-memory-id'
        )
        
        # Assert
        assert result['id'] == 'test-memory-id'
        assert result['status'] == 'ACTIVE'
        mock_control_client.get_memory.assert_called_once_with(memoryId='test-memory-id')

    def test_wait_for_memory_provider_creation_eventual_success(self):
        """Test wait_for_memory_provider_creation when memory becomes available after a delay."""
        # Arrange
        mock_control_client = mock.MagicMock()
        
        # Configure the mock to return 'CREATING' on first call, then 'ACTIVE'
        mock_control_client.get_memory.side_effect = [
            {'memory': {'id': 'test-memory-id', 'status': 'CREATING'}},
            {'memory': {'id': 'test-memory-id', 'status': 'ACTIVE'}}
        ]
        
        # Act
        with mock.patch('time.sleep') as mock_sleep:
            result = AgentCoreMemoryClient._wait_for_memory_provider_creation(
                mock_control_client,
                'test-memory-id'
            )
        
        # Assert
        assert result['id'] == 'test-memory-id'
        assert result['status'] == 'ACTIVE'
        assert mock_control_client.get_memory.call_count == 2

    def test_wait_for_memory_provider_creation_exception_then_success(self):
        """Test wait_for_memory_provider_creation when it gets an exception first, then succeeds."""
        # Arrange
        mock_control_client = mock.MagicMock()
        
        # First call raises 'Memory not found', second call succeeds
        mock_control_client.get_memory.side_effect = [
            Exception("Memory not found"),
            {'memory': {'id': 'test-memory-id', 'status': 'ACTIVE'}}
        ]
        
        # Act
        with mock.patch('time.sleep') as mock_sleep:
            result = AgentCoreMemoryClient._wait_for_memory_provider_creation(
                mock_control_client,
                'test-memory-id'
            )
        
        # Assert
        assert result['id'] == 'test-memory-id'
        assert result['status'] == 'ACTIVE'
        assert mock_control_client.get_memory.call_count == 2

    def test_wait_for_memory_provider_creation_timeout(self):
        """Test wait_for_memory_provider_creation when it times out."""
        # Arrange
        mock_control_client = mock.MagicMock()
        
        # Always return 'CREATING' status
        mock_control_client.get_memory.return_value = {
            'memory': {'id': 'test-memory-id', 'status': 'CREATING'}
        }
        
        # Act & Assert
        with mock.patch('time.sleep') as mock_sleep:
            with pytest.raises(TimeoutError) as excinfo:
                AgentCoreMemoryClient._wait_for_memory_provider_creation(
                    mock_control_client,
                    'test-memory-id'
                )
            
            assert "did not become available within the timeout period" in str(excinfo.value)
            assert mock_control_client.get_memory.call_count == 2

    def test_wait_for_memory_provider_creation_unexpected_error(self):
        """Test wait_for_memory_provider_creation with an unexpected error."""
        # Arrange
        mock_control_client = mock.MagicMock()
        
        # Return an unexpected error that's not 'Memory not found'
        mock_control_client.get_memory.side_effect = Exception("Service unavailable")
        
        # Act & Assert
        with mock.patch('time.sleep') as mock_sleep:
            with pytest.raises(TimeoutError) as excinfo:
                AgentCoreMemoryClient._wait_for_memory_provider_creation(
                    mock_control_client,
                    'test-memory-id'
                )
            
            assert "did not become available within the timeout period" in str(excinfo.value)

    def test_wait_for_memory_provider_deletion_immediate_success(self):
        """Test wait_for_memory_provider_deletion when memory is immediately deleted."""
        # Arrange
        mock_control_client = mock.MagicMock()
        mock_control_client.get_memory.side_effect = Exception("Memory not found")
        
        # Act
        result = AgentCoreMemoryClient._wait_for_memory_provider_deletion(
            mock_control_client,
            'test-memory-id'
        )
        
        # Assert
        assert result is True
        mock_control_client.get_memory.assert_called_once_with(memoryId='test-memory-id')

    def test_wait_for_memory_provider_deletion_eventual_success(self):
        """Test wait_for_memory_provider_deletion when memory is deleted after a delay."""
        # Arrange
        mock_control_client = mock.MagicMock()
        
        # First call returns the memory, second call raises 'Memory not found'
        mock_control_client.get_memory.side_effect = [
            {'memory': {'id': 'test-memory-id', 'status': 'DELETING'}},
            Exception("Memory not found")
        ]
        
        # Act
        with mock.patch('time.sleep') as mock_sleep:
            result = AgentCoreMemoryClient._wait_for_memory_provider_deletion(
                mock_control_client,
                'test-memory-id'
            )
        
        # Assert
        assert result is True
        assert mock_control_client.get_memory.call_count == 2

    def test_wait_for_memory_provider_deletion_timeout(self):
        """Test wait_for_memory_provider_deletion when it times out."""
        # Arrange
        mock_control_client = mock.MagicMock()
        
        # Always return the memory (deletion never completes)
        mock_control_client.get_memory.return_value = {
            'memory': {'id': 'test-memory-id', 'status': 'DELETING'}
        }
        
        # Act & Assert
        with mock.patch('time.sleep') as mock_sleep:
            with pytest.raises(TimeoutError) as excinfo:
                AgentCoreMemoryClient._wait_for_memory_provider_deletion(
                    mock_control_client,
                    'test-memory-id'
                )
            
            assert "was not deleted within the timeout period" in str(excinfo.value)
            assert mock_control_client.get_memory.call_count == 2

    def test_wait_methods_respect_timeouts(self):
        """Test that the wait methods respect the provided timeouts."""
        # Arrange
        mock_control_client = mock.MagicMock()
        
        # Set up mocks to always return a non-terminal state
        mock_control_client.get_memory.return_value = {
            'memory': {'id': 'test-memory-id', 'status': 'CREATING'}
        }
        
        # Act - Use spy to track sleep calls
        with mock.patch('time.sleep') as mock_sleep:
            try:
                # We expect this to time out
                AgentCoreMemoryClient._wait_for_memory_provider_creation(
                    mock_control_client,
                    'test-memory-id'
                )
            except TimeoutError:
                pass
        
        # Assert
        # Should have called sleep 2 times (max_attempts - 1)
        assert mock_sleep.call_count == 2
        # Check it was called with the right delay
        mock_sleep.assert_called_with(5)
