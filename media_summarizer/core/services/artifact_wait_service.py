"""
Resume — or end — the artifact requests that were waiting for their sources.

A generation asked for while a source was still being transcribed or translated is
not refused: it is written as a ``queued`` entry carrying ``awaiting_expires_at``
and nothing is enqueued (see ``artifact_service.plan_artifact_generation``). This
module is the other half — what turns that entry into a real generation once the
text lands, and what ends it when the text will never come (task-360).

It hangs off the two completion events the pipeline already emits, and adds no
queue, no schedule and no index of its own:

- ``workers/events/media_completed_worker`` — an ingestion finished, or failed;
- ``workers/transcript_translation_worker`` — a translation finished.

Both name a ``media_key``, so the lookup goes the same way every time: the saves
of that content (cross-user, since ingestion is deduplicated globally), then the
scopes those saves belong to — the media itself, its collection, and that
collection's ancestors, because a collection artifact covers every descendant —
then the ``queued`` entries of those scopes. An entry is waiting on *this* media
when its own snapshot says so: a source line carrying ``preparation``. Nothing
else has to be indexed, and an entry that had already excluded this media before
the request is never mistaken for one waiting on it.

Exactly-once is the conditional write in ``claim_awaiting_artifact``: the end of an
ingestion, the end of a translation and the last two sources of a collection
landing together all reach here, and only the caller that clears
``awaiting_expires_at`` sends the message.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from media_summarizer.core.models.media_artifact import (
    ArtifactScope,
    MediaArtifactRecord,
    MediaArtifactStatus,
    build_scope_key,
    content_scope_id_from_scope_key,
)
from media_summarizer.core.services import artifact_service
from media_summarizer.utils import media_artifacts, sqs
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)


async def resume_artifacts_awaiting_media(media_key: str) -> int:
    """Enqueue every waiting entry whose last unreadable source was this media.

    Returns how many generations were started. An entry that is still waiting on
    *another* source is left alone — and so is one whose own text turned out to
    need a translation, which this very call reserves and dispatches: the
    translation's completion event then brings it back here.

    Never raises. A completion event has a pipeline to finish; a generation that
    could not be resumed is bounded by its own deadline.
    """
    resumed = 0
    try:
        entries = await _entries_awaiting_media(media_key)
    except Exception as exc:  # noqa: BLE001 - a completion event must still complete
        logger.warning("Could not look up artifacts awaiting %s: %s", media_key, exc)
        return 0

    for record in entries:
        try:
            if await _resume_one(record):
                resumed += 1
        except Exception as exc:  # noqa: BLE001 - one entry must not stop the others
            log_event(
                logger,
                logging.ERROR,
                "artifact.resume_failed",
                "Could not resume an artifact waiting for its sources (non-fatal)",
                artifact_id=record.artifact_id,
                media_key=media_key,
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
    return resumed


async def fail_artifacts_awaiting_media(
    media_key: str,
    *,
    error_code: str,
    error_message: str,
) -> int:
    """End the waits that this media will never satisfy.

    A wait is not a failure, but a preparation that cannot complete is: the entry
    becomes ``failed`` with its ``error_code``, which is what the tile renders and
    what makes asking again a fresh generation over whatever is readable by then.

    Never raises, for the same reason as :func:`resume_artifacts_awaiting_media`.
    """
    ended = 0
    try:
        entries = await _entries_awaiting_media(media_key)
    except Exception as exc:  # noqa: BLE001 - a failure event must still complete
        logger.warning("Could not look up artifacts awaiting %s: %s", media_key, exc)
        return 0

    for record in entries:
        try:
            if await media_artifacts.fail_awaiting_artifact(
                artifact_id=record.artifact_id,
                error_code=error_code,
                error_message=error_message,
            ):
                ended += 1
                log_event(
                    logger,
                    logging.WARNING,
                    "artifact.wait_failed",
                    "Artifact wait ended: a source it needed will never be readable",
                    artifact_id=record.artifact_id,
                    artifact_type=record.artifact_type.value,
                    media_key=media_key,
                    error_code=error_code,
                )
        except Exception as exc:  # noqa: BLE001 - one entry must not stop the others
            logger.warning(
                "Could not fail the artifact %s waiting for %s: %s",
                record.artifact_id,
                media_key,
                exc,
            )
    return ended


async def _resume_one(record: MediaArtifactRecord) -> bool:
    """Re-resolve one waiting entry's scope and start it if everything is readable."""
    resolution = await artifact_service.resolve_scope_sources(
        user_id=record.user_id,
        scope=record.scope,
        scope_id=record.scope_id,
        # The language the *requester* was reading, read back off the entry. Using
        # the profile's current language instead would resolve a different corpus
        # than the one the id was computed over.
        reading_language=_reading_language(record),
    )

    if resolution.is_awaiting:
        log_event(
            logger,
            logging.INFO,
            "artifact.still_awaiting",
            "Artifact stays queued: another source is still being prepared",
            artifact_id=record.artifact_id,
            pending_count=len(resolution.pending),
        )
        return False

    try:
        artifact_service.enforce_scope_ceilings(resolution)
    except artifact_service.ArtifactServiceError as exc:
        # Everything it was waiting for is decided, and what is left cannot be
        # generated over: no source survived, or the corpus grew past a ceiling
        # while the request waited.
        await _fail(
            record,
            error_code=artifact_service.ERROR_CODE_PREPARATION_FAILED,
            error_message=str(exc),
        )
        return False

    expected_id = artifact_service.build_artifact_id(
        user_id=record.user_id,
        scope=record.scope,
        scope_id=content_scope_id_from_scope_key(record.scope_key),
        artifact_type=record.artifact_type,
        # Through the same normalizer the request went through, so the two hashes
        # are computed over byte-identical material.
        parameters=artifact_service.normalize_artifact_parameters(record.parameters),
        source_media_item_ids=resolution.expected_source_ids,
    )
    if expected_id != record.artifact_id:
        # The source set the request was accepted over is not the one that came
        # out. Generating anyway would store an artifact under an id that no
        # longer describes it, so the next identical request would regenerate and
        # be charged again — the reuse rule keys on exactly this equality.
        await _fail(
            record,
            error_code=artifact_service.ERROR_CODE_SOURCES_CHANGED,
            error_message=(
                "The sources of this generation changed while it was waiting for "
                "them to be prepared. Ask again to generate over the current ones."
            ),
        )
        return False

    if not await media_artifacts.claim_awaiting_artifact(
        artifact_id=record.artifact_id,
        sources=[
            source.model_dump(exclude_none=True) for source in resolution.snapshot()
        ],
        source_count=len(resolution.sources),
    ):
        # Another event resumed it, or its deadline ended it first.
        return False

    message = artifact_service.build_generation_message(
        record=record, resolution=resolution
    )
    try:
        await sqs.send_message(
            queue_name=artifact_service.get_artifact_queue(record.artifact_type),
            message_body=message,
        )
    except Exception as exc:
        # The entry no longer carries a deadline, so nothing would ever pick it up
        # again: it has to be failed here rather than left `queued` for good.
        await artifact_service.fail_artifact_generation(
            artifact_id=record.artifact_id,
            error_message=f"artifact_resume_enqueue_failed: {exc}",
            error_code="INTERNAL_ERROR",
        )
        raise

    log_event(
        logger,
        logging.INFO,
        "artifact.resumed",
        "Artifact generation started: the sources it was waiting for are readable",
        artifact_id=record.artifact_id,
        artifact_type=record.artifact_type.value,
        scope=record.scope.value,
        scope_id=record.scope_id,
        source_count=len(resolution.sources),
    )
    return True


async def _fail(
    record: MediaArtifactRecord,
    *,
    error_code: str,
    error_message: str,
) -> None:
    if await media_artifacts.fail_awaiting_artifact(
        artifact_id=record.artifact_id,
        error_code=error_code,
        error_message=error_message,
    ):
        log_event(
            logger,
            logging.WARNING,
            "artifact.wait_failed",
            "Artifact wait ended: what it was waiting for cannot be generated over",
            artifact_id=record.artifact_id,
            artifact_type=record.artifact_type.value,
            error_code=error_code,
            detail=error_message[:200],
        )


def _reading_language(record: MediaArtifactRecord) -> Optional[str]:
    language = record.parameters.get("language")
    return language if isinstance(language, str) and language else None


async def _entries_awaiting_media(media_key: str) -> List[MediaArtifactRecord]:
    """The waiting entries that named this media as one they are expecting."""
    from media_summarizer.utils import database_async
    from media_summarizer.utils import user_media as user_media_store

    media_key = (media_key or "").strip()
    if not media_key:
        return []

    rows = await user_media_store.list_by_media_key(media_key)
    if not rows:
        return []

    # scope_key -> the library row ids of that scope's owner pointing at this
    # content. A snapshot line names a row id, so matching needs both.
    scopes: Dict[str, Set[str]] = {}
    folders_by_user: Dict[str, List[Any]] = {}
    for row in rows:
        media_item_id = getattr(row, "media_item_id", None)
        if not media_item_id:
            continue
        keys = [
            build_scope_key(
                user_id=row.user_id, scope=ArtifactScope.MEDIA, scope_id=media_key
            )
        ]
        if row.folder_id:
            folders = folders_by_user.get(row.user_id)
            if folders is None:
                folders = await database_async.get_folders_by_user_id(row.user_id)
                folders_by_user[row.user_id] = folders
            for folder_id in _folder_and_ancestor_ids(row.folder_id, folders):
                keys.append(
                    build_scope_key(
                        user_id=row.user_id,
                        scope=ArtifactScope.FOLDER,
                        scope_id=folder_id,
                    )
                )
        for key in keys:
            scopes.setdefault(key, set()).add(media_item_id)

    entries: List[MediaArtifactRecord] = []
    for scope_key, media_item_ids in scopes.items():
        artifact_ids = await media_artifacts.list_queued_artifact_ids_by_scope(
            scope_key=scope_key
        )
        for artifact_id in artifact_ids:
            record = await media_artifacts.get_media_artifact_by_id(artifact_id)
            if record is None:
                continue
            if record.status != MediaArtifactStatus.QUEUED:
                continue
            # The marker that separates a request waiting for a source from one the
            # generator is about to pick up.
            if record.awaiting_expires_at is None:
                continue
            if not _awaits_any_of(record, media_item_ids):
                continue
            entries.append(record)
    return entries


def _awaits_any_of(record: MediaArtifactRecord, media_item_ids: Set[str]) -> bool:
    return any(
        source.preparation and source.media_item_id in media_item_ids
        for source in record.sources
    )


def _folder_and_ancestor_ids(folder_id: str, folders: List[Any]) -> List[str]:
    """A collection and the ones that contain it, transitively.

    A collection artifact covers the folder *and every descendant* (that is what
    the Sources tab shows), so a media in a sub-collection is a source of every
    collection above it. The visited set guards a cycle the folder tree should not
    contain but must not hang on.
    """
    by_id = {getattr(folder, "id", None): folder for folder in folders}
    chain: List[str] = []
    visited: Set[str] = set()
    current: Optional[str] = folder_id
    while current and current not in visited:
        visited.add(current)
        chain.append(current)
        folder = by_id.get(current)
        current = getattr(folder, "parent_folder_id", None) if folder else None
    return chain
