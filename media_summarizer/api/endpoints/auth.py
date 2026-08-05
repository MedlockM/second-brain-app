"""
Authentication endpoints for local email/password with 30-day absolute refresh sessions.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models import User
from media_summarizer.core.models.auth import (
    AuthToken,
    AuthUser,
    EmailVerificationRequest,
    LoginRequest,
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

# Config
REFRESH_COOKIE_NAME = os.environ.get("COOKIE_NAME_REFRESH", "refresh_token")
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax").lower()  # lax|strict|none


def _set_refresh_cookie(
    response: Response, token_value: str, absolute_expires_at: datetime
) -> None:
    max_age = int((absolute_expires_at - datetime.now(timezone.utc)).total_seconds())
    max_age = max(0, max_age)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token_value,
        max_age=max_age,
        expires=max_age,
        domain=COOKIE_DOMAIN,
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        domain=COOKIE_DOMAIN,
        path="/",
    )


def _refresh_cookie_clear_headers() -> dict[str, str]:
    response = Response()
    _clear_refresh_cookie(response)
    cookie_header = response.headers.get("set-cookie")
    if not cookie_header:
        return {}
    return {"set-cookie": cookie_header}


@router.post("/register", response_model=AuthUser, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    response: Response,
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
    _set_refresh_cookie(response, refresh.token, refresh.expires_at)

    return AuthUser(id=user.id, email=user.email, reading_language=user.reading_language)


@router.post("/login", response_model=TokenVerificationResponse)
async def login(
    request: LoginRequest, response: Response, db: DynamoDBConnection = Depends(get_db)
):
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
    _set_refresh_cookie(response, refresh.token, refresh.expires_at)

    # Access token
    access_seconds = get_access_token_expires_seconds()
    access_token = create_access_token(
        data=create_token_payload(user_id=user.id, email=user.email),
        expires_delta=timedelta(seconds=access_seconds),
    )
    return TokenVerificationResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=access_seconds,
        user={"id": user.id, "email": user.email, "reading_language": user.reading_language},
    )


@router.post("/refresh", response_model=TokenVerificationResponse)
async def refresh_token(
    request: Request, response: Response, db: DynamoDBConnection = Depends(get_db)
):
    clear_headers = _refresh_cookie_clear_headers()
    token_value = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
            headers=clear_headers,
        )

    # Load token from DB
    auth_token = await database_async.get_auth_token_by_token(token_value)
    if not auth_token or auth_token.token_type != TokenType.REFRESH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers=clear_headers,
        )

    if (
        not auth_token.is_active
        or auth_token.is_expired()
        or auth_token.used_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired or used refresh token",
            headers=clear_headers,
        )

    # Get user
    user = await database_async.get_user_by_id(auth_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers=clear_headers,
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
    _set_refresh_cookie(response, new_refresh.token, new_refresh.expires_at)

    # New access token
    access_seconds = get_access_token_expires_seconds()
    access_token = create_access_token(
        data=create_token_payload(user_id=user.id, email=user.email),
        expires_delta=timedelta(seconds=access_seconds),
    )

    return TokenVerificationResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=access_seconds,
        user={"id": user.id, "email": user.email, "reading_language": user.reading_language},
    )


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    request: EmailVerificationRequest, db: DynamoDBConnection = Depends(get_db)
):
    """
    Legacy compatibility endpoint.
    Email verification by mail has been removed; accounts are auto-verified at registration.
    """
    email = request.email.lower().strip()

    user = await database_async.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not getattr(user, "email_verified_at", None):
        user.email_verified_at = datetime.now(timezone.utc)
        await database_async.update_user(user)

    return {"message": "Email verification is disabled; account is active"}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification_email(
    current_user: AuthUser = Depends(get_current_user),
    db: DynamoDBConnection = Depends(get_db),
):
    """
    Legacy compatibility endpoint.
    Email verification by mail has been removed.
    """
    user = await database_async.get_user_by_id(current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not getattr(user, "email_verified_at", None):
        user.email_verified_at = datetime.now(timezone.utc)
        await database_async.update_user(user)

    return {"message": "Email verification is disabled; account is active"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    current_user: AuthUser = Depends(get_current_user),
    db: DynamoDBConnection = Depends(get_db),
):
    # Revoke refresh tokens for the user and clear cookie
    await database_async.revoke_user_tokens(current_user.id, TokenType.REFRESH_TOKEN)
    _clear_refresh_cookie(response)
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
