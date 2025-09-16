"""
Unit tests for audio URL validator.
"""
import importlib
import os
import pytest


@pytest.mark.asyncio
async def test_validate_audio_url_rejects_non_http_scheme(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    import media_summarizer.core.validators as validators
    importlib.reload(validators)

    with pytest.raises(ValueError) as exc:
        await validators.validate_audio_url("ftp://example.com/audio.mp3")
    # Avoid locale-sensitive accents; check a stable substring
    assert "URL" in str(exc.value)


@pytest.mark.asyncio
async def test_validate_audio_url_requires_https_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    import media_summarizer.core.validators as validators
    importlib.reload(validators)

    # http should be rejected in production
    with pytest.raises(ValueError) as exc:
        await validators.validate_audio_url("http://example.com/a.mp3")
    assert "HTTPS requis" in str(exc.value)

    # https passes scheme check (size check mocked as None)
    async def fake_head(_url, _timeout):
        return None

    monkeypatch.setattr(validators, "_head_content_length", fake_head)
    await validators.validate_audio_url("https://example.com/a.mp3")


@pytest.mark.asyncio
async def test_validate_audio_url_size_limit_enforced(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("MAX_AUDIO_SIZE_MB", "1")  # 1 MB
    import media_summarizer.core.validators as validators
    importlib.reload(validators)

    # Pretend content length 2 MB
    async def fake_head(_url, _timeout):
        return 2 * 1024 * 1024

    monkeypatch.setattr(validators, "_head_content_length", fake_head)

    with pytest.raises(ValueError) as exc:
        await validators.validate_audio_url("https://example.com/big.mp3")
    assert "> 1 MB" in str(exc.value) or "trop volumineux" in str(exc.value)


@pytest.mark.asyncio
async def test_validate_audio_url_allows_when_size_unknown(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    import media_summarizer.core.validators as validators
    importlib.reload(validators)

    # Unknown size -> allowed
    async def fake_head(_url, _timeout):
        return None

    monkeypatch.setattr(validators, "_head_content_length", fake_head)

    await validators.validate_audio_url("https://example.com/unknown.mp3")
