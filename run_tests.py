#!/usr/bin/env python3
"""
Test runner script for the Substack to Markdown CLI.

This script runs all the tests for the performance optimization modules.
"""

import os
import sys
import unittest
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_tests(test_modules=None, verbose=False):
    """
    Run the tests.
    
    Args:
        test_modules (list, optional): List of test modules to run. Defaults to None (all tests).
        verbose (bool, optional): Whether to run tests in verbose mode. Defaults to False.
    
    Returns:
        bool: True if all tests passed, False otherwise.
    """
    # Get the test directory
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests")
    
    # Add the current directory to the path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Get all test modules
    if test_modules is None:
        test_modules = [
            f[:-3] for f in os.listdir(test_dir)
            if f.startswith("test_") and f.endswith(".py")
        ]
    
    # Add tests to the suite
    for module_name in test_modules:
        try:
            # Import the module
            module = __import__(f"tests.{module_name}", fromlist=["*"])
            
            # Add all test cases from the module
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, unittest.TestCase) and obj != unittest.TestCase:
                    test_suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(obj))
        
        except ImportError as e:
            logger.error(f"Error importing test module {module_name}: {e}")
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(test_suite)
    
    # Return True if all tests passed
    return result.wasSuccessful()

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run tests for the Substack to Markdown CLI"
    )
    
    parser.add_argument(
        "--modules", "-m",
        nargs="+",
        help="Test modules to run (e.g., test_adaptive_throttler)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Run tests in verbose mode"
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_args()
    
    # Run the tests
    success = run_tests(args.modules, args.verbose)
    
    # Exit with the appropriate status code
    sys.exit(0 if success else 1)
