"""How much wall-clock time the current worker invocation has left.

A Lambda knows its own deadline -- ``context.get_remaining_time_in_millis()`` --
but that context stops at the handler, while the code that actually spends the
time (a provider poll loop, a download) sits several layers down. Passing a
deadline through every signature between the two is noise, so the handler
publishes it here once per record and the spender reads it.

Why it matters, concretely (task-274): the Instagram resolver polled Apify up to
``APIFY_MAX_POLLS x APIFY_POLL_INTERVAL_SECONDS`` = 120 s inside a worker whose
own ceiling was 120 s, after up to 30 s of yt-dlp. The Lambda was killed
mid-resolution, so the job never reached a terminal state and the SQS message
was redelivered to repeat the same doomed run. A poll budget expressed in poll
counts cannot see that; one expressed in remaining time can.

Never raises and never blocks. When no deadline has been published -- the local
polling loop, a script, a REPL -- ``remaining_seconds()`` returns ``None``,
which callers must read as "unknown, fall back to your own static cap".
"""

from __future__ import annotations

import time
from typing import Optional

_deadline_monotonic: Optional[float] = None


def set_remaining_seconds(remaining_seconds_value: float) -> None:
    """Publish the invocation deadline from a remaining-time measurement."""
    global _deadline_monotonic
    if remaining_seconds_value <= 0:
        _deadline_monotonic = None
        return
    _deadline_monotonic = time.monotonic() + float(remaining_seconds_value)


def clear() -> None:
    """Forget the current deadline, so a later caller cannot inherit a stale one."""
    global _deadline_monotonic
    _deadline_monotonic = None


def remaining_seconds() -> Optional[float]:
    """Seconds left in this invocation, or ``None`` when no deadline is known.

    Returns ``0.0`` rather than a negative number once the deadline has passed:
    callers branch on "is there room for one more step", not on how late it is.
    """
    if _deadline_monotonic is None:
        return None
    return max(0.0, _deadline_monotonic - time.monotonic())


def remaining_seconds_after_reserve(reserve_seconds: float) -> Optional[float]:
    """Remaining time minus what the caller must keep for its own finalisation.

    A resolver that spends every last second leaves the worker no room to write
    the job's terminal state and enqueue the next stage, which is the failure
    this module exists to prevent.
    """
    remaining = remaining_seconds()
    if remaining is None:
        return None
    return max(0.0, remaining - max(0.0, float(reserve_seconds)))
