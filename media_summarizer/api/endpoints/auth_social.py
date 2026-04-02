"""
Social authentication endpoints (Google, Apple) using OAuth/OIDC.

- Login endpoints redirect to provider auth pages with state protection
- Callback endpoints exchange code -> tokens, verify id_token,
  link or create user, set refresh cookie (30d absolute), and redirect frontend

Notes:
- Google id_token is validated via tokeninfo endpoint (server-side verification)
- Apple id_token is validated against Apple's JWKS (RS256)
- Client secrets and keys are read from environment variables
"""

import os
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from media_summarizer.core.models import User
from media_summarizer.core.models.auth import AuthToken
from media_summarizer.utils import database_async
from media_summarizer.utils.database_async import get_db, DynamoDBConnection
from media_summarizer.utils.auth_utils import get_refresh_token_expires_at

# Reuse cookie helper from local auth module
from media_summarizer.api.endpoints import auth as auth_local

logger = logging.getLogger(__name__)
router = APIRouter()

# Common cookie config
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax").lower()  # lax|strict|none
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Google OAuth config
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI") or os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback"
)

# Apple OAuth config
APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID")
APPLE_KEY_ID = os.environ.get("APPLE_KEY_ID")
APPLE_CLIENT_ID = os.environ.get("APPLE_CLIENT_ID")
APPLE_PRIVATE_KEY = os.environ.get("APPLE_PRIVATE_KEY")
APPLE_REDIRECT_URI = os.environ.get("APPLE_REDIRECT_URI") or os.environ.get(
    "APPLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/apple/callback"
)


# Helpers


def _set_state_cookie(
    response: Response, provider: str, state: str, ttl_seconds: int = 600
) -> None:
    response.set_cookie(
        key=f"oauth_state_{provider}",
        value=state,
        max_age=ttl_seconds,
        expires=ttl_seconds,
        domain=COOKIE_DOMAIN,
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )


def _get_state_cookie(request: Request, provider: str) -> Optional[str]:
    return request.cookies.get(f"oauth_state_{provider}")


def _clear_state_cookie(response: Response, provider: str) -> None:
    try:
        response.delete_cookie(
            key=f"oauth_state_{provider}", domain=COOKIE_DOMAIN, path="/"
        )
        response.delete_cookie(
            key=f"oauth_state_{provider}_uid", domain=COOKIE_DOMAIN, path="/"
        )
    except Exception:
        # Non-fatal: cookie will expire naturally
        pass


async def _link_or_create_user(email: str, provider: str, provider_sub: str) -> User:
    """Find existing user by email or create a new one; mark email as verified."""
    existing = await database_async.get_user_by_email(email)
    now = datetime.now(timezone.utc)
    if existing:
        # Update provider info if missing and ensure email verified
        updates: Dict[str, Any] = {}
        if not getattr(existing, "email_verified_at", None):
            updates["email_verified_at"] = now
        # Single provider_id field available in current model
        if getattr(existing, "provider_id", None) != provider_sub:
            updates["provider_id"] = provider_sub
        if getattr(existing, "auth_provider", None) != provider:
            updates["auth_provider"] = provider
        if updates:
            for k, v in updates.items():
                setattr(existing, k, v)
            existing = await database_async.update_user(existing)
        return existing

    # Create new user with starter credits (consistent with local register)
    user = User(
        email=email,
        credits=100,
        auth_provider=provider,
        provider_id=provider_sub,
        email_verified_at=now,
    )
    return await database_async.create_user(user)


def _redirect_success(provider: str) -> RedirectResponse:
    url = f"{FRONTEND_URL.rstrip('/')}/auth/callback-success?provider={provider}"
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


def _redirect_error(provider: str, reason: str) -> RedirectResponse:
    # Do not leak sensitive info; include a generic reason code
    url = f"{FRONTEND_URL.rstrip('/')}/auth/callback-error?provider={provider}&reason={reason}"
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


# ------------------ Google OAuth ------------------


@router.get("/google/login")
async def google_login(response: Response) -> RedirectResponse:
    if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    state = secrets.token_urlsafe(16)

    base = "https://accounts.google.com/o/oauth2/v2/auth"
    scope = "openid email profile"

    # Build redirect URL
    import urllib.parse as up

    params = {
        "response_type": "code",
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "scope": scope,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    redirect = RedirectResponse(url=f"{base}?{up.urlencode(params)}")
    # Set state cookie on the actual response object being returned
    _set_state_cookie(redirect, "google", state)
    return redirect


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    db: DynamoDBConnection = Depends(get_db),
):
    try:
        expected_state = _get_state_cookie(request, "google")
        if not state or not expected_state or state != expected_state:
            return _redirect_error("google", "state_mismatch")
        if not code:
            return _redirect_error("google", "missing_code")

        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_resp = await client.post(token_url, data=data)
            token_resp.raise_for_status()
            token_data = token_resp.json()

            id_token = token_data.get("id_token")
            if not id_token:
                return _redirect_error("google", "no_id_token")

            # Validate id_token via tokeninfo endpoint
            info_url = "https://oauth2.googleapis.com/tokeninfo"
            info_resp = await client.get(info_url, params={"id_token": id_token})
            info_resp.raise_for_status()
            info = info_resp.json()

        # Basic claim checks
        aud = info.get("aud")
        iss = info.get("iss")
        email = info.get("email")
        email_verified = str(info.get("email_verified", "false")).lower() in (
            "true",
            "1",
            "yes",
        )
        sub = info.get("sub")

        if aud != GOOGLE_CLIENT_ID or iss not in (
            "accounts.google.com",
            "https://accounts.google.com",
        ):
            return _redirect_error("google", "invalid_audience_or_issuer")
        if not email or not email_verified or not sub:
            return _redirect_error("google", "invalid_claims")

        # Link or create user
        user = await _link_or_create_user(
            email=email.lower().strip(), provider="google", provider_sub=sub
        )

        # Create refresh token and set cookie
        refresh_expires_at = get_refresh_token_expires_at()
        refresh = AuthToken.create_refresh_token(
            user_id=user.id, email=user.email, absolute_expires_at=refresh_expires_at
        )
        refresh = await database_async.create_auth_token(refresh)
        redirect = _redirect_success("google")
        auth_local._set_refresh_cookie(redirect, refresh.token, refresh.expires_at)
        return redirect

    except httpx.HTTPStatusError as e:
        logger.warning(f"Google callback HTTP error: {e.response.status_code}")
        return _redirect_error("google", "http_error")
    except Exception as e:
        logger.error(f"Google callback error: {e}")
        return _redirect_error("google", "server_error")


# ------------------ Apple OAuth ------------------

from jose import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import base64


def _b64_to_int(s: str) -> int:
    s = s.encode("ascii")
    s += b"=" * (-len(s) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(s), "big")


def _apple_build_client_secret() -> str:
    """Generate Apple client_secret JWT (ES256)."""
    if not (APPLE_TEAM_ID and APPLE_KEY_ID and APPLE_CLIENT_ID and APPLE_PRIVATE_KEY):
        raise RuntimeError("Apple OAuth not configured")
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {
        "iss": APPLE_TEAM_ID,
        "iat": now,
        "exp": now + 600,  # 10 minutes
        "aud": "https://appleid.apple.com",
        "sub": APPLE_CLIENT_ID,
    }
    headers = {"kid": APPLE_KEY_ID, "alg": "ES256"}
    private_key = APPLE_PRIVATE_KEY
    # Ensure proper newlines for PEM formatting if provided inline
    private_key = private_key.replace("\\n", "\n")
    token = jwt.encode(claims, private_key, algorithm="ES256", headers=headers)
    return token


async def _apple_verify_id_token(id_token: str) -> Dict[str, Any]:
    """Verify Apple id_token using Apple's JWKS.

    Returns decoded claims if valid; raises on failure.
    """
    # Fetch JWKS
    async with httpx.AsyncClient(timeout=20.0) as client:
        jwks_resp = await client.get("https://appleid.apple.com/auth/keys")
        jwks_resp.raise_for_status()
        jwks = jwks_resp.json().get("keys", [])

    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    alg = header.get("alg")

    key = next((k for k in jwks if k.get("kid") == kid and k.get("kty") == "RSA"), None)
    if not key:
        raise ValueError("No matching JWKS key")

    n = _b64_to_int(key["n"])  # modulus
    e = _b64_to_int(key["e"])  # exponent
    public_numbers = rsa.RSAPublicNumbers(e, n)
    public_key = public_numbers.public_key()
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    claims = jwt.decode(
        id_token,
        pem,
        algorithms=["RS256"],
        audience=APPLE_CLIENT_ID,
        issuer="https://appleid.apple.com",
    )
    return claims


@router.get("/apple/login")
async def apple_login(response: Response) -> RedirectResponse:
    if not APPLE_CLIENT_ID or not APPLE_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Apple OAuth not configured")

    state = secrets.token_urlsafe(16)

    base = "https://appleid.apple.com/auth/authorize"
    scope = "name email"

    import urllib.parse as up

    params = {
        "response_type": "code",
        "response_mode": "query",
        "client_id": APPLE_CLIENT_ID,
        "redirect_uri": APPLE_REDIRECT_URI,
        "scope": scope,
        "state": state,
    }
    redirect = RedirectResponse(url=f"{base}?{up.urlencode(params)}")
    _set_state_cookie(redirect, "apple", state)
    return redirect


@router.get("/apple/callback")
async def apple_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    db: DynamoDBConnection = Depends(get_db),
):
    try:
        expected_state = _get_state_cookie(request, "apple")
        if not state or not expected_state or state != expected_state:
            return _redirect_error("apple", "state_mismatch")
        if not code:
            return _redirect_error("apple", "missing_code")

        client_secret = _apple_build_client_secret()

        token_url = "https://appleid.apple.com/auth/token"
        data = {
            "client_id": APPLE_CLIENT_ID,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": APPLE_REDIRECT_URI,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_resp = await client.post(token_url, data=data, headers=headers)
            token_resp.raise_for_status()
            token_data = token_resp.json()

        id_token = token_data.get("id_token")
        if not id_token:
            return _redirect_error("apple", "no_id_token")

        claims = await _apple_verify_id_token(id_token)
        sub = claims.get("sub")
        email = claims.get("email")
        email_verified_raw = claims.get("email_verified")
        email_verified = (
            (str(email_verified_raw).lower() in ("true", "1", "yes"))
            if email_verified_raw is not None
            else True
        )  # Apple may omit when using private relay; treat as verified

        if not sub or not email:
            return _redirect_error("apple", "invalid_claims")
        if not email_verified:
            return _redirect_error("apple", "email_not_verified")

        # Link or create user
        user = await _link_or_create_user(
            email=email.lower().strip(), provider="apple", provider_sub=sub
        )

        # Create refresh token and set cookie
        refresh_expires_at = get_refresh_token_expires_at()
        refresh = AuthToken.create_refresh_token(
            user_id=user.id, email=user.email, absolute_expires_at=refresh_expires_at
        )
        refresh = await database_async.create_auth_token(refresh)
        redirect = _redirect_success("apple")
        auth_local._set_refresh_cookie(redirect, refresh.token, refresh.expires_at)
        return redirect

    except httpx.HTTPStatusError as e:
        logger.warning(f"Apple callback HTTP error: {e.response.status_code}")
        return _redirect_error("apple", "http_error")
    except Exception as e:
        logger.error(f"Apple callback error: {e}")
        return _redirect_error("apple", "server_error")
