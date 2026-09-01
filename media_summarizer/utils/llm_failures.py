"""LLM failure taxonomy shared by the two workers that call the LLM.

Why this module exists (task-330): on 2026-09-01 the OpenAI credit ran out and the
backend produced no artifact for a whole session while every CloudWatch alarm
stayed OK. Both LLM-backed workers hide their failures from ``AWS/Lambda``
``Errors``:

* the SQS handler factory in ``media_summarizer/workers/lambda_handlers.py``
  reports a failed record through ``batchItemFailures`` and returns normally, so
  the invocation is a success as far as Lambda is concerned;
* the translation worker goes further and swallows its own terminal failure
  (``ensure_translated_transcript`` falls back to the untranslated transcript).

So ``Errors`` stayed at 0, the DLQs stayed empty, and the ``lambda_error_rate``
alarm — built on ``100 * Errors / Invocations`` — could not fire by construction.

The only signal the alarm layer has for these two workers is therefore the
structured log event defined here. Per the module convention (metrics are derived
from log metric filters; the application never calls ``put_metric_data``), the
filters in ``infrastructure/terraform/modules/platform/llm_alerts.tf`` turn every
``llm.generation_failed`` line into the ``LlmGenerationFailures`` metric,
dimensioned by ``FailureKind``. Keep the event name and the ``failure_kind``
values below in sync with those filters: renaming either here silently blinds the
alarms.

Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#llm-generation-failures
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from media_summarizer.utils.logging_config import log_event

# Event name read by the log metric filters. Contract, not a free-text label.
LLM_GENERATION_FAILED_EVENT = "llm.generation_failed"

# Values of the FailureKind dimension of LlmGenerationFailures.
FAILURE_KIND_PROVIDER_REFUSED = "provider_refused"
FAILURE_KIND_OTHER = "other"

# Values of refusal_reason. Only set when failure_kind is provider_refused; they
# are the field an operator reads to know whether to pay, rotate a key or wait.
REFUSAL_QUOTA = "quota"
REFUSAL_AUTHENTICATION = "authentication"
REFUSAL_RATE_LIMIT = "rate_limit"


class LlmProviderRefusedError(RuntimeError):
    """The LLM provider declined the call outright.

    Raised for an exhausted balance, invalid or missing credentials, and
    throttling — the three cases where retrying the same request cannot help
    until someone acts on the account.
    """

    def __init__(
        self,
        message: str,
        *,
        refusal_reason: str,
        provider_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.refusal_reason = refusal_reason
        self.provider_status = provider_status


def refusal_reason_for_status(status: int, body: str = "") -> Optional[str]:
    """Classify an LLM HTTP status. ``None`` means "not a provider refusal".

    A 5xx or a 400 on a malformed request is the caller's or the provider's
    problem to fix in code, not an account state, so it stays ``other``.
    """
    if status in (401, 403):
        return REFUSAL_AUTHENTICATION
    if status == 402:
        return REFUSAL_QUOTA
    if status == 429:
        # OpenAI answers 429 both for an exhausted balance (error code
        # insufficient_quota, billing_hard_limit_reached) and for plain
        # throttling. Only the body tells them apart, and the operator action
        # differs: top the account up versus wait for the window to reopen.
        lowered = (body or "").lower()
        if (
            "insufficient_quota" in lowered
            or "billing" in lowered
            or "exceeded your current quota" in lowered
        ):
            return REFUSAL_QUOTA
        return REFUSAL_RATE_LIMIT
    return None


def log_llm_generation_failure(
    logger: logging.Logger,
    *,
    worker: str,
    exc: Optional[BaseException] = None,
    refusal_reason: Optional[str] = None,
    detail: Optional[str] = None,
    **fields: Any,
) -> None:
    """Emit ``llm.generation_failed``: the metric behind the LLM alarms.

    ``refusal_reason`` wins when given (the translation worker reads it off an
    outcome object, having no exception in hand); otherwise it is taken from the
    exception, so an ``LlmProviderRefusedError`` or a ``TranscriptTranslationError``
    carrying the same attributes classifies itself.
    """
    reason = refusal_reason or getattr(exc, "refusal_reason", None)
    kind = FAILURE_KIND_PROVIDER_REFUSED if reason else FAILURE_KIND_OTHER

    if detail is None and exc is not None:
        detail = str(exc)[:300]

    log_event(
        logger,
        logging.ERROR,
        LLM_GENERATION_FAILED_EVENT,
        "LLM-backed generation failed",
        worker=worker,
        provider="openai",
        failure_kind=kind,
        refusal_reason=reason,
        provider_status=getattr(exc, "provider_status", None),
        error_type=type(exc).__name__ if exc is not None else None,
        detail=detail,
        **fields,
    )
