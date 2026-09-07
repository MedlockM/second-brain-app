"""What the ingestion workers raise when they give up.

Each worker keeps its own exception name — `except InstagramIngestionError` has
to stay narrower than "any ingestion problem" — but the three pieces of a
failure are the same everywhere, so they are defined once:

- `code`: a `MediaFailureCode`, the only failure information the app receives.
  It is written on the job and turned into a sentence on the device, in the
  reader's language. Nothing variable ever belongs in it.
- `details`: a short, stable, lower-snake reason token (`apify_result_invalid`,
  `missing_tiktok_id`). Developer-facing, in the AIP-193 sense: it lands in
  logs, in `extraction_metadata.failure_details` and in the failure-event
  reason, all of which dashboards and alarms read. Renaming one is an
  observability change.
- `context`: the structured facts behind the token — an HTTP status, an actor id,
  an exception class name. Persisted in `ProcessingJob.error_metadata`, which the
  API does not serve.

Free-text sentences are not among them, by design (task-359).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from media_summarizer.core.models.failure_codes import MediaFailureCode


class IngestionFailure(Exception):
    """A terminal (or retryable) ingestion failure, named by a stable code."""

    def __init__(
        self,
        code: MediaFailureCode,
        *,
        details: str,
        retryable: bool = False,
        **context: Any,
    ) -> None:
        super().__init__(f"{code.value}:{details}")
        self.code = code
        self.details = details.strip()
        self.retryable = retryable
        # A `None` in the context means "not applicable here", not "null": it is
        # dropped rather than written, since DynamoDB would keep it forever.
        self.context: Dict[str, Any] = {key: value for key, value in context.items() if value is not None}

    @property
    def reason(self) -> str:
        """`CODE:reason_token` — what logs and failure events carry."""
        return f"{self.code.value}:{self.details}"

    def error_metadata(self, *, step: Optional[str] = None) -> Dict[str, Any]:
        """The structured context to persist on the job."""
        metadata: Dict[str, Any] = {"reason": self.details}
        if step:
            metadata["step"] = step
        metadata.update(self.context)
        return metadata


#: `ApifyAdapterError.code` -> what the reader of a failed item should be told.
#:
#: Four workers hand Apify failures to the same three or four outcomes, so the
#: translation lives here instead of being re-decided per worker. Anything absent
#: is a network, server or client error: the attempt did not land, and that is
#: `PROVIDER_UNAVAILABLE`.
_APIFY_FAILURE_CODES: Dict[str, MediaFailureCode] = {
    "apify_payment_required": MediaFailureCode.PROVIDER_CREDITS_DEPLETED,
    "apify_pool_exhausted": MediaFailureCode.PROVIDER_CREDITS_DEPLETED,
    "apify_auth_error": MediaFailureCode.PROVIDER_AUTH_FAILED,
    "apify_rate_limited": MediaFailureCode.PROVIDER_RATE_LIMITED,
    "apify_token_missing": MediaFailureCode.PROVIDER_CONFIG_ERROR,
    "apify_actor_missing": MediaFailureCode.PROVIDER_CONFIG_ERROR,
    "apify_dataset_missing": MediaFailureCode.PROVIDER_CONFIG_ERROR,
    "apify_webhook_url_missing": MediaFailureCode.PROVIDER_CONFIG_ERROR,
    "apify_webhook_secret_missing": MediaFailureCode.PROVIDER_CONFIG_ERROR,
    "apify_invalid_json": MediaFailureCode.PROVIDER_RESULT_INVALID,
    "apify_invalid_run": MediaFailureCode.PROVIDER_RESULT_INVALID,
    "apify_invalid_dataset": MediaFailureCode.PROVIDER_RESULT_INVALID,
}


def apify_failure_code(adapter_code: str) -> MediaFailureCode:
    """The failure code an `ApifyAdapterError.code` amounts to for a reader."""
    return _APIFY_FAILURE_CODES.get(adapter_code, MediaFailureCode.PROVIDER_UNAVAILABLE)
