"""The vocabulary a failed ingestion speaks to the app.

A worker that gives up writes a *code* on the job, never a sentence. The code is
the stable identifier of the failure; the client owns the wording and renders it
in the reader's language from `mobile/src/lib/getFriendlyErrorMessage.ts`. This is
RFC 9457's split between `type` (stable, machine-readable, part of the contract)
and `title`/`detail` (negotiated, never depended upon), and AIP-193's rule that
`Status.message` is developer-facing English while anything request-specific
belongs in metadata "so that machine actors do not need to parse error messages".

Consequences for whoever adds a code here:

- **Every member needs an entry in `ERROR_CODE_MESSAGES`** on the mobile side.
  A code the app does not know falls back to a generic line, which is a worse
  screen than the one this enum exists to produce.
- **Nothing variable goes in the code.** A status number, an id, a provider name,
  a duration are context: they go to `ProcessingJob.error_metadata`, which the API
  does not expose. The code answers "what happened", the metadata answers "on
  what", and the human sentence is built on the device.
- **A code is chosen for what the reader can do about it**, not for which
  provider raised it. Two providers timing out are one code; a geo-restricted
  video and an age-restricted one are two, because only one of them is worth a
  retry from another place.
- **The values are part of the contract.** Renaming one means changing the mobile
  map in the same commit.
"""

from enum import Enum


class MediaFailureCode(str, Enum):
    """Why an ingestion job failed, as the app will read it."""

    # --- The source itself cannot yield what we need -------------------------
    #: Deleted, private, or otherwise gone from the platform.
    MEDIA_UNAVAILABLE = "MEDIA_UNAVAILABLE"
    #: Blocked in the region our extraction runs from.
    GEO_RESTRICTED = "GEO_RESTRICTED"
    #: Behind a platform age gate we cannot pass.
    AGE_RESTRICTED = "AGE_RESTRICTED"
    #: A live stream or space: there is no finished recording to work on.
    LIVE_CONTENT_UNSUPPORTED = "LIVE_CONTENT_UNSUPPORTED"
    #: The page or post carries no audio, no video and no caption track.
    NO_TRANSCRIBABLE_MEDIA = "NO_TRANSCRIBABLE_MEDIA"
    #: There is media, but no transcript could be obtained from it.
    NO_TRANSCRIPT_AVAILABLE = "NO_TRANSCRIPT_AVAILABLE"
    #: A text post whose text is empty once markup is stripped.
    POST_TEXT_EMPTY = "POST_TEXT_EMPTY"
    #: A URL that resolves, but not to a readable article.
    NOT_AN_ARTICLE_PAGE = "NOT_AN_ARTICLE_PAGE"
    #: An article page whose body could not be extracted.
    ARTICLE_TEXT_NOT_FOUND = "ARTICLE_TEXT_NOT_FOUND"
    #: An uploaded document no parser could read.
    DOCUMENT_PARSE_FAILED = "DOCUMENT_PARSE_FAILED"

    # --- The extraction chain, not the source, is at fault ------------------
    #: The source or the extraction service could not be reached.
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    #: The extraction service answered, with something unusable.
    PROVIDER_RESULT_INVALID = "PROVIDER_RESULT_INVALID"
    #: Throttled upstream; the same link is worth another try later.
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    #: The attempt ran out of time.
    PROVIDER_TIMED_OUT = "PROVIDER_TIMED_OUT"

    # --- Our own configuration or budget ------------------------------------
    #: Our credentials for the extraction service were refused.
    PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
    #: Our paid allowance at the extraction service is exhausted.
    PROVIDER_CREDITS_DEPLETED = "PROVIDER_CREDITS_DEPLETED"
    #: A missing token, an unset actor id: the deployment is incomplete.
    PROVIDER_CONFIG_ERROR = "PROVIDER_CONFIG_ERROR"

    # --- The user's own allowance -------------------------------------------
    #: No transcription minutes left on the plan.
    OUT_OF_MINUTES = "OUT_OF_MINUTES"
    #: A single item longer than the plan allows in one go.
    ITEM_TOO_LONG = "ITEM_TOO_LONG"

    # --- Ours, and only ours ------------------------------------------------
    #: A queue message we could not act on (missing job, malformed body).
    INVALID_JOB_MESSAGE = "INVALID_JOB_MESSAGE"
    #: Handing the job to the ingestion core failed.
    SUBMISSION_FAILED = "SUBMISSION_FAILED"
    #: The safety net: an exception nobody claimed. Kept deliberately opaque —
    #: guessing a friendlier code from an exception string is how English
    #: sentences ended up on a French screen in the first place.
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
