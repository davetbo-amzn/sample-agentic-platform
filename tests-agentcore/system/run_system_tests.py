#!/usr/bin/env python3
"""
Test runner for AgentCore system tests.

This script runs the system tests against deployed AgentCore Lambda functions
and provides organized output and reporting.
"""

import argparse
import os
import sys
from pathlib import Path

import pytest


def main():
    """Main entry point for system test runner."""
    parser = argparse.ArgumentParser(description="Run AgentCore system tests")
    parser.add_argument(
        "--test-type",
        choices=["all", "memory", "runtime", "integration"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="Increase verbosity (use -v, -vv, or -vvv)"
    )
    parser.add_argument(
        "--no-slow",
        action="store_true",
        help="Skip slow-running tests"
    )
    parser.add_argument(
        "--discover-resources",
        action="store_true",
        help="Auto-discover deployed resources (may take longer)"
    )

    args = parser.parse_args()
    
    # Construct pytest arguments
    pytest_args = []
    
    # Add test selection based on type
    if args.test_type == "memory":
        pytest_args.extend(["-m", "lambda_test", "test_agentcore_memory_lambda_system.py"])
    elif args.test_type == "runtime":
        pytest_args.extend(["-m", "lambda_test", "test_agentcore_runtime_lambda_system.py"])
    elif args.test_type == "integration":
        pytest_args.extend(["-m", "lambda_test", "test_jwt_runtime_memory_integration.py"])
    else:  # all
        pytest_args.append(".")
    
    # Add verbosity
    if args.verbose >= 3:
        pytest_args.append("-vvv")
    elif args.verbose >= 2:
        pytest_args.append("-vv")
    elif args.verbose >= 1:
        pytest_args.append("-v")
    
    # Skip slow tests if requested
    if args.no_slow:
        pytest_args.extend(["-m", "not slow"])
    
    # Add some standard options
    pytest_args.extend([
        "--tb=short",
        "--color=yes",
        "-s",
        "-x"
    ])
    
    print("AgentCore System Tests")
    print("=" * 50)
    print(f"Test type: {args.test_type}")
    print(f"Verbosity: {args.verbose}")
    print(f"Skip slow tests: {args.no_slow}")
    print(f"Discover resources: {args.discover_resources}")
    print("\nEnvironment Check:")
    print(f"AWS Region: {os.getenv('REGION', 'Not set')}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'Not set')}")
    print(f"Test Container URI: {'Set' if os.getenv('TEST_CONTAINER_URI') else 'Not set'}")
    print(f"Test Role ARN: {'Set' if os.getenv('TEST_ROLE_ARN') else 'Not set'}")
    
    print("\nRunning tests...")
    print("=" * 50)
    
    # Run pytest with constructed arguments
    exit_code = pytest.main(pytest_args)
    
    print("\n" + "=" * 50)
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed.")
    
    print(f"Exit code: {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
