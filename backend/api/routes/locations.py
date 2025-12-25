"""
Locations API Routes - CRUD operations for abandoned home locations.

EDUCATIONAL: REST API Concepts
===============================

HTTP Methods and Their Purposes:
--------------------------------
GET:    Retrieve data (read-only, idempotent*)
POST:   Create new resource
PUT:    Update entire resource (replace)
PATCH:  Partial update (modify specific fields)
DELETE: Remove resource

*Idempotent: Calling it multiple times has the same effect as calling once
Example: GET /locations/123 returns the same data every time

HTTP Status Codes:
-----------------
2xx Success:
  200 OK: Request succeeded
  201 Created: Resource was created
  204 No Content: Success, but no data to return

4xx Client Errors:
  400 Bad Request: Invalid data sent by client
  401 Unauthorized: Authentication required
  403 Forbidden: Authenticated but no permission
  404 Not Found: Resource doesn't exist
  422 Unprocessable Entity: Valid format but invalid data

5xx Server Errors:
  500 Internal Server Error: Something broke on server
  503 Service Unavailable: Server temporarily can't handle request

RESTful Design Principles:
-------------------------
1. Resource-based URLs: /locations/123 (not /getLocation?id=123)
2. Use HTTP methods semantically: POST for create, PUT for update
3. Stateless: Each request contains all needed information
4. Consistent response format: Always return JSON with same structure
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import datetime

from database.base import get_async_session
from database.models import Location, Photo, create_point
from api.schemas import LocationCreate, LocationResponse, LocationUpdate, LocationListResponse
from api.auth import get_current_user
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# =============================================================================
# CREATE ENDPOINT
# =============================================================================

@router.post("/", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_location(
    location: LocationCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: str = Depends(get_current_user)
):
    """
    Create new abandoned home location.
    
    EDUCATIONAL: Creating Resources with POST
    ----------------------------------------
    - POST is used to create new resources
    - Returns status code 201 (Created) on success
    - Returns the created resource with its new ID
    - Rate limited to prevent abuse (10 requests/minute per user)
    
    Request body validation:
    - FastAPI automatically validates against LocationCreate schema
    - If validation fails, returns 422 Unprocessable Entity
    
    Args:
        location: Location data (coordinates, notes, condition)
        db: Database session (injected by FastAPI)
        current_user: Authenticated user (injected by auth middleware)
        
    Returns:
        LocationResponse: Created location with ID and timestamps
        
    Raises:
        400: Invalid coordinates
        401: Not authenticated (missing/invalid API key)
        422: Invalid request data (Pydantic validation)
        
    Example request:
        POST /api/v1/locations/
        Headers: {"X-API-Key": "your-key"}
        Body: {
            "latitude": 42.3314,
            "longitude": -83.0458,
            "confirmed": false,
            "condition": "partial_collapse",
            "accessibility": "moderate",
            "notes": "Boarded windows, overgrown yard"
        }
    """
    # EDUCATIONAL: Input Validation
    #
    # Always validate user input! Never trust client data.
    # Common validations:
    # - Range checks (latitude must be -90 to 90)
    # - Format checks (email must contain @)
    # - Business logic (can't delete if has dependencies)
    
    # Validate coordinates are within valid ranges
    if not (-90 <= location.latitude <= 90):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Latitude must be between -90 and 90"
        )
    if not (-180 <= location.longitude <= 180):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Longitude must be between -180 and 180"
        )
    
    # EDUCATIONAL: Creating Database Records
    #
    # Process:
    # 1. Create model instance with data
    # 2. Add to session (stages for commit)
    # 3. Commit (saves to database)
    # 4. Refresh (loads generated values like ID, timestamps)
    
    # Create PostGIS point from coordinates
    point = create_point(location.longitude, location.latitude)
    
    # Create Location model instance
    db_location = Location(
        coordinates=point,
        address=location.address,
        confirmed=location.confirmed,
        condition=location.condition,
        accessibility=location.accessibility,
        notes=location.notes
    )
    
    # Add to session
    db.add(db_location)
    
    # EDUCATIONAL: Async commit
    # await: Pause here until database operation completes
    # This is non-blocking - other requests can be processed
    await db.commit()
    
    # EDUCATIONAL: Refresh after commit
    # Loads generated values (ID, created_at, updated_at)
    # Without this, db_location.id would be None!
    await db.refresh(db_location)
    
    return db_location


# =============================================================================
# LIST ENDPOINT
# =============================================================================

@router.get("/", response_model=LocationListResponse)
@limiter.limit("30/minute")
async def list_locations(
    skip: int = Query(0, ge=0, description="Number of records to skip (for pagination)"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    confirmed_only: bool = Query(False, description="Only return confirmed locations"),
    condition: Optional[str] = Query(None, description="Filter by condition"),
    min_confidence: Optional[float] = Query(None, ge=0, le=1, description="Minimum confidence score"),
    bbox: Optional[str] = Query(
        None,
        description="Bounding box filter: 'min_lon,min_lat,max_lon,max_lat'",
        example="-83.5,42.0,-83.0,42.5"
    ),
    db: AsyncSession = Depends(get_async_session)
):
    """
    List locations with filtering and pagination.
    
    EDUCATIONAL: Pagination
    ----------------------
    Why paginate?
    - Prevents loading thousands of records at once (slow, memory intensive)
    - Better user experience (fast initial load)
    - Reduces server load
    
    Pagination patterns:
    1. Offset/Limit (what we use):
       - skip=0, limit=100: First 100 records
       - skip=100, limit=100: Next 100 records
       - Simple but can be slow for large offsets
    
    2. Cursor-based:
       - Use last_id to fetch next page
       - Faster for large datasets
       - More complex to implement
    
    EDUCATIONAL: Query Parameters vs Path Parameters
    -----------------------------------------------
    Path parameters: /locations/123
      - Part of the URL path
      - Required (can't omit)
      - Identify a specific resource
    
    Query parameters: /locations?skip=0&limit=100
      - After the ? in URL
      - Optional (have defaults)
      - Filter, sort, paginate
    
    Args:
        skip: How many records to skip (for pagination, default 0)
        limit: Maximum records to return (default 100, max 1000)
        confirmed_only: If true, only return human-verified locations
        condition: Filter by specific condition (intact, collapsed, etc.)
        min_confidence: Only return predictions above this confidence
        bbox: Geographic bounding box (format: "min_lon,min_lat,max_lon,max_lat")
        db: Database session
        
    Returns:
        LocationListResponse: List of locations plus total count
        
    Example requests:
        GET /api/v1/locations?skip=0&limit=20
        GET /api/v1/locations?confirmed_only=true
        GET /api/v1/locations?bbox=-83.5,42.0,-83.0,42.5&min_confidence=0.7
    """
    # EDUCATIONAL: Building Dynamic Queries
    #
    # Start with base query, then add filters conditionally
    # This prevents SQL injection (SQLAlchemy escapes values)
    query = select(Location)
    
    # Apply filters based on query parameters
    if confirmed_only:
        query = query.where(Location.confirmed == True)
    
    if condition:
        query = query.where(Location.condition == condition)
    
    if min_confidence is not None:
        query = query.where(Location.confidence_score >= min_confidence)
    
    if bbox:
        # EDUCATIONAL: Spatial Queries with PostGIS
        #
        # PostGIS provides spatial functions:
        # - ST_MakeEnvelope: Creates a rectangular polygon
        # - ST_Contains: Checks if geometry A contains geometry B
        # - ST_DWithin: Finds points within distance
        # - ST_Intersects: Checks if geometries overlap
        try:
            # Parse bounding box: "min_lon,min_lat,max_lon,max_lat"
            coords = bbox.split(',')
            if len(coords) != 4:
                raise ValueError("Bounding box must have 4 coordinates")
            
            min_lon, min_lat, max_lon, max_lat = map(float, coords)
            
            # EDUCATIONAL: ST_MakeEnvelope
            # Creates a rectangular polygon from corner coordinates
            # Arguments: xmin, ymin, xmax, ymax, srid
            # SRID 4326 = WGS 84 (standard GPS coordinates)
            envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
            
            # Filter to only points inside the envelope
            query = query.where(func.ST_Contains(envelope, Location.coordinates))
            
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid bounding box format: {str(e)}. Expected: 'min_lon,min_lat,max_lon,max_lat'"
            )
    
    # EDUCATIONAL: Count Query
    # Get total count before pagination
    # This is used for displaying "Page 1 of 10"
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total_count = total_result.scalar()
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    # EDUCATIONAL: execute() vs get() vs scalar()
    # - execute(): Returns Result object (for SELECT)
    # - get(): Fetch by primary key (for SELECT by ID)
    # - scalar(): Get single value (for COUNT)
    result = await db.execute(query)
    locations = result.scalars().all()
    
    return {
        "items": locations,
        "total": total_count,
        "skip": skip,
        "limit": limit
    }


# =============================================================================
# GET SINGLE ENDPOINT
# =============================================================================

@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: str,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get single location by ID.
    
    EDUCATIONAL: Path Parameters
    ---------------------------
    {location_id} in the route path is a path parameter
    - Extracted from URL: /locations/123 → location_id='123'
    - Always required (no default value)
    - Used to identify specific resources
    
    Args:
        location_id: UUID of the location
        db: Database session
        
    Returns:
        LocationResponse: Location data
        
    Raises:
        404: Location not found
        
    Example:
        GET /api/v1/locations/123e4567-e89b-12d3-a456-426614174000
    """
    # EDUCATIONAL: Fetching by Primary Key
    #
    # get() is optimized for primary key lookups
    # Faster than .where(Location.id == location_id)
    location = await db.get(Location, location_id)
    
    if not location:
        # EDUCATIONAL: 404 Not Found
        # Always return 404 when resource doesn't exist
        # Don't return 400 or 500 - those mean different things
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with ID {location_id} not found"
        )
    
    return location


# =============================================================================
# UPDATE ENDPOINT
# =============================================================================

@router.put("/{location_id}/feedback", status_code=status.HTTP_200_OK)
async def add_feedback(
    location_id: str,
    feedback: str = Query(..., description="Feedback on prediction accuracy"),
    db: AsyncSession = Depends(get_async_session),
    current_user: str = Depends(get_current_user)
):
    """
    Add user feedback on a location/prediction.
    
    EDUCATIONAL: Feedback Loops in ML Systems
    ----------------------------------------
    User feedback is crucial for:
    1. Active learning: Improve model with real-world data
    2. Quality metrics: Track prediction accuracy over time
    3. Trust building: Users see their feedback matters
    
    Best practices:
    - Make feedback easy (one-click is ideal)
    - Show users how feedback improves the system
    - Track feedback metrics over time
    
    Args:
        location_id: UUID of location
        feedback: User's feedback (e.g., "correct", "incorrect", "uncertain")
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Confirmation message
        
    Raises:
        404: Location not found
        401: Not authenticated
    """
    location = await db.get(Location, location_id)
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location not found"
        )
    
    # Update location with feedback
    # This is a simple example - in production, you'd likely
    # store feedback in a separate table with user_id, timestamp, etc.
    location.notes = f"{location.notes or ''}\n[Feedback at {datetime.now()}]: {feedback}"
    
    await db.commit()
    
    return {
        "message": "Feedback recorded successfully",
        "location_id": location_id,
        "feedback": feedback
    }

# =============================================================================
# DELETE ENDPOINT
# =============================================================================

@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: str = Depends(get_current_user)
):
    """
    Delete a location and all associated photos.
    
    EDUCATIONAL: DELETE Operations
    -----------------------------
    - Returns 204 No Content on success (no response body)
    - Should be idempotent (deleting already-deleted returns 204)
    - Consider soft deletes for audit trails (mark deleted=True instead)
    
    Cascading deletes:
    - Photos are automatically deleted (cascade="all, delete-orphan")
    - This is defined in the Location model relationship
    
Args:
        location_id: UUID of location to delete
        db: Database session
        current_user: Authenticated user (only authenticated users can delete)
        
    Returns:
        No content (204 status)
        
    Raises:
        404: Location not found
        401: Not authenticated
    """
    location = await db.get(Location, location_id)
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location not found"
        )
    
    await db.delete(location)
    await db.commit()
    
    # EDUCATIONAL: 204 No Content
    # Don't return any data - the status code says it all
    # FastAPI handles this automatically when you return None
    return None
