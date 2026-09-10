"""
Authentication endpoints for local email/password sessions.

The session is permanent for an active user (task-294): the refresh token carries a
*sliding* one-year expiry, reposed at every rotation, with no absolute cap. Opening
the app at least once a year is enough to never sign in again.

Both tokens travel in the JSON body: the access token as ``access_token`` and the
refresh token as ``refresh_token``. The only client is the mobile app, which keeps
the refresh token in its secure store and posts it back to /refresh — it cannot
read an httpOnly cookie, which is why the cookie transport is gone (task-293).

Rotation is single-use, so /refresh keeps a 60-second grace window: a token consumed
inside that window replays the pair it was exchanged for instead of answering 401,
which is what stops two concurrent refreshes from signing the user out.

/logout closes one device session, not the account: it revokes the lineage of the
refresh token it is given. Erasing every lineage of an account is account deletion's
job (core/services/account_deletion_service.py), which deletes the rows outright.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models import User
from media_summarizer.core.models.auth import (
    AuthToken,
    AuthUser,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenType,
    TokenVerificationResponse,
)
from media_summarizer.utils import database_async
from media_summarizer.utils.auth_utils import (
    REFRESH_ROTATION_GRACE_SECONDS,
    create_access_token,
    create_token_payload,
    get_access_token_expires_seconds,
    get_refresh_token_expires_at,
    hash_password,
    verify_password,
)
from media_summarizer.utils.database_async import DynamoDBConnection, get_db
from media_summarizer.utils.logging_config import log_event
from media_summarizer.utils.timezones import normalize_iana_timezone

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenVerificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    db: DynamoDBConnection = Depends(get_db),
):
    email = request.email.lower().strip()
    existing = await database_async.get_user_by_email(email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use"
        )

    user = User(
        email=email,
        password_hash=hash_password(request.password),
        auth_provider="local",
        email_verified_at=datetime.now(timezone.utc),
    )
    user = await database_async.create_user(user)

    # Refresh token: opens a new device-session lineage, sliding expiry
    refresh = AuthToken.create_refresh_token(
        user_id=user.id, email=user.email, expires_at=get_refresh_token_expires_at()
    )
    refresh = await database_async.create_auth_token(refresh)

    # Access token: registration opens a session, no second /login round-trip needed
    access_seconds = get_access_token_expires_seconds()
    access_token = create_access_token(
        data=create_token_payload(user_id=user.id, email=user.email),
        expires_delta=timedelta(seconds=access_seconds),
    )
    return TokenVerificationResponse(
        access_token=access_token,
        refresh_token=refresh.token,
        token_type="bearer",
        expires_in=access_seconds,
        user=AuthUser.from_user(user).model_dump(),
    )


@router.post("/login", response_model=TokenVerificationResponse)
async def login(request: LoginRequest, db: DynamoDBConnection = Depends(get_db)):
    email = request.email.lower().strip()
    user = await database_async.get_user_by_email(email)
    if (
        not user
        or not user.password_hash
        or not verify_password(request.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Refresh token: opens a new device-session lineage, sliding expiry
    refresh = AuthToken.create_refresh_token(
        user_id=user.id, email=user.email, expires_at=get_refresh_token_expires_at()
    )
    refresh = await database_async.create_auth_token(refresh)

    # Access token
    access_seconds = get_access_token_expires_seconds()
    access_token = create_access_token(
        data=create_token_payload(user_id=user.id, email=user.email),
        expires_delta=timedelta(seconds=access_seconds),
    )
    return TokenVerificationResponse(
        access_token=access_token,
        refresh_token=refresh.token,
        token_type="bearer",
        expires_in=access_seconds,
        user=AuthUser.from_user(user).model_dump(),
    )


@router.post("/refresh", response_model=TokenVerificationResponse)
async def refresh_token(
    request: RefreshRequest, db: DynamoDBConnection = Depends(get_db)
):
    # Load token from DB
    auth_token = await database_async.get_auth_token_by_token(request.refresh_token)
    if not auth_token or auth_token.token_type != TokenType.REFRESH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # A token consumed moments ago is a concurrent refresh, not an attack: replay the
    # pair its rotation minted. Checked before is_active/used_at, since a rotated token
    # is precisely an inactive, used one.
    replay = auth_token.rotation_replay(REFRESH_ROTATION_GRACE_SECONDS)

    if replay is None and (
        not auth_token.is_active
        or auth_token.is_expired()
        or auth_token.used_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired or used refresh token",
        )

    # Get user
    user = await database_async.get_user_by_id(auth_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    access_seconds = get_access_token_expires_seconds()

    if replay is not None:
        access_token, refresh_token_value = replay
        # The replayed access token was minted up to a minute ago: report what is left
        # of it, not a full lifetime, or the client would trust it past its expiry.
        expires_in = max(1, access_seconds - int(auth_token.rotated_seconds_ago()))
        log_event(
            logger,
            logging.INFO,
            "auth.refresh.grace_replay",
            "Replayed the rotation of a refresh token consumed moments ago",
            user_id=user.id,
            lineage_id=auth_token.lineage_id,
            rotated_seconds_ago=int(auth_token.rotated_seconds_ago()),
        )
    else:
        # Rotate: sliding expiry recomputed from now, same lineage, and the successor
        # is written before the parent is consumed so a failure in between leaves the
        # caller with a token that still works.
        new_refresh = AuthToken.create_refresh_token(
            user_id=user.id,
            email=user.email,
            expires_at=get_refresh_token_expires_at(),
            lineage_id=auth_token.lineage_id,
        )
        new_refresh = await database_async.create_auth_token(new_refresh)

        access_token = create_access_token(
            data=create_token_payload(user_id=user.id, email=user.email),
            expires_delta=timedelta(seconds=access_seconds),
        )

        auth_token.mark_as_rotated(
            refresh_token=new_refresh.token, access_token=access_token
        )
        await database_async.update_auth_token(auth_token)

        refresh_token_value = new_refresh.token
        expires_in = access_seconds

    return TokenVerificationResponse(
        access_token=access_token,
        refresh_token=refresh_token_value,
        token_type="bearer",
        expires_in=expires_in,
        user=AuthUser.from_user(user).model_dump(),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: LogoutRequest,
    current_user: AuthUser = Depends(get_current_user),
    db: DynamoDBConnection = Depends(get_db),
):
    """Sign out the calling device only.

    The refresh token names the device session; the access token only proves who
    owns it. An unknown token — already revoked, or belonging to someone else — is
    a no-op success: logout is idempotent and must not double as a probe telling a
    caller whether a token exists.
    """
    auth_token = await database_async.get_auth_token_by_token(request.refresh_token)
    if (
        auth_token is None
        or auth_token.token_type != TokenType.REFRESH_TOKEN
        or auth_token.user_id != current_user.id
    ):
        log_event(
            logger,
            logging.INFO,
            "auth.logout.unknown_refresh_token",
            "Logout presented a refresh token with no live session to close",
            user_id=current_user.id,
        )
        return {"message": "Successfully logged out"}

    revoked = await database_async.revoke_refresh_token_lineage(
        current_user.id, auth_token.lineage_id
    )
    log_event(
        logger,
        logging.INFO,
        "auth.logout.lineage_revoked",
        "Signed out one device session",
        user_id=current_user.id,
        lineage_id=auth_token.lineage_id,
        tokens_revoked=revoked,
    )
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=AuthUser)
async def get_current_user_info(current_user: AuthUser = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    return current_user


# V1 supported reading languages (ISO 639-1 codes)
V1_READING_LANGUAGES = {"fr", "en", "es", "de", "it", "pt", "nl", "ja", "zh", "ar", "hi"}

# The stable identifier of a reading-language change refused by the once-a-month
# guard-rail (see ``READING_LANGUAGE_CHANGE_INTERVAL``). The response carries this
# code and the date the guard lifts, never a sentence: the app words the refusal
# from its own catalogue, in the reader's interface language (task-359 convention).
READING_LANGUAGE_CHANGE_TOO_SOON = "reading_language_change_too_soon"


class UpdateMeRequest(BaseModel):
    """Request model for updating the current user's preferences."""

    reading_language: Optional[str] = Field(
        default=None, description="Preferred reading language (ISO 639-1 code)"
    )
    iana_timezone: Optional[str] = Field(
        default=None,
        description=(
            "IANA zone name of the device, e.g. 'Europe/Paris'. Never a UTC offset: "
            "a stored '+02:00' is wrong six months a year. Sent by the app on every "
            "return to the foreground, and only when it differs from what is stored."
        ),
    )


@router.patch("/me", response_model=AuthUser)
async def update_current_user(
    request: UpdateMeRequest,
    current_user: AuthUser = Depends(get_current_user),
    db: DynamoDBConnection = Depends(get_db),
):
    """Update the current user's preferences (reading language, device time zone).

    The reading language is rate-limited to one change per month, per account —
    it is the only preference here whose move costs money, since it re-translates
    every media the reader opens next. Setting a first language is not a change
    and is never refused; a second move inside the window answers 429 with
    ``reading_language_change_too_soon`` and the date the guard lifts.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    user = await database_async.get_user_by_id(current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    update_data: Dict[str, Any] = {}

    if request.reading_language is not None:
        lang = request.reading_language.lower().strip()
        if lang not in V1_READING_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                # The supported set used to travel as `sorted(...)`, i.e. a Python
                # list repr with its brackets and quotes. Joined instead: the app
                # picks from a fixed list and cannot reach this, but a refusal that
                # prints `['ar', 'de', …]` is not a sentence (task-397).
                detail=(
                    f"Unsupported reading language: {lang}. Supported: "
                    f"{', '.join(sorted(V1_READING_LANGUAGES))}"
                ),
            )
        # Re-sending the language already stored is not a change: it must neither
        # spend the monthly allowance nor be refused. The app does exactly that on
        # a Save it did not need to make.
        if lang != user.reading_language:
            if user.reading_language is None:
                # First setting of the account — the onboarding pick, or a first
                # visit to the setting. Never limited, and it does not start the
                # clock either: the guard-rail counts *changes*.
                update_data["reading_language"] = lang
            else:
                available_at = user.reading_language_change_available_at()
                if available_at is not None:
                    log_event(
                        logger,
                        logging.WARNING,
                        "auth.reading_language.change_refused",
                        "Reading language change refused: one change per month",
                        user_id=user.id,
                        error_code=READING_LANGUAGE_CHANGE_TOO_SOON,
                        available_at=available_at.isoformat(),
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error_code": READING_LANGUAGE_CHANGE_TOO_SOON,
                            "message": "The reading language can only be changed once a month",
                            "available_at": available_at.isoformat(),
                        },
                    )
                update_data["reading_language"] = lang
                update_data["reading_language_changed_at"] = datetime.now(timezone.utc)

    if request.iana_timezone is not None:
        zone = normalize_iana_timezone(request.iana_timezone)
        if zone is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported time zone: {request.iana_timezone}. "
                    "Expected an IANA zone name such as 'Europe/Paris', not a UTC offset."
                ),
            )
        update_data["iana_timezone"] = zone

    # Only write when a value actually moves. The app re-reads the device zone on
    # every return to the foreground, so without this a user who never travels
    # would pay a DynamoDB write per app opening for a value that never changes.
    changed = {
        field: value
        for field, value in update_data.items()
        if getattr(user, field) != value
    }
    if changed:
        user.update(**changed)
        user = await database_async.update_user(user)

    return AuthUser.from_user(user)
