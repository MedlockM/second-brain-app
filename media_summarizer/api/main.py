import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from media_summarizer.api.endpoints import health, users, podcast_search, jobs
from media_summarizer.api.endpoints import auth
from media_summarizer.api.endpoints import auth_social
from media_summarizer.api.endpoints import podcasts

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Initialisation des ressources (connexions DB, etc.)
    # Fail fast if required S3 buckets are missing (Terraform should provision infra)
    if os.environ.get("PRESTART_INFRA_CHECK", "1") == "1":
        from media_summarizer.utils.infra_check import s3_preflight_check
        missing = await s3_preflight_check()
        if missing:
            raise RuntimeError(
                "Infrastructure not ready: missing S3 buckets: " + ", ".join(missing) +
                ". Please run Terraform (docker-compose terraform service) and retry."
            )
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

# Rate limiting global (par IP)
from media_summarizer.api.rate_limit import limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Configuration CORS
# Use CORS_ORIGINS per project convention (fallback to '*')
allowed_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
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
    errors = []
    for error in exc.errors():
        error_dict = {}
        for key, value in error.items():
            if key == "ctx" and isinstance(value, dict) and "error" in value:
                # Convert Exception objects to strings
                error_dict[key] = {k: str(v) if isinstance(v, Exception) else v for k, v in value.items()}
            else:
                error_dict[key] = value
        errors.append(error_dict)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors, "body": exc.body},
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

# Public redirect landing pages for Stripe Checkout
# These are not webhooks; they are simple pages where the browser lands after payment
@app.get("/payment-success", include_in_schema=False)
async def payment_success(session_id: str | None = None):
    return {"status": "success", "session_id": session_id}

@app.get("/payment-cancel", include_in_schema=False)
async def payment_cancel():
    return {"status": "cancelled"}

# Inclusion des routes API
app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(auth_social.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(podcast_search.router, prefix="/api/v1/podcast-search", tags=["podcast-search"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
from media_summarizer.api.endpoints import billing
app.include_router(billing.router, prefix="/api/v1", tags=["billing"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(podcasts.router, prefix="/api/v1", tags=["podcasts"])
