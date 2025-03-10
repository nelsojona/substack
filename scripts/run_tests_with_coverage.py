#!/usr/bin/env python3
"""
Run tests with coverage and display results.

This script runs pytest with coverage reporting and displays the results.
It's useful for quickly checking test status before committing changes.
"""

import os
import sys
import subprocess
import webbrowser
from pathlib import Path

def run_tests_with_coverage():
    """Run tests with coverage and display results."""
    print("Running tests with coverage...")
    
    # Create directory for coverage reports
    os.makedirs("coverage_reports", exist_ok=True)
    
    # Run pytest with coverage
    result = subprocess.run([
        "pytest",
        "--cov=src",
        "--cov-report=term",
        "--cov-report=html:coverage_reports/html",
        "tests/"
    ], capture_output=True, text=True)
    
    # Print test output
    print(result.stdout)
    
    if result.stderr:
        print("Errors:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
    
    # Open coverage report in browser if tests passed
    if result.returncode == 0:
        print("\nTests passed! Opening coverage report in browser...")
        report_path = Path("coverage_reports/html/index.html").absolute().as_uri()
        webbrowser.open(report_path)
    else:
        print("\nTests failed with exit code:", result.returncode, file=sys.stderr)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_tests_with_coverage())
