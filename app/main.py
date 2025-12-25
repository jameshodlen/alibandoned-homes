"""FastAPI application entry point.

This module initializes the FastAPI application with CORS,
middleware, and route registration.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import health
from app.core.config import settings
from app.middleware.error_handler import ErrorHandlerMiddleware, setup_exception_handlers

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle events.

    Handles startup and shutdown operations such as
    database connection management.

    Args:
        app: FastAPI application instance.

    Yields:
        None during application runtime.
    """
    # Startup
    logger.info("Starting Abandoned Homes Prediction API...")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    yield

    # Shutdown
    logger.info("Shutting down Abandoned Homes Prediction API...")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="Abandoned Homes Prediction API",
        description=(
            "API for predicting abandoned homes using geospatial data "
            "and machine learning. Supports location management, photo "
            "uploads, and prediction analysis."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add error handling middleware
    app.add_middleware(ErrorHandlerMiddleware)

    # Setup exception handlers
    setup_exception_handlers(app)

    # Register routers
    app.include_router(health.router)

    return app


# Create the application instance
app = create_application()
