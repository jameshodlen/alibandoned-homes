"""
Predictions API - Generate predictions for areas and track ML jobs.

EDUCATIONAL: Background Tasks and Long-Running Operations
=========================================================

Problem:
--------
Some operations take a long time (minutes to hours):
- Training ML models
- Processing large datasets
- Generating reports
- Sending bulk emails

If we process these synchronously, the HTTP request times out!

Solution: Background Tasks
--------------------------
1. Accept request → Create job ID → Return immediately
2. Process task in background (separate thread/worker)
3. Client polls /jobs/{id} to check status

This pattern is called:
- Job Queue Pattern
- Async Processing Pattern
- Task Queue Pattern

Popular tools: Celery, RQ, FastAPI BackgroundTasks, Cloud Tasks
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
import uuid
import asyncio
from datetime import datetime

from api.auth import get_current_user
from database.base import get_async_session
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# EDUCATIONAL: In-Memory Job Storage
#
# For simplicity, we're using a dict to store job status
# In production, use:
# - Redis (fast, persistent)
# - PostgreSQL (reliable, queryable)
# - Cloud services (AWS SQS, Google Cloud Tasks)
#
# This dict will reset if server restarts!
JOBS: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================

class PredictAreaRequest(BaseModel):
    """
    Request schema for area prediction.
    
    EDUCATIONAL: Pydantic Validation
    --------------------------------
    Pydantic automatically validates:
    - Type checking (center_lat must be float)
    - Range checking (ge=greater-or-equal, le=less-or-equal)
    - Custom validators (using @validator decorator)
    
    If validation fails:
    - Returns 422 Unprocessable Entity
    - Includes details of what's wrong
    """
    center_lat: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Center latitude for prediction area",
        example=42.3314
    )
    center_lon: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Center longitude for prediction area",
        example=-83.0458
    )
    radius_km: float = Field(
        ...,
        gt=0,
        le=50,
        description="Search radius in kilometers (max 50km)",
        example=5.0
    )
    resolution_meters: int = Field(
        100,
        gt=0,
        le=1000,
        description="Grid resolution in meters (default 100m)",
        example=100
    )
    threshold: float = Field(
        0.5,
        ge=0,
        le=1,
        description="Probability threshold for positive predictions",
        example=0.7
    )
    
    @validator('radius_km')
    def validate_radius(cls, v):
        """
        Custom validation for radius.
        
        EDUCATIONAL: Custom Validators
        ------------------------------
        Use @validator for complex validation logic:
        - Cross-field validation
        - Business rules
        - External API checks
        
        Validators run AFTER type checking
        """
        if v > 50:
            raise ValueError('Radius too large. Maximum is 50km to prevent API abuse.')
        if v < 0.1:
            raise ValueError('Radius too small. Minimum is 0.1km (100m).')
        return v


class JobStatusResponse(BaseModel):
    """Response schema for job status"""
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: Optional[float] = None  # 0.0 to 1.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/predict-area", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/hour")
async def predict_area(
    request: PredictAreaRequest,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user)
):
    """
    Generate probability heatmap for an area.
    
    EDUCATIONAL: HTTP 202 Accepted
    -----------------------------
    202 means: "Request accepted for processing, but not complete yet"
    - Used for long-running operations
    - Returns a job ID for tracking
    - Client polls /jobs/{id} for status
    
    EDUCATIONAL: Rate Limiting for Expensive Operations
    --------------------------------------------------
    This endpoint is limited to 5 requests per hour because:
    - ML predictions are CPU-intensive
    - Prevents abuse and ensures fair resource sharing
    - Protects server from being overwhelmed
    
    Rate limiting strategies:
    - Per user: 5/hour per API key
    - Global: 100/hour across all users
    - Tiered: Free users 5/hour, paid users 50/hour
    
    Args:
        request: Prediction parameters
        background_tasks: FastAPI background task manager
        current_user: Authenticated user
        
    Returns:
        Job ID and status endpoint
        
    Raises:
        401: Not authenticated
        422: Invalid request data
        429: Rate limit exceeded (too many requests)
        
    Example:
        POST /api/v1/predictions/predict-area
        {
            "center_lat": 42.3314,
            "center_lon": -83.0458,
            "radius_km": 5.0,
            "resolution_meters": 100,
            "threshold": 0.7
        }
        
        Response:
        {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "pending",
            "message": "Prediction started. Poll GET /predictions/550e8400... for status"
        }
    """
    # EDUCATIONAL: Generate unique job ID
    # UUID4: Random 128-bit number (extremely unlikely to collide)
    # Used to track this specific job
    job_id = str(uuid.uuid4())
    
    # Initialize job status
    # EDUCATIONAL: Job States
    # pending → processing → completed/failed
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0.0,
        "result": None,
        "error": None,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "request": request.dict()
    }
    
    # EDUCATIONAL: Background Tasks
    #
    # add_task() schedules work to run after response is sent:
    # 1. Return response immediately (user sees job ID)
    # 2. Connection closes
    # 3. Background task runs
    # 4. Update job status in JOBS dict
    # 5. Client polls to check status
    #
    # Alternative approaches:
    # - Celery: Distributed task queue (production-grade)
    # - Redis Queue (RQ): Simple Python task queue
    # - Cloud Tasks: Managed service (AWS SQS, Google Cloud Tasks)
    background_tasks.add_task(
        run_area_prediction,
        job_id=job_id,
        request=request,
        user_id=current_user
    )
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"Prediction started. Poll GET /predictions/{job_id} for status.",
        "status_url": f"/api/v1/predictions/{job_id}"
    }


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_prediction_status(
    job_id: str,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Check status of a prediction job.
    
    EDUCATIONAL: Polling for Job Status
    -----------------------------------
    Client should poll this endpoint until status is "completed" or "failed"
    
    Polling pattern:
    1. Call GET /predictions/{job_id} every 5 seconds
    2. Check status field
    3. If "processing", show progress bar (use progress field)
    4. If "completed", display results
    5. If "failed", show error message
    
    Example client code (Python):
        ```python
        import time
        import requests
        
        # Start prediction
        response = requests.post("/predictions/predict-area", json=request_data)
        job_id = response.json()["job_id"]
        
        # Poll for results
        while True:
            status = requests.get(f"/predictions/{job_id}").json()
            
            if status["status"] == "completed":
                print("Results:", status["result"])
                break
            elif status["status"] == "failed":
                print("Error:", status["error"])
                break
            else:
                print(f"Progress: {status['progress']:.0%}")
                time.sleep(5)  # Wait 5 seconds before next poll
        ```
    
    Better alternatives to polling:
    - WebSockets: Server pushes updates to client
    - Server-Sent Events (SSE): One-way updates from server
    - Webhooks: Server calls client's endpoint when done
    
    Args:
        job_id: UUID of the prediction job
        db: Database session
        
    Returns:
        Job status and results (if completed)
        
    Raises:
        404: Job not found
    """
    # Check in-memory job storage
    if job_id not in JOBS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    job = JOBS[job_id]
    return job


# =============================================================================
# BACKGROUND TASK FUNCTION
# =============================================================================

async def run_area_prediction(job_id: str, request: PredictAreaRequest, user_id: str):
    """
    Background task that actually runs the prediction.
    
    EDUCATIONAL: Background Task Implementation
    ------------------------------------------
    This function runs AFTER the HTTP response is sent.
    It updates the job status as it progresses.
    
    Best practices:
    1. Update status frequently (for progress bars)
    2. Handle errors gracefully (catch exceptions, update status to "failed")
    3. Log everything (helps debugging)
    4. Set timeouts (prevent hanging forever)
    5. Clean up resources (close connections, delete temp files)
    
    Args:
        job_id: UUID of this job
        request: Prediction parameters
        user_id: Who requested this prediction
    """
    try:
        # Update status to processing
        JOBS[job_id]["status"] = "processing"
        JOBS[job_id]["updated_at"] = datetime.now()
        JOBS[job_id]["progress"] = 0.1
        
        # EDUCATIONAL: Simulating long-running task
        # In reality, this would:
        # 1. Load ML model from disk
        # 2. Generate grid of points within radius
        # 3. Fetch features for each point (census data, imagery, etc.)
        # 4. Run prediction for each point
        # 5. Generate heatmap
        # 6. Save results to database/storage
        
        # Simulate step 1: Load model (10% progress)
        await asyncio.sleep(2)
        JOBS[job_id]["progress"] = 0.2
        JOBS[job_id]["updated_at"] = datetime.now()
        
        # Simulate step 2: Generate grid (30% progress)
        await asyncio.sleep(3)
        JOBS[job_id]["progress"] = 0.5
        JOBS[job_id]["updated_at"] = datetime.now()
        
        # Simulate step 3: Fetch features (60% progress)
        await asyncio.sleep(3)
        JOBS[job_id]["progress"] = 0.8
        JOBS[job_id]["updated_at"] = datetime.now()
        
        # Simulate step 4: Run predictions (90% progress)
        await asyncio.sleep(2)
        JOBS[job_id]["progress"] = 0.95
        JOBS[job_id]["updated_at"] = datetime.now()
        
        # Simulate step 5: Generate heatmap (100% progress)
        await asyncio.sleep(1)
        
        # Mark as completed with results
        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["progress"] = 1.0
        JOBS[job_id]["result"] = {
            "predictions_count": 150,
            "high_probability_locations": [
                {"lat": 42.331, "lon": -83.045, "probability": 0.89},
                {"lat": 42.332, "lon": -83.047, "probability": 0.76},
                {"lat": 42.329, "lon": -83.043, "probability": 0.72},
            ],
            "heatmap_url": f"/storage/heatmaps/{job_id}.png",
            "completed_at": datetime.now().isoformat()
        }
        JOBS[job_id]["updated_at"] = datetime.now()
        
    except Exception as e:
        # EDUCATIONAL: Error Handling in Background Tasks
        #
        # Always catch exceptions in background tasks!
        # If uncaught, the error is logged but user never sees it
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)
        JOBS[job_id]["updated_at"] = datetime.now()
        
        # Log the full exception for debugging
        import traceback
        print(f"Job {job_id} failed:")
        print(traceback.format_exc())
