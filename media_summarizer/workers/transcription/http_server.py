"""
Serveur HTTP pour le service Whisper en mode E2E.
Permet d'exposer les fonctionnalités de transcription via une API REST.
"""
import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional

import whisper
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
import uvicorn

# Import direct de whisper - pas besoin d'async wrapper pour E2E

# Logger instance - setup happens at server start via uvicorn or setup_logging()
logger = logging.getLogger(__name__)

# Initialisation du modèle Whisper
def load_whisper_model():
    """Charge le modèle Whisper selon la configuration."""
    if os.environ.get("MOCK_WHISPER", "0") == "1":
        # Mock model pour les tests
        class MockWhisperModel:
            def transcribe(self, audio_file, **kwargs):
                return {
                    "text": "This is a mock transcription for E2E testing purposes.",
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

        logger.info("Using mock Whisper model for E2E testing")
        return MockWhisperModel()
    else:
        # Modèle réel
        environment = os.environ.get("ENVIRONMENT", "development")

        if environment == "production":
            default_model = "large"
        elif environment == "e2e":
            default_model = "base"  # Compromis entre qualité et vitesse pour E2E
        else:
            default_model = "tiny"

        whisper_model_size = os.environ.get("WHISPER_MODEL_SIZE", default_model)

        logger.info(f"Loading Whisper model: {whisper_model_size} for environment: {environment}")

        try:
            model = whisper.load_model(whisper_model_size)
            logger.info(f"Successfully loaded Whisper model: {whisper_model_size}")
            return model
        except Exception as e:
            logger.error(f"Failed to load Whisper model '{whisper_model_size}': {str(e)}")
            # Fallback vers tiny si le modèle demandé échoue
            if whisper_model_size != "tiny":
                logger.warning("Falling back to 'tiny' model")
                return whisper.load_model("tiny")
            else:
                raise RuntimeError(f"Cannot load even the fallback 'tiny' model: {str(e)}")

# Chargement du modèle au démarrage
model = load_whisper_model()

# Création de l'application FastAPI
app = FastAPI(
    title="Whisper Transcription Service",
    description="Service de transcription audio utilisant Whisper pour les tests E2E",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    """Endpoint de vérification de santé du service."""
    try:
        # Vérifier que le modèle est chargé
        model_loaded = model is not None

        # Obtenir des informations sur le modèle
        model_size = os.environ.get("WHISPER_MODEL_SIZE", "unknown")

        return {
            "status": "healthy",
            "model_loaded": model_loaded,
            "model_size": model_size,
            "environment": os.environ.get("ENVIRONMENT", "development"),
            "mock_mode": os.environ.get("MOCK_WHISPER", "0") == "1",
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.get("/model-info")
async def get_model_info():
    """Retourne les informations détaillées sur le modèle Whisper."""
    try:
        return {
            "model_size": os.environ.get("WHISPER_MODEL_SIZE", "unknown"),
            "environment": os.environ.get("ENVIRONMENT", "development"),
            "mock_mode": os.environ.get("MOCK_WHISPER", "0") == "1",
            "model_loaded": model is not None,
            "supported_languages": ["auto", "en", "fr", "es", "de", "it", "pt", "ru", "ja", "ko", "zh"],
            "max_audio_duration": int(os.environ.get("MAX_AUDIO_DURATION", "3600")),  # 1 heure par défaut
        }
    except Exception as e:
        logger.error(f"Model info request failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Model info request failed: {str(e)}")

@app.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None)
):
    """
    Transcrit un fichier audio uploadé.

    Args:
        audio: Fichier audio à transcrire (formats supportés: mp3, wav, m4a, etc.)
        language: Langue optionnelle (auto-détection si non spécifiée)

    Returns:
        JSON avec le texte transcrit, les segments et les métadonnées
    """
    if not model:
        raise HTTPException(status_code=500, detail="Whisper model not loaded")

    # Validation du fichier
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file provided")

    # Vérifier la taille du fichier (limite configurable)
    max_file_size = int(os.environ.get("MAX_FILE_SIZE", "104857600"))  # 100MB par défaut
    if audio.size and audio.size > max_file_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {max_file_size} bytes"
        )

    temp_path = None
    start_time = time.time()

    try:
        # Sauvegarder le fichier temporairement
        suffix = Path(audio.filename).suffix or ".mp3"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            temp_path = temp_file.name

            # Lire et sauvegarder le contenu
            content = await audio.read()
            temp_file.write(content)
            temp_file.flush()

        logger.info(f"Processing transcription for file: {audio.filename} ({len(content)} bytes)")

        # Transcription avec Whisper (synchrone - plus simple et direct pour E2E)
        transcription_start = time.time()

        # Préparer les options de transcription
        transcribe_options = {}
        if language and language != "auto":
            transcribe_options["language"] = language

        # Transcription synchrone dans un executor pour ne pas bloquer FastAPI
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(temp_path, **transcribe_options)
        )

        transcription_time = time.time() - transcription_start
        total_time = time.time() - start_time

        logger.info(f"Transcription completed in {transcription_time:.2f}s (total: {total_time:.2f}s)")

        # Préparer la réponse
        response = {
            "success": True,
            "text": result["text"],
            "language": result.get("language", "unknown"),
            "segments": result.get("segments", []),
            "model_size": os.environ.get("WHISPER_MODEL_SIZE", "unknown"),
            "processing_time": transcription_time,
            "total_time": total_time,
            "file_size": len(content),
            "filename": audio.filename
        }

        # Ajouter des avertissements si nécessaire
        text_content = result["text"]
        if isinstance(text_content, list):
            text_content = " ".join(str(item) for item in text_content)
        if not text_content.strip():
            response["warning"] = "Empty transcription - audio may be silent or corrupted"

        return JSONResponse(content=response)

    except Exception as e:
        error_time = time.time() - start_time
        logger.error(f"Transcription failed after {error_time:.2f}s: {str(e)}")

        # Retourner une erreur structurée
        error_response = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "processing_time": error_time,
            "filename": audio.filename if audio.filename else "unknown"
        }

        # Codes d'erreur spécifiques
        if "timeout" in str(e).lower():
            raise HTTPException(status_code=408, detail=error_response)
        elif "memory" in str(e).lower() or "out of memory" in str(e).lower():
            raise HTTPException(status_code=507, detail=error_response)
        else:
            raise HTTPException(status_code=500, detail=error_response)

    finally:
        # Nettoyage du fichier temporaire
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.debug(f"Temporary file cleaned up: {temp_path}")
            except OSError as e:
                logger.warning(f"Failed to clean up temporary file {temp_path}: {str(e)}")

@app.get("/")
async def root():
    """Endpoint racine avec informations sur le service."""
    return {
        "service": "Whisper Transcription Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "model_info": "/model-info",
            "transcribe": "/transcribe (POST)"
        }
    }

def create_app() -> FastAPI:
    """Factory pour créer l'application FastAPI."""
    return app

async def start_server(host: str = "0.0.0.0", port: int = 8080):
    """Démarre le serveur HTTP Whisper."""
    logger.info(f"Starting Whisper HTTP server on {host}:{port}")
    logger.info(f"Model: {os.environ.get('WHISPER_MODEL_SIZE', 'unknown')}")
    logger.info(f"Environment: {os.environ.get('ENVIRONMENT', 'development')}")

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )

    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    from media_summarizer.utils.logging_config import setup_logging
    setup_logging("whisper-http-server")

    # Configuration du serveur depuis les variables d'environnement
    host = os.environ.get("WHISPER_HOST", "0.0.0.0")
    port = int(os.environ.get("WHISPER_PORT", "8080"))

    # Démarrage du serveur
    asyncio.run(start_server(host, port))
