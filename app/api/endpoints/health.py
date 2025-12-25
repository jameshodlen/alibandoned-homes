"""Health check endpoint for service monitoring.

This module provides health and readiness endpoints for
container orchestration and monitoring systems.
"""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=Dict[str, Any],
    summary="Health Check",
    description="Check if the API service is running.",
)
async def health_check() -> Dict[str, Any]:
    """Perform a basic health check.

    Returns:
        Dictionary with service status and metadata.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.APP_ENV,
        "version": "0.1.0",
    }


@router.get(
    "/health/ready",
    response_model=Dict[str, Any],
    summary="Readiness Check",
    description="Check if the service is ready to accept requests (including DB).",
)
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Perform a readiness check including database connectivity.

    Args:
        db: Async database session.

    Returns:
        Dictionary with detailed service and dependency status.
    """
    db_status = "healthy"
    db_message = "Connected"

    try:
        # Test database connection
        result = await db.execute(text("SELECT 1"))
        result.scalar()
    except Exception as e:
        db_status = "unhealthy"
        db_message = str(e)

    overall_status = "ready" if db_status == "healthy" else "not_ready"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": {
                "status": db_status,
                "message": db_message,
            },
        },
    }
