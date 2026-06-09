import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError


from media_summarizer.api.endpoints import (
    artifacts,
    digest,
    health,
    jobs,
    media,
    newsletter_webhook,
    podcast_search,
    podcasts,
    pricing,
    review,
    users,
)
from media_summarizer.api.endpoints import auth
from media_summarizer.api.endpoints import auth_social
from media_summarizer.api.endpoints import bug_reports
from media_summarizer.api.endpoints import entitlements
from media_summarizer.api.endpoints import feedback
from media_summarizer.api.endpoints import revenucat_webhook
from media_summarizer.api.endpoints import folders
from media_summarizer.api.endpoints import search
from media_summarizer.api.endpoints import feeds
from media_summarizer.api.endpoints import tags
from media_summarizer.api.error_handling import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from media_summarizer.utils.logging_config import (
    bind_log_context,
    get_slow_request_threshold_ms,
    log_event,
    reset_log_context,
    setup_logging,
)

APP_VERSION = "0.1.0"

setup_logging("api", version=APP_VERSION)
logger = logging.getLogger(__name__)


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
                "Infrastructure not ready: missing S3 buckets: "
                + ", ".join(missing)
                + ". Please run Terraform (docker-compose terraform service) and retry."
            )
    yield
    # Shutdown
    # Libération des ressources
    pass


# Création de l'application FastAPI
app = FastAPI(
    title="Media Summarizer API",
    description="API pour le service de résumé automatique de podcasts",
    version=APP_VERSION,
    lifespan=lifespan,
)

# Rate limiting is handled by API Gateway throttling (no in-process limiter needed).

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

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    token = bind_log_context(
        request_id=request_id,
        path=str(request.url.path),
        method=request.method,
    )
    response = None
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        if (
            response is not None
            and response.status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
            and duration_ms >= get_slow_request_threshold_ms()
        ):
            log_event(
                logger,
                logging.WARNING,
                "api.request_slow",
                "Slow API request",
                duration_ms=duration_ms,
                status=response.status_code,
            )
        reset_log_context(token)


# Gestionnaire d'exceptions global
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API Media Summarizer"}


# Inclusion des routes API
app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(media.router, prefix="/api/media", tags=["media"])
app.include_router(newsletter_webhook.router, prefix="/api/media", tags=["newsletter"])
app.include_router(artifacts.router, prefix="/api", tags=["artifacts"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(auth_social.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(
    podcast_search.router, prefix="/api/v1/podcast-search", tags=["podcast-search"]
)
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(podcasts.router, prefix="/api/v1", tags=["podcasts"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(folders.router, prefix="/api/folders", tags=["folders"])
app.include_router(review.router, prefix="/api", tags=["review"])
app.include_router(tags.router, prefix="/api/tags", tags=["tags"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(feeds.router, prefix="/api/feeds", tags=["feeds"])
app.include_router(digest.router, prefix="/api", tags=["digest"])
app.include_router(pricing.router, prefix="/api", tags=["pricing"])
app.include_router(entitlements.router, prefix="/api/v1", tags=["entitlements"])
app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
app.include_router(revenucat_webhook.router, prefix="/api", tags=["webhooks"])
app.include_router(bug_reports.router, prefix="/api/bug-reports", tags=["bug-reports"])

# --- OpenAPI customization: add HTTP Bearer scheme alongside OAuth2PasswordBearer ---
from fastapi.openapi.utils import get_openapi


def custom_openapi():
    """Augment the generated OpenAPI with an HTTP Bearer security scheme.

    This does not change runtime auth. It only adds a Bearer scheme to the
    Swagger "Authorize" modal so a raw JWT can be pasted directly.
    For operations that already declare security (via dependencies), we add
    BearerAuth as an alternative requirement so either scheme can be used.
    """
    if app.openapi_schema:
        openapi_schema = app.openapi_schema
    else:
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

    components = openapi_schema.setdefault("components", {}).setdefault(
        "securitySchemes", {}
    )
    # Add or update BearerAuth scheme
    components["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }

    # For each operation that already has a security requirement, add BearerAuth
    for _path, methods in openapi_schema.get("paths", {}).items():
        for _method, operation in methods.items():
            if not isinstance(operation, dict):
                continue
            if "security" in operation and isinstance(operation["security"], list):
                if {"BearerAuth": []} not in operation["security"]:
                    operation["security"].append({"BearerAuth": []})

    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Apply customization
app.openapi = custom_openapi
