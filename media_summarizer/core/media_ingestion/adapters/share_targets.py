"""What the app accepts, as data — the list the paywall shows.

Until task-377 the subscription screen listed its sources as prose, retyped in
eleven translation catalogues, with nothing tying it to the code that decides
acceptance. It had drifted exactly the way duplicated facts do: it sold Instagram
photo posts, which `instagram_ingestion_worker` refuses with
`IMAGE_POST_UNSUPPORTED`, and it never mentioned WhatsApp, `music.youtube.com`,
`twitter.com`, the short TikTok links or a plain audio URL — all of which work.

So the list became data. `GET /api/pricing` serves it next to the allowances the
screen already fetches, and the client only *renders* it, the same way it renders
the figures from the pricing config and the prices from the store package.

Three properties this is built for:

- **Nothing translatable crosses.** What ships is an identifier and, when there
  is one, a proper noun: `YouTube`, `Spotify`, `WhatsApp`, `PDF`, `M4A`. Those
  are the same word in every locale — `ar.ts` already writes them in Latin
  script. Entries with no proper noun ("articles and web pages", "any audio
  link") carry no label at all and the client resolves one from its own
  catalogue by id, so marketing prose never gets served from here.
- **Drift becomes an error, not an omission.** A new `SourcePlatform` member
  that is neither offered below nor explicitly withheld raises at import, which
  means the API fails to start rather than quietly serving a short list.
- **One payload.** This rides on the pricing response; it is not a second
  endpoint, and the client must not keep a copy "for offline".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from media_summarizer.core.media_ingestion.adapters.classifiers import (
    AUDIO_URL_EXTENSIONS,
    RECOGNISED_HOSTS,
)
from media_summarizer.core.media_ingestion.domain import SourcePlatform
from media_summarizer.core.ports.document_parser import DocumentFormat

#: Something shared as a link or from another app.
GROUP_PLATFORM = "platform"
#: Something picked from the device's files.
GROUP_FILE = "file"


@dataclass(frozen=True)
class ShareTarget:
    """One thing the user can send, as the client will render it."""

    #: `SourcePlatform` value for a platform, or a file family name. The client
    #: keys its own label off this when `label` is `None`, so it is part of the
    #: contract and not an internal detail.
    id: str
    #: `GROUP_PLATFORM` or `GROUP_FILE` — which of the two showcase rows it
    #: belongs to, since the two answer different questions.
    group: str
    #: The proper noun to display, or `None` when the thing has no brand name
    #: and the client has to translate it.
    label: str | None = None
    #: Container or extension names, upper-cased, for the file families. Shown
    #: as the whole chip: "PDF DOCX PPTX XLSX" says more than "Documents".
    formats: tuple[str, ...] = ()


def _formats_from(*document_formats: DocumentFormat) -> tuple[str, ...]:
    """Extension names as the file picker will accept them, upper-cased."""
    return tuple(fmt.value.upper() for fmt in document_formats)


#: The document formats LlamaParse reads as text.
_DOCUMENT_FORMATS: tuple[DocumentFormat, ...] = (
    DocumentFormat.PDF,
    DocumentFormat.DOCX,
    DocumentFormat.PPTX,
    DocumentFormat.XLSX,
)

#: The text formats that need no parser at all: the file already *is* its text,
#: so the worker decodes it itself (task-380). Offered as their own family
#: because the chip they belong on answers a different question than
#: "documents" does — this is where a note exported from a note-taking app lands.
_TEXT_FORMATS: tuple[DocumentFormat, ...] = (
    DocumentFormat.TEXT_TXT,
    DocumentFormat.TEXT_MD,
    DocumentFormat.TEXT_RTF,
)

#: The image formats the same parser OCRs. `IMAGE_JPEG` is the `.jpeg` spelling
#: of `IMAGE_JPG` and `.heic` the Apple spelling of HEIF: listing both on a chip
#: would say the same thing twice, so one spelling stands for the pair.
_IMAGE_FORMATS: tuple[DocumentFormat, ...] = (
    DocumentFormat.IMAGE_JPG,
    DocumentFormat.IMAGE_PNG,
    DocumentFormat.IMAGE_HEIF,
    DocumentFormat.IMAGE_TIFF,
    DocumentFormat.IMAGE_BMP,
)

#: Alternate spellings of a format already named above.
_ALIAS_FORMATS: frozenset[DocumentFormat] = frozenset({DocumentFormat.IMAGE_JPEG})

#: Members of `SourcePlatform` deliberately not offered.
#:
#: `UNKNOWN` is the sentinel a failed classification carries, so there is
#: nothing to advertise. Anything else added to the enum has to be either
#: offered below or listed here, on purpose — see `_assert_exhaustive`.
_WITHHELD_PLATFORMS: frozenset[SourcePlatform] = frozenset({SourcePlatform.UNKNOWN})

#: Everything the user can send, in the order the screen reads it.
#:
#: Ordered by how a newcomer meets the app rather than alphabetically: the video
#: platforms they already share from, then the podcast apps, then the text
#: sources, then the two generic cases that catch everything else, then files.
#: Every line is a path a worker really handles — the cost regime is *not*
#: carried here, because four of these platforms have a conditional one (a
#: podcast episode that publishes a Podcasting 2.0 transcript costs nothing, the
#: same episode without one costs its length), which no single field can state.
#: The cost table on the screen is built from `unit_conversion` instead.
SHARE_TARGETS: tuple[ShareTarget, ...] = (
    ShareTarget(id=SourcePlatform.YOUTUBE.value, group=GROUP_PLATFORM, label="YouTube"),
    ShareTarget(id=SourcePlatform.TIKTOK.value, group=GROUP_PLATFORM, label="TikTok"),
    # Reels, IGTV and `/p/` videos. Photo posts are *not* offered, and never
    # were supported: `IMAGE_POST_UNSUPPORTED`. A chip that says "Instagram"
    # claims the platform, not every post type on it.
    ShareTarget(
        id=SourcePlatform.INSTAGRAM.value, group=GROUP_PLATFORM, label="Instagram"
    ),
    ShareTarget(id=SourcePlatform.SPOTIFY.value, group=GROUP_PLATFORM, label="Spotify"),
    ShareTarget(
        id=SourcePlatform.APPLE_PODCASTS.value,
        group=GROUP_PLATFORM,
        label="Apple Podcasts",
    ),
    ShareTarget(id=SourcePlatform.DEEZER.value, group=GROUP_PLATFORM, label="Deezer"),
    ShareTarget(id=SourcePlatform.RSS.value, group=GROUP_PLATFORM, label="RSS"),
    ShareTarget(id=SourcePlatform.X.value, group=GROUP_PLATFORM, label="X"),
    # Voice notes. Since task-380 a shared *text* is a note, not a WhatsApp
    # message: the platform never says which app the text came from, so the only
    # thing WhatsApp still claims here is the audio attachment.
    ShareTarget(
        id=SourcePlatform.WHATSAPP.value, group=GROUP_PLATFORM, label="WhatsApp"
    ),
    # No brand name, so no label: the client translates "articles and web pages",
    # "any audio link" and "a note from your notes app" from its own catalogue.
    # Notes is deliberately unbranded — it covers iOS Notes, Google Keep and
    # Samsung Notes at once, and naming one of them would undersell the others.
    ShareTarget(id=SourcePlatform.NOTES.value, group=GROUP_PLATFORM),
    ShareTarget(id=SourcePlatform.WEB.value, group=GROUP_PLATFORM),
    ShareTarget(id=SourcePlatform.DIRECT_URL.value, group=GROUP_PLATFORM),
    ShareTarget(
        id="document", group=GROUP_FILE, formats=_formats_from(*_DOCUMENT_FORMATS)
    ),
    ShareTarget(
        id="text_file", group=GROUP_FILE, formats=_formats_from(*_TEXT_FORMATS)
    ),
    ShareTarget(id="image", group=GROUP_FILE, formats=_formats_from(*_IMAGE_FORMATS)),
    ShareTarget(
        id="audio",
        group=GROUP_FILE,
        formats=tuple(ext.lstrip(".").upper() for ext in AUDIO_URL_EXTENSIONS),
    ),
)


def _assert_exhaustive() -> None:
    """Fail at import if a capability was added to the code but not to the list.

    This is the whole point of moving the showcase out of the catalogues: a
    forgotten platform used to be an omission nobody noticed for months, and
    here it is a startup error. Two directions are checked, because they catch
    different mistakes:

    - a `SourcePlatform` member that is neither offered nor withheld — someone
      added an ingestion path and the screen would never mention it;
    - a `DocumentFormat` member absent from the file families — someone
      taught the parser a format and the chip would understate what it accepts.
    """
    offered = {target.id for target in SHARE_TARGETS if target.group == GROUP_PLATFORM}
    unaccounted = sorted(
        platform.value
        for platform in SourcePlatform
        if platform.value not in offered and platform not in _WITHHELD_PLATFORMS
    )
    if unaccounted:
        raise RuntimeError(
            "SourcePlatform members missing from SHARE_TARGETS: "
            f"{', '.join(unaccounted)}. Add a ShareTarget for each, or list it "
            "in _WITHHELD_PLATFORMS with the reason it is not offered."
        )

    # Hosts are the other half of the same check: a platform the classifier can
    # recognise but the screen never names is the exact defect this replaces.
    unnamed_hosts = sorted(
        platform.value for platform in RECOGNISED_HOSTS if platform.value not in offered
    )
    if unnamed_hosts:
        raise RuntimeError(
            "Platforms the classifier recognises but SHARE_TARGETS does not "
            f"name: {', '.join(unnamed_hosts)}."
        )

    covered = (
        set(_DOCUMENT_FORMATS)
        | set(_TEXT_FORMATS)
        | set(_IMAGE_FORMATS)
        | _ALIAS_FORMATS
    )
    missing_formats = sorted(fmt.value for fmt in DocumentFormat if fmt not in covered)
    if missing_formats:
        raise RuntimeError(
            "DocumentFormat members missing from the file families: "
            f"{', '.join(missing_formats)}."
        )


_assert_exhaustive()


def share_targets_payload() -> list[dict[str, Any]]:
    """`SHARE_TARGETS` as the JSON the pricing endpoint embeds."""
    return [
        {
            "id": target.id,
            "group": target.group,
            "label": target.label,
            "formats": list(target.formats),
        }
        for target in SHARE_TARGETS
    ]
