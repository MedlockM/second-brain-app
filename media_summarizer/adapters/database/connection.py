"""
Module de connexion à la base de données PostgreSQL.
"""
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# URL de connexion à la base de données
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/media_summarizer"
)

# Création du moteur SQLAlchemy
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Mettre à True pour le débogage SQL
)

# Création du sessionmaker
async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dépendance pour obtenir une session de base de données.
    À utiliser avec FastAPI Depends.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise