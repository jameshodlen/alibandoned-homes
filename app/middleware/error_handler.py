"""Global error handling middleware.

This module provides centralized exception handling with
structured JSON responses and request tracking.
"""

import logging
import traceback
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for catching and formatting all exceptions.

    Converts exceptions to structured JSON responses with
    request IDs for debugging and correlation.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and handle any exceptions.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            Response from handler or error response.
        """
        # Generate unique request ID for tracing
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        except AppException as exc:
            # Handle application-specific exceptions
            logger.warning(
                f"Application error: {exc.message}",
                extra={
                    "request_id": request_id,
                    "status_code": exc.status_code,
                    "details": exc.details,
                },
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.message,
                    "details": exc.details,
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )

        except Exception as exc:
            # Handle unexpected exceptions
            logger.error(
                f"Unhandled exception: {str(exc)}",
                extra={
                    "request_id": request_id,
                    "traceback": traceback.format_exc(),
                },
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )


def setup_exception_handlers(app: FastAPI) -> None:
    """Configure global exception handlers for the FastAPI app.

    Args:
        app: FastAPI application instance.
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        """Handle AppException with structured response.

        Args:
            request: Incoming HTTP request.
            exc: Application exception instance.

        Returns:
            JSON response with error details.
        """
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "details": exc.details,
                "request_id": request_id,
            },
        )
