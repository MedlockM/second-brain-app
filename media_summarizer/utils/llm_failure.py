"""Is this LLM refusal worth retrying, or is the door closed?

Every LLM call in the pipeline has a retry budget, and until task-327 that budget
was spent on failures that could not possibly pass: an exhausted OpenAI credit
balance answered 429 to 75 consecutive translation attempts for one document
(3 backoff attempts x 25 re-enqueues). Retrying a refusal that comes from the
*account* rather than from the *moment* burns money and, worse, feeds a
re-reservation loop that keeps a media item pending forever.

So a failure is sorted into two kinds:

- ``TRANSIENT`` -- the same request may pass later: a socket timeout, a 5xx, a
  momentary rate limit. Retry with backoff, and let the state machine
  re-reserve.
- ``PERMANENT`` -- the same request will get the same answer: no credit left, a
  rejected key, an unknown model, a payload the provider refuses to parse. Stop
  after the first response, and do not re-reserve.

**The provider's error payload is an input contract we do not control.** OpenAI
puts its reason in ``error.type`` (``insufficient_quota``), sometimes in
``error.code`` (``credit_balance_exhausted``, ``billing_hard_limit_reached``),
sometimes only in prose, and a gateway in front of it may answer a bare 429 with
no body at all. Classification therefore never depends on one field being
present: it matches markers anywhere in the raw response text, then falls back on
the status code alone.

A bare 429 -- no marker, no ``Retry-After`` -- is read as PERMANENT on purpose.
A real pacing refusal from OpenAI always names itself (``rate_limit_exceeded``,
"Rate limit reached", "please try again in 20ms") and carries ``Retry-After``;
a 429 that says nothing is far more likely to be a billing wall, and the cost of
being wrong is asymmetric: a translation we skip degrades to the untranslated
transcript, while a billing wall we keep hammering costs real money on every
retry of every caller.
"""

from __future__ import annotations

from typing import Optional


class LLMFailureKind:
    """The two ways an LLM call can fail. Persisted verbatim on locks."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"


# Markers that name a refusal coming from the account, the key or the request
# itself. Matched as substrings against the lowercased raw body, so they hold
# whether the provider put them in ``error.type``, ``error.code`` or the message.
_PERMANENT_MARKERS: tuple[str, ...] = (
    # Billing / quota
    "insufficient_quota",
    "credit_balance_exhausted",
    "billing_hard_limit_reached",
    "billing_not_active",
    "no credits remaining",
    "credit balance is too low",
    "exceeded your current quota",
    "check your plan and billing",
    "quota",
    "payment_required",
    # Credentials
    "invalid_api_key",
    "incorrect api key",
    "invalid authentication",
    "account_deactivated",
    "permission_denied",
    "unsupported_country_region_territory",
    # Request shape
    "model_not_found",
    "do not have access to it",
    "context_length_exceeded",
    "string_above_max_length",
)

# Markers that name a pacing refusal: the same request passes once the window
# moves. Checked only after the permanent markers, because an exhausted quota is
# also served as a 429 and its message mentions neither of these.
_TRANSIENT_MARKERS: tuple[str, ...] = (
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

# Status codes whose answer does not change on a retry of the same request.
_PERMANENT_STATUS_CODES = frozenset({400, 401, 402, 403, 404, 422})


def classify_llm_failure(
    *,
    status_code: Optional[int] = None,
    body: Optional[str] = None,
    retry_after: Optional[str] = None,
) -> str:
    """Sort one LLM failure into :class:`LLMFailureKind`.

    ``status_code`` is ``None`` for a failure that never got an HTTP answer (a
    timeout, a DNS or TLS error), which is transient by nature. ``body`` is the
    raw response text -- never parsed as JSON, so a truncated or HTML body
    classifies exactly as well as a well-formed one. ``retry_after`` is the
    header of the same name when the provider sent one: its presence is the
    provider itself saying "later", which is the definition of transient.
    """
    text = (body or "").lower()

    if any(marker in text for marker in _PERMANENT_MARKERS):
        return LLMFailureKind.PERMANENT

    if status_code is None:
        return LLMFailureKind.TRANSIENT

    if status_code in _PERMANENT_STATUS_CODES:
        return LLMFailureKind.PERMANENT

    if status_code == 429:
        if retry_after or any(marker in text for marker in _TRANSIENT_MARKERS):
            return LLMFailureKind.TRANSIENT
        # A 429 that names nothing: read as a billing wall (see module docstring).
        return LLMFailureKind.PERMANENT

    return LLMFailureKind.TRANSIENT
