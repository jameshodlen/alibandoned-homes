"""Photo model for storing property images.

This module defines the Photo model which stores references
to images associated with property locations.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.location import Location


class Photo(Base, TimestampMixin):
    """Represents a photo associated with a property location.

    Stores metadata and storage paths for property images used
    in the abandonment prediction process.

    Attributes:
        id: Primary key identifier.
        location_id: Foreign key to the associated location.
        url: Public URL of the photo (if hosted externally).
        storage_path: Local/cloud storage path for the file.
        caption: Optional description of the photo.
        location: Related Location model.
    """

    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    location: Mapped["Location"] = relationship(
        "Location",
        back_populates="photos",
    )
