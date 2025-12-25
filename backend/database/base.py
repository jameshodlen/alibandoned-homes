"""
Database Base Configuration and Session Management
===================================================

This module provides the foundational infrastructure for all database models:

1. **DeclarativeBase**: The SQLAlchemy base class that all models inherit from
2. **TimestampMixin**: Automatic created_at/updated_at fields for auditing
3. **Async Session Management**: Connection pooling and session lifecycle

Key Concepts for New Developers:
-------------------------------
- SQLAlchemy uses the "Data Mapper" pattern where Python classes map to database tables
- We use SQLAlchemy 2.0's new async API for non-blocking I/O (important for FastAPI)
- The session is a "unit of work" that tracks changes and commits them as a transaction

PostGIS Notes:
--------------
PostGIS extends PostgreSQL with spatial capabilities. Before using PostGIS types,
the extension must be enabled: `CREATE EXTENSION IF NOT EXISTS postgis;`
This is handled in init_db.py.

Example Usage:
--------------
```python
from backend.database.base import AsyncSessionLocal, Base

# Create all tables (use Alembic migrations for production)
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

# Use a session for database operations
async def create_location(location_data: dict):
    async with AsyncSessionLocal() as session:
        location = Location(**location_data)
        session.add(location)
        await session.commit()
        await session.refresh(location)
        return location
```
"""

import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# =============================================================================
# DATABASE CONNECTION CONFIGURATION
# =============================================================================

# NOTE: In production, load this from environment variables (pydantic-settings)
# The 'postgresql+asyncpg://' scheme uses the async driver for non-blocking I/O
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/abandoned_homes"

# Create the async engine with connection pooling
# ---------------------------------------------
# pool_pre_ping=True: Test connections before using them (handles dropped connections)
# pool_size=5: Keep 5 connections open in the pool
# max_overflow=10: Allow up to 15 total connections (5 pool + 10 overflow)
# echo=True: Log all SQL statements (set to False in production for performance)
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_pre_ping=True,  # Test connections before using
    pool_size=5,  # Base pool size
    max_overflow=10,  # Additional connections allowed
)

# Session factory for creating async sessions
# ------------------------------------------
# expire_on_commit=False: Keep data accessible after commit (important for returning created objects)
# autocommit=False: Explicit transaction management (you must call commit())
# autoflush=False: Don't automatically write to DB before queries (gives you more control)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep attributes accessible after commit
    autocommit=False,  # Manual transaction management
    autoflush=False,  # Explicit flush control
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async database session as a dependency.
    
    This is designed to be used with FastAPI's Depends():
    
    ```python
    from fastapi import Depends
    from backend.database.base import get_async_session
    
    @router.get("/locations")
    async def list_locations(db: AsyncSession = Depends(get_async_session)):
        result = await db.execute(select(Location))
        return result.scalars().all()
    ```
    
    Why use a generator?
    -------------------
    The generator pattern ensures proper cleanup:
    1. Session is created when the request starts
    2. Session is yielded to your endpoint code
    3. After your code completes, the finally block runs
    4. Commit on success, rollback on exception, always close
    
    Yields:
        AsyncSession: A SQLAlchemy async session for database operations.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # If we reach here without exception, commit the transaction
            await session.commit()
        except Exception:
            # On any exception, rollback all changes in this transaction
            await session.rollback()
            raise
        finally:
            # Always close the session (returns connection to pool)
            await session.close()


# =============================================================================
# DECLARATIVE BASE CLASS
# =============================================================================

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    
    Why use a custom base class?
    ---------------------------
    1. Centralized configuration: Type annotations, naming conventions
    2. Common methods: __repr__, to_dict available on all models  
    3. Metadata access: Base.metadata contains all table definitions
    
    SQLAlchemy 2.0 Notes:
    --------------------
    In SQLAlchemy 2.0, we use `mapped_column()` instead of `Column()`,
    and `Mapped[type]` for type hints. This provides better IDE support
    and static type checking.
    
    Example:
    -------
    ```python
    class Location(Base):
        __tablename__ = "locations"
        
        # mapped_column() with Mapped[] for modern SQLAlchemy 2.0 syntax
        id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
        address: Mapped[str] = mapped_column(String(255), nullable=True)
    ```
    """
    
    def __repr__(self) -> str:
        """
        Generate a developer-friendly string representation.
        
        This helps when debugging by showing the class name and primary key.
        For example: <Location(id=123e4567-e89b-12d3-a456-426614174000)>
        
        Returns:
            str: Formatted string like <ClassName(pk_col=value)>
        """
        # Get all primary key columns for this model
        pk_columns = [col.name for col in self.__table__.primary_key.columns]
        # Build "col=value" strings for each primary key
        pk_values = ", ".join(
            f"{col}={getattr(self, col, None)}" for col in pk_columns
        )
        return f"<{self.__class__.__name__}({pk_values})>"
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert model instance to a dictionary.
        
        Useful for:
        - Serializing to JSON for API responses
        - Debugging and logging
        - Passing to Pydantic models
        
        Note: This is a simple implementation. For complex objects with
        relationships or special types (like PostGIS geometry), you may
        need custom serialization logic.
        
        Returns:
            dict: Column names mapped to their values.
        """
        return {
            column.name: getattr(self, column.name) 
            for column in self.__table__.columns
        }


# =============================================================================
# TIMESTAMP MIXIN
# =============================================================================

class TimestampMixin:
    """
    Mixin that adds automatic created_at and updated_at timestamps.
    
    Why use a mixin?
    ---------------
    Mixins let us share columns across multiple models without inheritance.
    Many tables need timestamps, so we define them once and mix them in.
    
    How auto-updating works:
    -----------------------
    - created_at: Set by the database server when row is inserted
    - updated_at: Set on insert AND automatically updated on every UPDATE
    
    Using server_default vs default:
    --------------------------------
    - server_default=func.now(): Executed by PostgreSQL, not Python
      This is more reliable because it uses the database server's clock
    - default=datetime.utcnow: Executed by Python before INSERT
      Could cause issues if app server and db server have different times
    
    Timezone awareness:
    ------------------
    We use DateTime(timezone=True) to store timezone-aware datetimes.
    PostgreSQL stores these in UTC internally, then converts to your
    session's timezone on retrieval. This is crucial for:
    - Multi-region applications
    - Correct time comparisons
    - Audit trails
    
    Example usage:
    -------------
    ```python
    class Location(Base, TimestampMixin):
        __tablename__ = "locations"
        id: Mapped[int] = mapped_column(primary_key=True)
        # created_at and updated_at are automatically available!
    ```
    """
    
    # Timestamp when the record was first created
    # server_default=func.now() runs NOW() on PostgreSQL server
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),  # Store with timezone info (UTC)
        server_default=func.now(),  # Database sets this on INSERT
        nullable=False,
        comment="Timestamp when this record was created (auto-set by database)",
    )
    
    # Timestamp when the record was last updated
    # onupdate=func.now() automatically updates on every UPDATE
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),  # Store with timezone info (UTC)
        server_default=func.now(),  # Set on INSERT
        onupdate=func.now(),  # Also set on every UPDATE
        nullable=False,
        comment="Timestamp when this record was last modified (auto-updated)",
    )


# =============================================================================
# UUID GENERATION HELPER
# =============================================================================

def generate_uuid() -> uuid.UUID:
    """
    Generate a new UUID4 for use as a primary key.
    
    Why UUID over auto-increment integer?
    ------------------------------------
    1. Globally unique: No collisions even across distributed systems
    2. Non-sequential: Harder to guess/enumerate (security)
    3. Merge-friendly: Can combine databases without ID conflicts
    4. Pre-generation: Can create ID before INSERT (useful for related objects)
    
    Why UUID4 specifically?
    ----------------------
    - UUID1: Uses MAC address + time (privacy concern, less random)
    - UUID4: Purely random (128 bits of randomness)
    - UUID5/3: Deterministic from namespace + name (not what we want here)
    
    Performance note:
    ----------------
    UUIDs are larger than integers (16 bytes vs 4-8 bytes), which means:
    - Slightly larger indexes
    - Slightly slower comparisons
    For most applications, this trade-off is worth it for the benefits above.
    
    Returns:
        uuid.UUID: A new random UUID4 value.
    """
    return uuid.uuid4()
