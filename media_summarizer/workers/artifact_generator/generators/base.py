"""Base protocol for artifact generators."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


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
        transcript: str,
        *,
        language: Optional[str] = None,
        podcast_title: Optional[str] = None,
        episode_title: Optional[str] = None,
    ) -> str:
        """Build the LLM prompt for this artifact kind."""
        ...

    def response_format_schema(self) -> Optional[Dict[str, Any]]:
        """Return OpenAI Structured Outputs schema, or None if not used."""
        ...

    def unwrap_structured_response(self, content: str) -> str:
        """Unwrap structured output wrapper if needed (e.g. {cards: [...]})."""
        ...

    def validate(self, content: str) -> Any:
        """Validate and parse the LLM output. Returns the validated payload."""
        ...

    def build_artifact_content(
        self,
        validated: Any,
        *,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the content dict to pass to complete_artifact_generation."""
        ...
