#!/usr/bin/env python3
"""Guard: every environment variable the app reads is declared in ``.env.example``.

``.env.example`` is the only documentation of what a working ``.env`` contains.
When a variable is read by the code but missing from the template, nobody
rebuilding a workstation can know it exists -- the app either crashes at import
(``required_env``) or silently degrades (a ``os.environ.get`` default that was
never meant to apply in production). That drift is invisible until someone
actually reconstructs an environment, which is the worst moment to discover it.

Two sources of truth are cross-checked against the template:

    ``media_summarizer/**/*.py``   every ``required_env("X")``, ``os.getenv("X")``,
                                   ``os.environ.get("X")`` and ``os.environ["X"]``
    ``runtime_env.tf``             every key of the ``table_names`` /
                                   ``queue_names`` / ``bucket_names`` maps, i.e.
                                   every name Terraform injects into a Lambda

Declarations count even when commented out: ``.env.example`` uses a leading ``#``
to mean "optional, uncomment to override", so ``# NOTES_LLM_MODEL=`` documents
the variable just as well as an active line.

This never opens a ``.env``. All three inputs are tracked files, so the result is
identical on a bare CI checkout and on a developer machine -- that is what makes
it runnable as a gate. Do not "improve" it by comparing against a local ``.env``:
that would make it pass or fail depending on whose laptop it runs on.

The reverse direction (every template key is read somewhere) is deliberately not
checked -- ``.env.example`` legitimately documents variables consumed by
``scripts/``, by the E2E suite, or by botocore itself.

Usage:
    python scripts/check_env_example_complete.py    # exit 1 on an undeclared variable
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

ENV_EXAMPLE = REPO_ROOT / ".env.example"
RUNTIME_ENV_TF = (
    REPO_ROOT / "infrastructure/terraform/modules/platform/runtime_env.tf"
)
SCAN_DIR = REPO_ROOT / "media_summarizer"

# Credentials resolved by the AWS SDK chain, never by this app. Putting them in a
# template invites committing a real key, and on Lambda they come from the
# execution role -- there is nothing for a developer to fill in. Anything added
# here stops being documented anywhere, so it needs the same review as a secret.
EXEMPT = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
    }
)

READ_PATTERNS = [
    re.compile(r"""required_env\(\s*["']([A-Z_0-9]+)["']"""),
    re.compile(r"""os\.environ\.get\(\s*["']([A-Z_0-9]+)["']"""),
    re.compile(r"""os\.getenv\(\s*["']([A-Z_0-9]+)["']"""),
    re.compile(r"""os\.environ\[\s*["']([A-Z_0-9]+)["']\s*\]"""),
]

# `NAME = "value"` inside one of the three resource-name maps. The map keys are
# the env var names Terraform injects, so they must be documented too.
TF_MAP_KEY = re.compile(r"""^\s{4}([A-Z_0-9]+)\s*=""")
TF_MAP_START = re.compile(r"""^\s{2}(table_names|queue_names|bucket_names)\s*=\s*\{""")

# Active or commented declaration: `NAME=`, `# NAME=`, `#NAME=`.
DECLARATION = re.compile(r"""^\s*#?\s*([A-Z_0-9]+)=""")


def declared_names() -> Set[str]:
    """Names documented in .env.example, commented lines included."""
    names: Set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = DECLARATION.match(line)
        if match:
            names.add(match.group(1))
    return names


def names_read_by_code() -> Dict[str, str]:
    """Map each env var the code reads to the first ``file:line`` reading it."""
    found: Dict[str, str] = {}
    for path in sorted(SCAN_DIR.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for pattern in READ_PATTERNS:
                for name in pattern.findall(line):
                    found.setdefault(name, f"{rel}:{lineno}")
    return found


def names_injected_by_terraform() -> Dict[str, str]:
    """Map each name of the three resource maps to its ``file:line``."""
    found: Dict[str, str] = {}
    rel = RUNTIME_ENV_TF.relative_to(REPO_ROOT).as_posix()
    in_map = False
    for lineno, line in enumerate(
        RUNTIME_ENV_TF.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if TF_MAP_START.match(line):
            in_map = True
            continue
        if in_map:
            if line.startswith("  }"):
                in_map = False
                continue
            match = TF_MAP_KEY.match(line)
            if match:
                found.setdefault(match.group(1), f"{rel}:{lineno}")
    return found


def main() -> int:
    declared = declared_names()
    sources: List[Tuple[str, Dict[str, str]]] = [
        ("read by the code", names_read_by_code()),
        ("injected by Terraform", names_injected_by_terraform()),
    ]

    missing: List[Tuple[str, str, str]] = []
    for origin, names in sources:
        for name, where in sorted(names.items()):
            if name in EXEMPT or name in declared:
                continue
            missing.append((name, origin, where))

    if not missing:
        total = sum(len(names) for _, names in sources)
        print(
            f"OK: the {total} environment variables the app reads or receives "
            f"are all declared in .env.example."
        )
        return 0

    print(
        "FAIL: some environment variables are used but not declared in "
        ".env.example.",
        file=sys.stderr,
    )
    for name, origin, where in missing:
        print(f"  {name} -- {origin}, at {where}", file=sys.stderr)
    print(
        "\nAdd each one to the matching section of .env.example, following the file's\n"
        "convention: the real dev value for an AWS resource name, an empty value for\n"
        "a secret, a commented line for an optional override. A variable that is not\n"
        "in the template cannot be found by anyone rebuilding an environment\n"
        "(docs/DEVBOX_SETUP.md).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
