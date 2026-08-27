"""Per-kind artifact generators (prompt, validator, model, content builder)."""

from media_summarizer.core.models.media_artifact import MediaArtifactType
from media_summarizer.workers.artifact_generator.generators.base import ArtifactGenerator
from media_summarizer.workers.artifact_generator.generators.flashcards import FlashcardsGenerator
from media_summarizer.workers.artifact_generator.generators.notes import NotesGenerator
from media_summarizer.workers.artifact_generator.generators.quiz import QuizGenerator
from media_summarizer.workers.artifact_generator.generators.review_blurb import ReviewBlurbGenerator
from media_summarizer.workers.artifact_generator.generators.summary_detailed import SummaryDetailedGenerator
from media_summarizer.workers.artifact_generator.generators.summary_short import SummaryShortGenerator

GENERATORS: dict[MediaArtifactType, ArtifactGenerator] = {
    MediaArtifactType.FLASHCARDS: FlashcardsGenerator(),
    MediaArtifactType.NOTES: NotesGenerator(),
    MediaArtifactType.QUIZ: QuizGenerator(),
    MediaArtifactType.SUMMARY_SHORT: SummaryShortGenerator(),
    MediaArtifactType.SUMMARY_DETAILED: SummaryDetailedGenerator(),
    # Internal type: the worker resolves it here like any other, what keeps it out
    # of the user-facing surface is artifact_service.INTERNAL_ARTIFACT_TYPES.
    MediaArtifactType.REVIEW_BLURB: ReviewBlurbGenerator(),
}

__all__ = [
    "GENERATORS",
    "ArtifactGenerator",
    "FlashcardsGenerator",
    "NotesGenerator",
    "QuizGenerator",
    "ReviewBlurbGenerator",
    "SummaryShortGenerator",
    "SummaryDetailedGenerator",
]
