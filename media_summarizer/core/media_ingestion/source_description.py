"""The presentation text the author wrote, read back off a job (task-383).

Instagram, TikTok and YouTube all let the author write a block of text next to
the media — a caption, a clip description, a video description. It is the only
human-*written* material those platforms expose, and it routinely carries what
the spoken audio never states: the recipe quantities, the source of the study,
the name of the tool being demoed, the chapter list. Until this module it was
read only to derive a title and then dropped, so the model generating a summary
or a quiz never saw a word of it.

Storage side: no new DynamoDB attribute. ``extraction_metadata`` is already a
free-form map on the job, it already carried the Instagram caption, and no
downstream worker rewrites it. Two spellings exist there and both are legitimate:

* ``extraction_metadata[SOURCE_DESCRIPTION_KEY]`` — what the TikTok and YouTube
  workers write, and the spelling any new platform should use.
* ``extraction_metadata["resolver_metadata"]["caption"]`` — where the Instagram
  resolver has always put it (``instagram_apify_resolver.py::_extract_caption``).
  Kept as-is rather than moved: the resolver's metadata block is its own record
  of what the actor returned, and the reader below is the single place that has
  to know both spellings.

Read side: ``job_source_description`` is that single place. Every consumer goes
through it, so a fourth platform is one tuple entry here and nothing anywhere
else.

Pure module: no I/O, no provider call.
"""

from __future__ import annotations

from typing import Any, Optional

#: Canonical ``extraction_metadata`` key for the author's presentation text.
#: One key for every platform that writes it directly on the job.
SOURCE_DESCRIPTION_KEY = "source_description"

#: Set by a worker that has already put the description *in the transcript*, which
#: makes it the body of the media rather than a block beside it (task-384).
#:
#: One source needs this: an Instagram photo post whose images returned no text at
#: all — a sunset, a portrait, a meme with no legible words. A job cannot complete
#: on an empty transcript (`artifact_service._load_transcript_bytes` refuses one),
#: so the caption becomes the transcript. Serving it *again* as the description
#: would put the same paragraph twice in every prompt built from that media.
#:
#: The caption itself stays where the resolver wrote it: ``resolver_metadata`` is
#: that actor's own record of what it returned, and deleting a field from it to
#: change a reading decision would be lying about the run.
SOURCE_DESCRIPTION_IN_TRANSCRIPT_KEY = "source_description_in_transcript"

#: Where the description may sit on a job's ``extraction_metadata``, in the order
#: it is probed: the canonical top-level key first, then the nested spellings a
#: resolver established before the key existed.
_DESCRIPTION_PATHS: tuple[tuple[str, ...], ...] = (
    (SOURCE_DESCRIPTION_KEY,),
    ("resolver_metadata", "caption"),
)


def normalize_source_description(raw: Any) -> Optional[str]:
    """A stripped description string, or None when there is nothing to keep.

    Used on the write side so a provider returning ``""``, ``"   "`` or a
    non-string stores ``None`` instead of a value the reader then has to
    second-guess. An empty description and an absent one are the same fact.
    """
    if not isinstance(raw, str):
        return None
    stripped = raw.strip()
    return stripped or None


def job_source_description(job: Any) -> Optional[str]:
    """The author's presentation text for this job, whatever the platform wrote.

    Returns None when the job carries none — which is the normal outcome for
    every platform that has no such field (podcasts, articles, documents,
    uploads), for the TikTok Apify fallback whose actor returns a transcript and
    nothing else, and for a YouTube actor that declares no description in its
    output schema. Absence is never an error here.

    Also None when the job carries ``SOURCE_DESCRIPTION_IN_TRANSCRIPT_KEY``: the
    text is already the body of the transcript, and a description is a block
    *beside* the transcript, never a second copy of it.

    Only the interior of the text is preserved: leading and trailing whitespace
    goes, and the text is *not* truncated. A cut would sever a sentence, and the
    corpus already has the right place to refuse a volume that got too big —
    ``MAX_FOLDER_CORPUS_TOKENS``.
    """
    metadata = getattr(job, "extraction_metadata", None)
    if not isinstance(metadata, dict):
        return None
    if metadata.get(SOURCE_DESCRIPTION_IN_TRANSCRIPT_KEY):
        return None
    for path in _DESCRIPTION_PATHS:
        node: Any = metadata
        for segment in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(segment)
        description = normalize_source_description(node)
        if description:
            return description
    return None
