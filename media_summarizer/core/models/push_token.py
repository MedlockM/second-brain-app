"""
Push notification tokens: one row per device an account has registered.

DynamoDB table: ``user_push_tokens``
- PK: ``user_id`` (S)
- SK: ``push_token`` (S) — the ``ExponentPushToken[...]`` string itself

**A push token is device data, not library data.** It therefore does not fall
under the central retention rule of ``docs/DATA_RETENTION.md`` ("a user's library
has no retention clock") but under the per-user-table regime, and three things
follow, all of them deliberate:

1. **No ``purge_at`` and no ``deleted_at``.** A dead token is *deleted*, never
   marked. ``scripts/check_purge_at_writers.py`` fails CI on a second writer of
   either attribute, and this table has no TTL at all.
2. **It goes with the account.** ``USER_PUSH_TOKENS_TABLE`` is listed in
   ``_USER_PARTITION_TABLES`` of ``core/services/account_deletion_service.py``,
   so ``purge_account`` empties it with everything else.
3. **``last_seen_at`` is refreshed on every app launch**, which is what makes the
   90-day sweep in ``utils/push_token_db.py`` able to catch the uninstalls no
   provider ever reports. Expo's own documentation warns that
   ``DeviceNotRegistered`` "takes an undefined amount of time and is often
   impossible to test", so the sweep is the only reliable end of a token's life
   besides account deletion.

The token value is a secret-shaped string: anyone holding it can push to that
device. It is never logged — see ``_SENSITIVE_FIELD_NAMES`` in
``utils/logging_config.py``, which redacts ``push_token`` and ``expo_push_token``
by name as defence in depth against a careless ``log_event`` call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PushTokenPlatform(str, Enum):
    """Which store the app registering this token came from.

    Recorded for diagnosis only: an Expo push token routes itself, so nothing in
    the send path branches on this value.
    """

    IOS = "ios"
    ANDROID = "android"


class PushToken(BaseModel):
    """One device's registration for an account."""

    user_id: str
    push_token: str
    platform: PushTokenPlatform
    created_at: str = Field(default_factory=_now_iso)
    last_seen_at: str = Field(default_factory=_now_iso)

    def to_dynamodb_item(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "push_token": self.push_token,
            "platform": self.platform.value,
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
        }

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "PushToken":
        return cls(
            user_id=item["user_id"],
            push_token=item["push_token"],
            platform=PushTokenPlatform(item.get("platform", "ios")),
            created_at=item.get("created_at", _now_iso()),
            last_seen_at=item.get("last_seen_at", _now_iso()),
        )

    def __repr__(self) -> str:
        # No token in the representation: this object ends up in tracebacks.
        return f"<PushToken(user_id='{self.user_id}', platform='{self.platform.value}')>"
