"""
Unified artifact generator worker.

Polls a single SQS queue (artifact-generator-queue) and dispatches to
per-kind generators based on `body.artifact_type`. Shared logic for S3
download, LLM call, retries, validation, and status transitions lives here
once instead of being duplicated across 5 separate workers.

Consolidates the former flashcards, notes, quiz, summarization, and summary
workers (task-195).

One invocation = one artifact type = one LLM call over the whole corpus
(task-269, strategy S1). N transcripts are downloaded in parallel and
concatenated, tagged, into a single prompt: no condensation stage, so the detail
that flashcards and quizzes live on is still in front of the model. The 300 s
timeout and the 180 s LLM timeout are unchanged because the number of sequential
calls per invocation is still one.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict

import aiohttp

from media_summarizer.core.models.media_artifact import (
    ArtifactLlmUsage,
    MediaArtifactType,
)
from media_summarizer.core.services import fsrs_service, quota_enforcer
from media_summarizer.core.services.artifact_service import (
    MAX_COLLECTION_CORPUS_TOKENS,
    claim_artifact_generation,
    complete_artifact_generation,
    estimate_tokens,
    fail_artifact_generation,
)
from media_summarizer.core.services.llm_pricing import estimate_llm_cost_eur
from media_summarizer.utils import s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.llm_failure import (
    REFUSAL_AUTHENTICATION,
    LLMFailureKind,
    LlmProviderRefusedError,
    classify_llm_failure,
    log_llm_generation_failure,
)
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)

logger = logging.getLogger(__name__)

ARTIFACT_GENERATOR_QUEUE = required_env("ARTIFACT_GENERATOR_QUEUE")
TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")
LLM_API_URL = os.environ.get(
    "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


class ArtifactValidationError(Exception):
    """Raised when the model output does not pass the generator's validator."""


def _strip_code_fences(content: str) -> str:
    """Remove markdown code fences from LLM output."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


async def _download_transcripts(
    sources: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    """Fetch the N transcripts in parallel, keeping the snapshot order.

    25 sources at the measured median are ~400 kB, comfortably inside the
    worker's 512 MB. Sequential downloads would spend most of the invocation
    waiting on S3 round-trips instead of on the model.
    """

    async def fetch(source: Dict[str, Any]) -> Dict[str, Any]:
        key = source.get("transcript_s3_key")
        bucket = source.get("transcript_bucket") or TRANSCRIPT_BUCKET
        content = await s3.download_file_to_memory(bucket=bucket, key=key)
        return {
            "media_item_id": source.get("media_item_id"),
            "title": source.get("title"),
            "language": source.get("language"),
            # Dates of the corpus header: the model needs them to resolve the
            # "today" a transcript is full of (task-316 §2.7).
            "published": source.get("published"),
            "captured": source.get("captured"),
            "text": content.decode("utf-8", errors="ignore"),
        }

    return list(await asyncio.gather(*(fetch(source) for source in sources)))


async def _call_llm(
    prompt: str,
    model: str,
    artifact_type: str,
    response_format: Dict[str, Any] | None = None,
    prompt_cache_key: str | None = None,
) -> tuple[str, Dict[str, Any]]:
    """Call the LLM API and return the raw content plus the provider usage block.

    ``prompt_cache_key`` routes the five requests of one generation to the same
    machine so they hit the same cached corpus prefix. The usage block is what
    makes the real cost measurable instead of estimated (`llm_usage`).
    """
    if not OPENAI_API_KEY:
        # A missing key and a revoked key are the same outage seen from here, and
        # they need the same action, so they carry the same refusal reason.
        raise LlmProviderRefusedError(
            "openai_api_key_missing",
            refusal_reason=REFUSAL_AUTHENTICATION,
            # Three deliveries of the same message would make three identical
            # no-ops: the key appears in the runtime secret, not between retries.
            failure_kind=LLMFailureKind.PERMANENT,
        )

    timeout = aiohttp.ClientTimeout(
        total=int(os.environ.get("LLM_TIMEOUT_SECONDS", "180"))
    )
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    if response_format is not None:
        payload["response_format"] = response_format
    if prompt_cache_key:
        payload["prompt_cache_key"] = prompt_cache_key

    # gpt-5 family does not support temperature parameter
    model_lower = (model or "").lower()
    if not any(marker in model_lower for marker in ["o1", "o3", "gpt-5"]):
        try:
            payload["temperature"] = float(os.environ.get("LLM_TEMPERATURE", "0.3"))
        except Exception:
            payload["temperature"] = 0.3

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            if response.status >= 400:
                body = await response.text()
                # One parse of the provider's answer, both axes out: what the
                # operator must do about it, and whether another delivery of this
                # message could ever get a different answer.
                failure = classify_llm_failure(
                    status_code=response.status,
                    body=body,
                    retry_after=response.headers.get("Retry-After"),
                )
                log_event(
                    logger,
                    logging.ERROR,
                    "external_call.failed",
                    "LLM API returned an error",
                    provider="openai",
                    artifact_type=artifact_type,
                    status=response.status,
                    failure_kind=failure.kind,
                    refusal_reason=failure.refusal_reason,
                    detail=body[:500],
                )
                # A refusal is raised as itself so the failure metric can name the
                # account state (no credit / bad key / throttled) instead of
                # lumping it in with a validation error.
                if failure.refusal_reason is not None:
                    raise LlmProviderRefusedError(
                        f"llm_provider_refused_http_{response.status}",
                        refusal_reason=failure.refusal_reason,
                        failure_kind=failure.kind,
                        provider_status=response.status,
                    )
            response.raise_for_status()
            result = await response.json()
            usage = result.get("usage") or {}
            return result["choices"][0]["message"]["content"], usage


def _read_llm_usage(usage: Dict[str, Any], model: str) -> ArtifactLlmUsage:
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    cached_tokens = int(
        (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    )
    completion_tokens = int(usage.get("completion_tokens") or 0)
    return ArtifactLlmUsage(
        prompt_tokens=prompt_tokens,
        cached_tokens=cached_tokens,
        completion_tokens=completion_tokens,
        cost_eur=estimate_llm_cost_eur(
            model=model,
            prompt_tokens=prompt_tokens,
            cached_tokens=cached_tokens,
            completion_tokens=completion_tokens,
        ),
    )


def _supports_structured_outputs(model: str) -> bool:
    """Check if the model supports OpenAI Structured Outputs."""
    model_lower = (model or "").lower()
    return any(
        marker in model_lower
        for marker in ["gpt-4o", "gpt-5", "gpt-4.1"]
    )


async def process_message(message: Dict[str, Any]) -> None:
    """Process a single artifact generation message from the unified queue."""
    from media_summarizer.workers.artifact_generator.generators import GENERATORS

    body = json.loads(message.get("Body", "{}"))
    artifact_id = body.get("artifact_id")
    artifact_type_str = body.get("artifact_type")
    sources = body.get("sources") or []
    parameters = body.get("parameters") or {}
    language = parameters.get("language")
    prompt_cache_key = body.get("prompt_cache_key")
    # Translation provenance set by the common detect+translate step (task-192).
    translation = body.get("translation") if isinstance(body.get("translation"), dict) else None

    # Resolve artifact type
    try:
        artifact_type = MediaArtifactType(artifact_type_str)
    except (ValueError, KeyError):
        log_event(
            logger,
            logging.ERROR,
            "worker.unknown_artifact_type",
            f"Unknown artifact_type: {artifact_type_str}",
            artifact_id=artifact_id,
        )
        raise ValueError(f"Unknown artifact_type: {artifact_type_str}")

    generator = GENERATORS.get(artifact_type)
    if generator is None:
        log_event(
            logger,
            logging.ERROR,
            "worker.unsupported_artifact_type",
            f"No generator registered for artifact_type: {artifact_type_str}",
            artifact_id=artifact_id,
        )
        raise ValueError(f"No generator for artifact_type: {artifact_type_str}")

    context_token = bind_log_context(
        artifact_id=artifact_id,
        artifact_type=artifact_type.value,
        scope=body.get("scope"),
        scope_id=body.get("scope_id"),
    )

    try:
        if not artifact_id or not sources:
            log_event(
                logger,
                logging.ERROR,
                "worker.invalid_message",
                f"Missing fields for {artifact_type.value} generation",
                queue=ARTIFACT_GENERATOR_QUEUE,
            )
            raise ValueError(f"Missing fields for {artifact_type.value} generation")

        # The lease is what absorbs at-least-once delivery: an entry already
        # terminal, or held by a live worker, is not generated a second time.
        # Standing down here costs one DynamoDB write and saves one LLM call.
        claimed = await claim_artifact_generation(artifact_id)
        if claimed is None:
            log_event(
                logger,
                logging.INFO,
                "artifact.claim_declined",
                "Artifact already terminal or leased by another worker; standing down",
                artifact_id=artifact_id,
                artifact_type=artifact_type.value,
            )
            return

        corpus_sources = await _download_transcripts(sources)

        # Second ceiling check, after translation: a translated corpus can be
        # longer than the original. Failing here costs nothing; sending a request
        # the provider will reject costs the whole invocation.
        corpus_bytes = sum(
            len(source["text"].encode("utf-8")) for source in corpus_sources
        )
        estimated_tokens = estimate_tokens(corpus_bytes)
        if estimated_tokens > MAX_COLLECTION_CORPUS_TOKENS:
            raise ValueError(
                f"corpus_too_large: {estimated_tokens} estimated tokens exceeds "
                f"{MAX_COLLECTION_CORPUS_TOKENS}"
            )

        prompt = generator.build_prompt(corpus_sources, language=language)

        # Determine model and structured output support
        model = generator.default_model
        response_format = None
        uses_structured_outputs = _supports_structured_outputs(model)
        schema = generator.response_format_schema()
        if uses_structured_outputs and schema is not None:
            response_format = schema

        # Call LLM
        raw_content, usage = await _call_llm(
            prompt=prompt,
            model=model,
            artifact_type=artifact_type.value,
            response_format=response_format,
            prompt_cache_key=prompt_cache_key,
        )
        llm_usage = _read_llm_usage(usage, model)

        # Unwrap structured response wrapper if applicable
        if uses_structured_outputs and schema is not None:
            raw_content = generator.unwrap_structured_response(raw_content)

        # Validate
        validated = generator.validate(raw_content)

        # Build artifact content
        artifact_content = generator.build_artifact_content(validated, body=body)
        # The title is the model's, not a derived label: it is what tells two
        # entries of the same type apart in the history (task-269 §5.4).
        artifact_title = validated.get("title") if isinstance(validated, dict) else None

        envelope: Dict[str, Any] = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type.value,
            "scope": body.get("scope"),
            "scope_id": body.get("scope_id"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_count": len(sources),
            "sources": [
                {
                    "media_item_id": source.get("media_item_id"),
                    "title": source.get("title"),
                    "language": source.get("language"),
                    "transcript_s3_key": source.get("transcript_s3_key"),
                }
                for source in sources
            ],
            "generator_version": body.get("generator_version"),
            "llm_usage": llm_usage.model_dump(),
            "content": artifact_content,
        }
        if translation:
            envelope["translation"] = translation

        await complete_artifact_generation(
            artifact_id=artifact_id,
            content=envelope,
            title=artifact_title,
            llm_usage=llm_usage,
        )

        await _record_generation_cost(body, artifact_id, llm_usage)

        # Post-generation hooks (per-kind)
        if artifact_type == MediaArtifactType.FLASHCARDS:
            await _init_fsrs_cards(body, artifact_id, validated["cards"])

    except Exception as exc:
        # Determine error code for validation errors
        error_code = None
        from media_summarizer.workers.artifact_generator.generators.flashcards import FlashcardsValidationError
        from media_summarizer.workers.artifact_generator.generators.notes import NotesValidationError
        from media_summarizer.workers.artifact_generator.generators.quiz import QuizValidationError
        from media_summarizer.workers.artifact_generator.generators.review_blurb import (
            ReviewBlurbValidationError,
        )
        from media_summarizer.workers.artifact_generator.generators.summary_detailed import (
            SummaryDetailedValidationError,
        )
        from media_summarizer.workers.artifact_generator.generators.summary_short import SummaryShortValidationError

        if isinstance(exc, (
            FlashcardsValidationError,
            NotesValidationError,
            QuizValidationError,
            ReviewBlurbValidationError,
            SummaryShortValidationError,
            SummaryDetailedValidationError,
        )):
            error_code = "VALIDATION_ERROR"

        # The alarm layer's only view of this failure: re-raising below produces a
        # batchItemFailures entry, which Lambda counts as a successful invocation
        # (see media_summarizer/utils/llm_failure.py). artifact_id and
        # artifact_type ride along from the bound log context.
        log_llm_generation_failure(
            logger,
            worker="artifact_generator",
            exc=exc,
            error_code=error_code,
            source_count=len(sources),
        )

        if artifact_id:
            await fail_artifact_generation(
                artifact_id=artifact_id,
                error_message=str(exc),
                error_code=error_code,
            )

        # The retry axis, read off the exception rather than re-derived from its
        # message. A permanent refusal -- no credit, rejected key -- gets the same
        # answer on every redelivery, so returning normally acknowledges the
        # message instead of spending its two remaining deliveries and filling the
        # DLQ with records nobody can usefully replay. The entry is already
        # terminal in DynamoDB, so the client stops polling either way. This is
        # the asymmetry the translation worker has enforced since task-327.
        # Everything else keeps its deliveries: the default is transient, so an
        # unclassified error still gets its three attempts.
        failure_kind = getattr(exc, "failure_kind", LLMFailureKind.TRANSIENT)
        if failure_kind == LLMFailureKind.PERMANENT:
            log_event(
                logger,
                logging.WARNING,
                "artifact.delivery_acknowledged",
                "Permanent refusal: acknowledging the message instead of retrying",
                failure_kind=failure_kind,
                refusal_reason=getattr(exc, "refusal_reason", None),
                error_type=type(exc).__name__,
            )
            return
        raise
    finally:
        reset_log_context(context_token)


async def _record_generation_cost(
    body: Dict[str, Any],
    artifact_id: str,
    llm_usage: ArtifactLlmUsage,
) -> None:
    """Store the measured LLM cost against the period, for observability only.

    Nothing gates on this figure -- the minute allowance is what bounds spend --
    but recording it is how the owner can compare the model's assumptions with the
    real invoice. Keyed on ``artifact_id`` so a redelivery cannot record twice.
    """
    user_id = body.get("user_id")
    if not user_id or llm_usage.cost_eur <= 0:
        return
    await quota_enforcer.record_observed_cost(
        user_id,
        cost_eur=llm_usage.cost_eur,
        idempotency_token=f"artifact_cost:{artifact_id}",
    )


async def _init_fsrs_cards(
    body: Dict[str, Any],
    artifact_id: str,
    flashcards: Any,
) -> None:
    """Initialize FSRS review schedule cards for spaced repetition (flashcards only).

    Cards are keyed by ``scope``/``scope_id`` rather than by media, which is what
    lets a collection's flashcards enter the review queue like any other deck —
    otherwise they would be the one artifact type that generates and then sits
    inert. The owner comes from the message, not from a processing-job lookup.
    """
    scope = body.get("scope")
    scope_id = body.get("scope_id")
    user_id = body.get("user_id")
    if not scope or not scope_id or not user_id:
        return
    try:
        await fsrs_service.initialize_cards_for_flashcards(
            user_id=user_id,
            scope=scope,
            scope_id=scope_id,
            artifact_id=artifact_id,
            flashcards=flashcards,
        )
    except Exception as fsrs_exc:
        # Non-fatal: flashcard generation succeeded, FSRS init is best-effort
        log_event(
            logger,
            logging.WARNING,
            "worker.fsrs_init_failed",
            "Failed to initialize FSRS cards (non-fatal)",
            artifact_id=artifact_id,
            scope=scope,
            scope_id=scope_id,
            error_type=type(fsrs_exc).__name__,
            detail=str(fsrs_exc)[:200],
        )


async def poll_queue() -> None:
    """Poll the unified artifact-generator queue."""
    from media_summarizer.workers.base_worker import process_message_with_retry

    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting artifact-generator worker queue poller",
        queue=ARTIFACT_GENERATOR_QUEUE,
    )
    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=ARTIFACT_GENERATOR_QUEUE,
                max_messages=5,
                wait_time_seconds=20,
                visibility_timeout=int(os.environ.get("SQS_VISIBILITY_TIMEOUT", "120")),
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=ARTIFACT_GENERATOR_QUEUE,
                        max_retries=int(os.environ.get("ARTIFACT_GENERATOR_MAX_RETRIES", "3")),
                        worker_name="artifact-generator-worker",
                    )
            await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Artifact generator worker polling failed",
                queue=ARTIFACT_GENERATOR_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("artifact-generator-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
