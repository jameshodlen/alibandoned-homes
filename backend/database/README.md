# Abandoned Homes Database Schema

This document describes the database schema for the Abandoned Homes Prediction application.

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Database Schema                                 │
│                     Abandoned Homes Prediction System                        │
└─────────────────────────────────────────────────────────────────────────────┘

                            ┌───────────────────┐
                            │   model_versions  │
                            ├───────────────────┤
                            │ • id (PK, UUID)   │
                            │ • version_name    │
                            │ • model_type      │◄──┐
                            │ • file_path       │   │
                            │ • is_active       │   │
                            │ • precision       │   │
                            │ • recall          │   │
                            │ • f1_score        │   │
                            │ • created_at      │   │
                            │ • updated_at      │   │
                            └───────────────────┘   │
                                      │             │
                                      │ 1:N         │
                                      ▼             │
┌───────────────────┐         ┌───────────────────┐│
│    locations      │         │    predictions    ││
├───────────────────┤         ├───────────────────┤│
│ • id (PK, UUID)   │◄───┐    │ • id (PK, UUID)   ││
│ • coordinates     │ G  │    │ • coordinates     │G
│   (PostGIS Point) │ I  │    │   (PostGIS Point) │I
│ • address         │ S  │    │ • confidence_score││S
│ • confirmed       │ T  │    │ • model_version_id├┘T
│ • confidence_score│    │    │ • reasoning       │
│ • accessibility   │    │    │ • user_feedback   │
│ • condition       │    │    │ • verified_       │
│ • notes           │    │    │   location_id (FK)├──┐
│ • created_at      │    │    │ • search_area     │  │
│ • updated_at      │    │    │   (PostGIS Poly)  │  │
└───────────────────┘    │    │ • created_at      │  │
        │                │    └───────────────────┘  │
        │ 1:N            │              ▲            │
        ▼                │              │            │
┌───────────────────┐    │              │ N:1        │
│      photos       │    │              │            │
├───────────────────┤    └──────────────┼────────────┘
│ • id (PK, UUID)   │                   │
│ • location_id (FK)├───────────────────┘
│ • file_path       │
│ • thumbnail_path  │
│ • photo_type      │    ┌───────────────────┐
│ • stripped_       │    │  search_history   │
│   metadata_json   │    ├───────────────────┤
│ • original_       │    │ • id (PK, UUID)   │
│   metadata_       │    │ • search_center   │ G
│   encrypted       │    │   (PostGIS Point) │ I
│ • taken_at        │    │ • search_area     │ S
│ • created_at      │    │   (PostGIS Poly)  │ T
└───────────────────┘    │ • radius_meters   │
                         │ • filters_json    │
                         │ • results_count   │
                         │ • created_at      │
                         └───────────────────┘

Legend:
  PK = Primary Key               FK = Foreign Key
  GIST = Has GIST spatial index  1:N = One-to-Many relationship
  ──► = Foreign key direction    G = Geometry column
```

## Tables Overview

| Table              | Purpose                          | Key Features                                             |
| ------------------ | -------------------------------- | -------------------------------------------------------- |
| **locations**      | Properties that may be abandoned | PostGIS Point, GIST index, accessibility/condition enums |
| **photos**         | Images of properties             | Encrypted EXIF metadata, multiple photo types            |
| **predictions**    | ML model outputs                 | Confidence scores, user feedback loop                    |
| **search_history** | User search analytics            | Polygon areas, filter tracking                           |
| **model_versions** | ML model tracking                | Performance metrics, single active per type              |

## PostGIS Spatial Types

### Geometry vs Geography

| Type          | Coordinates      | Units   | Use Case                   |
| ------------- | ---------------- | ------- | -------------------------- |
| **Geometry**  | Cartesian (flat) | Degrees | City-scale, fast queries   |
| **Geography** | Spherical        | Meters  | Global, accurate distances |

We use **Geometry with SRID 4326** (WGS 84) for all spatial columns.

### Key Spatial Functions

```sql
-- Create a point from coordinates (note: longitude FIRST)
ST_SetSRID(ST_MakePoint(-97.7431, 30.2672), 4326)

-- Find points within 5km distance (uses GIST index!)
ST_DWithin(location.coordinates, search_point, 5000)

-- Calculate distance between points
ST_Distance(location1.coordinates, location2.coordinates)

-- Check if point is within polygon
ST_Contains(search_area, prediction.coordinates)
```

### GIST Index

GIST (Generalized Search Tree) enables fast spatial queries:

- **Without GIST**: Full table scan → O(n)
- **With GIST**: Spatial partitioning → O(log n)

## Quick Start

```python
from backend.database.init_db import init_database
from backend.database.models import Location, get_nearby_locations
from backend.database.base import AsyncSessionLocal
import asyncio

# Initialize database
asyncio.run(init_database(sample_data=True))

# Query nearby locations
async def find_nearby():
    async with AsyncSessionLocal() as session:
        locations = await get_nearby_locations(
            session,
            longitude=-97.7431,  # Austin, TX
            latitude=30.2672,
            radius_meters=10000,
            confirmed_only=True,
        )
        for loc in locations:
            print(f"{loc.address}")

asyncio.run(find_nearby())
```

## Common Queries

### Insert a Location with Coordinates

```python
from sqlalchemy import func

location = Location(
    id=uuid.uuid4(),
    coordinates=func.ST_SetSRID(func.ST_MakePoint(-97.7431, 30.2672), 4326),
    address="123 Main St, Austin, TX",
    confirmed=True,
)
session.add(location)
await session.commit()
```

### Find Locations in Bounding Box

```python
from geoalchemy2.functions import ST_MakeEnvelope, ST_Contains

# Bounding box: (min_lon, min_lat, max_lon, max_lat)
bbox = func.ST_MakeEnvelope(-97.8, 30.2, -97.7, 30.3, 4326)

result = await session.execute(
    select(Location).where(ST_Contains(bbox, Location.coordinates))
)
```

### Get Active Model Version

```python
from backend.database.models import get_active_model_version, ModelType

model = await get_active_model_version(session, ModelType.ENSEMBLE)
print(f"Active model: {model.version_name}")
```

## Files

| File         | Description                                         |
| ------------ | --------------------------------------------------- |
| `base.py`    | DeclarativeBase, TimestampMixin, session management |
| `models.py`  | All table definitions with documentation            |
| `init_db.py` | PostGIS setup, table creation, sample data          |

## Dependencies

```
sqlalchemy[asyncio]>=2.0.25
asyncpg>=0.29.0
geoalchemy2>=0.14.3
```
