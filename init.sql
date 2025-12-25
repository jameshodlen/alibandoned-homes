-- Initialize database with PostGIS extension
-- Comment: "Runs automatically on first container start"

-- Create PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
-- Comment: "PostGIS adds spatial/geographic data types and functions"

-- Create PostGIS Topology extension (optional but useful)
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Create initial tables or users if not using Alembic for first run
-- NOTE: In production, rely on Alembic migrations for schema creation.
-- This script is primarily for extensions and database-level config.

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_locations_confirmed 
    ON locations(confirmed);

CREATE INDEX IF NOT EXISTS idx_locations_created_at 
    ON locations(created_at DESC);

-- Comment: "Spatial index created automatically by PostGIS for geometry columns"
