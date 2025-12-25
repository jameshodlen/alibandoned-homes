"""
Enhanced Admin API Routes - Model Management, Statistics, System Control

EDUCATIONAL: Admin Endpoints Best Practices
===========================================

Admin endpoints require special care:
1. Authentication: Only authenticated users
2. Authorization: Only admin role users  
3. Audit logging: Log all admin actions
4. Rate limiting: Prevent admin credential brute force
5. Input validation: Same as regular endpoints (attackers target admin!)

Common admin operations:
- User management (roles, permissions)
- System configuration
- Data management (exports, cleanup)
- Model management (deploy, rollback)
- Monitoring and statistics
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid

from api.auth import get_current_user, require_permission, Permissions
from database.base import get_async_session
from database.models import Location, Photo, Prediction
from api.middleware.rate_limit import RateLimitConfig

router = APIRouter()


# =============================================================================
# SYSTEM STATISTICS
# =============================================================================

@router.get("/stats", response_model=Dict[str, Any])
async def get_system_stats(
    db: AsyncSession = Depends(get_async_session),
    current_user: str = Depends(get_current_user)
):
    """
    Get comprehensive system statistics.
    
    EDUCATIONAL: Dashboard Metrics
    -----------------------------
    Good dashboard metrics are:
    - Actionable: Can you do something with this info?
    - Real-time or near real-time
    - Historical: Show trends
    - Comparative: vs last period
    
    Key metrics for ML system:
    - Data volume (locations, photos)
    - Model performance (accuracy, precision)
    - System health (response times, errors)
    - User activity (requests, feedback)
    
    Returns:
        Dict with comprehensive system stats
    """
    # EDUCATIONAL: Efficient Aggregation
    # Use SQL aggregates instead of loading all records
    # Bad: len(db.query(Location).all())  # Loads ALL records
    # Good: db.scalar(select(func.count()).select_from(Location))
    
    # Location counts
    total_locations = await db.scalar(
        select(func.count()).select_from(Location)
    ) or 0
    
    confirmed_locations = await db.scalar(
        select(func.count())
        .where(Location.confirmed == True)
        .select_from(Location)
    ) or 0
    
    # Photo count
    total_photos = await db.scalar(
        select(func.count()).select_from(Photo)
    ) or 0
    
    # Prediction count
    total_predictions = await db.scalar(
        select(func.count()).select_from(Prediction)
    ) or 0
    
    # Recent activity (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    locations_24h = await db.scalar(
        select(func.count())
        .where(Location.created_at >= yesterday)
        .select_from(Location)
    ) or 0
    
    # Calculate confirmation rate
    confirmation_rate = (
        (confirmed_locations / total_locations * 100)
        if total_locations > 0 else 0
    )
    
    return {
        "locations": {
            "total": total_locations,
            "confirmed": confirmed_locations,
            "unconfirmed": total_locations - confirmed_locations,
            "confirmation_rate": round(confirmation_rate, 2),
            "added_24h": locations_24h
        },
        "photos": {
            "total": total_photos,
            "avg_per_location": round(total_photos / max(total_locations, 1), 2)
        },
        "predictions": {
            "total": total_predictions
        },
        "ml_model": {
            "active_version": "v1.0.0",  # TODO: Get from model manager
            "last_trained": "2024-01-15T10:00:00Z",
            "accuracy": 0.85,
            "precision": 0.82,
            "recall": 0.78
        },
        "system": {
            "uptime_hours": 168,  # TODO: Calculate actual uptime
            "database_size_mb": 250,  # TODO: Calculate actual size
            "last_backup": "2024-01-14T00:00:00Z"
        },
        "timestamp": datetime.utcnow().isoformat()
    }


# =============================================================================
# MODEL MANAGEMENT
# =============================================================================

@router.get("/models")
async def list_model_versions(
    limit: int = 20,
    current_user: str = Depends(get_current_user)
):
    """
    List all trained model versions.
    
    EDUCATIONAL: Model Versioning
    ----------------------------
    Model versioning is crucial for:
    1. Reproducibility: Know which model made each prediction
    2. Rollback: Revert to previous if new model fails
    3. A/B testing: Compare model performance
    4. Compliance: Audit trail for decisions
    
    Best practices:
    - Semantic versioning (v1.0.0)
    - Store hyperparameters with version
    - Store training data hash
    - Store performance metrics
    
    Returns:
        List of model versions with metadata
    """
    # TODO: Get from actual model manager
    return {
        "versions": [
            {
                "id": "model-v1.2.0",
                "version": "1.2.0",
                "created_at": "2024-01-15T10:00:00Z",
                "is_active": True,
                "metrics": {
                    "accuracy": 0.85,
                    "precision": 0.82,
                    "recall": 0.78,
                    "f1_score": 0.80
                },
                "training_samples": 15000,
                "features_used": 45
            },
            {
                "id": "model-v1.1.0",
                "version": "1.1.0",
                "created_at": "2024-01-01T10:00:00Z",
                "is_active": False,
                "metrics": {
                    "accuracy": 0.82,
                    "precision": 0.79,
                    "recall": 0.75,
                    "f1_score": 0.77
                },
                "training_samples": 12000,
                "features_used": 42
            }
        ],
        "active_version": "1.2.0",
        "total_versions": 2
    }


@router.post("/models/train")
async def trigger_model_training(
    strategy: str = "auto",
    background_tasks: BackgroundTasks = None,
    current_user: str = Depends(require_permission(Permissions.ADMIN))
):
    """
    Trigger model retraining.
    
    EDUCATIONAL: Training Strategies
    --------------------------------
    Different situations call for different approaches:
    
    1. FULL RETRAIN:
       - Train from scratch on all data
       - When: Major data changes, algorithm updates
       - Time: Hours to days
       
    2. INCREMENTAL:
       - Update existing model with new data
       - When: Regular updates, streaming data
       - Time: Minutes to hours
       
    3. FINE-TUNE:
       - Adjust model weights slightly
       - When: Domain shift, new edge cases
       - Time: Minutes
       
    4. AUTO:
       - System decides based on data drift, time since last training
       - Recommended for production
    
    Args:
        strategy: Training strategy (auto, full, incremental, fine_tune)
        
    Returns:
        Training job status
    """
    valid_strategies = ["auto", "full", "incremental", "fine_tune"]
    if strategy not in valid_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy. Choose from: {valid_strategies}"
        )
    
    job_id = str(uuid.uuid4())
    
    # Queue training job (in production, use Celery or similar)
    # background_tasks.add_task(run_training, job_id, strategy)
    
    return {
        "job_id": job_id,
        "status": "queued",
        "strategy": strategy,
        "message": f"Training job {job_id} queued with strategy: {strategy}"
    }


@router.post("/models/{version}/activate")
async def activate_model(
    version: str,
    current_user: str = Depends(require_permission(Permissions.ADMIN))
):
    """
    Activate a specific model version for production.
    
    EDUCATIONAL: Model Deployment
    ----------------------------
    Deployment patterns:
    
    1. Blue-Green: Two environments, switch traffic
    2. Canary: Route small % to new model, monitor
    3. Shadow: Run new model in parallel, compare results
    4. A/B Test: Split traffic randomly, measure business metrics
    
    Safety checks before activation:
    - Verify model file exists
    - Check model loads successfully
    - Compare metrics to current model
    - Run on test dataset
    
    Args:
        version: Model version to activate
        
    Returns:
        Activation status
    """
    # TODO: Implement actual model activation
    return {
        "status": "activated",
        "version": version,
        "previous_version": "1.1.0",
        "activated_at": datetime.utcnow().isoformat(),
        "activated_by": current_user
    }


@router.post("/models/{version}/rollback")
async def rollback_model(
    version: str,
    reason: str = "Performance degradation",
    current_user: str = Depends(require_permission(Permissions.ADMIN))
):
    """
    Rollback to a previous model version.
    
    EDUCATIONAL: When to Rollback
    ----------------------------
    Rollback when:
    - Prediction quality drops
    - Error rate increases
    - Response time increases
    - User feedback deteriorates
    
    Post-rollback actions:
    1. Log the rollback (who, when, why)
    2. Alert the team
    3. Investigate root cause
    4. Fix and redeploy
    
    Args:
        version: Version to rollback to
        reason: Reason for rollback (for audit log)
        
    Returns:
        Rollback status
    """
    return {
        "status": "rolled_back",
        "target_version": version,
        "reason": reason,
        "rolled_back_at": datetime.utcnow().isoformat(),
        "rolled_back_by": current_user
    }


# =============================================================================
# DATA MANAGEMENT
# =============================================================================

@router.post("/cleanup/old-predictions")
async def cleanup_old_predictions(
    days: int = 90,
    dry_run: bool = True,
    db: AsyncSession = Depends(get_async_session),
    current_user: str = Depends(require_permission(Permissions.ADMIN))
):
    """
    Clean up old, unverified predictions.
    
    EDUCATIONAL: Data Cleanup Best Practices
    ----------------------------------------
    1. DRY RUN FIRST: Always preview what will be deleted
    2. BACKUP: Create backup before deletion
    3. SOFT DELETE: Mark as deleted instead of actual delete
    4. AUDIT LOG: Record what was deleted and when
    5. BATCH SIZE: Delete in batches (don't lock table too long)
    6. OFF-PEAK: Run during low traffic periods
    
    Args:
        days: Delete predictions older than this many days
        dry_run: If True, only count what would be deleted
        
    Returns:
        Cleanup results
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Count what would be deleted
    count = await db.scalar(
        select(func.count())
        .where(Prediction.created_at < cutoff_date)
        .where(Prediction.verified_location_id == None)
        .select_from(Prediction)
    ) or 0
    
    if dry_run:
        return {
            "dry_run": True,
            "would_delete": count,
            "cutoff_date": cutoff_date.isoformat(),
            "message": f"Would delete {count} old unverified predictions. "
                       "Set dry_run=false to execute."
        }
    
    # TODO: Implement actual deletion with batching
    # In production:
    # 1. Create backup
    # 2. Delete in batches of 1000
    # 3. Log each batch
    # 4. Commit after batches
    
    return {
        "dry_run": False,
        "deleted": count,
        "cutoff_date": cutoff_date.isoformat(),
        "deleted_by": current_user,
        "deleted_at": datetime.utcnow().isoformat()
    }


@router.post("/export/locations")
async def export_locations(
    format: str = "csv",
    confirmed_only: bool = False,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: str = Depends(require_permission(Permissions.ADMIN))
):
    """
    Export location data.
    
    EDUCATIONAL: Data Export Considerations
    --------------------------------------
    1. PRIVACY: Strip/encrypt sensitive fields
    2. SIZE: Use streaming for large datasets
    3. FORMAT: Support multiple formats (CSV, JSON, GeoJSON)
    4. ACCESS: Time-limited download links
    5. AUDIT: Log all exports (compliance)
    
    For large datasets:
    - Queue as background job
    - Notify when complete
    - Provide secure download link
    
    Args:
        format: Export format (csv, json, geojson)
        confirmed_only: Only export confirmed locations
        
    Returns:
        Export job status or download link
    """
    valid_formats = ["csv", "json", "geojson"]
    if format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format. Choose from: {valid_formats}"
        )
    
    job_id = str(uuid.uuid4())
    
    # TODO: Queue export job
    
    return {
        "job_id": job_id,
        "status": "queued",
        "format": format,
        "confirmed_only": confirmed_only,
        "message": f"Export job {job_id} queued. "
                   "Poll /admin/exports/{job_id} for status."
    }


# =============================================================================
# AUDIT LOG
# =============================================================================

@router.get("/audit-log")
async def get_audit_log(
    limit: int = 100,
    action_type: Optional[str] = None,
    current_user: str = Depends(require_permission(Permissions.ADMIN))
):
    """
    Get admin action audit log.
    
    EDUCATIONAL: Audit Logging
    -------------------------
    What to log:
    - WHO: User who performed action
    - WHAT: Action type and parameters
    - WHEN: Timestamp
    - WHERE: IP address, user agent
    - WHY: Reason (if provided)
    - RESULT: Success/failure
    
    Retention:
    - Typically 1-7 years (depends on compliance)
    - May need tamper-proof storage
    
    Args:
        limit: Max entries to return
        action_type: Filter by action type
        
    Returns:
        List of audit log entries
    """
    # TODO: Get from actual audit log
    return {
        "entries": [
            {
                "id": "log-001",
                "timestamp": "2024-01-15T10:30:00Z",
                "user": "admin@example.com",
                "action": "model_activated",
                "details": {"version": "1.2.0"},
                "ip_address": "192.168.1.1",
                "result": "success"
            },
            {
                "id": "log-002",
                "timestamp": "2024-01-15T09:00:00Z",
                "user": "admin@example.com",
                "action": "training_started",
                "details": {"strategy": "auto"},
                "ip_address": "192.168.1.1",
                "result": "success"
            }
        ],
        "total": 2,
        "limit": limit
    }
