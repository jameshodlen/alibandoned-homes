"""SQLAlchemy declarative base and common mixins.

This module provides the base class for all database models
along with reusable mixins for common patterns.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Provides a common foundation for model definitions with
    automatic table name generation and repr.
    """

    def __repr__(self) -> str:
        """Generate string representation of the model instance.

        Returns:
            String with class name and primary key values.
        """
        pk_cols = [col.name for col in self.__table__.primary_key.columns]
        pk_values = ", ".join(f"{col}={getattr(self, col, None)}" for col in pk_cols)
        return f"<{self.__class__.__name__}({pk_values})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary.

        Returns:
            Dictionary of column names to values.
        """
        return {col.name: getattr(self, col.name) for col in self.__table__.columns}


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps.

    Attributes:
        created_at: Timestamp when record was created.
        updated_at: Timestamp when record was last updated.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
