"""One reading of an LLM provider's refusal, along two axes that never merge.

Every LLM call in the pipeline needs two different answers about the same
failure, and they are decided from the same bytes -- an HTTP status, a raw body,
maybe a ``Retry-After`` header. So this module reads those bytes **once** and
returns both answers as one :class:`LlmFailure`.

**Axis 1 -- ``kind``: is this call worth making again?** It drives the retry
budget and, for translations, the re-reservation gate. Until task-327 that budget
was spent on failures that could not possibly pass: an exhausted OpenAI credit
balance answered 429 to 75 consecutive translation attempts for one document
(3 backoff attempts x 25 re-enqueues). Retrying a refusal that comes from the
*account* rather than from the *moment* burns money and feeds a re-reservation
loop that keeps a media item pending forever.

- ``TRANSIENT`` -- the same request may pass later: a socket timeout, a 5xx, a
  momentary rate limit. Retry with backoff, and let the state machine re-reserve.
- ``PERMANENT`` -- the same request will get the same answer: no credit left, a
  rejected key, an unknown model, a payload the provider refuses to parse. Stop
  after the first response, do not re-reserve, and acknowledge the SQS message
  instead of spending the remaining deliveries on it.

**Axis 2 -- ``refusal_reason``: what must a human do about it?** It is the field
an operator reads off the ``llm.generation_failed`` event when an alarm fires:
``quota`` means top the account up, ``authentication`` means rotate the key,
``rate_limit`` means wait. ``None`` means the provider did not decline the call
at all -- the failure is ours (a corpus over the ceiling, a schema the model
broke, an S3 read that died), and no account action would help.

**Neither axis derives from the other, which is why both are returned.** An
unknown model is ``PERMANENT`` with no refusal reason (nobody can pay their way
out of a typo in a model id). A named rate limit is a provider refusal that is
``TRANSIENT`` (the window reopens on its own). Collapsing them -- as task-327 and
task-330 did by writing two independent classifiers -- produces the worst of both:
a pipeline that stops retrying because the failure is permanent while the alarm
says ``rate_limit``, i.e. "do nothing and wait", about a billing wall.

**The provider's error payload is an input contract we do not control.** OpenAI
puts its reason in ``error.type`` (``insufficient_quota``), sometimes in
``error.code`` (``credit_balance_exhausted``, ``billing_hard_limit_reached``),
sometimes only in prose, and a gateway in front of it may answer a bare 429 with
no body at all. Classification therefore never depends on one field being
present: it matches markers anywhere in the raw response text, then falls back on
the status code alone.

A bare 429 -- no marker, no ``Retry-After`` -- is read as a ``PERMANENT`` quota
refusal on purpose. A real pacing refusal from OpenAI always names itself
(``rate_limit_exceeded``, "Rate limit reached", "please try again in 20ms") and
carries ``Retry-After``; a 429 that says nothing is far more likely to be a
billing wall, and the cost of being wrong is asymmetric: a translation we skip
degrades to the untranslated transcript, while a billing wall we keep hammering
costs real money on every retry of every caller.

**The values below are a contract with the alarm layer.** The filters in
``infrastructure/terraform/modules/platform/llm_alerts.tf`` turn every
``llm.generation_failed`` line into the ``LlmGenerationFailures`` metric,
dimensioned by ``FailureKind``; per the module convention metrics are derived
from log metric filters and the application never calls ``put_metric_data``.
Renaming the event, a failure kind or a refusal reason here without changing that
file silently blinds both LLM alarms -- and they are the only signal these two
workers have: the SQS handler factory in
``media_summarizer/workers/lambda_handlers.py`` reports a failed record through
``batchItemFailures`` and returns normally, and the translation worker swallows
its own terminal failure, so ``AWS/Lambda`` ``Errors`` stays at 0 and
``lambda_error_rate`` cannot fire by construction.

Runbook: infrastructure/observability/runbooks/pipeline-alerts.md#llm-generation-failures
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from media_summarizer.utils.logging_config import log_event


class LLMFailureKind:
    """Axis 1: the two ways an LLM call can fail. Persisted verbatim on locks."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"


# Axis 2 values. Set only when the provider itself declined; they are what an
# operator reads to know whether to pay, rotate a key or wait.
REFUSAL_QUOTA = "quota"
REFUSAL_AUTHENTICATION = "authentication"
REFUSAL_RATE_LIMIT = "rate_limit"

# Event name read by the log metric filters. Contract, not a free-text label.
LLM_GENERATION_FAILED_EVENT = "llm.generation_failed"

# Values of the FailureKind dimension of LlmGenerationFailures. Deliberately
# coarser than refusal_reason: the alarm layer only needs "is the provider
# turning us away", the event's refusal_reason field carries the rest.
#
# Reader beware: the ``failure_kind`` *field* of the llm.generation_failed event
# holds one of these two values -- it is the alarm dimension, not axis 1. The
# ``failure_kind`` written on a translation lock, carried by an exception or logged
# by a worker's own event is axis 1 (``transient`` / ``permanent``). Same name, two
# vocabularies, because the alarm dimension was named before the two axes met.
FAILURE_KIND_PROVIDER_REFUSED = "provider_refused"
FAILURE_KIND_OTHER = "other"


# --- Markers ------------------------------------------------------------------
# Each marker appears in exactly one list, and every list decides both axes at
# once. Matched as substrings against the lowercased raw body, so they hold
# whether the provider put them in ``error.type``, ``error.code`` or the prose.

# The account has no money left. PERMANENT + quota: no retry and no other caller
# gets a different answer until someone tops the balance up.
# ``quota`` and ``billing`` are deliberately broad -- they cover
# ``insufficient_quota``, ``billing_hard_limit_reached``, ``billing_not_active``,
# "exceeded your current quota" and "check your plan and billing" without
# enumerating each wording, and a body that says either word is about the account
# rather than about this request.
_BILLING_MARKERS: tuple[str, ...] = (
    "quota",
    "billing",
    "credit_balance_exhausted",
    "no credits remaining",
    "credit balance is too low",
    "payment_required",
)

# The credential is refused, missing or not allowed to do this. PERMANENT +
# authentication: the key has to change.
_CREDENTIAL_MARKERS: tuple[str, ...] = (
    "invalid_api_key",
    "incorrect api key",
    "invalid authentication",
    "account_deactivated",
    "permission_denied",
    "unsupported_country_region_territory",
)

# The provider understood us and says the *request* is wrong. PERMANENT, but not
# a refusal: no amount of paying or key rotation fixes an unknown model or a
# prompt over the context window, so refusal_reason stays None and the alarm
# layer files it under ``other``.
_UNPROCESSABLE_REQUEST_MARKERS: tuple[str, ...] = (
    "model_not_found",
    "do not have access to it",
    "context_length_exceeded",
    "string_above_max_length",
)

# The provider is pacing us or briefly unwell: the same request passes once the
# window moves. TRANSIENT + rate_limit. Consulted only on a 429, because an
# exhausted quota is served as a 429 too and its body mentions none of these --
# which is exactly why the billing list is checked first.
_PACING_MARKERS: tuple[str, ...] = (
    "rate_limit_exceeded",
    "rate limit reached",
    "requests per min",
    "tokens per min",
    "please try again in",
    "server_error",
    "engine_overloaded",
    "overloaded",
    "service unavailable",
    "try again later",
)

# Status codes whose answer does not change on a retry of the same request, and
# that name no account state by themselves.
_UNPROCESSABLE_STATUS_CODES = frozenset({400, 404, 422})
_AUTHENTICATION_STATUS_CODES = frozenset({401, 403})


@dataclass(frozen=True)
class LlmFailure:
    """The two axes of one provider answer, read from one parse of the body."""

    #: Axis 1, a :class:`LLMFailureKind` value. Drives retries and reservations.
    kind: str
    #: Axis 2, a ``REFUSAL_*`` value, or ``None`` when the provider did not
    #: decline the call. Drives the operator's action and the failure metric.
    refusal_reason: Optional[str] = None


class LlmProviderRefusedError(RuntimeError):
    """The LLM provider declined the call outright.

    Raised for an exhausted balance, invalid or missing credentials, and
    throttling -- the three cases where retrying the same request cannot help
    until someone acts on the account or the window reopens. Carries both axes so
    a worker never re-parses a provider message: ``refusal_reason`` for the
    failure metric, ``failure_kind`` for the decision to stop consuming
    deliveries.
    """

    def __init__(
        self,
        message: str,
        *,
        refusal_reason: str,
        failure_kind: str,
        provider_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.refusal_reason = refusal_reason
        self.failure_kind = failure_kind
        self.provider_status = provider_status


def classify_llm_failure(
    *,
    status_code: Optional[int] = None,
    body: Optional[str] = None,
    retry_after: Optional[str] = None,
) -> LlmFailure:
    """Read one provider answer once, and return both of its axes.

    ``status_code`` is ``None`` for a failure that never got an HTTP answer (a
    timeout, a DNS or TLS error), which is transient by nature and no refusal.
    ``body`` is the raw response text -- never parsed as JSON, so a truncated or
    HTML body classifies exactly as well as a well-formed one. ``retry_after`` is
    the header of the same name when the provider sent one: its presence is the
    provider itself saying "later", which is the definition of transient.

    Marker order is significance order, not list order: an exhausted balance and
    a throttle are both served as 429s, so the body is asked about money before
    it is asked about pacing.
    """
    text = (body or "").lower()

    if any(marker in text for marker in _BILLING_MARKERS):
        return LlmFailure(LLMFailureKind.PERMANENT, REFUSAL_QUOTA)

    if any(marker in text for marker in _CREDENTIAL_MARKERS):
        return LlmFailure(LLMFailureKind.PERMANENT, REFUSAL_AUTHENTICATION)

    if any(marker in text for marker in _UNPROCESSABLE_REQUEST_MARKERS):
        return LlmFailure(LLMFailureKind.PERMANENT)

    if status_code is None:
        return LlmFailure(LLMFailureKind.TRANSIENT)

    if status_code in _AUTHENTICATION_STATUS_CODES:
        return LlmFailure(LLMFailureKind.PERMANENT, REFUSAL_AUTHENTICATION)

    if status_code == 402:
        return LlmFailure(LLMFailureKind.PERMANENT, REFUSAL_QUOTA)

    if status_code in _UNPROCESSABLE_STATUS_CODES:
        return LlmFailure(LLMFailureKind.PERMANENT)

    if status_code == 429:
        if retry_after or any(marker in text for marker in _PACING_MARKERS):
            return LlmFailure(LLMFailureKind.TRANSIENT, REFUSAL_RATE_LIMIT)
        # A 429 that names nothing: read as a billing wall (see module docstring).
        return LlmFailure(LLMFailureKind.PERMANENT, REFUSAL_QUOTA)

    # 5xx and anything unexpected: the provider's problem, and it may pass.
    return LlmFailure(LLMFailureKind.TRANSIENT)


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
