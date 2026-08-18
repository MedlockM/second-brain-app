"""
Authentication endpoints for local email/password with 30-day absolute refresh sessions.

Both tokens travel in the JSON body: the access token as ``access_token`` and the
refresh token as ``refresh_token``. The only client is the mobile app, which keeps
the refresh token in its secure store and posts it back to /refresh — it cannot
read an httpOnly cookie, which is why the cookie transport is gone (task-293).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

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
    RefreshRequest,
    RegisterRequest,
    TokenType,
    TokenVerificationResponse,
)
from media_summarizer.utils import database_async
from media_summarizer.utils.auth_utils import (
    create_access_token,
    create_token_payload,
    get_access_token_expires_seconds,
    get_refresh_token_expires_at,
    hash_password,
    verify_password,
)
from media_summarizer.utils.database_async import DynamoDBConnection, get_db

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

    # Create refresh token (absolute lifetime)
    refresh_expires_at = get_refresh_token_expires_at()
    refresh = AuthToken.create_refresh_token(
        user_id=user.id, email=user.email, absolute_expires_at=refresh_expires_at
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
        user={"id": user.id, "email": user.email, "reading_language": user.reading_language},
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

    # Issue refresh token (absolute lifetime)
    refresh_expires_at = get_refresh_token_expires_at()
    refresh = AuthToken.create_refresh_token(
        user_id=user.id, email=user.email, absolute_expires_at=refresh_expires_at
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
        user={"id": user.id, "email": user.email, "reading_language": user.reading_language},
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

    if (
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

    # Rotate refresh: mark used + inactive, then create a new one with same absolute expiry
    auth_token.mark_as_used()
    await database_async.update_auth_token(auth_token)

    new_refresh = AuthToken.create_refresh_token(
        user_id=user.id,
        email=user.email,
        absolute_expires_at=auth_token.expires_at,
    )
    new_refresh = await database_async.create_auth_token(new_refresh)

    # New access token
    access_seconds = get_access_token_expires_seconds()
    access_token = create_access_token(
        data=create_token_payload(user_id=user.id, email=user.email),
        expires_delta=timedelta(seconds=access_seconds),
    )

    return TokenVerificationResponse(
        access_token=access_token,
        refresh_token=new_refresh.token,
        token_type="bearer",
        expires_in=access_seconds,
        user={"id": user.id, "email": user.email, "reading_language": user.reading_language},
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    current_user: AuthUser = Depends(get_current_user),
    db: DynamoDBConnection = Depends(get_db),
):
    # Revoke every refresh token of the user; the client drops its stored copy
    await database_async.revoke_user_tokens(current_user.id, TokenType.REFRESH_TOKEN)
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


class UpdateMeRequest(BaseModel):
    """Request model for updating the current user's preferences."""

    reading_language: Optional[str] = Field(
        default=None, description="Preferred reading language (ISO 639-1 code)"
    )


@router.patch("/me", response_model=AuthUser)
async def update_current_user(
    request: UpdateMeRequest,
    current_user: AuthUser = Depends(get_current_user),
    db: DynamoDBConnection = Depends(get_db),
):
    """Update the current user's preferences (e.g., reading_language)."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    user = await database_async.get_user_by_id(current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    update_data = {}

    if request.reading_language is not None:
        lang = request.reading_language.lower().strip()
        if lang not in V1_READING_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported reading language: {lang}. Supported: {sorted(V1_READING_LANGUAGES)}",
            )
        update_data["reading_language"] = lang

    if update_data:
        user.update(**update_data)
        user = await database_async.update_user(user)

    return AuthUser(id=user.id, email=user.email, reading_language=user.reading_language)
