"""Helper for enqueueing Deepgram transcription jobs.

The Deepgram worker (``media_summarizer.workers.transcription.deepgram_worker``)
consumes SQS messages with a strict schema. Several upstream workers (TikTok,
Instagram, podcasts, YouTube) need to enqueue those messages with the right
shape — this module centralises the payload construction so producers don't
duplicate the field list and don't drift on the ``deepgram_mode`` contract.

See ``deepgram_worker.VALID_DEEPGRAM_MODES`` for the accepted values:

- ``pull`` — Deepgram fetches the URL itself; fail loudly on CDN block.
- ``push`` — the worker downloads the audio and POSTs the bytes; for CDNs
  known to block Deepgram (Instagram, TikTok).
- ``pull_with_push_fallback`` — try pull first, fall back to push when the
  source CDN reports ``REMOTE_CONTENT_ERROR``. Use this when the producer
  isn't sure whether the CDN will let Deepgram in.
"""

from __future__ import annotations

from typing import Any, Optional

from media_summarizer.utils import sqs
from media_summarizer.utils.env import required_env

DeepgramMode = str  # one of: "pull" | "push" | "pull_with_push_fallback"

DEEPGRAM_TRANSCRIPTION_QUEUE = required_env("DEEPGRAM_TRANSCRIPTION_QUEUE")


async def enqueue_deepgram_transcription(
    *,
    job_id: str,
    audio_url: str,
    deepgram_mode: DeepgramMode,
    source_platform: str,
    media_key: Optional[str] = None,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    normalized_url: Optional[str] = None,
    episode_title: Optional[str] = None,
    podcast_title: Optional[str] = None,
    audio_duration_seconds: int = 0,
    quota_debited_minutes: int = 0,
    quota_debit_skipped: bool = False,
    content_mime_type: Optional[str] = None,
    original_name: Optional[str] = None,
    quota_source_platform: Optional[str] = None,
    resolver_key: Optional[str] = None,
    caption: Optional[str] = None,
    comments: Optional[list[Any]] = None,
    comments_count: Optional[int] = None,
    queue_name: str = DEEPGRAM_TRANSCRIPTION_QUEUE,
) -> None:
    """Send a Deepgram transcription job to SQS with the canonical schema.

    Producers MUST set ``deepgram_mode`` explicitly: the Deepgram worker
    logs a warning and silently falls back to ``pull`` when the field is
    missing, which masks bugs.

    ``quota_debited_minutes`` is how many audio minutes the producer already
    debited at its quota gate. The worker settles the difference with Deepgram's
    own duration, so a producer that omits it makes the user pay the whole real
    duration a second time.

    ``quota_debit_skipped`` says the gate deliberately debited nothing because the
    user already holds this content (task-281). It is not the same statement as
    ``quota_debited_minutes == 0``: the worker settles the full billed duration
    against a zero debit, so an exempt save that omits this flag ends up charged
    exactly what the exemption was meant to spare it.

    ``quota_source_platform`` names the platform whose quota category applies.
    The worker settles audio minutes for every message that leaves it unset, so
    a producer whose media is metered in another category (Instagram, per the
    validated task-250 decision) must pass it or its minutes get billed as
    audio on top of the category the API already debited.
    """
    body: dict[str, Any] = {
        "job_id": job_id,
        "audio_url": audio_url,
        "deepgram_mode": deepgram_mode,
        "source_platform": source_platform,
        "audio_duration_seconds": audio_duration_seconds,
        "quota_debited_minutes": quota_debited_minutes,
        "quota_debit_skipped": quota_debit_skipped,
    }
    optional_fields = {
        "media_key": media_key,
        "quota_source_platform": quota_source_platform,
        "resolver_key": resolver_key,
        "caption": caption,
        "comments": comments,
        "comments_count": comments_count,
        "user_id": user_id,
        "user_email": user_email,
        "normalized_url": normalized_url,
        "episode_title": episode_title,
        "podcast_title": podcast_title,
        "content_mime_type": content_mime_type,
        "original_name": original_name,
    }
    for key, value in optional_fields.items():
        if value is not None:
            body[key] = value

    await sqs.send_message(queue_name=queue_name, message_body=body)
