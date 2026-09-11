from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pathlib import Path
import ipaddress
import logging
import re

from app.routers import (
    venues,
    users,
    shows,
    passes,
    admin,
    promoters,
    lottery,
    specialty_shows,
)
from app.routers import legacy_import as legacy_import_router
from app.scheduler import (
    start_scheduler,
    shutdown_scheduler,
    bootstrap_users_if_empty,
    bootstrap_feature_bin_if_stale,
)
from app.auth import check_apache_auth_layer
from app.config import settings
from app.rate_limiter import RateLimitExceeded

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("musicbrainzngs").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def check_network_config(
    apache_conf_path: str = "/etc/apache2/conf-enabled/kalx-variables.conf",
) -> None:
    """
    Validate DJ studio network configuration consistency at startup.

    Compares DJ_STUDIO_NETWORK env var against the matching Apache Define
    directive, and verifies that DJ_STUDIO_NETWORK is a subnet of
    STATION_OFFICE_NETWORK (required by authentication logic).

    :param apache_conf_path: Path to the Apache variables conf file.
    """
    define_name = (
        "KALXSTAGE_DJ_STUDIO_NETWORK"
        if settings.environment == "staging"
        else "KALX_DJ_STUDIO_NETWORK"
    )
    conf = Path(apache_conf_path)
    if conf.exists():
        text = conf.read_text()
        match = re.search(
            rf"^\s*Define\s+{re.escape(define_name)}\s+(\S+)",
            text,
            re.MULTILINE,
        )
        if match:
            apache_value = match.group(1)
            if apache_value != settings.dj_studio_network:
                logger.critical(
                    "NETWORK CONFIG MISMATCH: Apache %s=%r differs from "
                    "DJ_STUDIO_NETWORK env var %r. Update one to match the other.",
                    define_name,
                    apache_value,
                    settings.dj_studio_network,
                )
            else:
                logger.info(
                    "Network config check passed: %s matches DJ_STUDIO_NETWORK (%s).",
                    define_name,
                    settings.dj_studio_network,
                )
        else:
            logger.warning(
                "Could not find %s in %s; skipping Apache/env mismatch check.",
                define_name,
                apache_conf_path,
            )
    else:
        logger.warning(
            "%s not found; skipping Apache/env DJ studio network mismatch check.",
            apache_conf_path,
        )

    try:
        dj_net = ipaddress.ip_network(settings.dj_studio_network, strict=False)
        office_net = ipaddress.ip_network(settings.station_office_network, strict=False)
        if not dj_net.subnet_of(office_net):
            logger.critical(
                "NETWORK CONFIG ERROR: DJ_STUDIO_NETWORK %r is not a subnet of"
                " STATION_OFFICE_NETWORK %r. Authentication logic relies on this"
                " relationship.",
                settings.dj_studio_network,
                settings.station_office_network,
            )
        else:
            logger.info(
                "Network config check passed: DJ_STUDIO_NETWORK (%s) is a subnet of "
                "STATION_OFFICE_NETWORK (%s).",
                settings.dj_studio_network,
                settings.station_office_network,
            )
    except ValueError as exc:
        logger.critical("NETWORK CONFIG ERROR: Invalid CIDR network value: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    check_network_config()
    start_scheduler()
    await bootstrap_users_if_empty()
    await bootstrap_feature_bin_if_stale()
    yield
    # Shutdown
    shutdown_scheduler()


app = FastAPI(
    title="Promotions Pass Giveaway API",
    description="API for managing radio station pass giveaways",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS - origins loaded from environment variable
# In production, this should be set to your actual domain(s)
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": (
                f"Too many requests. Please wait {exc.retry_after} second"
                f"{'s' if exc.retry_after != 1 else ''} before trying again."
            ),
            "retry_after": exc.retry_after,
        },
        headers={"Retry-After": str(exc.retry_after)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors (422 Unprocessable Entity).

    Returns detailed field-level validation errors.
    """
    logger.warning(f"Validation error on {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": exc.errors()},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """
    Handle database integrity errors (400 Bad Request).

    These typically indicate constraint violations like duplicate keys.
    """
    logger.error(f"Database integrity error on {request.url}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": (
                "Database constraint violation. The operation could not be completed due to"
                " data integrity requirements."
            )
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """
    Handle general database errors (500 Internal Server Error).

    These are unexpected database errors that should be logged for investigation.
    """
    logger.error(f"Database error on {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal database error occurred. Please try again later."},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected errors (500 Internal Server Error).

    This is a catch-all for any unhandled exceptions.
    """
    logger.error(f"Unexpected error on {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


# Include routers — apply check_apache_auth_layer to all API routes as a
# defense-in-depth check that Apache's authentication layer was in effect.
# GET / and GET /health (defined below) are excluded: they are internal
# backend endpoints not proxied through Apache.
_auth_check = [Depends(check_apache_auth_layer)]
app.include_router(venues.router, dependencies=_auth_check)
app.include_router(users.router, dependencies=_auth_check)
app.include_router(shows.router, dependencies=_auth_check)
app.include_router(passes.router, dependencies=_auth_check)
app.include_router(admin.router, dependencies=_auth_check)
app.include_router(promoters.router, dependencies=_auth_check)
app.include_router(lottery.router, dependencies=_auth_check)
app.include_router(specialty_shows.router, dependencies=_auth_check)
if settings.legacy_import_enabled:
    app.include_router(legacy_import_router.router, dependencies=_auth_check)


@app.get("/")
async def root():
    return {"message": "Promotions Pass Giveaway API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
