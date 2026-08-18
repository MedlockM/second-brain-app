import re
import unicodedata
from typing import Optional, Sequence, Tuple

DEFAULT_ERROR_MESSAGE = "Error"

_ACTIONABLE_RULES: Sequence[Tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"session expired|session has expired|token expired|invalid token|"
            r"authentication token required|missing token|unauthorized|not authenticated|"
            r"authentication failed"
        ),
        "Your session has expired. Please sign in again.",
    ),
    (
        re.compile(
            r"invalid credentials|incorrect email or password|identifiants? invalides|"
            r"email.*mot de passe.*incorrect|mot de passe.*incorrect|echec.*connexion|"
            r"connexion.*echou"
        ),
        "Invalid email or password. Please try again.",
    ),
    (
        re.compile(
            r"email not verified|email.*non verifie|adresse e-?mail.*non verifie"
        ),
        "Please verify your email address before signing in.",
    ),
    (
        re.compile(
            r"account not found|user not found|compte.*introuvable|utilisateur.*introuvable|"
            r"aucun compte"
        ),
        "No account found with this email address. Please check the email or create a new account.",
    ),
    (
        re.compile(
            r"email already exists|email.*deja|adresse e-?mail.*deja"
        ),
        "An account with this email already exists.",
    ),
    (
        re.compile(r"rate_limited|hourly_quota_exceeded"),
        "TikTok media extraction is temporarily rate limited. Please retry later.",
    ),
    (
        re.compile(
            r"insufficient credits|not enough credits|payment required|insufficient minutes|"
            r"quota|credits insuffisants|minutes insuffisantes"
        ),
        "You need more minutes or credits to continue.",
    ),
    (
        re.compile(r"payment failed|invalid payment method"),
        "Payment failed. Please check your payment method and try again.",
    ),
    (
        re.compile(r"invalid email|email.*invalide"),
        "Please enter a valid email address.",
    ),
    (
        re.compile(
            r"password too short|password must be at least|mot de passe.*trop court|"
            r"mot de passe.*au moins|mot de passe.*minimum"
        ),
        "Password must be at least 8 characters long.",
    ),
    (
        re.compile(r"passwords do not match|mots? de passe.*diff"),
        "Passwords do not match. Please try again.",
    ),
    (
        re.compile(r"missing required field|field.*required|champ.*requis|champ.*obligatoire"),
        "Please fill in all required fields.",
    ),
    (
        re.compile(r"file too large|fichier.*trop volumineux"),
        "File is too large. Please choose a smaller file.",
    ),
    (
        re.compile(r"invalid file type"),
        "Invalid file type. Please choose a supported file format.",
    ),
    (
        re.compile(r"youtube_timeout|youtube_transcript_fetch_failed|requestblocked|ipblocked"),
        "YouTube transcript retrieval is temporarily unavailable. Please retry.",
    ),
    (
        re.compile(r"youtube_unavailable|videounavailable|videounplayable|age-restricted"),
        "This YouTube video is unavailable or cannot be processed.",
    ),
    (
        re.compile(r"youtube_audio_fallback_failed"),
        "YouTube audio extraction failed. Please retry.",
    ),
    (
        re.compile(r"unsupported_content|missing_tiktok_id"),
        "This TikTok video is unavailable or cannot be processed.",
    ),
    (
        re.compile(r"no_direct_media_url|no_transcribable_media_url"),
        "Unable to resolve transcribable media from this TikTok URL.",
    ),
    (
        re.compile(r"extractor_failed|yt_dlp_timeout|subtitle_fetch|subtitle_http_status"),
        "TikTok extraction is temporarily unavailable. Please retry.",
    ),
    # --- Consumption refusals ---
    # Only a safety net: a refused import already carries the enforcer's own
    # sentence, with the figures that explain it ("You're out of minutes until
    # Sep 12"). These two rules exist for the case where only the machine code
    # survived into an exception string.
    (
        re.compile(r"out_of_minutes"),
        "You're out of minutes for this period. Upgrade to keep importing audio and video.",
    ),
    (
        re.compile(r"item_too_long"),
        "This is too long for a single import on your plan. Split it into shorter parts.",
    ),
]


def _normalize_message(message: str) -> str:
    return (
        unicodedata.normalize("NFKD", message)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def get_user_facing_error_message(raw_message: Optional[str]) -> str:
    if not raw_message:
        return DEFAULT_ERROR_MESSAGE

    normalized = _normalize_message(str(raw_message))
    for pattern, friendly_message in _ACTIONABLE_RULES:
        if pattern.search(normalized):
            return friendly_message

    return DEFAULT_ERROR_MESSAGE
