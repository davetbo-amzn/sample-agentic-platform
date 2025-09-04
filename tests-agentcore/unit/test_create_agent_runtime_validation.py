"""
Test cases for the create_agent_runtime method parameter validation.

This test file focuses on testing the either/or validation logic for
agent_description and ecr_repo_uri parameters.
"""

import pytest
from unittest.mock import Mock, patch
from agentic_platform.service.agentcore.runtime.client.agentcore_runtime_client import AgentCoreRuntimeClient


class TestCreateAgentRuntimeValidation:
    """Test parameter validation for create_agent_runtime method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = AgentCoreRuntimeClient()
    
    def test_create_agent_runtime_with_agent_description_only(self):
        """Test that create_agent_runtime works with only agent_description provided."""
        with patch.object(self.client, '_create_runtime_from_description') as mock_create_desc:
            mock_create_desc.return_value = "Success with description"
            
            result = self.client.create_agent_runtime(
                name="test-agent",
                agent_description="A helpful AI assistant"
            )
            
            assert result == "Success with description"
            mock_create_desc.assert_called_once()
    
    def test_create_agent_runtime_with_ecr_repo_uri_only(self):
        """Test that create_agent_runtime works with only ecr_repo_uri provided."""
        with patch.object(self.client, '_create_runtime_from_ecr') as mock_create_ecr:
            mock_create_ecr.return_value = "Success with ECR"
            
            result = self.client.create_agent_runtime(
                name="test-agent",
                ecr_repo_uri="123456789012.dkr.ecr.us-west-2.amazonaws.com/my-agent:latest"
            )
            
            assert result == "Success with ECR"
            mock_create_ecr.assert_called_once()
    
    def test_create_agent_runtime_with_both_parameters_raises_error(self):
        """Test that providing both agent_description and ecr_repo_uri raises Exception."""
        with pytest.raises(Exception) as exc_info:
            self.client.create_agent_runtime(
                name="test-agent",
                agent_description="A helpful AI assistant",
                ecr_repo_uri="123456789012.dkr.ecr.us-west-2.amazonaws.com/my-agent:latest"
            )
        
        assert "Cannot provide both agent_description and ecr_repo_uri" in str(exc_info.value)
    
    def test_create_agent_runtime_with_neither_parameter_raises_error(self):
        """Test that providing neither agent_description nor ecr_repo_uri raises Exception."""
        with pytest.raises(Exception) as exc_info:
            self.client.create_agent_runtime(
                name="test-agent"
            )
        
        assert "Must provide either agent_description or ecr_repo_uri" in str(exc_info.value)
    
    def test_create_agent_runtime_with_empty_agent_description_raises_error(self):
        """Test that providing empty agent_description raises Exception."""
        with pytest.raises(Exception) as exc_info:
            self.client.create_agent_runtime(
                name="test-agent",
                agent_description=""
            )
        
        assert "Must provide either agent_description or ecr_repo_uri" in str(exc_info.value)
    
    def test_create_agent_runtime_with_empty_ecr_repo_uri_raises_error(self):
        """Test that providing empty ecr_repo_uri raises Exception."""
        with pytest.raises(Exception) as exc_info:
            self.client.create_agent_runtime(
                name="test-agent",
                ecr_repo_uri=""
            )
        
        assert "Must provide either agent_description or ecr_repo_uri" in str(exc_info.value)
    
    def test_sanitize_name_method(self):
        """Test the sanitize_name static method."""
        # Test normal name
        assert AgentCoreRuntimeClient.sanitize_name("my-agent") == "my_agent"
        
        # Test name with special characters
        assert AgentCoreRuntimeClient.sanitize_name("my@agent#test") == "my_agent_test"
        
        # Test long name truncation
        long_name = "a" * 60
        result = AgentCoreRuntimeClient.sanitize_name(long_name)
        assert len(result) <= 48
        assert result.startswith("a")
        
        # Test name starting with number raises ValueError
        with pytest.raises(ValueError) as exc_info:
            AgentCoreRuntimeClient.sanitize_name("123agent")
        assert "must start with a letter" in str(exc_info.value)
        
        # Test empty name raises ValueError
        with pytest.raises(ValueError) as exc_info:
            AgentCoreRuntimeClient.sanitize_name("")
        assert "cannot be empty" in str(exc_info.value)
        
        # Test name starting with underscore raises ValueError
        with pytest.raises(ValueError) as exc_info:
            AgentCoreRuntimeClient.sanitize_name("_agent")
        assert "must start with a letter" in str(exc_info.value)
        
        # Test name with only special characters raises ValueError
        with pytest.raises(ValueError) as exc_info:
            AgentCoreRuntimeClient.sanitize_name("@#$%")
        assert "must start with a letter" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
