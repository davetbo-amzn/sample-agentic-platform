#!/usr/bin/env python3
"""
Integration Test Runner for AgentCore Services

This script provides an easy way to run the AgentCore integration tests
with proper environment setup and reporting.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def check_environment():
    """Check if required environment variables are set."""
    required_vars = [
        'TEST_CONTAINER_URI',
        'TEST_ROLE_ARN',
        'REGION'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("⚠️  Warning: Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nSome tests may be skipped. Check your .env file.")
        return False
    
    print("✅ All required environment variables are set.")
    return True


def check_dependencies():
    """Check if required Python packages are installed."""
    try:
        import pytest
        import requests
        import dotenv
        print("✅ All required Python packages are available.")
        return True
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("Run: pip install -r requirements.txt")
        return False


def run_tests(test_pattern=None, verbose=False, show_output=False, stop_on_error=True):
    """Run the integration tests."""
    cmd = ["python", "-m", "pytest"]
    
    if stop_on_error:
        cmd.append("-x")

    if verbose:
        cmd.append("-v")
    
    if show_output:
        cmd.append("-s")
    
    if test_pattern:
        cmd.append(test_pattern)
    else:
        # Run all test files by default
        cmd.extend([
            "test_agentcore_runtime_integration.py",
            "test_memory_gateway_integration.py", 
            "test_agentcore_combined_integration.py"
        ])
    
    # Add coverage if available
    try:
        import coverage
        cmd.extend(["--cov=.", "--cov-report=term-missing"])
    except ImportError:
        pass
    
    print(f"🚀 Running tests: {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    print(f"run_tests result {result}")
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Run AgentCore integration tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_integration_tests.py                                    # Run all tests
  python run_integration_tests.py --runtime-only                     # Runtime tests only
  python run_integration_tests.py --memory-only                      # Memory tests only  
  python run_integration_tests.py --combined-only                    # Combined tests only
  python run_integration_tests.py --verbose --show-output            # Verbose with output
  python run_integration_tests.py --test "test_ping_endpoint"        # Specific test
        """
    )
    
    parser.add_argument(
        "--runtime-only",
        action="store_true",
        help="Run only AgentCore Runtime tests"
    )
    
    parser.add_argument(
        "--memory-only", 
        action="store_true",
        help="Run only Memory Gateway tests"
    )
    
    parser.add_argument(
        "--combined-only",
        action="store_true", 
        help="Run only combined integration tests"
    )
    
    parser.add_argument(
        "--test",
        help="Run specific test pattern (e.g., 'test_ping_endpoint')"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--show-output", "-s", 
        action="store_true",
        help="Show print statements and detailed output"
    )
    
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip environment and dependency checks"
    )
    
    args = parser.parse_args()
    
    print("🧪 AgentCore Integration Test Runner")
    print("=" * 40)
    
    # Run checks unless skipped
    if not args.skip_checks:
        print("\n📋 Checking prerequisites...")
        env_ok = check_environment()
        deps_ok = check_dependencies()
        
        if not deps_ok:
            print("\n❌ Prerequisites not met. Exiting.")
            return 1
        
        if not env_ok:
            response = input("\nContinue anyway? (y/N): ")
            if response.lower() != 'y':
                print("Exiting.")
                return 1
    
    # Determine test pattern
    test_pattern = None
    if args.runtime_only:
        test_pattern = "test_agentcore_runtime_integration.py"
    elif args.memory_only:
        test_pattern = "test_memory_gateway_integration.py"
    elif args.combined_only:
        test_pattern = "test_agentcore_combined_integration.py"
    elif args.test:
        test_pattern = f"-k {args.test}"
    
    print(f"\n🏃 Starting integration tests...")
    print(f"Working directory: {Path.cwd()}")
    
    # Run the tests
    exit_code = run_tests(
        test_pattern=test_pattern,
        verbose=args.verbose,
        show_output=args.show_output
    )
    
    print("-" * 60)
    if exit_code == 0:
        print("✅ All tests completed successfully!")
    else:
        print(f"❌ Tests failed with exit code: {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
