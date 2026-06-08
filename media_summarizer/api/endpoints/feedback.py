"""
Feedback SSO endpoint for Canny integration.

Generates a Canny-compatible JWT SSO token so users are auto-authenticated
on the feedback board without needing to sign in again.

Reference: https://developers.canny.io/install/widget/sso
"""

import logging
import os
import time

from jose import jwt
from fastapi import APIRouter, Depends, HTTPException, status

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_canny_sso_key() -> str:
    """Read the Canny SSO private key from environment."""
    key = os.getenv("CANNY_SSO_PRIVATE_KEY", "")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback SSO is not configured",
        )
    return key


def _get_canny_board_token() -> str:
    """Read the Canny board token from environment."""
    token = os.getenv("CANNY_BOARD_TOKEN", "")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback board is not configured",
        )
    return token


@router.get("/feedback/token")
async def get_feedback_sso_token(
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Generate a Canny SSO token for the authenticated user.

    Returns the full WebView URL with boardToken and ssoToken params
    so the mobile app can open it directly in a browser.

    The Canny SSO JWT payload contains:
    - id: user's unique ID
    - name: user's display name (falls back to email local part)
    - email: user's email address
    - iat: issued at timestamp

    Signed with HS256 using the Canny SSO private key.
    """
    sso_key = _get_canny_sso_key()
    board_token = _get_canny_board_token()

    # Build display name from email if no explicit name available
    display_name = current_user.email.split("@")[0] if current_user.email else "User"

    # Build Canny SSO payload per https://developers.canny.io/install/widget/sso
    payload = {
        "id": current_user.id,
        "name": display_name,
        "email": current_user.email,
        "iat": int(time.time()),
    }

    try:
        sso_token: str = jwt.encode(payload, sso_key, algorithm="HS256")
    except Exception as e:
        logger.error(f"Failed to generate Canny SSO token for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate feedback token",
        )

    # Build the Canny WebView URL
    url = (
        f"https://webview.canny.io"
        f"?boardToken={board_token}"
        f"&ssoToken={sso_token}"
        f"&theme=light"
    )

    return {
        "url": url,
        "sso_token": sso_token,
        "board_token": board_token,
    }
