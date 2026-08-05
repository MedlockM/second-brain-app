"""Shared ISO 639-1 language-code normalization for the ingestion pipeline.

The transcript language travels API -> orchestrator -> SQS -> ingestion worker
(task-216). Every hop must agree on the canonical form of a language code so the
value the user picked in onboarding/Settings (``User.reading_language``, task-190)
is the exact value handed to the transcript providers.

Canonical form: lowercase bare primary subtag (``"EN-US"`` -> ``"en"``,
``"pt_BR"`` -> ``"pt"``). Placeholder tags that carry no usable language
information are normalized to ``None`` so callers can fall back explicitly
instead of forwarding garbage to a provider.

Some providers report the delivered language as an English display name
(``"English"``) rather than a code; ``resolve_language_code`` accepts both so a
single canonical value reaches ``transcription_metadata.language``.
"""

from __future__ import annotations

from typing import Any, Optional

# Tags that mean "no/unknown language" and must never reach a provider payload.
_PLACEHOLDER_LANGUAGE_TAGS = frozenset({"unknown", "und", "auto", "mul", "zxx"})

# English display names some providers return instead of a code. Covers the 11
# V1 reading languages (task-189) plus the neighbours actually observed in
# YouTube caption tracks.
_LANGUAGE_NAME_TO_CODE = {
    "arabic": "ar",
    "catalan": "ca",
    "chinese": "zh",
    "dutch": "nl",
    "english": "en",
    "french": "fr",
    "german": "de",
    "hindi": "hi",
    "italian": "it",
    "japanese": "ja",
    "korean": "ko",
    "portuguese": "pt",
    "russian": "ru",
    "spanish": "es",
    "turkish": "tr",
}


def normalize_language_code(value: Any) -> Optional[str]:
    """Normalize a language tag to a bare lowercase ISO 639-1 code.

    Returns ``None`` when the value is missing, not a string, empty, or a
    placeholder tag such as ``"und"`` / ``"auto"``.
    """
    if not isinstance(value, str):
        return None
    code = value.strip().replace("_", "-").lower()
    if not code:
        return None
    primary = code.split("-", 1)[0].strip()
    if not primary or primary in _PLACEHOLDER_LANGUAGE_TAGS:
        return None
    return primary


def resolve_language_code(value: Any) -> Optional[str]:
    """Normalize a code *or* an English language name to ISO 639-1.

    ``"English"`` -> ``"en"``, ``"Chinese (Simplified)"`` -> ``"zh"``, while
    plain codes fall through to :func:`normalize_language_code`. Needed because
    provider payloads are inconsistent: the same pipeline sees ``"en"`` from one
    Apify actor and ``"English"`` from another.
    """
    if not isinstance(value, str):
        return None
    label = value.strip().lower()
    if not label:
        return None
    if label in _LANGUAGE_NAME_TO_CODE:
        return _LANGUAGE_NAME_TO_CODE[label]
    # "Chinese (Simplified)", "Portuguese - Brazil", "English (auto-generated)".
    head = label.split("(")[0].split(" - ")[0].strip()
    if head in _LANGUAGE_NAME_TO_CODE:
        return _LANGUAGE_NAME_TO_CODE[head]
    return normalize_language_code(value)
