"""
Utilitaires pour l'approche hybride async/sync de Whisper.

Ce module fournit des wrappers async pour Whisper qui permettent de maintenir
une interface async cohérente tout en gardant Whisper synchrone en interne
pour des performances optimales.
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


async def transcribe_async_with_model(
    whisper_model,
    audio_path: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Wrapper async pour Whisper utilisant run_in_executor avec modèle pré-chargé.

    Cette approche hybride permet de :
    - Garder Whisper synchrone en interne (optimisé pour le CPU)
    - Avoir une interface async cohérente avec le reste de l'application
    - Permettre le traitement concurrent d'autres tâches
    - Éviter de bloquer la boucle d'événements

    Args:
        whisper_model: Le modèle Whisper chargé (réel ou mock)
        audio_path: Chemin vers le fichier audio à transcrire
        **kwargs: Arguments supplémentaires pour Whisper (language, task, etc.)

    Returns:
        Résultat de la transcription au format Whisper standard:
        {
            "text": str,
            "segments": List[Dict],
            "language": str
        }

    Raises:
        FileNotFoundError: Si le fichier audio n'existe pas
        RuntimeError: En cas d'erreur lors de la transcription
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        loop = asyncio.get_event_loop()
        # Create a partial function with kwargs to work with run_in_executor
        from functools import partial
        transcribe_with_kwargs = partial(whisper_model.transcribe, audio_path, **kwargs)
        result = await loop.run_in_executor(None, transcribe_with_kwargs)

        # Validation du format de retour
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid transcription result format: {type(result)}")

        # S'assurer que les champs requis sont présents
        if "text" not in result:
            logger.warning("Transcription result missing 'text' field")
            result["text"] = ""

        if "segments" not in result:
            logger.warning("Transcription result missing 'segments' field")
            result["segments"] = []

        if "language" not in result:
            logger.warning("Transcription result missing 'language' field")
            result["language"] = "unknown"

        logger.debug(f"Successfully transcribed audio: {len(result['text'])} characters")
        return result

    except Exception as e:
        logger.error(f"Error during async transcription: {e}")
        raise RuntimeError(f"Transcription failed: {str(e)}") from e


class AsyncWhisperWrapper:
    """
    Wrapper classe pour rendre n'importe quel modèle Whisper async.

    Cette classe peut wrapper:
    - Un vrai modèle Whisper
    - Un mock Whisper pour les tests
    - Tout objet ayant une méthode transcribe()
    """

    def __init__(self, whisper_model):
        """
        Initialise le wrapper avec un modèle Whisper.

        Args:
            whisper_model: Le modèle Whisper à wrapper (réel ou mock)
        """
        self.model = whisper_model
        self._validate_model()

    def _validate_model(self):
        """Valide que le modèle a bien une méthode transcribe."""
        if not hasattr(self.model, 'transcribe'):
            raise ValueError("Model must have a 'transcribe' method")

    async def transcribe(self, audio_path: str, **kwargs) -> Dict[str, Any]:
        """
        Transcrit un fichier audio de manière asynchrone.

        Args:
            audio_path: Chemin vers le fichier audio
            **kwargs: Arguments pour Whisper

        Returns:
            Résultat de la transcription
        """
        return await transcribe_async_with_model(self.model, audio_path, **kwargs)

    def transcribe_sync(self, audio_path: str, **kwargs) -> Dict[str, Any]:
        """
        Transcrit un fichier audio de manière synchrone.

        Args:
            audio_path: Chemin vers le fichier audio
            **kwargs: Arguments pour Whisper

        Returns:
            Résultat de la transcription
        """
        return self.model.transcribe(audio_path, **kwargs)

    @property
    def is_available(self) -> bool:
        """Vérifie si le modèle est disponible."""
        return self.model is not None

    @property
    def model_info(self) -> Dict[str, Any]:
        """Retourne des informations sur le modèle."""
        info = {
            "type": type(self.model).__name__,
            "available": self.is_available
        }

        # Ajouter des infos spécifiques si disponibles
        if hasattr(self.model, 'is_mock'):
            info["is_mock"] = self.model.is_mock

        return info


def create_async_whisper_model(model_size: str = "tiny") -> AsyncWhisperWrapper:
    """
    Factory pour créer un modèle Whisper async.

    Args:
        model_size: Taille du modèle Whisper (tiny, large)

    Returns:
        AsyncWhisperWrapper configuré

    Raises:
        ImportError: Si whisper n'est pas installé
        RuntimeError: Si le chargement du modèle échoue
    """
    try:
        import whisper
        model = whisper.load_model(model_size)
        return AsyncWhisperWrapper(model)
    except ImportError as e:
        raise ImportError("Whisper package not found. Install with: pip install openai-whisper") from e
    except Exception as e:
        raise RuntimeError(f"Failed to load Whisper model '{model_size}': {str(e)}") from e


async def transcribe_async(
    audio_path: str,
    model_name: str = "tiny",
    **kwargs
) -> Dict[str, Any]:
    """
    Transcrit un fichier audio de manière asynchrone en chargeant le modèle Whisper.

    Cette fonction est une version simplifiée qui charge le modèle à la demande.
    Pour des performances optimales avec de nombreuses transcriptions, utilisez
    AsyncWhisperWrapper avec un modèle pré-chargé.

    Args:
        audio_path: Chemin vers le fichier audio à transcrire
        model_name: Nom/taille du modèle Whisper (tiny, large, etc.)
        **kwargs: Arguments supplémentaires pour Whisper (language, task, etc.)

    Returns:
        Résultat de la transcription au format Whisper standard:
        {
            "text": str,
            "segments": List[Dict],
            "language": str
        }

    Raises:
        FileNotFoundError: Si le fichier audio n'existe pas
        RuntimeError: En cas d'erreur lors de la transcription
        ImportError: Si whisper n'est pas installé
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        import whisper

        # Charger le modèle
        model = whisper.load_model(model_name)

        # Exécuter la transcription dans un executor pour éviter de bloquer
        loop = asyncio.get_event_loop()
        from functools import partial
        transcribe_with_kwargs = partial(model.transcribe, audio_path, **kwargs)
        result = await loop.run_in_executor(None, transcribe_with_kwargs)

        # Validation du format de retour
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid transcription result format: {type(result)}")

        # S'assurer que les champs requis sont présents
        if "text" not in result:
            logger.warning("Transcription result missing 'text' field")
            result["text"] = ""

        if "segments" not in result:
            logger.warning("Transcription result missing 'segments' field")
            result["segments"] = []

        if "language" not in result:
            logger.warning("Transcription result missing 'language' field")
            result["language"] = "unknown"

        logger.debug(f"Successfully transcribed audio: {len(result['text'])} characters")
        return result

    except ImportError as e:
        raise ImportError("Whisper package not found. Install with: pip install openai-whisper") from e
    except Exception as e:
        logger.error(f"Error during async transcription: {e}")
        raise RuntimeError(f"Transcription failed: {str(e)}") from e


def create_mock_async_whisper_model() -> AsyncWhisperWrapper:
    """
    Factory pour créer un modèle Whisper mock async.

    Returns:
        AsyncWhisperWrapper avec un modèle mock pour les tests
    """
    class MockWhisperModel:
        """Modèle Whisper mock pour les tests."""

        def __init__(self):
            self.is_mock = True

        def transcribe(self, audio_file: str, **kwargs) -> Dict[str, Any]:
            """Mock transcription avec résultat prédéfini."""
            return {
                "text": "This is a mock transcription for testing purposes.",
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 10.0,
                        "text": "This is a mock transcription segment."
                    }
                ],
                "language": "en"
            }

    mock_model = MockWhisperModel()
    return AsyncWhisperWrapper(mock_model)


# Fonction de convenance pour les tests
async def transcribe_audio_for_testing(audio_file: str, use_mock: bool = False) -> Dict[str, Any]:
    """
    Fonction de test pour vérifier la transcription async.

    Args:
        audio_file: Fichier audio à transcrire
        use_mock: Utiliser un mock au lieu du vrai modèle

    Returns:
        Résultat de la transcription
    """
    if use_mock:
        wrapper = create_mock_async_whisper_model()
    else:
        wrapper = create_async_whisper_model("tiny")

    return await wrapper.transcribe(audio_file)
