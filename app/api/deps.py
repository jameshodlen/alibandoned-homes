"""Dependency injection utilities for API endpoints.

This module provides common dependencies used across API routes,
such as database sessions and pagination parameters.
"""

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db

# Type alias for database session dependency
DBSession = Annotated[AsyncSession, Depends(get_db)]


class PaginationParams:
    """Common pagination parameters for list endpoints.

    Attributes:
        skip: Number of records to skip (offset).
        limit: Maximum number of records to return.
    """

    def __init__(
        self,
        skip: Annotated[int, Query(ge=0, description="Records to skip")] = 0,
        limit: Annotated[
            int, Query(ge=1, le=100, description="Max records to return")
        ] = 20,
    ) -> None:
        """Initialize pagination parameters.

        Args:
            skip: Number of records to skip (default: 0).
            limit: Maximum number of records to return (default: 20, max: 100).
        """
        self.skip = skip
        self.limit = limit


# Type alias for pagination dependency
Pagination = Annotated[PaginationParams, Depends()]
