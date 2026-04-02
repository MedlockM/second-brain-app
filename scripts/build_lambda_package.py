#!/usr/bin/env python3
"""
Build a Lambda deployment package (zip) for LocalStack/Terraform.

This script creates a minimal zip that contains the application code needed by
the Lambda handler, specifically the `media_summarizer` package. Dependencies
are not bundled (the Lambda in LocalStack tests uses modules provided by the
runtime and the app code itself).

Default output:
  infrastructure/terraform/localstack/lambda_package.zip

Examples:
  # Build with default output path
  python scripts/build_lambda_package.py

  # Build to a custom path
  python scripts/build_lambda_package.py --output /tmp/lambda_package.zip

  # Increase verbosity
  python scripts/build_lambda_package.py -v
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger("build_lambda_package")


def find_project_root(current_file: Path) -> Path:
    """
    Resolve project root based on this script's location.

    Expected layout:
      <project_root>/
        media_summarizer/
        infrastructure/terraform/localstack/
        scripts/build_lambda_package.py  <-- this file
    """
    # scripts/ is directly under the project root
    root = current_file.resolve().parent.parent
    if not (root / "media_summarizer").exists():
        raise RuntimeError(f"Could not find 'media_summarizer' under {root}")
    return root


def default_output_path(project_root: Path) -> Path:
    """Return the default output zip path under terraform localstack dir."""
    return (
        project_root
        / "infrastructure"
        / "terraform"
        / "localstack"
        / "lambda_package.zip"
    )


def ignore_predicates() -> Iterable[shutil.ignore_patterns]:
    """Define ignore patterns for copying source files to staging."""
    return [
        shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".ropeproject",
            ".DS_Store",
            "*.so",
            "*.dylib",
            "*.egg-info",
        )
    ]


def copy_source_to_staging(project_root: Path, staging_dir: Path) -> None:
    """
    Copy the application source into staging.

    We only include the 'media_summarizer' package, excluding caches and tests.
    """
    src_pkg = project_root / "media_summarizer"
    dst_pkg = staging_dir / "media_summarizer"

    if not src_pkg.exists():
        raise FileNotFoundError(f"Source package not found: {src_pkg}")

    LOGGER.info("Copying source package: %s -> %s", src_pkg, dst_pkg)
    shutil.copytree(
        src_pkg,
        dst_pkg,
        ignore=shutil.ignore_patterns(
            "tests", "__pycache__", "*.pyc", "*.pyo", "*.pyd",
            ".pytest_cache", ".mypy_cache", ".ruff_cache",
            ".ropeproject", ".DS_Store", "*.so", "*.dylib", "*.egg-info"
        ),
    )


def make_zip_from_dir(source_dir: Path, zip_path: Path) -> None:
    """
    Create a zip file from the contents of source_dir.

    The zip will contain files with paths relative to source_dir (so that
    'media_summarizer' is at the root of the zip).
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    zip_path.parent.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Creating zip: %s", zip_path)
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for root, _, files in os_walk_sorted(source_dir):
            for file in files:
                file_path = Path(root) / file
                # Store relative to source_dir
                arcname = file_path.relative_to(source_dir)
                zf.write(file_path, arcname)


def os_walk_sorted(base: Path):
    """
    Deterministic os.walk: sorts directories and files for reproducible zips.
    """
    for root, dirs, files in shutil.os.walk(base):
        dirs.sort()
        files.sort()
        yield root, dirs, files


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Lambda deployment package zip for LocalStack/Terraform"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output zip path (default: infrastructure/terraform/localstack/lambda_package.zip)",
    )
    parser.add_argument(
        "--module",
        default="media_summarizer.workers.cleanup.job_archiver",
        help="Lambda handler module to validate import (default: %(default)s)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv)",
    )
    return parser.parse_args(argv)


def configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def validate_import(staging_dir: Path, module: str) -> None:
    """
    Validate that the handler module can be imported from the staging directory.

    This helps catch packaging errors before creating the final zip.
    """
    LOGGER.info("Validating import of module '%s' from staging", module)
    sys.path.insert(0, str(staging_dir))
    try:
        __import__(module)
    except Exception as e:
        raise RuntimeError(f"Failed to import '{module}' from staging: {e}") from e
    finally:
        # Remove staging path from sys.path
        try:
            sys.path.remove(str(staging_dir))
        except ValueError:
            pass


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    current_file = Path(__file__)
    project_root = find_project_root(current_file)
    out_path = args.output or default_output_path(project_root)

    LOGGER.info("Project root: %s", project_root)
    LOGGER.info("Output zip:    %s", out_path)

    # Prepare a temporary staging directory
    with tempfile.TemporaryDirectory(prefix="lambda_build_") as tmpdir:
        staging_dir = Path(tmpdir)
        LOGGER.debug("Staging dir: %s", staging_dir)

        # Copy sources
        copy_source_to_staging(project_root, staging_dir)

        # Validate that the handler module can be imported
        # TODO: Re-enable after adding dependency bundling
        # validate_import(staging_dir, args.module)

        # Create zip
        make_zip_from_dir(staging_dir, out_path)


    LOGGER.info("✅ Lambda package built successfully at: %s", out_path)
    LOGGER.info("You can now run Terraform to (re)deploy the Lambda with LocalStack.")
    return 0


if __name__ == "__main__":
    try:
        import os  # Local import here to avoid top-level pollution

        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
