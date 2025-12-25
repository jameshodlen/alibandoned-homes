"""Custom exception classes for the application.

This module defines application-specific exceptions that map
to appropriate HTTP status codes and error responses.
"""

from typing import Any, Dict, Optional


class AppException(Exception):
    """Base exception for all application errors.

    Attributes:
        message: Human-readable error message.
        status_code: HTTP status code to return.
        details: Additional error context.
    """

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code to return.
            details: Additional error context.
        """
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundException(AppException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize not found exception.

        Args:
            message: Human-readable error message.
            details: Additional error context.
        """
        super().__init__(message=message, status_code=404, details=details)


class ValidationException(AppException):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str = "Validation error",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize validation exception.

        Args:
            message: Human-readable error message.
            details: Additional error context.
        """
        super().__init__(message=message, status_code=422, details=details)


class DatabaseException(AppException):
    """Raised when a database operation fails."""

    def __init__(
        self,
        message: str = "Database operation failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize database exception.

        Args:
            message: Human-readable error message.
            details: Additional error context.
        """
        super().__init__(message=message, status_code=500, details=details)


class UnauthorizedException(AppException):
    """Raised when authentication is required but not provided."""

    def __init__(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize unauthorized exception.

        Args:
            message: Human-readable error message.
            details: Additional error context.
        """
        super().__init__(message=message, status_code=401, details=details)


class ForbiddenException(AppException):
    """Raised when user lacks permission for the requested action."""

    def __init__(
        self,
        message: str = "Permission denied",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize forbidden exception.

        Args:
            message: Human-readable error message.
            details: Additional error context.
        """
        super().__init__(message=message, status_code=403, details=details)
