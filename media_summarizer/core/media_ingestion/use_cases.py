"""Application use-cases for media ingestion."""

from __future__ import annotations

import hashlib
import re

from media_summarizer.core.media_ingestion.domain import (
    IngestionOutcome,
    IngestSharedContentCommand,
    IngestUrlCommand,
    MediaFamily,
    MediaType,
    ResolveContext,
    ResolvedMedia,
    SharedContentType,
)
from media_summarizer.core.media_ingestion.errors import (
    DEFAULT_INVALID_URL_MESSAGE,
    InvalidUrlError,
    MediaIngestionError,
    ResolutionError,
)
from media_summarizer.core.media_ingestion.ports import SubmissionOrchestratorPort
from media_summarizer.core.media_ingestion.router import ResolverRouter
from media_summarizer.core.media_ingestion.title_derivation import first_sentence
from media_summarizer.core.services.media_identity import (
    derive_media_identity,
    generate_media_key,
)

_MULTI_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_shared_text(raw_text: str) -> str:
    return _MULTI_WHITESPACE_RE.sub(" ", (raw_text or "").strip())


def _share_locator(*, source_platform: str, share_type: str, content_hash: str) -> str:
    return f"share://{source_platform}/{share_type}/{content_hash}"


class IngestUrlUseCase:
    """
    Orchestrates the media ingestion core flow.

    Flow:
    1) canonicalize and derive media identity
    2) route URL to classification + resolver through central router
    3) resolve media payload via routed resolver
    4) submit processing via orchestrator port
    """

    def __init__(
        self,
        *,
        router: ResolverRouter,
        orchestrator: SubmissionOrchestratorPort,
    ) -> None:
        self._router = router
        self._orchestrator = orchestrator

    async def execute(self, command: IngestUrlCommand) -> IngestionOutcome:
        raw_url = (command.request.url or "").strip()
        if not raw_url:
            raise InvalidUrlError(DEFAULT_INVALID_URL_MESSAGE)

        try:
            normalized_url, media_key = derive_media_identity(raw_url)
        except ValueError as exc:
            raise InvalidUrlError(DEFAULT_INVALID_URL_MESSAGE) from exc

        route = self._router.route(normalized_url)

        resolve_context = ResolveContext(
            command=command,
            normalized_url=normalized_url,
            media_key=media_key,
            classification=route.classification,
        )

        try:
            resolved = await route.resolver.resolve(resolve_context)
        except MediaIngestionError:
            raise
        except Exception as exc:
            raise ResolutionError(
                f"Resolver '{route.resolver.key}' failed: {exc}"
            ) from exc

        return await self._orchestrator.submit(command=command, resolved=resolved)


class IngestSharedContentUseCase:
    """
    Orchestrates shared-content ingestion without URL classification.

    Flow:
    1) validate shared payload metadata from API/mobile
    2) derive deterministic locator + media key
    3) normalize into `ResolvedMedia`
    4) submit through the shared orchestrator port
    """

    def __init__(
        self,
        *,
        orchestrator: SubmissionOrchestratorPort,
    ) -> None:
        self._orchestrator = orchestrator

    async def execute(
        self,
        command: IngestSharedContentCommand,
    ) -> IngestionOutcome:
        request = command.request
        source_platform = request.source_platform
        share_type = request.share_type

        if share_type == SharedContentType.TEXT:
            normalized_text = _normalize_shared_text(request.text or "")
            if not normalized_text:
                raise ResolutionError("Shared text payload is empty.")

            content_hash = hashlib.sha256(
                f"{source_platform.value}:text:{normalized_text}".encode("utf-8")
            ).hexdigest()
            locator = _share_locator(
                source_platform=source_platform.value,
                share_type=share_type.value,
                content_hash=content_hash,
            )
            resolved = ResolvedMedia(
                media_key=generate_media_key(locator),
                normalized_url=locator,
                media_family=MediaFamily.TEXT,
                media_type=MediaType.SHARED_TEXT,
                source_platform=source_platform,
                resolver_key="shared.text",
                raw_text=normalized_text,
                # Shared text carries no metadata at all, so its own first
                # sentence is the title (task-266): the same rule X already
                # applies to a post body.
                title=first_sentence(normalized_text),
                # No cover and no creator, by construction rather than by
                # omission: there is no provider to ask and the sharer is the
                # user themselves (task-302 §4, row 7). The tile renders its
                # media-type icon and drops its second line.
                cover_url=None,
                creator_name=None,
                metadata={
                    "share_type": share_type.value,
                    "resolver_key": "shared.text",
                    "media_family": MediaFamily.TEXT.value,
                    "media_type": MediaType.SHARED_TEXT.value,
                    "source_platform": source_platform.value,
                    "content_hash": content_hash,
                },
            )
            return await self._orchestrator.submit(command=command, resolved=resolved)

        if share_type == SharedContentType.AUDIO:
            content_hash = (request.content_hash or "").strip().lower()
            staged_audio_s3_key = (request.staged_audio_s3_key or "").strip()
            if not content_hash:
                raise ResolutionError("Shared audio content hash is required.")
            if not staged_audio_s3_key:
                raise ResolutionError("Shared audio staging key is required.")

            locator = _share_locator(
                source_platform=source_platform.value,
                share_type=share_type.value,
                content_hash=content_hash,
            )
            resolved = ResolvedMedia(
                media_key=generate_media_key(locator),
                normalized_url=locator,
                media_family=MediaFamily.AUDIO,
                media_type=MediaType.AUDIO_FILE,
                source_platform=source_platform,
                resolver_key="shared.audio",
                # No title here on purpose: the orchestrator derives it from
                # `metadata["original_name"]` below, and a WhatsApp voice note
                # whose name is `PTT-20260817-WA0003.opus` legitimately falls
                # through to the "Voice note — <date>" label (task-266).
                #
                # No cover and no creator either, and deliberately so: reading an
                # ID3 `APIC`/`artist` tag would need `mutagen` in the runtime and
                # only ever pays off for a ripped podcast episode, which already
                # has real artwork through the podcast path (task-302 §11).
                audio_s3_key=staged_audio_s3_key,
                metadata={
                    "share_type": share_type.value,
                    "resolver_key": "shared.audio",
                    "media_family": MediaFamily.AUDIO.value,
                    "media_type": MediaType.AUDIO_FILE.value,
                    "source_platform": source_platform.value,
                    "content_hash": content_hash,
                    "content_mime_type": request.content_mime_type,
                    "original_name": request.original_name,
                    "content_size_bytes": request.content_size_bytes,
                    "audio_duration_seconds": int(request.audio_duration_seconds or 0),
                },
            )
            return await self._orchestrator.submit(command=command, resolved=resolved)

        raise ResolutionError("Unsupported shared content type.")
