"""Base protocol for artifact generators."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, Sequence


class ArtifactGenerator(Protocol):
    """Protocol that each per-kind generator must implement."""

    @property
    def artifact_type_value(self) -> str:
        """The string value of the artifact type (e.g. 'flashcards')."""
        ...

    @property
    def default_model(self) -> str:
        """Default LLM model for this artifact kind."""
        ...

    def build_prompt(
        self,
        sources: Sequence[Dict[str, Any]],
        *,
        language: Optional[str] = None,
    ) -> str:
        """Build the LLM prompt over the ordered corpus.

        ``sources`` is the snapshot order: one dict per source with ``title``,
        ``language`` and ``text``. A single-media scope is a one-element sequence
        — there is no separate per-media code path.
        """
        ...

    def response_format_schema(self) -> Optional[Dict[str, Any]]:
        """Return OpenAI Structured Outputs schema, or None if not used."""
        ...

    def unwrap_structured_response(self, content: str) -> str:
        """Unwrap structured output wrapper if needed (e.g. {cards: [...]})."""
        ...

    def validate(self, content: str) -> Dict[str, Any]:
        """Validate and parse the LLM output. Always returns a dict carrying ``title``."""
        ...

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the content dict to pass to complete_artifact_generation."""
        ...
