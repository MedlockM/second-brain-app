#!/usr/bin/env python
"""
Script to run tests with coverage and generate reports.
Usage:
    python -m media_summarizer.scripts.run_coverage [--html] [--xml] [--json] [--term] [--skip-integration] [--mock-whisper] [--refactored]

Options:
    --html: Generate HTML coverage report
    --xml: Generate XML coverage report
    --json: Generate JSON coverage report
    --term: Show coverage report in terminal
    --all: Generate all report formats (default)
    --skip-integration: Skip integration tests
    --mock-whisper: Mock the Whisper model to avoid downloading it
    --refactored: Run only refactored tests
    --compare: Compare coverage between original and refactored tests
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Run tests with coverage")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--xml", action="store_true", help="Generate XML coverage report")
    parser.add_argument("--json", action="store_true", help="Generate JSON coverage report")
    parser.add_argument("--term", action="store_true", help="Show coverage report in terminal")
    parser.add_argument("--all", action="store_true", help="Generate all report formats (default)")
    parser.add_argument("--skip-integration", action="store_true", help="Skip integration tests")
    parser.add_argument("--mock-whisper", action="store_true", help="Mock the Whisper model to avoid downloading it")
    parser.add_argument("--refactored", action="store_true", help="Run only refactored tests")
    parser.add_argument("--compare", action="store_true", help="Compare coverage between original and refactored tests")
    return parser.parse_args()


def run_coverage(args):
    # If no specific format is selected, generate all formats
    if not (args.html or args.xml or args.json or args.term):
        args.all = True

    # Build pytest command with coverage options
    cmd = ["pytest"]
    
    # Add coverage module option
    cmd.append("--cov=media_summarizer")
    
    # Add report formats
    if args.term or args.all:
        cmd.append("--cov-report=term-missing")
    
    if args.html or args.all:
        cmd.append("--cov-report=html")
    
    if args.xml or args.all:
        cmd.append("--cov-report=xml")
    
    if args.json or args.all:
        cmd.append("--cov-report=json")
    
    # Skip integration tests if requested
    if args.skip_integration:
        cmd.append("-k")
        cmd.append("not integration")
    
    # Run only refactored tests if requested
    if args.refactored:
        cmd.append("-k")
        cmd.append("refactored")
    
    # Set environment variables for mocking Whisper if requested
    env = os.environ.copy()
    if args.mock_whisper:
        env["MOCK_WHISPER"] = "1"
    
    # Run the command
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env)
    
    # Print report locations if generated
    if result.returncode == 0:
        print("\nCoverage reports generated:")
        if args.html or args.all:
            html_path = Path("htmlcov/index.html").absolute()
            print(f"HTML report: {html_path}")
            print(f"  Open with: file://{html_path}")
        
        if args.xml or args.all:
            xml_path = Path("coverage.xml").absolute()
            print(f"XML report: {xml_path}")
        
        if args.json or args.all:
            json_path = Path("coverage.json").absolute()
            print(f"JSON report: {json_path}")
    
    return result.returncode


def compare_coverage(args):
    """
    Compare coverage between original and refactored tests.
    
    This function runs the tests twice - once with original tests and once with refactored tests,
    then compares the coverage results.
    """
    print("=== Running original tests ===")
    original_args = argparse.Namespace(**vars(args))
    original_args.refactored = False
    original_args.json = True
    original_args.html = False
    original_args.xml = False
    original_args.term = False
    
    # Run original tests
    run_coverage(original_args)
    
    # Save original coverage data
    if os.path.exists("coverage.json"):
        os.rename("coverage.json", "coverage_original.json")
    else:
        print("Error: Original coverage data not generated")
        return 1
    
    print("\n=== Running refactored tests ===")
    refactored_args = argparse.Namespace(**vars(args))
    refactored_args.refactored = True
    refactored_args.json = True
    refactored_args.html = False
    refactored_args.xml = False
    refactored_args.term = False
    
    # Run refactored tests
    run_coverage(refactored_args)
    
    # Save refactored coverage data
    if os.path.exists("coverage.json"):
        os.rename("coverage.json", "coverage_refactored.json")
    else:
        print("Error: Refactored coverage data not generated")
        return 1
    
    # Compare coverage data
    try:
        import json
        
        with open("coverage_original.json", "r") as f:
            original_data = json.load(f)
        
        with open("coverage_refactored.json", "r") as f:
            refactored_data = json.load(f)
        
        original_coverage = original_data["totals"]["percent_covered"]
        refactored_coverage = refactored_data["totals"]["percent_covered"]
        
        print("\n=== Coverage Comparison ===")
        print(f"Original tests coverage: {original_coverage:.2f}%")
        print(f"Refactored tests coverage: {refactored_coverage:.2f}%")
        
        if refactored_coverage > original_coverage:
            print(f"Improvement: +{refactored_coverage - original_coverage:.2f}%")
        elif refactored_coverage < original_coverage:
            print(f"Regression: {refactored_coverage - original_coverage:.2f}%")
        else:
            print("No change in coverage")
        
        # Compare coverage by file
        print("\n=== Coverage by File ===")
        print("File | Original | Refactored | Difference")
        print("-" * 60)
        
        all_files = set(original_data["files"].keys()) | set(refactored_data["files"].keys())
        for file_path in sorted(all_files):
            if "/tests/" in file_path:
                continue  # Skip test files
                
            original_file_coverage = original_data["files"].get(file_path, {}).get("summary", {}).get("percent_covered", 0)
            refactored_file_coverage = refactored_data["files"].get(file_path, {}).get("summary", {}).get("percent_covered", 0)
            difference = refactored_file_coverage - original_file_coverage
            
            # Format the difference with a + sign for improvements
            if difference > 0:
                diff_str = f"+{difference:.2f}%"
            elif difference < 0:
                diff_str = f"{difference:.2f}%"
            else:
                diff_str = "0.00%"
            
            print(f"{file_path} | {original_file_coverage:.2f}% | {refactored_file_coverage:.2f}% | {diff_str}")
        
        return 0
    except Exception as e:
        print(f"Error comparing coverage data: {str(e)}")
        return 1


if __name__ == "__main__":
    args = parse_args()
    if args.compare:
        sys.exit(compare_coverage(args))
    else:
        sys.exit(run_coverage(args))