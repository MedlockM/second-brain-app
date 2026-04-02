"""
Package pour les endpoints de l'API.
"""

from fastapi import APIRouter

# Endpoints package initialization (legacy credits system fully removed).
from . import artifacts, health, media, podcast_search, users

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(media.router, tags=["media"])
api_router.include_router(artifacts.router, tags=["artifacts"])
api_router.include_router(
    podcast_search.router, prefix="/podcast-search", tags=["podcast-search"]
)
api_router.include_router(users.router, prefix="/users", tags=["users"])
