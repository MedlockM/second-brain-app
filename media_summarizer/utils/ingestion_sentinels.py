"""Per-request sentinels used by ingestion workers as E2E test seams.

``test_tiktok_apify_fallback`` needs to deterministically exercise the Apify
fallback path that normally only fires when Lambda is IP-blocked by TikTok.
Rather than depending on which videos are currently geo-blocked (a moving
target), the test submits an URL carrying a sentinel query param; the worker
detects and strips it, then behaves as if yt-dlp had just been IP-blocked.

TikTok is the only consumer: task-310 removed the Instagram yt-dlp branch, so
Instagram has no fallback left to force.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

E2E_FORCE_IP_BLOCK_PARAM = "__e2e_force_ip_block__"


def strip_e2e_force_ip_block_sentinel(normalized_url: str) -> tuple[str, bool]:
    """Detect and remove the E2E force-IP-block sentinel from the URL.

    Returns ``(clean_url, force_ip_block)``. When ``force_ip_block`` is True
    the caller MUST skip yt-dlp and route the cleaned URL straight to the
    Apify fallback. The cleaned URL has the sentinel query param stripped so
    downstream actors receive a plain platform URL.
    """
    if E2E_FORCE_IP_BLOCK_PARAM not in (normalized_url or ""):
        return normalized_url, False

    split = urlsplit(normalized_url)
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(split.query, keep_blank_values=True)
        if k != E2E_FORCE_IP_BLOCK_PARAM
    ]
    cleaned_query = urlencode(query_pairs)
    cleaned = urlunsplit(
        (split.scheme, split.netloc, split.path, cleaned_query, split.fragment)
    )
    return cleaned, True
