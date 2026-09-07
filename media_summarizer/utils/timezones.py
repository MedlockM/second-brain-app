"""IANA time-zone validation for ``User.iana_timezone``.

The Digest notifies at 18:30 *local* time (daily) and Monday 09:30 local
(weekly), so the user's zone has to be stored. What is stored is the IANA
**name** (``"Europe/Paris"``), never a UTC offset: a stored ``"+02:00"`` is
wrong six months a year, while the name carries its own DST rules and needs no
logic server-side. This module is the gate that keeps an offset — or any other
string — out of the field.

The accepted set is ``zoneinfo.available_timezones()``, i.e. the tz database
shipped with the runtime (``/usr/share/zoneinfo``, present in the
``public.ecr.aws/lambda/python:3.11`` base image), so it follows tzdata releases
without a list to maintain here.

Lookups are case-sensitive on purpose. IANA names are, and the database is keyed
exactly: ``"europe/paris"`` is not a zone. Lower-casing the way
``reading_language`` does would turn a valid name into a rejected one.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, FrozenSet, Optional
from zoneinfo import available_timezones

# Entries that live in the tz database directory but name no region, so no
# device can legitimately report them. ``localtime`` is the host's own symlink
# and ``Factory`` is the placeholder shipped for unconfigured machines; storing
# either would give a Digest scheduler a zone it cannot reason about.
_NON_REGION_KEYS = frozenset({"localtime", "Factory"})


@lru_cache(maxsize=1)
def _known_timezones() -> FrozenSet[str]:
    """The zone names the runtime's tz database knows.

    Cached: ``available_timezones()`` walks the zone directory (~600 entries),
    which is wasteful per request but free once per Lambda container.
    """
    return frozenset(available_timezones()) - _NON_REGION_KEYS


def normalize_iana_timezone(value: Any) -> Optional[str]:
    """Return the IANA zone name, or ``None`` when the value is not one.

    ``None`` covers every rejection the caller has to answer 400 for: a UTC
    offset (``"+02:00"``, ``"UTC+2"``, ``"GMT+02:00"`` — none of them are zone
    names), an unknown or misspelled zone, a non-string, or an empty string.
    """
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or name not in _known_timezones():
        return None
    return name
