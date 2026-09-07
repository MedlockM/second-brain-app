"""
Device registration for Digest push notifications.

- ``POST /api/push-token``   register this device, or refresh its ``last_seen_at``
- ``DELETE /api/push-token`` drop this device (sign-out)

Both answer 204. Nothing is echoed back, deliberately: the only thing the server
could return is the token the client just sent, and a response body carrying it
is one more place it can be logged by an intermediary.

**The DELETE is not optional.** A device is registered under the account that was
signed in when it launched. Without a sign-out unregistration, a second account
signing in on the same phone would leave the token registered under *both*, and
the first account's Digest notification would land on a screen the second account
is looking at. The mobile client calls it from ``AuthContext.logout``, before the
session is torn down, because it needs the session to authenticate.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models.push_token import PushTokenPlatform
from media_summarizer.utils import push_token_db
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
)

router = APIRouter()
logger = logging.getLogger(__name__)

#: The two shapes Expo's SDK hands back from ``getExpoPushTokenAsync``.
#:
#: Checked here so a device that reported a *native* APNs/FCM token — which the
#: Expo push API refuses — is rejected at registration rather than silently
#: accumulating rows that every send will fail on.
_EXPO_TOKEN_PREFIXES = ("ExponentPushToken[", "ExpoPushToken[")


class PushTokenRequest(BaseModel):
    """The token, and which platform reported it."""

    expo_push_token: str = Field(
        ..., description="Expo push token, e.g. ExponentPushToken[...]"
    )
    platform: PushTokenPlatform = Field(..., description="ios or android")

    @field_validator("expo_push_token")
    @classmethod
    def must_be_an_expo_token(cls, value: str) -> str:
        token = value.strip()
        if not token.startswith(_EXPO_TOKEN_PREFIXES) or not token.endswith("]"):
            # The message names the shape, never the value received.
            raise ValueError(
                "Not an Expo push token: expected ExponentPushToken[...] or "
                "ExpoPushToken[...]"
            )
        return token


class PushTokenDeleteRequest(BaseModel):
    """The token to forget. No platform: the pair (user, token) is the key."""

    expo_push_token: str = Field(..., description="Expo push token to unregister")


@router.post("/push-token", status_code=status.HTTP_204_NO_CONTENT)
async def register_push_token(
    payload: PushTokenRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> Response:
    """Register this device for the authenticated account, or refresh it."""
    token = bind_log_context(user_id=current_user.id)
    try:
        await push_token_db.save_token(
            current_user.id, payload.expo_push_token, payload.platform
        )
        log_event(
            logger,
            logging.INFO,
            "push_token.registered",
            "Push token registered",
            user_id=current_user.id,
            platform=payload.platform.value,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "push_token.register.failed",
            "Failed to register push token",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register push token",
        )
    finally:
        reset_log_context(token)


@router.delete("/push-token", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_push_token(
    payload: PushTokenDeleteRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> Response:
    """Forget this device. Idempotent: deleting an absent row is a success."""
    token = bind_log_context(user_id=current_user.id)
    try:
        await push_token_db.delete_token(
            current_user.id, payload.expo_push_token.strip()
        )
        log_event(
            logger,
            logging.INFO,
            "push_token.unregistered",
            "Push token unregistered",
            user_id=current_user.id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "push_token.unregister.failed",
            "Failed to unregister push token",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unregister push token",
        )
    finally:
        reset_log_context(token)
