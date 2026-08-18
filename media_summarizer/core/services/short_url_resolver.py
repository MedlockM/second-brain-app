"""
Share-link expansion for platforms whose share button hands out an opaque code.

TikTok's "Share" button never produces the canonical `/@user/video/<id>` URL: it
produces `https://vm.tiktok.com/<code>/` (Android) or `https://vt.tiktok.com/<code>/`
(iOS), where `<code>` identifies a redirect, not a media. Nothing downstream can
read it -- the classifier cannot tell a video from a photo post, and
`canonicalize_media_url` cannot derive a stable identity from it.

That last point is the reason this runs at ingestion time rather than being left
to yt-dlp, which follows redirects perfectly well on its own: the `media_key` is
derived from the canonical URL *before* any worker sees the submission. Two
shares of the same TikTok produce two different short codes, so leaving them
unexpanded means two media keys for one media -- deduplication breaks, and with
it the "user already holds this media" exemption that keeps a re-save from being
billed a second time (task-281).

Best effort by design: on timeout, on an HTTP error, or on a redirect that leaves
TikTok, the original URL is returned unchanged. The caller stays functional with
an unexpanded link (the classifier accepts short hosts, and yt-dlp resolves them
itself); only the deduplication quality degrades.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlsplit

import httpx

from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# Wall-clock budget for the expansion. A share link is one 301 away from its
# target, so this is generous; the point is that a slow TikTok can never hold an
# API request open.
DEFAULT_RESOLUTION_BUDGET_SECONDS = 4.0

# Redirect chains longer than this are a redirect loop, not a share link.
_MAX_REDIRECTS = 5

# Hosts whose path is an opaque redirect code.
_TIKTOK_SHORT_HOSTS = frozenset({"vm.tiktok.com", "vt.tiktok.com"})

# Hosts the expansion is allowed to land on. A share link that redirects off
# TikTok is not a share link; refusing to follow it keeps this from being an
# open redirect resolver usable to probe arbitrary hosts.
_TIKTOK_HOSTS = frozenset(
    {
        "tiktok.com",
        "www.tiktok.com",
        "m.tiktok.com",
        *_TIKTOK_SHORT_HOSTS,
    }
)


def _host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_tiktok_short_link(url: str) -> bool:
    """True when the URL carries an opaque TikTok redirect code.

    Covers the two share hosts and the `/t/<code>` route, which is the same
    opaque code served from the main domain.
    """
    if not isinstance(url, str) or not url.strip():
        return False

    split = urlsplit(url.strip())
    host = (split.hostname or "").lower()
    if host in _TIKTOK_SHORT_HOSTS:
        return True
    return host in _TIKTOK_HOSTS and split.path.lower().startswith("/t/")


async def resolve_tiktok_short_link(
    url: str,
    *,
    budget_seconds: float = DEFAULT_RESOLUTION_BUDGET_SECONDS,
) -> str:
    """Expand a TikTok share link, or return it unchanged.

    Uses `HEAD` so the media page itself is never downloaded -- only the redirect
    chain is followed. Returns the original URL whenever the expansion cannot be
    trusted: network failure, non-2xx answer, or a final host outside TikTok.
    """
    if not is_tiktok_short_link(url):
        return url

    original = url.strip()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=_MAX_REDIRECTS,
            timeout=budget_seconds,
        ) as client:
            response = await client.head(original)
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "media.short_link.unresolved",
            "TikTok share link could not be expanded; using it as submitted",
            source_platform="tiktok",
            error_type=type(exc).__name__,
        )
        return original

    if response.status_code >= 400:
        log_event(
            logger,
            logging.WARNING,
            "media.short_link.unresolved",
            "TikTok refused the share link expansion; using it as submitted",
            source_platform="tiktok",
            status=response.status_code,
        )
        return original

    expanded: Optional[str] = str(response.url) if response.url else None
    if not expanded or _host_of(expanded) not in _TIKTOK_HOSTS:
        log_event(
            logger,
            logging.WARNING,
            "media.short_link.off_platform",
            "TikTok share link redirected off TikTok; using it as submitted",
            source_platform="tiktok",
        )
        return original

    log_event(
        logger,
        logging.INFO,
        "media.short_link.resolved",
        "TikTok share link expanded to its canonical URL",
        source_platform="tiktok",
        resolved_host=_host_of(expanded),
    )
    return expanded
