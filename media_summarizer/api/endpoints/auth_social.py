"""
Social authentication endpoints (Google, Apple) using OAuth/OIDC.

- Native endpoints (/google/native, /apple/native) verify an id_token obtained by
  the mobile SDK and return access + refresh tokens in JSON. This is the only path
  that opens a session — the mobile app is the only client.
- Web login/callback endpoints redirect to the provider and, on return, verify the
  id_token and link or create the user. They no longer issue any session material:
  the refresh cookie they used to set had no client left able to read it (task-293).
  They are kept because their redirect URIs are registered with Apple and Google.

Notes:
- Google id_token is validated via tokeninfo endpoint (server-side verification)
- Apple id_token is validated against Apple's JWKS (RS256)
- Client secrets and keys are read from environment variables
"""

import base64
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from jose import jwt
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from media_summarizer.core.models import User
from media_summarizer.core.models.auth import AuthToken
from media_summarizer.utils import database_async
from media_summarizer.utils.auth_utils import (
    create_access_token,
    create_token_payload,
    get_access_token_expires_seconds,
    get_refresh_token_expires_at,
)
from media_summarizer.utils.database_async import DynamoDBConnection, get_db

logger = logging.getLogger(__name__)
router = APIRouter()

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Google OAuth config
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI") or os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"
)
# Google native (mobile app) audiences — the iOS and Android OAuth client IDs,
# distinct from GOOGLE_CLIENT_ID (web client) used by the web callback flow.
# expo-auth-session exchanges the authorization code against the platform client,
# so the id_token the app sends to /google/native carries that client as its
# `aud`; it can never equal the web client ID.
GOOGLE_NATIVE_AUDIENCE_IOS = os.environ.get("GOOGLE_NATIVE_AUDIENCE_IOS")
GOOGLE_NATIVE_AUDIENCE_ANDROID = os.environ.get("GOOGLE_NATIVE_AUDIENCE_ANDROID")

# Apple OAuth config
APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID")
APPLE_KEY_ID = os.environ.get("APPLE_KEY_ID")
APPLE_CLIENT_ID = os.environ.get("APPLE_CLIENT_ID")
APPLE_PRIVATE_KEY = os.environ.get("APPLE_PRIVATE_KEY")
APPLE_REDIRECT_URI = os.environ.get("APPLE_REDIRECT_URI") or os.environ.get(
    "APPLE_REDIRECT_URI", "http://localhost:8000/api/auth/apple/callback"
)
# Apple native (iOS app) audience — equals the iOS app bundle id, distinct
# from APPLE_CLIENT_ID (Services ID) used for the web callback flow.
APPLE_NATIVE_AUDIENCE = os.environ.get("APPLE_NATIVE_AUDIENCE")


# Helpers


def _set_state_cookie(
    response: Response, provider: str, state: str, ttl_seconds: int = 600
) -> None:
    """Bind the OAuth ``state`` to the browser that started the web flow.

    This is the CSRF guard of the web login/callback pair, read back by the
    callback through ``_get_state_cookie``. It is host-only on purpose: the
    cookie is set and read by the API host, so a Domain attribute pointing at
    the app domain would simply be rejected by the browser.
    """
    response.set_cookie(
        key=f"oauth_state_{provider}",
        value=state,
        max_age=ttl_seconds,
        expires=ttl_seconds,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _get_state_cookie(request: Request, provider: str) -> Optional[str]:
    return request.cookies.get(f"oauth_state_{provider}")


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


def _google_native_accepted_audiences() -> list[str]:
    """Audiences accepted for an id_token coming from the mobile app.

    Google mints the id_token for the OAuth client the code exchange ran against,
    and ``expo-auth-session`` runs it against the *platform* client — the iOS one
    on iOS, the Android one on Android (``providers/Google.js`` selects the client
    id from ``Platform.select``). So the native ``aud`` is one of those two, and
    the web client in ``GOOGLE_CLIENT_ID`` is only reachable through the web
    ``/google/callback`` flow. It stays in the list because it is a legitimate
    audience for a token minted by that flow, and because it is the only value
    configured until the two native keys are provisioned.

    This mirrors what ``APPLE_NATIVE_AUDIENCE`` does for Apple: widen the accepted
    set for the native endpoint only, never for the web callback.
    """
    accepted: list[str] = []
    for candidate in (
        GOOGLE_CLIENT_ID,
        GOOGLE_NATIVE_AUDIENCE_IOS,
        GOOGLE_NATIVE_AUDIENCE_ANDROID,
    ):
        if candidate and candidate not in accepted:
            accepted.append(candidate)
    return accepted


@router.get("/google/login")
async def google_login() -> RedirectResponse:
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

        # Single audience on purpose: this flow exchanged the code against the web
        # client itself a few lines up, so the id_token can only be minted for
        # GOOGLE_CLIENT_ID. The native audiences widen /google/native only.
        if aud != GOOGLE_CLIENT_ID or iss not in (
            "accounts.google.com",
            "https://accounts.google.com",
        ):
            return _redirect_error("google", "invalid_audience_or_issuer")
        if not email or not email_verified or not sub:
            return _redirect_error("google", "invalid_claims")

        # Link or create user. No session material is issued here: the web flow
        # has no client able to receive it (task-293).
        await _link_or_create_user(
            email=email.lower().strip(), provider="google", provider_sub=sub
        )

        return _redirect_success("google")

    except httpx.HTTPStatusError as e:
        logger.warning(f"Google callback HTTP error: {e.response.status_code}")
        return _redirect_error("google", "http_error")
    except Exception as e:
        logger.error(f"Google callback error: {e}")
        return _redirect_error("google", "server_error")


# ------------------ Apple OAuth ------------------


def _b64_to_int(s: str) -> int:
    s = s.encode("ascii")
    s += b"=" * (-len(s) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(s), "big")


def _normalize_apple_private_key(raw: str) -> str:
    """Turn an APPLE_PRIVATE_KEY env value into a loadable PEM.

    The variable travels as a single line with ``\\n`` escapes, which makes it easy
    to carry decoration that a PEM parser rejects. It has happened: the value was
    once copied out of .env into Secrets Manager with its surrounding quotes and a
    trailing ``# PEM, single line with \\n escapes`` comment included, and Apple
    Sign-In broke in the deployed environment (task-136). python-dotenv strips both
    when reading a .env, so the corruption is invisible locally and only surfaces
    where the value comes from the secret instead.

    Terraform used to catch this in a ``validation`` block on the secret payload,
    but that block went away with ``secret_payload`` (task-221 §7.3: an inline
    ``secret_string`` leaks the value in plaintext into the state). This function
    is now the only place that can, so it raises with the variable name rather than
    letting ``jwt.encode`` fail on an opaque backend error.

    Deliberately scoped to this one variable: no other credential is known to be
    polluted, and stripping quotes and comments off every secret would hide real
    corruption in values where a ``#`` or a quote is legitimate content.
    """
    key = raw.strip()
    # Requiring whitespace before the # keeps a base64 body containing one intact.
    key = re.sub(r"\s+#.*$", "", key, flags=re.DOTALL).strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
        key = key[1:-1].strip()
    key = key.replace("\\n", "\n")
    if not key.startswith("-----BEGIN"):
        raise RuntimeError(
            "APPLE_PRIVATE_KEY is not a PEM private key: expected it to start with "
            "'-----BEGIN' after normalization. Store the raw PEM with \\n escapes, "
            "with no surrounding quotes and no trailing comment (task-136). In a "
            "deployed environment the value comes from the runtime secret, not .env."
        )
    return key


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
    private_key = _normalize_apple_private_key(APPLE_PRIVATE_KEY)
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

    # Apple uses different audiences for web (Services ID) vs native (Bundle ID).
    # python-jose's jwt.decode only accepts a single string for `audience`, so
    # we skip its built-in audience check and verify manually below.
    accepted_audiences: list[str] = []
    if APPLE_CLIENT_ID:
        accepted_audiences.append(APPLE_CLIENT_ID)
    if APPLE_NATIVE_AUDIENCE and APPLE_NATIVE_AUDIENCE not in accepted_audiences:
        accepted_audiences.append(APPLE_NATIVE_AUDIENCE)

    claims = jwt.decode(
        id_token,
        pem,
        algorithms=["RS256"],
        issuer="https://appleid.apple.com",
        options={"verify_aud": False},
    )

    token_aud = claims.get("aud")
    if token_aud not in accepted_audiences:
        raise ValueError(
            f"Invalid audience: token aud={token_aud!r} not in accepted={accepted_audiences!r}"
        )
    return claims


@router.get("/apple/login")
async def apple_login() -> RedirectResponse:
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

        # Link or create user. No session material is issued here: the web flow
        # has no client able to receive it (task-293).
        await _link_or_create_user(
            email=email.lower().strip(), provider="apple", provider_sub=sub
        )

        return _redirect_success("apple")

    except httpx.HTTPStatusError as e:
        logger.warning(f"Apple callback HTTP error: {e.response.status_code}")
        return _redirect_error("apple", "http_error")
    except Exception as e:
        logger.error(f"Apple callback error: {e}")
        return _redirect_error("apple", "server_error")


# ------------------ Native Mobile Token Endpoints ------------------
# These endpoints accept ID tokens obtained by native mobile SDKs
# (expo-apple-authentication, expo-auth-session/google) and return
# access + refresh tokens in JSON (no cookies, mobile stores in secure store).


class GoogleNativeRequest(PydanticBaseModel):
    id_token: str = Field(..., description="Google ID token from native SDK")


class AppleNativeRequest(PydanticBaseModel):
    identity_token: str = Field(..., description="Apple identity token from native SDK")
    user: Optional[Dict[str, Any]] = Field(
        default=None, description="User info from Apple (name, email) - only sent on first login"
    )


class NativeAuthResponse(PydanticBaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


@router.post("/google/native", response_model=NativeAuthResponse)
async def google_native(
    request: GoogleNativeRequest,
    db: DynamoDBConnection = Depends(get_db),
):
    """
    Verify a Google ID token obtained by the mobile native SDK and return
    access + refresh tokens for the mobile app.
    """
    accepted_audiences = _google_native_accepted_audiences()
    if not accepted_audiences:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    try:
        # Validate id_token via Google tokeninfo endpoint
        async with httpx.AsyncClient(timeout=20.0) as client:
            info_url = "https://oauth2.googleapis.com/tokeninfo"
            info_resp = await client.get(info_url, params={"id_token": request.id_token})
            info_resp.raise_for_status()
            info = info_resp.json()

        # Claim checks
        aud = info.get("aud")
        iss = info.get("iss")
        email = info.get("email")
        email_verified = str(info.get("email_verified", "false")).lower() in (
            "true", "1", "yes",
        )
        sub = info.get("sub")

        if aud not in accepted_audiences or iss not in (
            "accounts.google.com",
            "https://accounts.google.com",
        ):
            # Client IDs are public identifiers, so logging them is safe — and it
            # is the only way to tell "the native audience keys were never
            # provisioned" apart from "a token from another project reached us".
            logger.warning(
                "Google native token rejected: aud=%r iss=%r accepted=%r",
                aud,
                iss,
                accepted_audiences,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid audience or issuer",
            )
        if not email or not email_verified or not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims: missing email or unverified",
            )

        # Link or create user
        user = await _link_or_create_user(
            email=email.lower().strip(), provider="google", provider_sub=sub
        )

        # Refresh token: opens a new device-session lineage, sliding expiry
        refresh = AuthToken.create_refresh_token(
            user_id=user.id, email=user.email, expires_at=get_refresh_token_expires_at()
        )
        refresh = await database_async.create_auth_token(refresh)

        # Create access token
        access_seconds = get_access_token_expires_seconds()
        access_token = create_access_token(
            data=create_token_payload(user_id=user.id, email=user.email),
            expires_delta=timedelta(seconds=access_seconds),
        )

        return NativeAuthResponse(
            access_token=access_token,
            refresh_token=refresh.token,
            token_type="bearer",
            expires_in=access_seconds,
            user={"id": user.id, "email": user.email, "reading_language": user.reading_language},
        )

    except httpx.HTTPStatusError as e:
        logger.warning(f"Google native token verification HTTP error: {e.response.status_code}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to verify Google ID token",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google native auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during Google authentication",
        )


@router.post("/apple/native", response_model=NativeAuthResponse)
async def apple_native(
    request: AppleNativeRequest,
    db: DynamoDBConnection = Depends(get_db),
):
    """
    Verify an Apple identity token obtained by the mobile native SDK and return
    access + refresh tokens for the mobile app.
    """
    if not APPLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Apple OAuth not configured")

    try:
        # Verify identity_token using Apple JWKS
        claims = await _apple_verify_id_token(request.identity_token)

        sub = claims.get("sub")
        email = claims.get("email")
        email_verified_raw = claims.get("email_verified")
        email_verified = (
            (str(email_verified_raw).lower() in ("true", "1", "yes"))
            if email_verified_raw is not None
            else True  # Apple may omit when using private relay; treat as verified
        )

        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims: missing sub",
            )

        # Email may not be in the token on subsequent logins; try from request.user
        if not email and request.user:
            email = request.user.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to determine email from Apple token or user info",
            )

        if not email_verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email not verified",
            )

        # Link or create user
        user = await _link_or_create_user(
            email=email.lower().strip(), provider="apple", provider_sub=sub
        )

        # Refresh token: opens a new device-session lineage, sliding expiry
        refresh = AuthToken.create_refresh_token(
            user_id=user.id, email=user.email, expires_at=get_refresh_token_expires_at()
        )
        refresh = await database_async.create_auth_token(refresh)

        # Create access token
        access_seconds = get_access_token_expires_seconds()
        access_token = create_access_token(
            data=create_token_payload(user_id=user.id, email=user.email),
            expires_delta=timedelta(seconds=access_seconds),
        )

        return NativeAuthResponse(
            access_token=access_token,
            refresh_token=refresh.token,
            token_type="bearer",
            expires_in=access_seconds,
            user={"id": user.id, "email": user.email, "reading_language": user.reading_language},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apple native auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during Apple authentication",
        )
