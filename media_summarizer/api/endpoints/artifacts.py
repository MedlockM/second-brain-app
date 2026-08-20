"""Artifact routes, scope-addressed.

One set of routes serves both scopes (task-269 §9.1): a media artifact is
requested with ``scope="media"``, a collection artifact with ``scope="folder"``.
The per-media routes are gone, with no alias and no deprecation window.

Ownership is a comparison, not a query: the record carries ``user_id``, and the
listing index is keyed on it. The previous check resolved the artifact's media
item, which cannot work for a collection artifact — it has no media.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models.media_artifact import ArtifactScope
from media_summarizer.core.services import engagement_service, quota_enforcer
from media_summarizer.core.services.artifact_service import (
    ArtifactGenerationDisabledError,
    ArtifactScopeEmptyError,
    ArtifactScopeTooLargeError,
    ArtifactTranscriptNotReadyError,
    ArtifactTypeNotEnabledError,
    commit_artifact_generation,
    enforce_scope_ceilings,
    get_media_artifact_record,
    list_scope_artifacts,
    plan_artifact_generation,
    resolve_scope_sources,
)
from media_summarizer.utils import s3
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 100


class ArtifactCreateRequest(BaseModel):
    scope: str = Field(..., description="Scope of the generation: 'media' or 'folder'")
    scope_id: str = Field(..., description="Media item id, or folder (collection) id")
    artifact_type: str = Field(
        ...,
        description="Type of artifact: summary_short, summary_detailed, notes, quiz, flashcards",
    )
    parameters: Optional[dict] = Field(
        default=None, description="Optional parameters for artifact generation"
    )


class ArtifactSourceResponse(BaseModel):
    media_item_id: str
    title: Optional[str] = None
    language: Optional[str] = None
    excluded: bool = False
    excluded_reason: Optional[str] = None


class ArtifactSummaryResponse(BaseModel):
    """One history row. These are exactly the attributes the GSI projects."""

    artifact_id: str
    artifact_type: str
    status: str
    title: Optional[str] = None
    source_count: int
    created_at: str
    completed_at: Optional[str] = None
    error_code: Optional[str] = None


class ArtifactDetailResponse(ArtifactSummaryResponse):
    scope: str
    scope_id: str
    sources: List[ArtifactSourceResponse] = Field(default_factory=list)
    s3_key: Optional[str] = None


class ArtifactListResponse(BaseModel):
    scope: str
    scope_id: str
    artifacts: List[ArtifactSummaryResponse]
    next_cursor: Optional[str] = None


class ArtifactContentResponse(BaseModel):
    artifact_id: str
    artifact_type: str
    scope: str
    scope_id: str
    status: str
    content: Dict[str, Any] = Field(
        ..., description="Parsed JSON content of the artifact (summary, notes, quiz, flashcards)"
    )


def _parse_scope(value: str) -> ArtifactScope:
    try:
        return ArtifactScope(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope must be 'media' or 'folder'",
        )


def _summary(record: Any) -> ArtifactSummaryResponse:
    return ArtifactSummaryResponse(
        artifact_id=record.artifact_id,
        artifact_type=record.artifact_type.value,
        status=record.status.value,
        title=record.title,
        source_count=record.source_count,
        created_at=record.created_at.isoformat(),
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
        error_code=record.error_code,
    )


def _detail(record: Any) -> ArtifactDetailResponse:
    return ArtifactDetailResponse(
        **_summary(record).model_dump(),
        scope=record.scope.value,
        scope_id=record.scope_id,
        sources=[
            ArtifactSourceResponse(
                media_item_id=source.media_item_id,
                title=source.title,
                language=source.language,
                excluded=source.excluded,
                excluded_reason=source.excluded_reason,
            )
            for source in record.sources
        ],
        s3_key=record.storage.key if record.storage is not None else None,
    )


async def _assert_scope_owned(
    *,
    scope: ArtifactScope,
    scope_id: str,
    user_id: str,
) -> str:
    from media_summarizer.utils import database_async
    from media_summarizer.utils import user_media as user_media_store

    if scope == ArtifactScope.MEDIA:
        record = await user_media_store.get_user_media(user_id, scope_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found"
            )
        return record.media_key

    folder = await database_async.get_folder_by_id(scope_id)
    if folder is None or folder.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
        )
    return scope_id


@router.post(
    "/artifacts",
    response_model=ArtifactDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_artifact(
    payload: ArtifactCreateRequest,
    request: Request,
    response: Response,
    current_user: AuthUser = Depends(get_current_user),
):
    """Request a generation over a scope.

    The order of the checks matters: a deduplicated request must consume nothing,
    so the quota is debited *after* the dedup verdict is known and never before
    (task-269 §10.3).
    """
    scope = _parse_scope((payload.scope or "").strip().lower())
    artifact_type = (payload.artifact_type or "").strip().lower()
    scope_id = (payload.scope_id or "").strip()
    token = bind_log_context(
        user_id=current_user.id,
        scope=scope.value,
        scope_id=scope_id,
        artifact_type=artifact_type,
    )
    try:
        content_scope_id = await _assert_scope_owned(
            scope=scope, scope_id=scope_id, user_id=current_user.id
        )

        resolution = await resolve_scope_sources(
            user_id=current_user.id,
            scope=scope,
            scope_id=scope_id,
            reading_language=current_user.reading_language,
        )
        enforce_scope_ceilings(resolution)

        plan = await plan_artifact_generation(
            user_id=current_user.id,
            scope=scope,
            scope_id=scope_id,
            content_scope_id=content_scope_id,
            artifact_type=artifact_type,
            resolution=resolution,
            parameters=payload.parameters,
        )

        # Quota comes after the dedup verdict and before the write: the same tap
        # twice must consume nothing, and a denied request must leave no entry.
        if not plan.deduplicated:
            quota_result = await quota_enforcer.check_generation_allowed(
                current_user.id,
                scope=scope.value,
                source_count=len(resolution.sources),
            )
            if not quota_result.allowed:
                log_event(
                    logger,
                    logging.WARNING,
                    "artifact.create.quota_denied",
                    "Artifact generation denied by quota",
                    error_code=quota_result.error_code,
                )
                raise HTTPException(
                    status_code=quota_result.http_status,
                    detail={
                        "error_code": quota_result.error_code,
                        "message": quota_result.message,
                    },
                    headers={"X-Quota-Error-Code": quota_result.error_code or ""},
                )

        record, deduplicated = await commit_artifact_generation(plan)

        if deduplicated:
            response.status_code = status.HTTP_200_OK
        else:
            await quota_enforcer.record_generation(
                current_user.id,
                scope=scope.value,
                source_count=record.source_count,
                idempotency_token=record.artifact_id,
            )

        # E1 of task-303: launching a generation is the strongest intent signal the
        # app has, and the wait is precisely when the user needs a way back — so the
        # scope enters "Continue learning" here, deduplicated path included. The
        # ownership assertion above is what lets this skip its own check. Swallows
        # everything by contract: a recency stamp must never fail a generation the
        # user asked for.
        await engagement_service.stamp(
            user_id=current_user.id,
            kind=(
                engagement_service.KIND_MEDIA
                if scope == ArtifactScope.MEDIA
                else engagement_service.KIND_COLLECTION
            ),
            subject_id=scope_id,
        )

        log_event(
            logger,
            logging.INFO,
            "artifact.create.requested",
            "Artifact generation queued"
            if not deduplicated
            else "Artifact request deduplicated",
            artifact_id=record.artifact_id,
            artifact_type=artifact_type,
            source_count=record.source_count,
            deduplicated=deduplicated,
        )
        return _detail(record)

    except ArtifactTypeNotEnabledError as exc:
        log_event(
            logger,
            logging.WARNING,
            "artifact.create.invalid_type",
            "Invalid artifact type requested",
            artifact_type=artifact_type,
            error_code="INVALID_ARTIFACT_TYPE",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except ArtifactGenerationDisabledError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Artifact generation is currently disabled",
        )
    except ArtifactScopeEmptyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "scope_empty",
                "message": str(exc),
            },
        )
    except ArtifactScopeTooLargeError as exc:
        # The four numbers travel with the refusal so the mobile has nothing to
        # compute to render it (task-272 AC#9).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "scope_too_large",
                "message": str(exc),
                "source_count": exc.source_count,
                "max_sources": exc.max_sources,
                "estimated_tokens": exc.estimated_tokens,
                "max_tokens": exc.max_tokens,
            },
        )
    except ArtifactTranscriptNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "sources_not_ready",
                "message": str(exc),
                "pending_count": exc.pending_count,
                "pending_titles": exc.pending_titles,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "artifact.create.failed",
            "Failed to queue artifact generation",
            scope=scope.value,
            scope_id=scope_id,
            artifact_type=artifact_type,
            error_type=type(exc).__name__,
            error_code="ARTIFACT_CREATE_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue artifact generation",
        )
    finally:
        reset_log_context(token)


@router.get("/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    request: Request,
    scope: str = Query(..., description="'media' or 'folder'"),
    scope_id: str = Query(..., description="Media item id, or folder id"),
    limit: int = Query(DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    cursor: Optional[str] = Query(None),
    current_user: AuthUser = Depends(get_current_user),
):
    """A scope's whole history, newest first, every type mixed.

    This is also the progress endpoint: in-flight entries appear here with status
    ``queued`` or ``generating``, so the mobile polls once per scope rather than
    once per artifact type.
    """
    resolved_scope = _parse_scope((scope or "").strip().lower())
    token = bind_log_context(
        user_id=current_user.id, scope=resolved_scope.value, scope_id=scope_id
    )
    try:
        content_scope_id = await _assert_scope_owned(
            scope=resolved_scope, scope_id=scope_id, user_id=current_user.id
        )

        records, next_cursor = await list_scope_artifacts(
            user_id=current_user.id,
            scope=resolved_scope,
            scope_id=scope_id,
            content_scope_id=content_scope_id,
            limit=limit,
            cursor=cursor,
        )

        log_event(
            logger,
            logging.INFO,
            "artifact.list.succeeded",
            "Artifact history retrieved",
            scope=resolved_scope.value,
            scope_id=scope_id,
            artifact_count=len(records),
        )

        return ArtifactListResponse(
            scope=resolved_scope.value,
            scope_id=scope_id,
            artifacts=[_summary(record) for record in records],
            next_cursor=next_cursor,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "artifact.list.failed",
            "Failed to list artifacts",
            scope=resolved_scope.value,
            scope_id=scope_id,
            error_type=type(exc).__name__,
            error_code="ARTIFACT_LIST_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list artifacts",
        )
    finally:
        reset_log_context(token)


@router.get("/artifacts/{artifact_id}", response_model=ArtifactDetailResponse)
async def get_artifact(
    artifact_id: str,
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    """One entry with its full source snapshot."""
    token = bind_log_context(user_id=current_user.id, artifact_id=artifact_id)
    try:
        record = await get_media_artifact_record(artifact_id)
        if record is None or record.user_id != current_user.id:
            log_event(
                logger,
                logging.WARNING,
                "artifact.get.not_found",
                "Artifact not found",
                artifact_id=artifact_id,
                error_code="ARTIFACT_NOT_FOUND",
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

        log_event(
            logger,
            logging.INFO,
            "artifact.get.succeeded",
            "Artifact retrieved",
            artifact_id=artifact_id,
            artifact_type=record.artifact_type.value,
            scope=record.scope.value,
            scope_id=record.scope_id,
            status=record.status.value,
        )
        return _detail(record)

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "artifact.get.failed",
            "Failed to retrieve artifact",
            artifact_id=artifact_id,
            error_type=type(exc).__name__,
            error_code="ARTIFACT_GET_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve artifact",
        )
    finally:
        reset_log_context(token)


@router.get("/artifacts/{artifact_id}/content", response_model=ArtifactContentResponse)
async def get_artifact_content(
    artifact_id: str,
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    """Return the JSON payload an artifact resolved to.

    The worker pipeline writes each artifact as a JSON blob in its dedicated
    S3 bucket (one bucket per artifact type). This endpoint resolves the
    record, verifies ownership, downloads the blob and inlines the parsed
    content in the response so the mobile client doesn't need to deal with
    presigned URLs.

    Side-effect-free, and it must stay that way: the "artifact opened" engagement
    (task-303 §5.2) is reported by an explicit ``POST /api/engagements`` from the
    viewer, not stamped here. This route is replayed by the client after a 401
    refresh and can be run by a router preload for a screen the user never opens, so
    a write on this path would record engagements nobody made.
    """
    token = bind_log_context(user_id=current_user.id, artifact_id=artifact_id)
    try:
        record = await get_media_artifact_record(artifact_id)
        if record is None or record.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )

        if record.storage is None:
            # Artifact exists but isn't ready yet (queued / generating / failed).
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Artifact is not ready (status: {record.status.value}). "
                    "Try again once generation completes."
                ),
            )

        try:
            payload_bytes = await s3.download_file_to_memory(
                bucket=record.storage.bucket,
                key=record.storage.key,
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "artifact.content.download_failed",
                "Failed to download artifact payload from S3",
                artifact_id=artifact_id,
                bucket=record.storage.bucket,
                key=record.storage.key,
                error_type=type(exc).__name__,
                error_code="ARTIFACT_CONTENT_DOWNLOAD_FAILED",
                exc_info=exc,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Artifact storage is currently unreachable",
            )

        try:
            content = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            log_event(
                logger,
                logging.ERROR,
                "artifact.content.parse_failed",
                "Failed to parse artifact payload as JSON",
                artifact_id=artifact_id,
                error_type=type(exc).__name__,
                error_code="ARTIFACT_CONTENT_PARSE_FAILED",
                exc_info=exc,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Artifact payload is malformed",
            )

        if not isinstance(content, dict):
            content = {"value": content}

        log_event(
            logger,
            logging.INFO,
            "artifact.content.succeeded",
            "Artifact content retrieved",
            artifact_id=artifact_id,
            artifact_type=record.artifact_type.value,
            scope=record.scope.value,
            scope_id=record.scope_id,
            content_size=len(payload_bytes),
        )

        return ArtifactContentResponse(
            artifact_id=record.artifact_id,
            artifact_type=record.artifact_type.value,
            scope=record.scope.value,
            scope_id=record.scope_id,
            status=record.status.value,
            content=content,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "artifact.content.failed",
            "Failed to retrieve artifact content",
            artifact_id=artifact_id,
            error_type=type(exc).__name__,
            error_code="ARTIFACT_CONTENT_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve artifact content",
        )
    finally:
        reset_log_context(token)
