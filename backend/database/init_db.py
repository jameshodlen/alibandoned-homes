"""
Database Initialization Script
==============================

This module handles first-time database setup:
1. Enables required PostgreSQL extensions (PostGIS)
2. Creates all tables defined in our models
3. Runs initial data migrations if needed

PostGIS Extension:
-----------------
PostGIS must be installed on your PostgreSQL server. The Docker image
`postgis/postgis:16-3.4` includes it pre-installed.

When to run this:
----------------
- Once when setting up a new database
- In development, can be run to reset the database
- In production, use Alembic migrations instead for incremental changes

Usage:
------
```python
import asyncio
from backend.database.init_db import init_database

asyncio.run(init_database())
```

Or from command line:
```bash
python -m backend.database.init_db
```
"""

import asyncio
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.database.base import Base, engine

# Configure logging for database operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_postgis_extension(engine: AsyncEngine) -> None:
    """
    Enable the PostGIS extension in PostgreSQL.
    
    What is PostGIS?
    ---------------
    PostGIS adds geographic object support to PostgreSQL, allowing you to:
    - Store points, lines, polygons as column values
    - Query spatial relationships (contains, intersects, within distance)
    - Calculate distances, areas, and other geometric properties
    - Use spatial indexes for fast geographic queries
    
    Why 'CREATE EXTENSION IF NOT EXISTS'?
    -------------------------------------
    This is idempotent - safe to run multiple times without error.
    If PostGIS is already enabled, PostgreSQL just does nothing.
    
    Required PostgreSQL permissions:
    --------------------------------
    The database user needs superuser OR be in the pg_read_server_files role
    to create extensions. The postgis/postgis Docker image handles this.
    
    Args:
        engine: SQLAlchemy async engine connected to the database.
    """
    async with engine.begin() as conn:
        # Enable PostGIS extension for spatial types and functions
        # This adds types like GEOMETRY, GEOGRAPHY and functions like ST_Distance
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        logger.info("PostGIS extension enabled successfully")
        
        # Optional: Enable PostGIS topology for advanced use cases
        # Topology handles shared boundaries between polygons
        # await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology"))
        
        # Check PostGIS version to verify it's working
        result = await conn.execute(text("SELECT PostGIS_Version()"))
        version = result.scalar()
        logger.info(f"PostGIS version: {version}")


async def create_all_tables(engine: AsyncEngine) -> None:
    """
    Create all tables defined in the SQLAlchemy models.
    
    How this works:
    --------------
    1. Base.metadata contains all table definitions from models that inherit Base
    2. create_all() generates CREATE TABLE statements for each model
    3. checkfirst=True (default) means it won't error if tables exist
    
    Why run_sync?
    ------------
    SQLAlchemy's metadata.create_all() is synchronous, but we're using
    an async engine. run_sync() runs the sync function in a thread pool
    while keeping the async engine happy.
    
    Warning for production:
    ----------------------
    create_all() is great for development but NOT for production!
    Use Alembic migrations for production to:
    - Track schema changes over time
    - Roll back changes if needed
    - Apply incremental updates without data loss
    
    Args:
        engine: SQLAlchemy async engine connected to the database.
    """
    # Import models to ensure they're registered with Base.metadata
    # These imports have side effects: they add tables to Base.metadata
    from backend.database import models  # noqa: F401
    
    async with engine.begin() as conn:
        # run_sync converts the sync create_all to work with async
        await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Created {len(Base.metadata.tables)} tables")
        
        # Log which tables were created
        for table_name in Base.metadata.tables.keys():
            logger.info(f"  - {table_name}")


async def drop_all_tables(engine: AsyncEngine) -> None:
    """
    Drop all tables defined in the SQLAlchemy models.
    
    ⚠️  DANGER: This permanently deletes all data!
    
    When to use:
    -----------
    - Development: Reset database to clean state
    - Testing: Clean up between test runs
    - NEVER in production without explicit backup
    
    Drop order matters:
    ------------------
    Tables with foreign keys must be dropped in the right order.
    SQLAlchemy handles this automatically by analyzing dependencies.
    
    Args:
        engine: SQLAlchemy async engine connected to the database.
    """
    from backend.database import models  # noqa: F401
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.warning("All tables dropped!")


async def init_database(
    drop_existing: bool = False,
    sample_data: bool = False,
) -> None:
    """
    Initialize the database with required extensions and tables.
    
    This is the main entry point for database setup. It:
    1. Enables PostGIS extension
    2. Optionally drops existing tables (DANGER!)
    3. Creates all model tables
    4. Optionally inserts sample data for development
    
    Args:
        drop_existing: If True, drop all tables before creating.
                       DANGER: This deletes all data!
        sample_data: If True, insert sample records for development.
    
    Example:
    -------
    ```python
    # Development: Clean slate with sample data
    await init_database(drop_existing=True, sample_data=True)
    
    # CI/Testing: Clean slate, no sample data
    await init_database(drop_existing=True, sample_data=False)
    
    # Production: Just ensure tables exist (use migrations instead!)
    await init_database(drop_existing=False, sample_data=False)
    ```
    """
    logger.info("Starting database initialization...")
    
    # Step 1: Enable PostGIS for spatial features
    await create_postgis_extension(engine)
    
    # Step 2: Optionally drop existing tables
    if drop_existing:
        logger.warning("Dropping existing tables...")
        await drop_all_tables(engine)
    
    # Step 3: Create all model tables
    await create_all_tables(engine)
    
    # Step 4: Optionally add sample data
    if sample_data:
        await insert_sample_data()
    
    logger.info("Database initialization complete!")


async def insert_sample_data() -> None:
    """
    Insert sample records for development and testing.
    
    This creates a few example records to help developers:
    - See how the data looks in the database
    - Test queries without creating data manually
    - Understand relationships between tables
    
    Note: This data is fake and only for development!
    """
    from backend.database.base import AsyncSessionLocal
    from backend.database.models import Location, ModelVersion, AccessibilityLevel, ConditionLevel, ModelType
    import uuid
    
    async with AsyncSessionLocal() as session:
        # Create a sample model version
        model = ModelVersion(
            id=uuid.uuid4(),
            version_name="v1.0.0",
            model_type=ModelType.ENSEMBLE,
            file_path="/models/ensemble_v1.0.0.pt",
            training_samples_count=10000,
            validation_accuracy=0.92,
            precision=0.89,
            recall=0.95,
            f1_score=0.92,
            is_active=True,
            notes="Initial production model",
        )
        session.add(model)
        
        # Create a sample location
        # Note: We're using WKT (Well-Known Text) format for the geometry
        # ST_GeomFromText converts WKT to PostGIS geometry
        location = Location(
            id=uuid.uuid4(),
            coordinates="SRID=4326;POINT(-97.7431 30.2672)",  # Austin, TX
            address="123 Main St, Austin, TX 78701",
            confirmed=True,
            confidence_score=0.95,
            accessibility=AccessibilityLevel.EASY,
            condition=ConditionLevel.INTACT,
            notes="Sample location for development testing",
        )
        session.add(location)
        
        await session.commit()
        logger.info("Sample data inserted successfully")


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

if __name__ == "__main__":
    """
    Run database initialization from command line.
    
    Usage:
        python -m backend.database.init_db
    
    For development with sample data:
        python -m backend.database.init_db --sample-data
    
    To reset everything (DANGER!):
        python -m backend.database.init_db --drop --sample-data
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize the database")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop existing tables before creating (DANGER: deletes data!)",
    )
    parser.add_argument(
        "--sample-data",
        action="store_true",
        help="Insert sample data for development",
    )
    
    args = parser.parse_args()
    
    asyncio.run(init_database(
        drop_existing=args.drop,
        sample_data=args.sample_data,
    ))
