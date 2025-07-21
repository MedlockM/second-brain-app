"""
Endpoints pour la vérification de l'état du service.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from media_summarizer.adapters.database.connection import get_db

router = APIRouter()

@router.get("/health")
async def health_check():
    """Vérifie l'état du service."""
    return {"status": "ok"}

@router.get("/health/db")
async def db_health_check(db: AsyncSession = Depends(get_db)):
    """Vérifie la connexion à la base de données."""
    try:
        # Exécute une requête simple pour vérifier la connexion
        await db.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception as e:
        return {"database": "error", "message": str(e)}