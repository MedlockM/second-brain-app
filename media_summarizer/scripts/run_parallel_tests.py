#!/usr/bin/env python
"""
Script to run tests in parallel using pytest-xdist.
Usage:
    python -m media_summarizer.scripts.run_parallel_tests [--workers N] [--skip-integration] [--skip-slow]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Run tests in parallel")
    parser.add_argument("--workers", "-n", type=int, default=0, 
                        help="Number of workers (0 for auto-detection, default: 0)")
    parser.add_argument("--skip-integration", action="store_true", 
                        help="Skip integration tests")
    parser.add_argument("--skip-slow", action="store_true", 
                        help="Skip tests marked as slow")
    parser.add_argument("--coverage", action="store_true", 
                        help="Generate coverage report")
    parser.add_argument("--html", action="store_true", 
                        help="Generate HTML coverage report")
    parser.add_argument("--xml", action="store_true", 
                        help="Generate XML coverage report")
    parser.add_argument("--json", action="store_true", 
                        help="Generate JSON coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Verbose output")
    return parser.parse_args()


def run_parallel_tests(args):
    # Build pytest command
    cmd = ["pytest"]
    
    # Add parallel execution option
    if args.workers > 0:
        cmd.extend(["-n", str(args.workers)])
    else:
        cmd.extend(["-n", "auto"])
    
    # Add test selection options
    if args.skip_integration:
        cmd.append("-k")
        cmd.append("not integration")
    
    if args.skip_slow:
        cmd.append("-m")
        cmd.append("not slow")
    
    # Add coverage options
    if args.coverage:
        cmd.append("--cov=media_summarizer")
        
        if args.html:
            cmd.append("--cov-report=html")
        
        if args.xml:
            cmd.append("--cov-report=xml")
        
        if args.json:
            cmd.append("--cov-report=json")
        
        if not (args.html or args.xml or args.json):
            cmd.append("--cov-report=term-missing")
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    
    # Run the command
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    # Print report locations if generated
    if args.coverage and result.returncode == 0:
        print("\nCoverage reports generated:")
        if args.html:
            html_path = Path("htmlcov/index.html").absolute()
            print(f"HTML report: {html_path}")
            print(f"  Open with: file://{html_path}")
        
        if args.xml:
            xml_path = Path("coverage.xml").absolute()
            print(f"XML report: {xml_path}")
        
        if args.json:
            json_path = Path("coverage.json").absolute()
            print(f"JSON report: {json_path}")
    
    return result.returncode


if __name__ == "__main__":
    args = parse_args()
    sys.exit(run_parallel_tests(args))