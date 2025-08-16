"""
Tests unitaires pour le module whisper_async.

Ces tests vérifient le bon fonctionnement de l'approche hybride async/sync
pour Whisper, incluant les wrappers et les utilitaires.
"""
import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import pytest_asyncio

from media_summarizer.core.utils.whisper_async import (
    transcribe_async,
    AsyncWhisperWrapper,
    create_async_whisper_model,
    create_mock_async_whisper_model,
    transcribe_audio_for_testing
)


class TestTranscribeAsync:
    """Tests pour la fonction transcribe_async."""

    @pytest.mark.asyncio
    async def test_transcribe_async_success(self):
        """Test de transcription async réussie."""
        # Setup
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "Hello world",
            "segments": [{"start": 0, "end": 1, "text": "Hello world"}],
            "language": "en"
        }

        with patch("os.path.exists", return_value=True):
            with patch("whisper.load_model", return_value=mock_model):
                # Execute
                result = await transcribe_async("/tmp/test.mp3", "base")

                # Verify
                assert result["text"] == "Hello world"
                assert len(result["segments"]) == 1
                assert result["language"] == "en"
                mock_model.transcribe.assert_called_once_with("/tmp/test.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_async_with_kwargs(self):
        """Test de transcription async avec des arguments supplémentaires."""
        # Setup
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "Bonjour monde",
            "segments": [],
            "language": "fr"
        }

        with patch("os.path.exists", return_value=True):
            with patch("whisper.load_model", return_value=mock_model):
                # Execute
                result = await transcribe_async(
                    "/tmp/test.mp3",
                    "base",
                    language="fr",
                    task="transcribe"
                )

                # Verify
                mock_model.transcribe.assert_called_once_with(
                    "/tmp/test.mp3",
                    language="fr",
                    task="transcribe"
                )
                assert result["language"] == "fr"

    @pytest.mark.asyncio
    async def test_transcribe_async_file_not_found(self):
        """Test quand le fichier audio n'existe pas."""
        with patch("os.path.exists", return_value=False):
            # Execute & Verify
            with pytest.raises(FileNotFoundError, match="Audio file not found"):
                await transcribe_async("/tmp/nonexistent.mp3", "base")

    @pytest.mark.asyncio
    async def test_transcribe_async_model_error(self):
        """Test quand le modèle lève une exception."""
        # Setup
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = Exception("Model error")

        with patch("os.path.exists", return_value=True):
            with patch("whisper.load_model", return_value=mock_model):
                # Execute & Verify
                with pytest.raises(RuntimeError, match="Transcription failed"):
                    await transcribe_async("/tmp/test.mp3", "base")

    @pytest.mark.asyncio
    async def test_transcribe_async_invalid_result_format(self):
        """Test quand le modèle retourne un format invalide."""
        # Setup
        mock_model = MagicMock()
        mock_model.transcribe.return_value = "invalid result"

        with patch("os.path.exists", return_value=True):
            with patch("whisper.load_model", return_value=mock_model):
                # Execute & Verify
                with pytest.raises(RuntimeError, match="Invalid transcription result format"):
                    await transcribe_async("/tmp/test.mp3", "base")

    @pytest.mark.asyncio
    async def test_transcribe_async_missing_fields(self):
        """Test quand le résultat manque de champs requis."""
        # Setup
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {}  # Missing required fields

        with patch("os.path.exists", return_value=True):
            with patch("whisper.load_model", return_value=mock_model):
                # Execute
                result = await transcribe_async("/tmp/test.mp3", "base")

            # Verify - fields should be added with default values
            assert result["text"] == ""
            assert result["segments"] == []
            assert result["language"] == "unknown"


class TestAsyncWhisperWrapper:
    """Tests pour la classe AsyncWhisperWrapper."""

    def test_init_valid_model(self):
        """Test d'initialisation avec un modèle valide."""
        mock_model = MagicMock()
        mock_model.transcribe = MagicMock()

        wrapper = AsyncWhisperWrapper(mock_model)

        assert wrapper.model == mock_model
        assert wrapper.is_available

    def test_init_invalid_model(self):
        """Test d'initialisation avec un modèle invalide."""
        mock_model = MagicMock()
        delattr(mock_model, 'transcribe')  # Remove transcribe method

        with pytest.raises(ValueError, match="Model must have a 'transcribe' method"):
            AsyncWhisperWrapper(mock_model)

    @pytest.mark.asyncio
    async def test_transcribe_async_method(self):
        """Test de la méthode transcribe async."""
        # Setup
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "Test transcription",
            "segments": [],
            "language": "en"
        }

        wrapper = AsyncWhisperWrapper(mock_model)

        with patch("os.path.exists", return_value=True):
            # Execute
            result = await wrapper.transcribe("/tmp/test.mp3")

            # Verify
            assert result["text"] == "Test transcription"
            mock_model.transcribe.assert_called_once()

    def test_transcribe_sync_method(self):
        """Test de la méthode transcribe synchrone."""
        # Setup
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "Sync transcription",
            "segments": [],
            "language": "en"
        }

        wrapper = AsyncWhisperWrapper(mock_model)

        # Execute
        result = wrapper.transcribe_sync("/tmp/test.mp3")

        # Verify
        assert result["text"] == "Sync transcription"
        mock_model.transcribe.assert_called_once_with("/tmp/test.mp3")

    def test_model_info_property(self):
        """Test de la propriété model_info."""
        # Setup
        mock_model = MagicMock()
        mock_model.is_mock = True

        wrapper = AsyncWhisperWrapper(mock_model)

        # Execute
        info = wrapper.model_info

        # Verify
        assert info["type"] == "MagicMock"
        assert info["available"] is True
        assert info["is_mock"] is True

    def test_model_info_without_mock_attribute(self):
        """Test de model_info sans attribut is_mock."""
        # Setup
        mock_model = MagicMock()
        if hasattr(mock_model, 'is_mock'):
            delattr(mock_model, 'is_mock')

        wrapper = AsyncWhisperWrapper(mock_model)

        # Execute
        info = wrapper.model_info

        # Verify
        assert info["type"] == "MagicMock"
        assert info["available"] is True
        assert "is_mock" not in info


class TestFactoryFunctions:
    """Tests pour les fonctions factory."""

    @patch('whisper.load_model')
    def test_create_async_whisper_model_success(self, mock_load_model):
        """Test de création réussie d'un modèle async."""
        # Setup
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model

        # Execute
        wrapper = create_async_whisper_model("tiny")

        # Verify
        assert isinstance(wrapper, AsyncWhisperWrapper)
        assert wrapper.model == mock_model
        mock_load_model.assert_called_once_with("tiny")

    @patch('whisper.load_model')
    def test_create_async_whisper_model_whisper_not_installed(self, mock_load_model):
        """Test quand whisper n'est pas installé."""
        # Setup
        mock_load_model.side_effect = ImportError("No module named 'whisper'")

        # Execute & Verify
        with pytest.raises(ImportError, match="Whisper package not found"):
            create_async_whisper_model("tiny")

    @patch('whisper.load_model')
    def test_create_async_whisper_model_load_error(self, mock_load_model):
        """Test quand le chargement du modèle échoue."""
        # Setup
        mock_load_model.side_effect = Exception("Model load error")

        # Execute & Verify
        with pytest.raises(RuntimeError, match="Failed to load Whisper model"):
            create_async_whisper_model("large")

    def test_create_mock_async_whisper_model(self):
        """Test de création d'un modèle mock async."""
        # Execute
        wrapper = create_mock_async_whisper_model()

        # Verify
        assert isinstance(wrapper, AsyncWhisperWrapper)
        assert wrapper.model.is_mock is True

        # Test the mock transcription
        result = wrapper.model.transcribe("dummy.mp3")
        assert "text" in result
        assert "segments" in result
        assert "language" in result
        assert result["text"] == "This is a mock transcription for testing purposes."


class TestUtilityFunctions:
    """Tests pour les fonctions utilitaires."""

    @pytest.mark.asyncio
    async def test_test_transcription_async_with_mock(self):
        """Test de la fonction de test avec mock."""
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_file.write(b"fake audio content")
            temp_path = temp_file.name

        try:
            # Execute
            result = await transcribe_audio_for_testing(temp_path, use_mock=True)

            # Verify
            assert isinstance(result, dict)
            assert "text" in result
            assert "segments" in result
            assert "language" in result
        finally:
            # Cleanup
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_test_transcription_async_with_real_model(self):
        """Test de la fonction de test avec vrai modèle."""
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_file.write(b"fake audio content")
            temp_path = temp_file.name

        try:
            with patch('whisper.load_model') as mock_load_model:
                # Setup mock model
                mock_model = MagicMock()
                mock_model.transcribe.return_value = {
                    "text": "Real model result",
                    "segments": [],
                    "language": "en"
                }
                mock_load_model.return_value = mock_model

                # Execute
                result = await transcribe_audio_for_testing(temp_path, use_mock=False)

                # Verify
                assert result["text"] == "Real model result"
                mock_load_model.assert_called_once_with("tiny")
        finally:
            # Cleanup
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestIntegration:
    """Tests d'intégration pour l'approche hybride."""

    @pytest.mark.asyncio
    async def test_async_concurrent_transcriptions(self):
        """Test de transcriptions concurrentes."""
        # Setup
        mock_model = MagicMock()
        call_count = 0

        def mock_transcribe(audio_path, **kwargs):
            nonlocal call_count
            call_count += 1
            return {
                "text": f"Transcription {call_count}",
                "segments": [],
                "language": "en"
            }

        mock_model.transcribe = mock_transcribe
        wrapper = AsyncWhisperWrapper(mock_model)

        with patch("os.path.exists", return_value=True):
            # Execute multiple concurrent transcriptions
            tasks = [
                wrapper.transcribe(f"/tmp/test{i}.mp3")
                for i in range(3)
            ]
            results = await asyncio.gather(*tasks)

            # Verify
            assert len(results) == 3
            assert all("text" in result for result in results)
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_wrapper_preserves_interface(self):
        """Test que le wrapper async préserve l'interface Whisper."""
        # Setup
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "Interface test",
            "segments": [
                {"id": 0, "start": 0.0, "end": 1.0, "text": "Interface test"}
            ],
            "language": "en"
        }

        wrapper = AsyncWhisperWrapper(mock_model)

        with patch("os.path.exists", return_value=True):
            # Execute both sync and async
            sync_result = wrapper.transcribe_sync("/tmp/test.mp3")
            async_result = await wrapper.transcribe("/tmp/test.mp3")

            # Verify both have same structure
            assert sync_result.keys() == async_result.keys()
            assert sync_result["text"] == async_result["text"]
            assert len(sync_result["segments"]) == len(async_result["segments"])
