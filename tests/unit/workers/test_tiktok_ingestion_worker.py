"""Unit tests for tiktok_ingestion_worker._extract_tiktok_id."""

from __future__ import annotations

import pytest

from media_summarizer.workers.tiktok_ingestion_worker import (
    TikTokIngestionError,
    _extract_tiktok_id,
)


def test_extract_tiktok_id_from_canonical_video_url():
    url = "https://www.tiktok.com/@someuser/video/7123456789012345678"
    assert _extract_tiktok_id(url) == "7123456789012345678"


def test_extract_tiktok_id_from_short_t_path():
    url = "https://www.tiktok.com/t/ZTd1abcd2/"
    assert _extract_tiktok_id(url) == "ZTd1abcd2"


def test_extract_tiktok_id_from_vm_share_link():
    """vm.tiktok.com share links carry a shortcode yt-dlp resolves itself.

    Regression test: this used to raise unsupported_content/missing_tiktok_id
    before yt-dlp even got a chance to follow the redirect.
    """
    url = "https://vm.tiktok.com/ZNRc7AAcY/"
    assert _extract_tiktok_id(url) == "ZNRc7AAcY"


def test_extract_tiktok_id_unsupported_url_raises():
    url = "https://www.tiktok.com/some/unsupported/path"
    with pytest.raises(TikTokIngestionError) as exc_info:
        _extract_tiktok_id(url)
    assert exc_info.value.code == "unsupported_content"
    assert exc_info.value.details == "missing_tiktok_id"
