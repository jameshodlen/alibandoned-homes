"""
Database Models for Abandoned Homes Prediction Application
===========================================================

This module contains all SQLAlchemy ORM models for the application.
Each model is extensively documented to help developers understand:
- What data each table stores and why
- How PostGIS spatial types work
- Relationship patterns and foreign key behavior
- Index strategies for query performance

Table of Contents:
-----------------
1. Enums: AccessibilityLevel, ConditionLevel, PhotoType, ModelType, UserFeedback
2. ModelVersion: ML model tracking and versioning
3. Location: Properties with geographic coordinates (PostGIS Point)
4. Photo: Images associated with locations
5. Prediction: ML model predictions with spatial data
6. SearchHistory: User search patterns for analytics

PostGIS Concepts for Beginners:
------------------------------
PostGIS extends PostgreSQL with spatial types and functions. Key concepts:

**Geometry vs Geography:**
- Geometry: Uses Cartesian (flat) coordinates. Fast but distances are in degrees.
- Geography: Uses spherical coordinates. More accurate for Earth, but slower.
- We use Geometry with SRID 4326 (WGS 84) which is the GPS standard.

**SRID (Spatial Reference System ID):**
- 4326: WGS 84 - Standard GPS coordinates (longitude, latitude)
- 3857: Web Mercator - Used by web maps (Google Maps, OpenStreetMap)
- We store in 4326 and convert to 3857 for display if needed.

**Key PostGIS Functions:**
- ST_DWithin(geom1, geom2, distance): Are two geometries within distance?
- ST_Distance(geom1, geom2): Calculate distance between geometries
- ST_Contains(geom1, geom2): Does geom1 contain geom2?
- ST_MakePoint(lon, lat): Create a point from coordinates
- ST_SetSRID(geom, srid): Assign a spatial reference system

**GIST Index:**
GIST (Generalized Search Tree) is a special index type for spatial data.
It partitions space into bounding boxes for fast region queries.
Without GIST, spatial queries scan every row = O(n).
With GIST, queries use spatial partitioning = O(log n).

Example Queries:
---------------
```python
from sqlalchemy import select, func
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakePoint

# Find locations within 5km of a point (Austin, TX)
point = func.ST_SetSRID(func.ST_MakePoint(-97.7431, 30.2672), 4326)
nearby = await session.execute(
    select(Location)
    .where(ST_DWithin(Location.coordinates, point, 5000))  # 5000 meters
    .order_by(ST_Distance(Location.coordinates, point))
)

# Find all photos for a location
photos = await session.execute(
    select(Photo)
    .where(Photo.location_id == location_id)
    .order_by(Photo.created_at.desc())
)

# Get the currently active model
active_model = await session.execute(
    select(ModelVersion)
    .where(ModelVersion.model_type == ModelType.ENSEMBLE)
    .where(ModelVersion.is_active == True)
)
```
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.database.base import Base, TimestampMixin, generate_uuid


# =============================================================================
# ENUMERATION TYPES
# =============================================================================
# Python enums map to PostgreSQL ENUM types for type safety.
# This prevents invalid values at the database level, not just in Python.

class AccessibilityLevel(str, enum.Enum):
    """
    Indicates how accessible a property is for physical inspection.
    
    This is safety-critical information for field workers:
    - EASY: Safe to approach, clear access routes
    - MODERATE: Some obstacles, use caution
    - DIFFICULT: Significant barriers, may need equipment
    - DANGEROUS: Do not attempt without safety measures
    
    Why str, enum.Enum?
    ------------------
    Inheriting from str makes the enum JSON-serializable automatically.
    The values are stored as strings in PostgreSQL ("easy", "moderate", etc.)
    """
    EASY = "easy"
    MODERATE = "moderate"
    DIFFICULT = "difficult"
    DANGEROUS = "dangerous"


class ConditionLevel(str, enum.Enum):
    """
    Describes the structural condition of a property.
    
    Used for:
    - Safety assessments
    - Prioritizing which properties to investigate
    - Training ML models on condition classification
    
    Categories:
    - INTACT: Building is structurally sound
    - PARTIAL_COLLAPSE: Some structural damage visible
    - FULL_COLLAPSE: Major structural failure, unsafe
    """
    INTACT = "intact"
    PARTIAL_COLLAPSE = "partial_collapse"
    FULL_COLLAPSE = "full_collapse"


class PhotoType(str, enum.Enum):
    """
    Source/type of imagery for a property.
    
    Different image sources have different characteristics:
    - GROUND: Photos taken on-site with camera/phone. Best detail.
    - SATELLITE: Aerial imagery from satellites. Shows roof/lot.
    - STREET: Street-level imagery (like Google Street View).
    """
    GROUND = "ground"
    SATELLITE = "satellite"
    STREET = "street"


class ModelType(str, enum.Enum):
    """
    Type of ML model used for predictions.
    
    Our pipeline uses multiple model types:
    - IMAGE_CLASSIFIER: Analyzes photos to detect abandonment signs
    - LOCATION_PREDICTOR: Uses geospatial features to predict likelihood
    - ENSEMBLE: Combines multiple models for final prediction
    
    Each model type can have multiple versions over time.
    """
    IMAGE_CLASSIFIER = "image_classifier"
    LOCATION_PREDICTOR = "location_predictor"
    ENSEMBLE = "ensemble"


class UserFeedback(str, enum.Enum):
    """
    User's verification of a prediction's accuracy.
    
    This feedback loop is crucial for:
    - Measuring model accuracy in production
    - Creating training data for model retraining
    - Identifying systematic errors
    
    Values:
    - CORRECT: Prediction was accurate
    - INCORRECT: Prediction was wrong
    - UNSURE: User couldn't determine
    - NULL (not provided): User hasn't reviewed yet
    """
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNSURE = "unsure"


# =============================================================================
# MODEL VERSION TABLE
# =============================================================================
# Place this first because other models reference it via foreign keys

class ModelVersion(Base, TimestampMixin):
    """
    Tracks versions of ML models used for predictions.
    
    Why version tracking matters:
    ---------------------------
    - Reproducibility: Know which model made each prediction
    - Comparison: Compare performance across model versions
    - Rollback: Revert to previous version if new model performs worse
    - Compliance: Audit trail for model decisions
    
    Performance Metrics Explained:
    -----------------------------
    - accuracy: (correct predictions) / (total predictions)
    - precision: (true positives) / (true positives + false positives)
      "Of things we said were abandoned, how many actually were?"
    - recall: (true positives) / (true positives + false negatives)
      "Of things that were abandoned, how many did we find?"
    - f1_score: Harmonic mean of precision and recall
      Balances both metrics; useful when you care about both equally.
    
    Example: Get the active ensemble model
    -------------------------------------
    ```python
    active_model = await session.execute(
        select(ModelVersion)
        .where(ModelVersion.model_type == ModelType.ENSEMBLE)
        .where(ModelVersion.is_active == True)
    )
    model = active_model.scalar_one_or_none()
    ```
    
    Attributes:
        id: Unique identifier (UUID for distributed safety)
        version_name: Semantic version string like "v1.2.3"
        model_type: Which model pipeline this belongs to
        file_path: Where the model weights are stored
        training_date: When the model was trained
        training_samples_count: Number of training examples used
        validation_accuracy: Overall accuracy on validation set
        precision: Precision metric on validation set
        recall: Recall metric on validation set
        f1_score: F1 score on validation set
        is_active: Whether this version is currently being used
        training_config_json: Hyperparameters and settings used
        notes: Human-readable notes about this version
    """
    
    __tablename__ = "model_versions"
    
    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    # UUID vs auto-increment integer:
    # - UUID: Globally unique, can generate before INSERT, merge-friendly
    # - Integer: Smaller, faster, sequential (but predictable)
    # We use UUID because models might be trained on different machines
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),  # as_uuid=True means Python gets uuid.UUID objects
        primary_key=True,
        default=generate_uuid,
        comment="Unique identifier for this model version",
    )
    
    # -------------------------------------------------------------------------
    # Model Identification
    # -------------------------------------------------------------------------
    # Semantic versioning (v1.2.3) makes it clear what changed:
    # - Major (1.x.x): Breaking changes, retraining required
    # - Minor (x.2.x): New features, backward compatible
    # - Patch (x.x.3): Bug fixes, no new features
    version_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Semantic version identifier (e.g., v1.2.3)",
    )
    
    # See ModelType enum above for explanation
    model_type: Mapped[ModelType] = mapped_column(
        Enum(ModelType, name="model_type_enum", create_type=True),
        nullable=False,
        index=True,  # Index for fast filtering by model type
        comment="Type of model: image_classifier, location_predictor, or ensemble",
    )
    
    # Path to saved model weights (relative to model storage root)
    # Example: "/models/ensemble/v1.2.3/weights.pt"
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Path to saved model weights file",
    )
    
    # -------------------------------------------------------------------------
    # Training Metadata
    # -------------------------------------------------------------------------
    # When the model was trained (not when this record was created)
    training_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When model training completed",
    )
    
    # More training samples generally = better model (up to a point)
    training_samples_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of training examples used",
    )
    
    # -------------------------------------------------------------------------
    # Performance Metrics
    # -------------------------------------------------------------------------
    # All metrics should be between 0.0 and 1.0
    # See docstring above for metric explanations
    
    validation_accuracy: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Overall accuracy on held-out validation set (0.0 to 1.0)",
    )
    
    precision: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Precision: of positive predictions, how many were correct (0.0 to 1.0)",
    )
    
    recall: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Recall: of actual positives, how many did we find (0.0 to 1.0)",
    )
    
    f1_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="F1 score: harmonic mean of precision and recall (0.0 to 1.0)",
    )
    
    # -------------------------------------------------------------------------
    # Status and Configuration
    # -------------------------------------------------------------------------
    # Only one model of each type should be active at a time
    # This is enforced by a partial unique constraint below
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,  # Fast query for active models
        comment="Whether this model version is currently being used for predictions",
    )
    
    # Store training configuration as JSON for flexibility
    # Includes: learning_rate, batch_size, epochs, augmentation settings, etc.
    training_config_json: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Training hyperparameters and configuration as JSON",
    )
    
    # Human-readable notes about what changed in this version
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Release notes describing changes in this version",
    )
    
    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    # Link to all predictions made by this model version
    # back_populates creates a bidirectional relationship
    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction",
        back_populates="model_version",
        lazy="dynamic",  # Don't load all predictions eagerly (could be millions)
    )
    
    # -------------------------------------------------------------------------
    # Table-level Constraints
    # -------------------------------------------------------------------------
    __table_args__ = (
        # Ensure only one active model per type
        # This creates a partial unique index on model_type WHERE is_active = true
        # PostgreSQL partial unique index syntax
        Index(
            "ix_model_versions_active_type",
            "model_type",
            unique=True,
            postgresql_where=(is_active == True),
        ),
        # Add comment to the table itself
        {"comment": "Tracks ML model versions and their performance metrics"},
    )
    
    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    @validates("validation_accuracy", "precision", "recall", "f1_score")
    def validate_metrics(self, key: str, value: Optional[float]) -> Optional[float]:
        """
        Ensure all metric values are between 0.0 and 1.0.
        
        This validation runs automatically when you set these attributes,
        BEFORE the value is saved to the database.
        
        Args:
            key: Name of the attribute being validated
            value: The value being assigned
            
        Returns:
            The validated value (unchanged if valid)
            
        Raises:
            ValueError: If value is outside [0.0, 1.0] range
        """
        if value is not None and (value < 0.0 or value > 1.0):
            raise ValueError(f"{key} must be between 0.0 and 1.0, got {value}")
        return value
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        status = "ACTIVE" if self.is_active else "inactive"
        return f"<ModelVersion({self.version_name}, {self.model_type.value}, {status})>"


# =============================================================================
# LOCATION TABLE
# =============================================================================

class Location(Base, TimestampMixin):
    """
    Represents a property location that may be abandoned.
    
    This is the central table of the application. Each location represents
    a real-world property with geographic coordinates stored as a PostGIS
    Point geometry.
    
    Coordinate System:
    -----------------
    We use SRID 4326 (WGS 84), the standard GPS coordinate system:
    - Longitude: -180 to +180 (negative = West, positive = East)
    - Latitude: -90 to +90 (negative = South, positive = North)
    - Example: Austin, TX = (-97.7431, 30.2672)
    
    Why PostGIS Geometry (not Geography)?
    -------------------------------------
    - Geometry: Cartesian math, faster, but distances are in the SRID's units
    - Geography: Spherical math, slower, but distances are in meters
    - For city-scale queries (< 100km), Geometry is accurate enough and faster
    - We use Geometry with ST_DWithin which uses meters for 4326
    
    Confirmed vs Predicted:
    ----------------------
    - confirmed=True: User has verified this is actually abandoned
    - confirmed=False: ML model predicted this, pending verification
    - confidence_score: Only meaningful for predicted (unconfirmed) locations
    
    Example: Insert a new location
    -----------------------------
    ```python
    from geoalchemy2.functions import ST_SetSRID, ST_MakePoint
    
    location = Location(
        id=uuid.uuid4(),
        # ST_MakePoint takes (longitude, latitude) - note the order!
        coordinates=func.ST_SetSRID(func.ST_MakePoint(-97.7431, 30.2672), 4326),
        address="123 Main St, Austin, TX 78701",
        confirmed=True,
        accessibility=AccessibilityLevel.EASY,
        condition=ConditionLevel.INTACT,
    )
    session.add(location)
    await session.commit()
    ```
    
    Example: Find locations within 10km of a point
    ----------------------------------------------
    ```python
    from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
    
    center = func.ST_SetSRID(func.ST_MakePoint(-97.7431, 30.2672), 4326)
    result = await session.execute(
        select(Location)
        .where(ST_DWithin(
            Location.coordinates,
            center,
            10000  # 10,000 meters = 10km
        ))
    )
    nearby_locations = result.scalars().all()
    ```
    """
    
    __tablename__ = "locations"
    
    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
        comment="Unique identifier for this location",
    )
    
    # -------------------------------------------------------------------------
    # Geographic Data
    # -------------------------------------------------------------------------
    # PostGIS Point geometry for storing GPS coordinates
    # SRID 4326 = WGS 84 (standard GPS coordinate system)
    # 
    # Why nullable=False?
    # Every location MUST have coordinates - it's the fundamental data point.
    # If we don't know where something is, we can't use it.
    coordinates: Mapped[Any] = mapped_column(
        Geometry(
            geometry_type="POINT",  # Only allow Point geometry, not lines/polygons
            srid=4326,  # WGS 84 - standard GPS coordinates
            spatial_index=False,  # We create our own GIST index below
        ),
        nullable=False,
        comment="GPS coordinates as PostGIS Point (SRID 4326: longitude, latitude)",
    )
    
    # -------------------------------------------------------------------------
    # Address Information
    # -------------------------------------------------------------------------
    # Address is nullable because we might find abandoned properties via
    # satellite imagery before we know the address
    address: Mapped[Optional[str]] = mapped_column(
        String(500),  # Street addresses can be long in some countries
        nullable=True,
        comment="Street address (nullable: may be unknown initially)",
    )
    
    # -------------------------------------------------------------------------
    # Temporal Data
    # -------------------------------------------------------------------------
    # date_added is handled by TimestampMixin.created_at
    
    # When the abandonment was first observed (may differ from when we added it)
    # Example: Photo taken 2 months ago, added to system today
    date_discovered: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),  # Always store with timezone for accuracy
        nullable=True,
        comment="When abandonment was first observed (vs. when record was created)",
    )
    
    # -------------------------------------------------------------------------
    # Verification Status
    # -------------------------------------------------------------------------
    # Has a human confirmed this is actually abandoned?
    # False = ML prediction only, True = human verified
    confirmed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,  # Often filter by confirmed/unconfirmed
        comment="True if human-verified; False if only ML-predicted",
    )
    
    # ML model's confidence in its prediction
    # Only meaningful for confirmed=False (predicted) locations
    # Range: 0.0 (no confidence) to 1.0 (complete confidence)
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,  # NULL for human-submitted locations
        comment="ML confidence score (0.0-1.0); NULL if human-submitted",
    )
    
    # -------------------------------------------------------------------------
    # Property Assessment
    # -------------------------------------------------------------------------
    # Safety information for field workers
    accessibility: Mapped[Optional[AccessibilityLevel]] = mapped_column(
        Enum(AccessibilityLevel, name="accessibility_level_enum", create_type=True),
        nullable=True,
        comment="Physical accessibility for field inspection",
    )
    
    # Structural condition assessment
    condition: Mapped[Optional[ConditionLevel]] = mapped_column(
        Enum(ConditionLevel, name="condition_level_enum", create_type=True),
        nullable=True,
        comment="Structural condition of the building",
    )
    
    # Free-form notes from investigators
    notes: Mapped[Optional[str]] = mapped_column(
        Text,  # Text allows unlimited length (vs String with max length)
        nullable=True,
        comment="User observations and notes about the property",
    )
    
    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    # One location can have many photos
    # cascade="all, delete-orphan" means:
    # - "all": Changes to location propagate to photos
    # - "delete-orphan": Photos without a location are automatically deleted
    # This ensures we don't have orphaned photos in the database
    photos: Mapped[List["Photo"]] = relationship(
        "Photo",
        back_populates="location",
        cascade="all, delete-orphan",  # Delete photos when location is deleted
        lazy="selectin",  # Load photos efficiently when accessing location.photos
    )
    
    # Link to prediction that might have created this location
    # A prediction can be verified and become a confirmed location
    verified_from_predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction",
        back_populates="verified_location",
        lazy="dynamic",
    )
    
    # -------------------------------------------------------------------------
    # Table-level Configuration
    # -------------------------------------------------------------------------
    __table_args__ = (
        # GIST index for spatial queries (see docstring for explanation)
        # This is CRITICAL for performance - without it, every spatial query
        # would scan every row in the table
        Index(
            "ix_locations_coordinates_gist",
            "coordinates",
            postgresql_using="gist",  # GIST is the index type for spatial data
        ),
        # Check constraint to ensure confidence_score is in valid range
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="ck_locations_confidence_score_range",
        ),
        {"comment": "Properties that may be abandoned, with GPS coordinates"},
    )
    
    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    @validates("confidence_score")
    def validate_confidence_score(
        self, key: str, value: Optional[float]
    ) -> Optional[float]:
        """Ensure confidence_score is between 0 and 1 if provided."""
        if value is not None and (value < 0.0 or value > 1.0):
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0, got {value}"
            )
        return value
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        status = "confirmed" if self.confirmed else "predicted"
        return f"<Location({self.id!s:.8}..., {status})>"


# =============================================================================
# PHOTO TABLE
# =============================================================================

class Photo(Base):
    """
    Stores images associated with property locations.
    
    Photo Privacy & Security:
    ------------------------
    Photos can contain sensitive EXIF metadata, especially GPS coordinates.
    We handle this by:
    1. stripped_metadata_json: Safe metadata (camera model, dimensions) in plain JSON
    2. original_metadata_encrypted: Original EXIF encrypted with a key
    3. encryption_key_id: Which key was used (for key rotation)
    
    This allows us to use safe metadata for ML training while protecting
    location data from unauthorized access.
    
    Storage Architecture:
    --------------------
    - file_path: Path relative to storage root ("/uploads/2024/01/abc123.jpg")
    - thumbnail_path: Smaller version for fast loading in UI
    - Actual files stored in cloud storage (S3, GCS) or local filesystem
    
    Example: Get all photos for a location
    --------------------------------------
    ```python
    photos = await session.execute(
        select(Photo)
        .where(Photo.location_id == location_id)
        .order_by(Photo.taken_at.desc())  # Most recent first
    )
    ```
    
    Example: Count photos by type
    ----------------------------
    ```python
    from sqlalchemy import func as sqlfunc
    
    counts = await session.execute(
        select(Photo.photo_type, sqlfunc.count(Photo.id))
        .group_by(Photo.photo_type)
    )
    ```
    """
    
    __tablename__ = "photos"
    
    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
        comment="Unique identifier for this photo",
    )
    
    # -------------------------------------------------------------------------
    # Location Relationship
    # -------------------------------------------------------------------------
    # Foreign key to the location this photo belongs to
    # ondelete="CASCADE": When location is deleted, delete this photo too
    # This maintains referential integrity - no orphaned photos
    location_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # Fast lookup of photos by location
        comment="Location this photo is associated with",
    )
    
    # -------------------------------------------------------------------------
    # File Storage
    # -------------------------------------------------------------------------
    # Path relative to storage root (not absolute path)
    # Example: "/2024/01/15/abc123def456.jpg"
    # Using relative path allows moving storage without updating DB
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Relative path to original image file from storage root",
    )
    
    # Thumbnails are smaller versions for fast loading in UI
    # Generated automatically when original is uploaded
    # Example: "/2024/01/15/abc123def456_thumb.jpg"
    thumbnail_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Relative path to thumbnail version (smaller, faster to load)",
    )
    
    # -------------------------------------------------------------------------
    # Photo Classification
    # -------------------------------------------------------------------------
    # See PhotoType enum for explanation of each type
    photo_type: Mapped[PhotoType] = mapped_column(
        Enum(PhotoType, name="photo_type_enum", create_type=True),
        nullable=False,
        default=PhotoType.GROUND,
        index=True,  # Often filter by photo type
        comment="Source of image: ground, satellite, or street",
    )
    
    # -------------------------------------------------------------------------
    # Metadata Storage
    # -------------------------------------------------------------------------
    # Safe metadata that doesn't contain sensitive information
    # Examples: camera model, lens info, ISO, shutter speed
    # Stored as JSON for flexibility (schema-less)
    stripped_metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Non-sensitive EXIF metadata (camera model, etc.) as JSON",
    )
    
    # Encrypted original EXIF data including GPS coordinates
    # Binary because encryption produces raw bytes
    # Only decrypt when authorized user needs the full metadata
    original_metadata_encrypted: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary,  # For storing binary data (encrypted bytes)
        nullable=True,
        comment="Encrypted original EXIF data (may contain sensitive GPS)",
    )
    
    # Which encryption key was used (for key rotation)
    # When we rotate keys, we know which photos use old keys
    encryption_key_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="ID of encryption key used (for key rotation support)",
    )
    
    # -------------------------------------------------------------------------
    # Image Dimensions
    # -------------------------------------------------------------------------
    # File size helps with:
    # - Storage quota calculations
    # - Detecting corrupted uploads (size mismatch)
    # - Filtering large files for bandwidth-constrained situations
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="File size in bytes",
    )
    
    # Image dimensions help with:
    # - Aspect ratio calculations for UI display
    # - Identifying thumbnail vs full resolution
    # - ML model input preprocessing
    width: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Image width in pixels",
    )
    
    height: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Image height in pixels",
    )
    
    # -------------------------------------------------------------------------
    # Temporal Data
    # -------------------------------------------------------------------------
    # When the photo was actually taken (from EXIF or user-provided)
    # Different from created_at which is when record was added to DB
    taken_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When photo was taken (from EXIF); differs from record creation time",
    )
    
    # When this record was created (from Base or explicit)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this record was created in the database",
    )
    
    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    # Back-reference to the parent location
    location: Mapped["Location"] = relationship(
        "Location",
        back_populates="photos",
    )
    
    # -------------------------------------------------------------------------
    # Table-level Configuration
    # -------------------------------------------------------------------------
    __table_args__ = (
        # Composite index for common query pattern:
        # "Get all photos of type X for location Y"
        Index(
            "ix_photos_location_type",
            "location_id",
            "photo_type",
        ),
        {"comment": "Images associated with property locations"},
    )
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"<Photo({self.id!s:.8}..., {self.photo_type.value})>"


# =============================================================================
# PREDICTION TABLE
# =============================================================================

class Prediction(Base):
    """
    ML model predictions for potential abandoned properties.
    
    This table stores the output of our ML pipeline:
    1. Model analyzes an area and generates predictions
    2. Each prediction has coordinates, confidence, and reasoning
    3. Users can provide feedback (correct/incorrect/unsure)
    4. If user confirms, a Location record is created and linked
    
    Feature Scores:
    --------------
    The model considers multiple factors. feature_scores_json might contain:
    {
        "vegetation_overgrowth": 0.85,
        "roof_damage": 0.72,
        "broken_windows": 0.60,
        "no_vehicles": 0.90,
        "mail_accumulation": 0.65
    }
    
    Search Area:
    -----------
    When users search a region, we store the geometry (polygon) they searched.
    This helps us:
    - Avoid re-analyzing the same area
    - Track which areas have been analyzed
    - Measure coverage of our analysis
    
    Example: Create a prediction
    ---------------------------
    ```python
    prediction = Prediction(
        id=uuid.uuid4(),
        coordinates=func.ST_SetSRID(func.ST_MakePoint(-97.7431, 30.2672), 4326),
        confidence_score=0.85,
        model_version_id=active_model.id,
        feature_scores_json={
            "vegetation_overgrowth": 0.85,
            "roof_damage": 0.72,
        },
        reasoning="High vegetation overgrowth and visible roof damage detected.",
    )
    ```
    """
    
    __tablename__ = "predictions"
    
    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
        comment="Unique identifier for this prediction",
    )
    
    # -------------------------------------------------------------------------
    # Geographic Data
    # -------------------------------------------------------------------------
    # Predicted coordinates of the potentially abandoned property
    coordinates: Mapped[Any] = mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=4326,
            spatial_index=False,  # Custom GIST index below
        ),
        nullable=False,
        comment="Predicted GPS coordinates (PostGIS Point, SRID 4326)",
    )
    
    # The polygon representing the area that was searched
    # This could be a user-drawn polygon or a circle converted to polygon
    # Useful for tracking which areas have been analyzed
    search_area_geometry: Mapped[Optional[Any]] = mapped_column(
        Geometry(
            geometry_type="POLYGON",  # Polygon, not point
            srid=4326,
            spatial_index=False,
        ),
        nullable=True,
        comment="The search area that contained this prediction (PostGIS Polygon)",
    )
    
    # -------------------------------------------------------------------------
    # Model Information
    # -------------------------------------------------------------------------
    # Ensemble model's final confidence (weighted combination of all models)
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Overall confidence score from ensemble model (0.0 to 1.0)",
    )
    
    # Which model version made this prediction
    # Critical for reproducibility and model performance tracking
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,  # Allow NULL if model is deleted
        index=True,
        comment="Model version that generated this prediction",
    )
    
    # Breakdown of individual feature scores
    # JSON allows flexible schema as model architecture evolves
    feature_scores_json: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Individual feature scores from model analysis (JSON)",
    )
    
    # Human-readable explanation of why model made this prediction
    # Example: "Detected significant vegetation overgrowth and visible roof damage"
    reasoning: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable explanation of prediction factors",
    )
    
    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this prediction was generated",
    )
    
    # -------------------------------------------------------------------------
    # User Feedback Loop
    # -------------------------------------------------------------------------
    # User's assessment of prediction accuracy
    # NULL means user hasn't reviewed yet
    user_feedback: Mapped[Optional[UserFeedback]] = mapped_column(
        Enum(UserFeedback, name="user_feedback_enum", create_type=True),
        nullable=True,
        index=True,  # Often filter by feedback status
        comment="User's verification: correct, incorrect, or unsure (NULL = not reviewed)",
    )
    
    # Additional notes from user about why they marked it as they did
    user_feedback_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User's notes explaining their feedback",
    )
    
    # When user provided their feedback
    feedback_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when user provided feedback",
    )
    
    # -------------------------------------------------------------------------
    # Verification Link
    # -------------------------------------------------------------------------
    # If user confirms prediction, they create a Location and link it here
    # This closes the loop: prediction -> user confirms -> location created
    verified_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        comment="If user confirmed and created a location, link to it here",
    )
    
    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    model_version: Mapped[Optional["ModelVersion"]] = relationship(
        "ModelVersion",
        back_populates="predictions",
    )
    
    verified_location: Mapped[Optional["Location"]] = relationship(
        "Location",
        back_populates="verified_from_predictions",
    )
    
    # -------------------------------------------------------------------------
    # Table-level Configuration
    # -------------------------------------------------------------------------
    __table_args__ = (
        # GIST index for spatial queries on predicted coordinates
        Index(
            "ix_predictions_coordinates_gist",
            "coordinates",
            postgresql_using="gist",
        ),
        # Composite index for model performance analysis
        # "How did model version X perform for high-confidence predictions?"
        Index(
            "ix_predictions_model_confidence",
            "model_version_id",
            "confidence_score",
        ),
        # Constraint to ensure confidence_score is valid
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_predictions_confidence_score_range",
        ),
        {"comment": "ML model predictions for potential abandoned properties"},
    )
    
    @validates("confidence_score")
    def validate_confidence_score(self, key: str, value: float) -> float:
        """Ensure confidence_score is between 0 and 1."""
        if value < 0.0 or value > 1.0:
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0, got {value}"
            )
        return value
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        feedback = self.user_feedback.value if self.user_feedback else "unreviewed"
        return f"<Prediction({self.id!s:.8}..., conf={self.confidence_score:.2f}, {feedback})>"


# =============================================================================
# SEARCH HISTORY TABLE
# =============================================================================

class SearchHistory(Base):
    """
    Tracks user search patterns for analytics and UX optimization.
    
    Why track search history?
    ------------------------
    1. Analytics: Understand which areas users are interested in
    2. Coverage: Track which geographic areas have been analyzed
    3. UX: Show recent searches, suggest similar areas
    4. Performance: Avoid re-analyzing recently searched areas
    
    Search Types:
    ------------
    - Radius-based: User picks a center point and distance (e.g., 5km around address)
    - Polygon: User draws a custom shape on the map
    
    For radius searches:
    - search_center: The center point (user's location or search address)
    - radius_meters: The search radius in meters
    - search_area: Still stored as polygon (circle approximation)
    
    For polygon searches:
    - search_center: Centroid of the polygon (for quick lookups)
    - radius_meters: NULL (not applicable)
    - search_area: The actual polygon the user drew
    
    Example: Record a search
    -----------------------
    ```python
    search = SearchHistory(
        id=uuid.uuid4(),
        search_center=func.ST_SetSRID(func.ST_MakePoint(-97.7431, 30.2672), 4326),
        radius_meters=5000,  # 5km
        search_area=func.ST_Buffer(
            func.ST_SetSRID(func.ST_MakePoint(-97.7431, 30.2672), 4326),
            5000  # ST_Buffer creates polygon from point + distance
        ),
        filters_json={"min_confidence": 0.7, "include_confirmed": False},
        results_count=42,
    )
    ```
    """
    
    __tablename__ = "search_history"
    
    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
        comment="Unique identifier for this search record",
    )
    
    # -------------------------------------------------------------------------
    # Geographic Data
    # -------------------------------------------------------------------------
    # Center point of the search (for radius searches or polygon centroid)
    search_center: Mapped[Optional[Any]] = mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=4326,
            spatial_index=False,
        ),
        nullable=True,
        comment="Center point of search (for radius) or centroid (for polygon)",
    )
    
    # The actual area that was searched
    # For radius search: circle converted to polygon
    # For drawn search: the exact polygon the user drew
    search_area: Mapped[Any] = mapped_column(
        Geometry(
            geometry_type="POLYGON",
            srid=4326,
            spatial_index=False,  # Custom GIST index below
        ),
        nullable=False,
        comment="Actual search area as PostGIS Polygon",
    )
    
    # For radius-based searches, the radius used
    # NULL for polygon-based (user-drawn) searches
    radius_meters: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Search radius in meters (NULL for polygon-based searches)",
    )
    
    # -------------------------------------------------------------------------
    # Search Parameters
    # -------------------------------------------------------------------------
    # Any filters the user applied, stored as JSON for flexibility
    # Examples: min_confidence, max_confidence, photo_required, etc.
    filters_json: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Search filters applied (confidence threshold, etc.) as JSON",
    )
    
    # -------------------------------------------------------------------------
    # Results
    # -------------------------------------------------------------------------
    # How many predictions were returned for this search
    # Useful for understanding search effectiveness
    results_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of predictions returned by this search",
    )
    
    # -------------------------------------------------------------------------
    # Timestamp
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this search was performed",
    )
    
    # -------------------------------------------------------------------------
    # Table-level Configuration
    # -------------------------------------------------------------------------
    __table_args__ = (
        # GIST index for spatial queries
        # Useful for: "Find overlapping searches" or "Has this area been searched?"
        Index(
            "ix_search_history_area_gist",
            "search_area",
            postgresql_using="gist",
        ),
        {"comment": "User search history for analytics and coverage tracking"},
    )
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        search_type = f"{self.radius_meters}m radius" if self.radius_meters else "polygon"
        return f"<SearchHistory({self.id!s:.8}..., {search_type}, {self.results_count} results)>"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
# These functions provide convenient ways to perform common spatial queries

async def get_nearby_locations(
    session,  # AsyncSession
    longitude: float,
    latitude: float,
    radius_meters: int = 5000,
    confirmed_only: bool = False,
) -> List[Location]:
    """
    Find locations within a radius of a point.
    
    This function demonstrates how to use PostGIS spatial queries
    with SQLAlchemy. It uses:
    - ST_MakePoint: Creates a point geometry from coordinates
    - ST_SetSRID: Assigns the coordinate system (4326 = GPS)
    - ST_DWithin: Tests if geometries are within a distance
    - ST_Distance: Calculates distance for ordering
    
    Why ST_DWithin instead of ST_Distance < X?
    ------------------------------------------
    ST_DWithin can use the GIST spatial index, making it O(log n).
    ST_Distance < X cannot use the index, making it O(n).
    For large tables, this is the difference between 10ms and 10 seconds.
    
    Args:
        session: SQLAlchemy async session
        longitude: Longitude (-180 to 180, negative = West)
        latitude: Latitude (-90 to 90, negative = South)
        radius_meters: Search radius in meters (default 5km)
        confirmed_only: If True, only return human-verified locations
        
    Returns:
        List of Location objects within the radius, ordered by distance
        
    Example:
    -------
    ```python
    from backend.database.models import get_nearby_locations
    from backend.database.base import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # Find confirmed locations within 10km of Austin, TX
        nearby = await get_nearby_locations(
            session,
            longitude=-97.7431,
            latitude=30.2672,
            radius_meters=10000,
            confirmed_only=True,
        )
        for loc in nearby:
            print(f"Location: {loc.address}")
    ```
    """
    from sqlalchemy import select
    from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakePoint, ST_SetSRID
    
    # Create a point geometry from the input coordinates
    # ST_MakePoint takes (longitude, latitude) - note the order!
    # ST_SetSRID assigns SRID 4326 (WGS 84 / GPS coordinates)
    point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    
    # Build the query
    query = select(Location).where(
        # ST_DWithin checks if geometries are within distance
        # Uses the GIST index for O(log n) performance
        ST_DWithin(Location.coordinates, point, radius_meters)
    )
    
    # Optionally filter to confirmed locations only
    if confirmed_only:
        query = query.where(Location.confirmed == True)
    
    # Order by distance (closest first)
    # ST_Distance calculates the distance between geometries
    query = query.order_by(ST_Distance(Location.coordinates, point))
    
    # Execute and return results
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_active_model_version(
    session,  # AsyncSession
    model_type: ModelType,
) -> Optional[ModelVersion]:
    """
    Get the currently active model version for a given type.
    
    Each model type (image_classifier, location_predictor, ensemble)
    has exactly one active version at a time. This is enforced by
    the unique constraint on (model_type) WHERE is_active = true.
    
    Args:
        session: SQLAlchemy async session
        model_type: Which type of model to get
        
    Returns:
        The active ModelVersion, or None if none is active
        
    Example:
    -------
    ```python
    active_ensemble = await get_active_model_version(
        session,
        ModelType.ENSEMBLE
    )
    if active_ensemble:
        print(f"Using model: {active_ensemble.version_name}")
    ```
    """
    from sqlalchemy import select
    
    result = await session.execute(
        select(ModelVersion)
        .where(ModelVersion.model_type == model_type)
        .where(ModelVersion.is_active == True)
    )
    return result.scalar_one_or_none()
