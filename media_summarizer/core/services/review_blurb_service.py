"""Trigger the internal ``review_blurb`` artifact at the end of ingestion (task-323).

Its own module rather than a function in ``digest_service``: the completion path of
every ingestion would then import the digest graph — digest records, digest
settings, weekly assembly, the push producer — to write one triage card. This module
imports the artifact service and the library store, nothing else.

The shape is deliberately the same as ``digest_service.trigger_summary_short_generation``:
``resolve_scope_sources`` → ``enforce_scope_ceilings`` → ``plan_artifact_generation``
→ ``commit_artifact_generation``. Like it, **no quota is debited**: the allowance is
spent by what the *user* asks for, and the endpoint in ``api/endpoints/artifacts.py``
is the only place that debits it. A background artifact nobody requested must not
eat into what the user paid for.
"""

from __future__ import annotations

import logging
from typing import Optional

from media_summarizer.core.models.media_artifact import ArtifactScope, MediaArtifactType
from media_summarizer.core.services.durable_media_service import resolve_job_for_record
from media_summarizer.utils import database_async
from media_summarizer.utils import user_media as user_media_store

logger = logging.getLogger(__name__)


async def trigger_review_blurb_generation(
    user_id: str,
    media_item_id: str,
) -> Optional[str]:
    """Queue the blurb for one library row, or return ``None`` if there is nothing to do.

    Returns the ``artifact_id`` that answers this row (queued or already existing),
    ``None`` when the row cannot produce one — no row, deleted row, no transcript,
    a blurb already there, or a service error. Never raises: every caller is a
    completion hook whose SQS message must still be deleted.
    """
    try:
        record = await user_media_store.get_user_media(user_id, media_item_id)
    except Exception as exc:
        logger.warning(
            "review_blurb: cannot read library row %s: %s", media_item_id, exc
        )
        return None

    if record is None or record.is_deleted:
        logger.debug(
            "review_blurb: no live library row for %s, nothing to generate",
            media_item_id,
        )
        return None

    # Already provisioned. Checked first so a redelivered completion event, or a
    # backfill re-run, costs one GetItem instead of a scope resolution.
    if record.review_blurb is not None and record.review_blurb.hook.strip():
        return None

    job = await resolve_job_for_record(record)
    if job is None or not getattr(job, "transcription_s3_key", None):
        logger.debug("review_blurb: no transcript yet for %s", media_item_id)
        return None

    from media_summarizer.core.services.artifact_service import (
        ArtifactGenerationOutcome,
        ArtifactScopeEmptyError,
        ArtifactServiceError,
        ArtifactTranscriptNotReadyError,
        commit_artifact_generation,
        copy_review_blurb_to_library_row,
        enforce_scope_ceilings,
        plan_artifact_generation,
        resolve_scope_sources,
    )

    reading_language = await _reading_language(user_id)

    try:
        # ``reading_language=None`` on purpose, and it is the whole trick of this
        # hook. Passing the user's language here would send the resolver into the
        # translation pipeline: on a source that is not yet in that language it
        # enqueues a translation and raises ``ArtifactTranscriptNotReadyError``, so
        # a first-ingestion blurb would essentially never be produced — there is no
        # retry loop behind this call, ingestion completes once. Resolving without a
        # target language reads the transcript that exists and cannot raise that
        # error for translation reasons.
        #
        # The output language is carried by ``parameters`` instead: the model reads
        # the original text and writes the blurb in the user's reading language,
        # which is what the reader actually needs. It also keeps the language part
        # of ``artifact_id``, so changing reading language yields a new blurb rather
        # than silently reusing the old one.
        resolution = await resolve_scope_sources(
            user_id=user_id,
            scope=ArtifactScope.MEDIA,
            scope_id=media_item_id,
            reading_language=None,
        )
        enforce_scope_ceilings(resolution)

        parameters = {"language": reading_language} if reading_language else {}
        plan = await plan_artifact_generation(
            user_id=user_id,
            scope=ArtifactScope.MEDIA,
            scope_id=media_item_id,
            content_scope_id=record.media_key,
            artifact_type=MediaArtifactType.REVIEW_BLURB,
            resolution=resolution,
            parameters=parameters,
        )
        artifact, outcome = await commit_artifact_generation(plan)

        # A second save of the same content by the same user hashes to the same
        # artifact_id, so it is answered by REUSED and its own row was never
        # written to. Repairing it from the stored object costs one S3 read and
        # spends nothing on the model.
        if outcome == ArtifactGenerationOutcome.REUSED:
            await copy_review_blurb_to_library_row(
                record=artifact,
                media_item_id=media_item_id,
            )

        logger.info(
            "review_blurb: %s for %s (artifact %s)",
            outcome.value,
            media_item_id,
            artifact.artifact_id,
        )
        return artifact.artifact_id
    except (
        ArtifactScopeEmptyError,
        ArtifactTranscriptNotReadyError,
        ArtifactServiceError,
    ) as exc:
        logger.warning(
            "review_blurb: failed to trigger for %s: %s", media_item_id, exc
        )
        return None


async def _reading_language(user_id: str) -> Optional[str]:
    """The owner's reading language, or ``None`` when it cannot be read.

    ``None`` is a valid answer, not a failure: the prompt then tells the model to
    answer in the language of the sources.
    """
    try:
        user = await database_async.get_user_by_id(user_id)
    except Exception:
        return None
    return getattr(user, "reading_language", None) if user is not None else None
