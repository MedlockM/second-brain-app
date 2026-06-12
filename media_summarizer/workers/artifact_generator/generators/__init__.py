"""Per-kind artifact generators (prompt, validator, model, content builder)."""

from media_summarizer.core.models.media_artifact import MediaArtifactType
from media_summarizer.workers.artifact_generator.generators.base import ArtifactGenerator
from media_summarizer.workers.artifact_generator.generators.flashcards import FlashcardsGenerator
from media_summarizer.workers.artifact_generator.generators.notes import NotesGenerator
from media_summarizer.workers.artifact_generator.generators.quiz import QuizGenerator
from media_summarizer.workers.artifact_generator.generators.summary_short import SummaryShortGenerator
from media_summarizer.workers.artifact_generator.generators.summary_detailed import SummaryDetailedGenerator

GENERATORS: dict[MediaArtifactType, ArtifactGenerator] = {
    MediaArtifactType.FLASHCARDS: FlashcardsGenerator(),
    MediaArtifactType.NOTES: NotesGenerator(),
    MediaArtifactType.QUIZ: QuizGenerator(),
    MediaArtifactType.SUMMARY_SHORT: SummaryShortGenerator(),
    MediaArtifactType.SUMMARY_DETAILED: SummaryDetailedGenerator(),
}

__all__ = [
    "GENERATORS",
    "ArtifactGenerator",
    "FlashcardsGenerator",
    "NotesGenerator",
    "QuizGenerator",
    "SummaryShortGenerator",
    "SummaryDetailedGenerator",
]
