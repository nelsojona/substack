#!/usr/bin/env python3
"""
Test runner for the Substack to Markdown CLI tool.

This script runs all the tests for the Substack to Markdown CLI tool.
"""

import unittest
import sys
import os

if __name__ == '__main__':
    # Add the parent directory to the path so that the tests can import the modules
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    
    # Discover and run all tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Exit with non-zero status if any tests failed
    sys.exit(not result.wasSuccessful())
