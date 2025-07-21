#!/usr/bin/env python
"""
Script to generate a coverage report summary.
Usage:
    python -m media_summarizer.scripts.coverage_report [--json-file COVERAGE_JSON_FILE]
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a coverage report summary")
    parser.add_argument(
        "--json-file",
        default="coverage.json",
        help="Path to the coverage JSON file (default: coverage.json)",
    )
    return parser.parse_args()


def load_coverage_data(json_file: str) -> Dict[str, Any]:
    """Load coverage data from a JSON file."""
    try:
        with open(json_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Coverage file '{json_file}' not found.")
        print("Run tests with coverage first: python -m media_summarizer.scripts.run_coverage")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Coverage file '{json_file}' is not valid JSON.")
        sys.exit(1)


def get_module_coverage(data: Dict[str, Any]) -> List[Tuple[str, float]]:
    """Extract module coverage data."""
    modules = []
    
    for file_path, file_data in data["files"].items():
        # Skip test files and __init__.py files
        if "/tests/" in file_path or file_path.endswith("__init__.py"):
            continue
        
        # Extract module name (remove .py extension and convert path to module notation)
        module_name = file_path.replace("/", ".").replace(".py", "")
        
        # Calculate coverage percentage
        coverage = file_data["summary"]["percent_covered"]
        
        modules.append((module_name, coverage))
    
    # Sort by coverage (ascending)
    return sorted(modules, key=lambda x: x[1])


def print_coverage_summary(data: Dict[str, Any], modules: List[Tuple[str, float]]):
    """Print a summary of the coverage report."""
    total_coverage = data["totals"]["percent_covered"]
    
    print("\n=== Coverage Report Summary ===\n")
    print(f"Total coverage: {total_coverage:.2f}%")
    
    # Print threshold status
    threshold = 80.0  # Same as in pytest.ini
    if total_coverage >= threshold:
        print(f"✅ Coverage threshold of {threshold}% met")
    else:
        print(f"❌ Coverage below threshold of {threshold}%")
    
    print("\n=== Modules with Lowest Coverage ===\n")
    
    # Print the 10 modules with the lowest coverage
    for module, coverage in modules[:10]:
        color = "\033[92m"  # Green
        if coverage < 70:
            color = "\033[91m"  # Red
        elif coverage < 80:
            color = "\033[93m"  # Yellow
        
        reset = "\033[0m"
        print(f"{module}: {color}{coverage:.2f}%{reset}")
    
    print("\n=== Coverage by Category ===\n")
    
    # Group modules by category
    categories = {}
    for module, coverage in modules:
        parts = module.split(".")
        if len(parts) >= 2:
            category = parts[1]  # e.g., "adapters", "api", "core", etc.
            if category not in categories:
                categories[category] = []
            categories[category].append(coverage)
    
    # Calculate average coverage by category
    for category, coverages in categories.items():
        avg_coverage = sum(coverages) / len(coverages)
        color = "\033[92m"  # Green
        if avg_coverage < 70:
            color = "\033[91m"  # Red
        elif avg_coverage < 80:
            color = "\033[93m"  # Yellow
        
        reset = "\033[0m"
        print(f"{category}: {color}{avg_coverage:.2f}%{reset}")


def main():
    args = parse_args()
    data = load_coverage_data(args.json_file)
    modules = get_module_coverage(data)
    print_coverage_summary(data, modules)
    
    # Print path to HTML report
    html_path = Path("htmlcov/index.html").absolute()
    print(f"\nDetailed HTML report: file://{html_path}")


if __name__ == "__main__":
    main()