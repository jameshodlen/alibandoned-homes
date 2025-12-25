"""Prediction model for storing abandonment analysis results.

This module defines the Prediction model which stores the
results of the ML model's abandonment predictions.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.location import Location


class Prediction(Base, TimestampMixin):
    """Represents an abandonment prediction for a property.

    Stores the prediction score, confidence level, and model
    metadata for each analysis run.

    Attributes:
        id: Primary key identifier.
        location_id: Foreign key to the associated location.
        abandoned_score: Probability score (0.0 to 1.0) indicating
            likelihood of abandonment.
        confidence: Model confidence in the prediction (0.0 to 1.0).
        model_version: Version identifier of the ML model used.
        prediction_date: Timestamp when prediction was made.
        notes: Optional analysis notes or explanations.
        location: Related Location model.
    """

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    abandoned_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Probability of abandonment (0.0 to 1.0)",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Model confidence level (0.0 to 1.0)",
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="ML model version identifier",
    )
    prediction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    location: Mapped["Location"] = relationship(
        "Location",
        back_populates="predictions",
    )
