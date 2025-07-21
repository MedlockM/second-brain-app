"""
Package pour les endpoints de l'API.
"""
from fastapi import APIRouter

from . import health, podcasts, users, credits

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(podcasts.router, prefix="/podcasts", tags=["podcasts"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(credits.router, prefix="/credits", tags=["credits"])