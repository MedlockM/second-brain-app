import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from media_summarizer.api.endpoints import health, users, credits, podcast_search, jobs

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Initialisation des ressources (connexions DB, etc.)
    yield
    # Shutdown
    # Libération des ressources
    pass

# Création de l'application FastAPI
app = FastAPI(
    title="Media Summarizer API",
    description="API pour le service de résumé automatique de podcasts",
    version="0.1.0",
    lifespan=lifespan,
)

# Configuration CORS
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Gestionnaire d'exceptions global
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )



@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API Media Summarizer"}

# Inclusion des routes API
app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(podcast_search.router, prefix="/api/v1/podcast-search", tags=["podcast-search"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(credits.router, prefix="/api/v1", tags=["credits"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
