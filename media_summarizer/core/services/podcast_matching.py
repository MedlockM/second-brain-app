"""
Provider-agnostic podcast episode title matching helpers.

This module preserves reusable title matching behavior for podcast resolvers
without depending on provider-specific services.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping, Sequence

_NON_WORD_PATTERN = re.compile(r"[\W_]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")

DEFAULT_MIN_TOKEN_OVERLAP_SCORE = 0.60


def normalize_podcast_title(title: str) -> str:
    """
    Normalize podcast titles for robust matching.

    Behavior:
    - lower-case
    - strip accents/combining characters
    - replace punctuation/underscores with spaces
    - collapse consecutive spaces
    """
    normalized = (title or "").lower()
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    normalized = unicodedata.normalize("NFC", normalized)
    normalized = _NON_WORD_PATTERN.sub(" ", normalized)
    normalized = _WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return normalized


def jaccard_token_overlap_score(left_title: str, right_title: str) -> float:
    """
    Compute Jaccard overlap score between normalized title token sets.
    """
    left_tokens = set(normalize_podcast_title(left_title).split())
    right_tokens = set(normalize_podcast_title(right_title).split())
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union if union else 0.0


def best_match_episode(
    episodes: Sequence[Mapping[str, Any]],
    target_title: str,
    *,
    min_token_overlap_score: float = DEFAULT_MIN_TOKEN_OVERLAP_SCORE,
) -> Mapping[str, Any] | None:
    """
    Select the best matching episode candidate for a target title.

    Matching strategy (same behavior as legacy sync services):
    1. strict equality on normalized titles
    2. substring match in either direction on normalized titles
    3. highest Jaccard token overlap, accepted when score >= threshold

    The scoring is deterministic: for ties, the first candidate encountered
    keeps precedence.
    """
    target_normalized = normalize_podcast_title(target_title)

    for episode in episodes:
        episode_normalized = normalize_podcast_title(_episode_title(episode))
        if episode_normalized == target_normalized:
            return episode

    for episode in episodes:
        episode_normalized = normalize_podcast_title(_episode_title(episode))
        if (
            target_normalized in episode_normalized
            or episode_normalized in target_normalized
        ):
            return episode

    best_episode: Mapping[str, Any] | None = None
    best_score = 0.0
    for episode in episodes:
        score = jaccard_token_overlap_score(target_title, _episode_title(episode))
        if score > best_score:
            best_score = score
            best_episode = episode

    if best_score >= min_token_overlap_score:
        return best_episode
    return None


def _episode_title(episode: Mapping[str, Any]) -> str:
    title = episode.get("title", "")
    return title if isinstance(title, str) else str(title or "")
