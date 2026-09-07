"""
Digest service: captures the ordered list of media a period held.

What a digest *is*, since task-366: the ids of the media saved in one period,
oldest first. The client renders each one as the media page itself, so nothing is
pre-computed here — no summary, no theme, no statistic, and above all **no
artifact generation**. Assembling a digest costs one library query and never
debits a quota. A generation started from the digest is one the user asked for,
on the media page, exactly as anywhere else in the app.

Two rules carry the whole design.

**A period ends at a send instant that is already past.** The daily digest is the
24 hours before the last 18:30 local; the weekly one is the Monday-to-Sunday week
that closed before the last Monday 09:30 local. Neither window can still be
filling up, so what the screen shows is exactly what the notification announced —
which a window recomputed as "the last 24 hours" could never be: opened at 21:00
it would show 21:00−24h, a different set from the one announced at 18:30. Between
midnight and 18:30 the screen therefore shows yesterday's capture, and that is
the intended reading, not a staleness bug.

**An empty period is not stored.** Nothing was announced and there is nothing to
show, so the assembly returns an unsaved empty record: the tab shows its empty
state, no row accumulates for the days a user saved nothing, and the next read
re-derives the same emptiness. There is no fallback to an older, fuller period
and no automatic switch to the weekly tab.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone, tzinfo
from typing import List, Optional
from zoneinfo import ZoneInfo

from media_summarizer.core.models.digest import (
    DigestMediaItem,
    DigestRecord,
    DigestType,
    UserDigestSettings,
)
from media_summarizer.utils import digest_db
from media_summarizer.utils import user_media as user_media_store

logger = logging.getLogger(__name__)


#: When the daily digest notification goes out, in the user's local time.
DAILY_SEND_TIME = time(hour=18, minute=30)

#: When the weekly digest notification goes out: Monday, local time.
WEEKLY_SEND_TIME = time(hour=9, minute=30)


def resolve_zone(iana_timezone: Optional[str]) -> tzinfo:
    """The zone to resolve a *read* in, falling back to UTC when there is none.

    The fallback is for reading only, and the asymmetry is deliberate. A screen
    has to render something, so an account whose zone has not been reported yet
    reads its digest in UTC — off by a few hours, never empty. A **notification**
    for that same account is not sent at all (see ``workers/digest/scheduler.py``):
    guessing the moment to interrupt someone is worse than not interrupting them,
    and the app reports its zone on every foreground pass, so the state is
    short-lived by construction.

    An unknown name gets the same treatment as an absent one. The field is gated
    by ``normalize_iana_timezone`` on the way in, so this only fires if the
    runtime's tz database is older than the one that accepted the value.
    """
    if not iana_timezone:
        return timezone.utc
    try:
        return ZoneInfo(iana_timezone)
    except Exception:
        logger.warning(
            "Unknown IANA zone %r; reading the digest in UTC", iana_timezone
        )
        return timezone.utc


def local_now(iana_timezone: Optional[str]) -> datetime:
    """``now`` carried in the account's own zone, which is what the windows read."""
    return datetime.now(resolve_zone(iana_timezone))


@dataclass(frozen=True)
class DigestWindow:
    """The period one notification announced.

    Half-open, ``[start, end)``, and that matters: a media saved at exactly the
    send instant belongs to the *next* period, so every media is announced once
    and none is skipped between two consecutive digests.
    """

    period_key: str
    start: datetime
    end: datetime
    #: The local instant this period's notification is due at — the last 18:30, or
    #: the last Monday 09:30. Always in the past, since both resolvers step back a
    #: period when the upcoming send has not happened yet.
    #:
    #: Distinct from ``end`` because the two coincide only for the daily window.
    #: The weekly one ends on the Monday at 00:00 and is announced nine and a half
    #: hours later, so a scheduler reading ``end`` as the send instant would notify
    #: the whole world's Sunday nights at midnight.
    send_at: datetime


def resolve_daily_window(now: datetime) -> DigestWindow:
    """The 24 hours the last 18:30 send announced.

    ``now`` carries the zone the send is scheduled in, and the window is derived
    from it — nothing here reads a clock of its own. Every caller now passes
    ``local_now(user.iana_timezone)`` (task-369), so the window is the user's
    18:30 and not UTC's; ``resolve_zone`` documents what an account with no zone
    gets.

    The ``period_key`` is the local date of the send, so the digest announced on
    the evening of the 12th is ``2026-05-12`` even though most of its content was
    saved on the 11th. It is therefore per-user by construction: two accounts in
    different zones legitimately hold different keys for the same evening.
    """
    send = now.replace(
        hour=DAILY_SEND_TIME.hour,
        minute=DAILY_SEND_TIME.minute,
        second=0,
        microsecond=0,
    )
    if send > now:
        # Before this evening's send: the digest currently live is yesterday's.
        send -= timedelta(days=1)
    return DigestWindow(
        period_key=send.date().isoformat(),
        start=send - timedelta(days=1),
        end=send,
        send_at=send,
    )


def resolve_weekly_window(now: datetime) -> DigestWindow:
    """The Monday-to-Sunday week the last Monday 09:30 send announced.

    The week *before* that send, never the one in progress: the ISO week the send
    happens in is nine hours old when the notification leaves, so announcing it
    would announce almost nothing.
    """
    send = now.replace(
        hour=WEEKLY_SEND_TIME.hour,
        minute=WEEKLY_SEND_TIME.minute,
        second=0,
        microsecond=0,
    ) - timedelta(days=now.weekday())  # weekday() is 0 on Monday
    if send > now:
        # Monday, before 09:30: the digest currently live is the previous send's.
        send -= timedelta(days=7)

    # `send` is a Monday, so the week that closed starts seven days before it and
    # ends where the send's own week starts.
    week_start = (send - timedelta(days=7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    iso_year, iso_week, _ = week_start.isocalendar()
    return DigestWindow(
        period_key=f"{iso_year}-W{iso_week:02d}",
        start=week_start,
        end=week_start + timedelta(days=7),
        send_at=send,
    )


async def _collect_window_items(
    user_id: str, window: DigestWindow
) -> List[DigestMediaItem]:
    """Every library row saved inside the window, oldest first.

    One query, whatever the period holds. There is deliberately no job lookup any
    more: the digest used to drop an item without a transcript because it existed
    to serve a pre-generated summary of it, and it now shows the media page, which
    states for itself where an item stands. So "saved in the period" is the whole
    of the rule, which is also what makes it checkable against ``user_media-dev``
    with one query.
    """
    records = [
        record
        for record in await user_media_store.list_library_for_user(user_id)
        if window.start <= record.saved_at < window.end
    ]
    # Sorted on the datetime, not on the serialised string: two rows written with
    # different offsets would compare wrong as text.
    records.sort(key=lambda record: record.saved_at)
    return [
        DigestMediaItem(
            media_item_id=record.media_item_id,
            added_at=record.saved_at.isoformat(),
        )
        for record in records
    ]


async def get_or_assemble_for_window(
    user_id: str, digest_type: DigestType, window: DigestWindow
) -> DigestRecord:
    """The stored capture of a period, assembling it on first read.

    The capture is what makes the screen agree with the notification: the first
    read of a period freezes the list, and every later read returns that list
    verbatim. Re-deriving it would be harmless — the window is entirely in the
    past, so it can no longer change — but it would cost a library scan per open.

    Public because the send path resolves its own window: the scheduler has to
    know whether a period is *due* before it assembles it, so it computes the
    window itself and hands it here rather than going through the two wrappers
    below. Assembly stays in one place either way.
    """
    existing = await digest_db.get_digest(user_id, digest_type, window.period_key)
    if existing is not None:
        return existing

    media_items = await _collect_window_items(user_id, window)
    record = DigestRecord(
        user_id=user_id,
        digest_type=digest_type,
        period_key=window.period_key,
        media_items=media_items,
    )
    # An empty period is not written. See the module docstring: there is nothing
    # to announce and nothing to show, and a row per silent day is pure noise.
    if media_items:
        await digest_db.save_digest(record)
    return record


async def get_or_assemble_daily_digest(
    user_id: str, *, iana_timezone: Optional[str]
) -> DigestRecord:
    """The daily digest currently live for this user.

    ``iana_timezone`` is keyword-only and has no default on purpose: it is the
    difference between the period the notification announced and a different one,
    and a caller that forgets it has to fail at import rather than answer the
    wrong day.
    """
    return await get_or_assemble_for_window(
        user_id, DigestType.DAILY, resolve_daily_window(local_now(iana_timezone))
    )


async def get_or_assemble_weekly_digest(
    user_id: str, *, iana_timezone: Optional[str]
) -> DigestRecord:
    """The weekly digest currently live for this user."""
    return await get_or_assemble_for_window(
        user_id, DigestType.WEEKLY, resolve_weekly_window(local_now(iana_timezone))
    )


async def get_user_digest_settings(user_id: str) -> UserDigestSettings:
    """Get digest settings for a user, returning defaults if none exist."""
    settings = await digest_db.get_user_digest_settings(user_id)
    if settings is None:
        return UserDigestSettings(user_id=user_id)
    return settings


async def update_user_digest_settings(
    user_id: str,
    *,
    digest_enabled: Optional[bool] = None,
    daily_digest_enabled: Optional[bool] = None,
    weekly_digest_enabled: Optional[bool] = None,
) -> UserDigestSettings:
    """Update digest settings for a user."""
    settings = await get_user_digest_settings(user_id)

    if digest_enabled is not None:
        settings.digest_enabled = digest_enabled
    if daily_digest_enabled is not None:
        settings.daily_digest_enabled = daily_digest_enabled
    if weekly_digest_enabled is not None:
        settings.weekly_digest_enabled = weekly_digest_enabled

    return await digest_db.save_user_digest_settings(settings)
