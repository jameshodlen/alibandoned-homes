"""Location model with PostGIS geometry support.

This module defines the Location model which stores geographic
coordinates using PostGIS Point geometry for spatial queries.
"""

from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Location(Base, TimestampMixin):
    """Represents a property location with geographic coordinates.

    Uses PostGIS Point geometry (SRID 4326 / WGS 84) for storing
    latitude/longitude coordinates, enabling spatial queries like
    distance calculations and radius searches.

    Attributes:
        id: Primary key identifier.
        address: Street address of the property.
        city: City name.
        state: State abbreviation (e.g., 'TX', 'CA').
        zip_code: ZIP/postal code.
        geom: PostGIS Point geometry (longitude, latitude).
        photos: Related photo records.
        predictions: Related prediction records.
    """

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)

    # PostGIS Point geometry (SRID 4326 = WGS 84 / GPS coordinates)
    geom: Mapped[Optional[str]] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=True,
    )

    # Relationships
    photos: Mapped[list["Photo"]] = relationship(
        "Photo",
        back_populates="location",
        cascade="all, delete-orphan",
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction",
        back_populates="location",
        cascade="all, delete-orphan",
    )


# Import related models for relationship resolution
from app.models.photo import Photo  # noqa: E402
from app.models.prediction import Prediction  # noqa: E402
