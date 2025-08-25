"""
AgentCore System Tests

This package contains system tests for deployed AgentCore services.
Tests validate Lambda functions and AgentCore service operations after Terraform deployment.

Test Categories:
- Memory Lambda function tests
- Runtime controller Lambda function tests  
- End-to-end workflow tests
- Performance and observability tests

Usage:
    python run_system_tests.py --test-type all
    pytest -v
    pytest -m lambda_test
    pytest -m e2e_test
"""

__version__ = "1.0.0"
