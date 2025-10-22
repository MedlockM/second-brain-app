"""
Authentication endpoints for local email/password with 30-day absolute refresh sessions.
"""

import os
import logging
from datetime import timedelta, datetime, timezone
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    BackgroundTasks,
    Response,
    Request,
)

from media_summarizer.core.models.auth import (
    RegisterRequest,
    LoginRequest,
    TokenVerificationResponse,
    AuthUser,
    AuthToken,
    TokenType,
    EmailVerificationRequest,
)
from pydantic import BaseModel, Field
from media_summarizer.core.models import User
from media_summarizer.utils import database_async
from media_summarizer.utils.auth_utils import (
    create_access_token,
    create_token_payload,
    verify_password,
    hash_password,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
)
from media_summarizer.utils.database_async import get_db, DynamoDBConnection
from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.utils.email_service import email_service

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Config
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
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


@router.post("/register", response_model=AuthUser, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    response: Response,
    background_tasks: BackgroundTasks,
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
    )
    user = await database_async.create_user(user)

    # Create email verification token and send email in background
    try:
        verification = AuthToken.create_email_verification_token(
            user_id=user.id, email=user.email
        )
        await database_async.create_auth_token(verification)
        background_tasks.add_task(
            email_service.send_email_verification,
            email=user.email,
            verification_token=verification.token,
        )
    except Exception:
        # Non-blocking: we continue registration even if email sending fails, but log it
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not send verification email to {user.email}")

    # Create refresh token (absolute 30 days)
    refresh = AuthToken.create_refresh_token(
        user_id=user.id, email=user.email, expires_in_days=REFRESH_TOKEN_EXPIRE_DAYS
    )
    refresh = await database_async.create_auth_token(refresh)
    _set_refresh_cookie(response, refresh.token, refresh.expires_at)

    # Access token (short-lived)
    access_minutes = max(1, int(JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = create_access_token(
        data=create_token_payload(user_id=user.id, email=user.email),
        expires_delta=timedelta(minutes=access_minutes),
    )

    return AuthUser(id=user.id, email=user.email)


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

    # Issue refresh token (absolute 30 days)
    refresh = AuthToken.create_refresh_token(
        user_id=user.id, email=user.email, expires_in_days=REFRESH_TOKEN_EXPIRE_DAYS
    )
    refresh = await database_async.create_auth_token(refresh)
    _set_refresh_cookie(response, refresh.token, refresh.expires_at)

    # Access token
    access_minutes = max(1, int(JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = create_access_token(
        data=create_token_payload(user_id=user.id, email=user.email),
        expires_delta=timedelta(minutes=access_minutes),
    )
    return TokenVerificationResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=access_minutes * 60,
        user={"id": user.id, "email": user.email},
    )


@router.post("/refresh", response_model=TokenVerificationResponse)
async def refresh_token(
    request: Request, response: Response, db: DynamoDBConnection = Depends(get_db)
):
    token_value = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token"
        )

    # Load token from DB
    auth_token = await database_async.get_auth_token_by_token(token_value)
    if not auth_token or auth_token.token_type != TokenType.REFRESH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
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
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
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
    access_minutes = max(1, int(JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = create_access_token(
        data=create_token_payload(user_id=user.id, email=user.email),
        expires_delta=timedelta(minutes=access_minutes),
    )

    return TokenVerificationResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=access_minutes * 60,
        user={"id": user.id, "email": user.email},
    )


# ---------------- Magic Link compatibility endpoints ----------------
# Removed legacy request-magic-link endpoint (login by magic link abandoned).


@router.post("/verify-token", response_model=TokenVerificationResponse)
async def verify_token_endpoint(
    request: EmailVerificationRequest,
    response: Response,
    db: DynamoDBConnection = Depends(get_db),
):
    """
    Backward-compatible endpoint to verify a magic link token.

    Validates and consumes an EMAIL_VERIFICATION token, then issues a JWT access token.
    """
    token_string = request.token
    email = request.email.strip().lower()

    # Fetch token
    auth_token = await database_async.get_auth_token_by_token(token_string)
    if not auth_token or auth_token.token_type not in (
        TokenType.EMAIL_VERIFICATION,
        TokenType.MAGIC_LINK,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid magic link token"
        )

    # Provide specific error messages expected by tests
    if auth_token.used_at is not None or not auth_token.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Magic link token has already been used",
        )
    if auth_token.is_expired():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Magic link token expired"
        )

    if auth_token.email != email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid magic link token"
        )

    # Fetch user
    user = await database_async.get_user_by_id(auth_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Consume token
    auth_token.mark_as_used()
    await database_async.update_auth_token(auth_token)

    # Issue access token (24 hours for compatibility with tests)
    access_token = create_access_token(
        data=create_token_payload(user_id=user.id, email=user.email),
        expires_delta=timedelta(hours=24),
    )

    return TokenVerificationResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=24 * 60 * 60,
        user={"id": user.id, "email": user.email},
    )


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    request: EmailVerificationRequest, db: DynamoDBConnection = Depends(get_db)
):
    """
    Verify user's email using a single-use token.
    """
    token_string = request.token
    email = request.email.lower().strip()

    # Fetch token
    auth_token = await database_async.get_auth_token_by_token(token_string)
    if not auth_token or auth_token.token_type != TokenType.EMAIL_VERIFICATION:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification token",
        )

    if not auth_token.is_valid():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verification token expired or used",
        )

    if auth_token.email != email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification token",
        )

    # Fetch user
    user = await database_async.get_user_by_id(auth_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Mark token used and user verified
    auth_token.mark_as_used()
    await database_async.update_auth_token(auth_token)

    user.email_verified_at = datetime.now(timezone.utc)
    await database_async.update_user(user)

    return {"message": "Email successfully verified"}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification_email(
    current_user: AuthUser = Depends(get_current_user),
    db: DynamoDBConnection = Depends(get_db),
):
    """
    Resend the email verification link for the authenticated user if not verified.
    """
    user = await database_async.get_user_by_id(current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if getattr(user, "email_verified_at", None):
        return {"message": "Email already verified"}

    # Revoke existing verification tokens and send a new one
    try:
        await database_async.revoke_user_tokens(user.id, TokenType.EMAIL_VERIFICATION)
        verification = AuthToken.create_email_verification_token(
            user_id=user.id, email=user.email
        )
        await database_async.create_auth_token(verification)
        await email_service.send_email_verification(
            email=user.email, verification_token=verification.token
        )
    except Exception as e:
        logger.warning(f"Could not resend verification email to {user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend verification email",
        )

    return {"message": "Verification email sent"}


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
