#!/usr/bin/env python3
"""Guard invariant I2: only ``user_media.mark_deleted`` may write a library TTL.

``purge_at`` is a DynamoDB TTL: whatever writes it decides when a user's library
row is destroyed. Task-218 §2.2 makes that a single-writer attribute
(``media_summarizer/utils/user_media.py``, reached only from
``core/services/media_deletion_service.py``), because the incident this table
exists to fix was caused by a *metadata* write path clobbering rows nobody
intended it to touch. A second writer — a "cleanup" job, a migration script, a
convenience helper that forwards arbitrary attributes — silently converts that
invariant into a comment.

This checks the DynamoDB *write* shapes only, so reading ``record.purge_at``,
returning it in an API contract or logging it stays free:

    ``":purge_at"``      an ExpressionAttributeValues binding
    ``"purge_at":``      an item attribute key in a put_item Item
    ``purge_at = :``     an UpdateExpression SET fragment
    ``REMOVE purge_at``  an UpdateExpression REMOVE fragment -- cancelling a purge
                         is as much a decision about a user's data as scheduling
                         one, so it is guarded the same way

Usage:
    python scripts/check_purge_at_writers.py       # exit 1 on a second writer
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories scanned. Scripts are included on purpose: a one-off migration that
# stamps a TTL onto real library rows is exactly the accident being prevented.
SCAN_DIRS = ("media_summarizer", "scripts")

# The single legitimate writer, plus this guard itself (its docstring quotes the
# very shapes it forbids). Adding anything else here means accepting that a
# second code path can expire a user's library, so it needs the same review as
# the table itself.
ALLOWED = frozenset(
    {
        "media_summarizer/utils/user_media.py",
        "scripts/check_purge_at_writers.py",
    }
)

GUARDED_ATTRS = ("purge_at", "deleted_at")

WRITE_PATTERNS = [
    re.compile(r"""["']:(%s)["']""" % "|".join(GUARDED_ATTRS)),
    re.compile(r"""["'](%s)["']\s*:""" % "|".join(GUARDED_ATTRS)),
    re.compile(r"""\b(%s)\s*=\s*:""" % "|".join(GUARDED_ATTRS)),
    re.compile(r"""\bREMOVE\b[^"']*\b(%s)\b""" % "|".join(GUARDED_ATTRS)),
]


def find_violations() -> List[Tuple[str, int, str]]:
    violations: List[Tuple[str, int, str]] = []
    for scan_dir in SCAN_DIRS:
        for path in sorted((REPO_ROOT / scan_dir).rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in ALLOWED:
                continue
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if any(pattern.search(line) for pattern in WRITE_PATTERNS):
                    violations.append((rel, lineno, line.strip()))
    return violations


def main() -> int:
    violations = find_violations()
    if not violations:
        print(
            "OK: purge_at / deleted_at are written only by "
            "media_summarizer/utils/user_media.py (task-218 invariant I2)."
        )
        return 0

    print(
        "FAIL: a second writer of a user_media TTL attribute appeared.",
        file=sys.stderr,
    )
    for rel, lineno, line in violations:
        print(f"  {rel}:{lineno}: {line}", file=sys.stderr)
    print(
        "\nOnly user_media.mark_deleted() may write purge_at / deleted_at, and it is\n"
        "reachable only from the user-initiated deletion use case\n"
        "(core/services/media_deletion_service.py). Route the write through it, or\n"
        "delete the write: nothing else is allowed to decide when a user's library\n"
        "row expires (task-218 §2.2 invariant I2, task-243 §6.2).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
