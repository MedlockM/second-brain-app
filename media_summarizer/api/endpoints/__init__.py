"""
Package pour les endpoints de l'API.
"""
from fastapi import APIRouter

from . import health, users, credits, podcast_search

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(podcast_search.router, prefix="/podcast-search", tags=["podcast-search"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(credits.router, prefix="/credits", tags=["credits"])