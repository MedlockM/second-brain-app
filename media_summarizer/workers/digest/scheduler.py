"""Digest scheduler: the producer of Digest push notifications.

Invoked by EventBridge on a fixed UTC grid (see
``infrastructure/terraform/modules/platform/lambda_digest_scheduler.tf``) and,
on every tick, answers one question per account: *is a Digest period due for
this person right now, in their own zone?*

**Why a sweep and not a per-user schedule.** The daily Digest goes out at 18:30
and the weekly one on Monday at 09:30 — both in the *user's* local time, so
there is no single UTC instant to fire at. One EventBridge schedule per account
does not scale and one Lambda per zone is 400-odd rules to maintain. Instead a
single tick runs often enough that every local send instant falls inside one of
its passes, and the tick itself decides who is due. Task-368's benchmark
measured that across the 498 zones of the IANA database, 18:30 local and Monday
09:30 local only ever land on UTC minutes :00, :30 and :45 — the grid is chosen
to cover them with room to spare.

**Dueness is a grace window, not an equality.** A period is due when its send
instant is behind us by less than ``SEND_GRACE`` and nothing has been announced
for it yet. Matching the minute exactly would be tighter but brittle in both
directions: a tick that fails and is retried a minute late would drop the
notification entirely, and a future zone at an offset the grid does not cover
would go permanently silent. With a grace window, the worst case is a
notification a few minutes late.

**One notification per period per account, whatever the sweep does.** The
guarantee does not come from this module's control flow — 72 passes a day, plus
Lambda retries, make that unprovable. It comes from
``digest_db.mark_digest_published``, a conditional write on ``published_at``
that exactly one caller can win. The message is enqueued only by that winner.

**Three ways an account produces nothing**, all silent and all normal: the
period holds no media (nothing was captured, so there is nothing to announce and
no row is even written), the account has never reported an IANA zone (guessing
when to interrupt someone is worse than not interrupting them, and the app
reports its zone on every foreground pass so the state is short-lived), or the
settings say no.

Usage (a single tick, same as the Lambda does):
  uv run python -m media_summarizer.workers.digest.scheduler
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from media_summarizer.core.models.digest import DigestType
from media_summarizer.core.services import digest_service
from media_summarizer.utils import digest_db, push_token_db, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

#: Where the notification goes once a period is claimed. Consumed by
#: ``workers/push_notification_worker.py``.
PUSH_NOTIFICATION_QUEUE = required_env("PUSH_NOTIFICATION_QUEUE")

#: How late a send instant may be and still be worth announcing.
#:
#: An hour is long enough to absorb a failed tick, a cold start and a clock skew,
#: and short enough that a notification never arrives in a context where it reads
#: as wrong — 19:30 for an 18:30 Digest is a late notification, 23:00 would be a
#: bug. Nothing is lost past the grace: the Digest is stored and the tab shows it.
SEND_GRACE = timedelta(hours=1)

#: Event source of the scheduled token purge, set by the EventBridge target in
#: ``lambda_digest_scheduler.tf``. Routed on in ``handle_event``.
PURGE_EVENT_SOURCE = "media-summarizer.push-token-purge"


@dataclass(frozen=True)
class _Account:
    """An account the sweep can reason about: an id and a zone to read it in."""

    user_id: str
    iana_timezone: str


async def _list_accounts_with_timezone() -> List[_Account]:
    """Every account that has reported an IANA zone, as one Scan.

    Accounts with no zone are dropped here rather than later, so the rest of the
    tick never has to carry an ``Optional`` it must not fall back on.

    A full Scan per tick is the right shape at this scale: the projection is two
    short attributes, and 72 ticks a day over a few thousand accounts stays in
    cents per month. Above roughly five thousand accounts, task-368's benchmark
    documents the escape hatch — a GSI on the zone name, queried only for the
    zones whose local time is currently a send instant.
    """
    from media_summarizer.utils.database_async import (
        USERS_TABLE,
        _dynamodb_client_kwargs,
        get_session,
    )

    session = get_session()
    accounts: List[_Account] = []
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(USERS_TABLE)
        # `id` needs no alias; `iana_timezone` is not a reserved word either, but
        # the alias costs nothing and survives a rename.
        scan_kwargs: Dict[str, Any] = {
            "ProjectionExpression": "id, #tz",
            "ExpressionAttributeNames": {"#tz": "iana_timezone"},
        }
        while True:
            resp = await table.scan(**scan_kwargs)
            for item in resp.get("Items", []):
                zone = (item.get("iana_timezone") or "").strip()
                if not zone:
                    continue
                accounts.append(_Account(user_id=item["id"], iana_timezone=zone))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key
    return accounts


def _is_due(window: digest_service.DigestWindow, now_local: datetime) -> bool:
    """Is this window's send instant recent enough to still announce?

    ``send_at`` is always in the past — the resolvers step back a period when the
    upcoming send has not happened — so this is really "how long ago", and the
    lower bound only guards against a caller that hands in a window resolved from
    a different clock.
    """
    since_send = now_local - window.send_at
    return timedelta(0) <= since_send <= SEND_GRACE


def _notification_message(
    account: _Account,
    digest_type: DigestType,
    period_key: str,
    item_count: int,
) -> Dict[str, Any]:
    """The queue message for one notification.

    The body is a count and nothing else, deliberately. Expo's push service is a
    third party that relays the payload and whose staff can see it while
    debugging, so nothing about *what* the user saved travels: no title, no
    source, no excerpt. The count is enough to make the notification worth
    opening, and everything past that is behind the user's own authentication.

    ``data`` is what the app routes on when the notification is opened — the
    Digest tab to select, and the period so a stale notification opened days
    later is still legible in logs.
    """
    plural = "item" if item_count == 1 else "items"
    if digest_type is DigestType.DAILY:
        title = "Your daily digest is ready"
        body = f"You saved {item_count} {plural} today."
    else:
        title = "Your weekly digest is ready"
        body = f"You saved {item_count} {plural} last week."

    return {
        "notification_type": "send",
        "user_id": account.user_id,
        "title": title,
        "body": body,
        "data": {
            "digest_type": digest_type.value,
            "period_key": period_key,
        },
    }


async def _notify_if_due(
    account: _Account,
    digest_type: DigestType,
    window: digest_service.DigestWindow,
    now_local: datetime,
) -> bool:
    """Announce one period for one account, if there is anything to announce.

    Returns whether a message was enqueued. The order of the checks is the point:
    the cheap local ones first, the settings read next, the library assembly only
    for a period actually due, and the conditional claim last — right before the
    enqueue, so the window in which a crash could duplicate a notification is a
    single SQS call wide.
    """
    if not _is_due(window, now_local):
        return False

    settings = await digest_service.get_user_digest_settings(account.user_id)
    if not settings.digest_enabled:
        return False
    if digest_type is DigestType.DAILY and not settings.daily_digest_enabled:
        return False
    if digest_type is DigestType.WEEKLY and not settings.weekly_digest_enabled:
        return False

    digest = await digest_service.get_or_assemble_for_window(
        account.user_id, digest_type, window
    )
    if not digest.media_items:
        # Nothing captured in the period. No row was written and none is needed:
        # there is no "nothing today" notification.
        return False

    if not await digest_db.mark_digest_published(
        account.user_id, digest_type, window.period_key
    ):
        # Another tick already claimed this period. This is the normal outcome of
        # every pass after the first one inside the grace window.
        return False

    await sqs.send_message(
        queue_name=PUSH_NOTIFICATION_QUEUE,
        message_body=_notification_message(
            account, digest_type, window.period_key, len(digest.media_items)
        ),
    )
    log_event(
        logger,
        logging.INFO,
        "digest.notification.queued",
        "Digest notification queued",
        user_id=account.user_id,
        queue=PUSH_NOTIFICATION_QUEUE,
        digest_type=digest_type.value,
        period_key=window.period_key,
        item_count=len(digest.media_items),
    )
    return True


async def run_tick() -> int:
    """One sweep over every account with a zone. Returns notifications queued.

    A failure on one account is logged and skipped rather than raised: one
    account's broken settings row must not cost the whole world its Digest. The
    tick as a whole only fails on something that would fail for everyone — the
    Scan itself, or the queue being unreachable.
    """
    accounts = await _list_accounts_with_timezone()
    queued = 0

    for account in accounts:
        try:
            now_local = digest_service.local_now(account.iana_timezone)
            for digest_type, window in (
                (DigestType.DAILY, digest_service.resolve_daily_window(now_local)),
                (DigestType.WEEKLY, digest_service.resolve_weekly_window(now_local)),
            ):
                if await _notify_if_due(account, digest_type, window, now_local):
                    queued += 1
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "digest.notification.failed",
                "Digest notification sweep failed for one account",
                user_id=account.user_id,
                error_type=type(exc).__name__,
                exc_info=exc,
            )

    log_event(
        logger,
        logging.INFO,
        "digest.sweep.completed",
        "Digest notification sweep completed",
        account_count=len(accounts),
        queued=queued,
    )
    return queued


async def run_token_purge() -> int:
    """Drop push tokens no device has claimed in ninety days.

    Here rather than in its own Lambda because it is the same concern on the same
    schedule granularity, and a second container image for one Scan is not worth
    the deploy surface. A token is otherwise deleted the moment Expo reports the
    device is gone (``DeviceNotRegistered``); this catches the devices that stop
    reporting without Expo ever noticing — a phone wiped, an app uninstalled with
    the notification permission already off.
    """
    deleted = await push_token_db.delete_stale_tokens()
    log_event(
        logger,
        logging.INFO,
        "push_token.purge.completed",
        "Stale push tokens purged",
        deleted_count=deleted,
        retention_days=push_token_db.STALE_TOKEN_DAYS,
    )
    return deleted


def handle_event(event: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Lambda entry point, routing on the EventBridge target's ``source``.

    Two schedules share this function: the frequent Digest sweep and the daily
    token purge. Called from ``workers/lambda_handlers.py`` so the cold-start
    secret load happens once and in one place, exactly like
    ``media_lifecycle_handler``.
    """
    source = (event or {}).get("source") if isinstance(event, dict) else None
    if source == PURGE_EVENT_SOURCE:
        return {"deleted_tokens": asyncio.run(run_token_purge())}
    return {"queued_notifications": asyncio.run(run_tick())}


if __name__ == "__main__":
    from media_summarizer.utils.logging_config import setup_logging

    setup_logging("digest-scheduler")
    asyncio.run(run_tick())
