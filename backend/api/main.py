"""
Main FastAPI application entry point.

FastAPI: Modern, fast web framework for building APIs with Python.
- Automatic OpenAPI documentation
- Data validation with Pydantic
- Async support for high performance
- Type hints for better IDE support

Educational Notes:
- async/await: Allows handling multiple requests concurrently without blocking
- Middleware: Code that processes requests before they reach routes
- CORS: Cross-Origin Resource Sharing - allows frontend from different origin to call API
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging

# Import routers
from api.routes import locations, predictions, photos, admin, advanced

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ... (lines 31-84 retained)

app.include_router(locations.router, prefix="/api/v1/locations", tags=["locations"])
app.include_router(predictions.router, prefix="/api/v1/predictions", tags=["predictions"])
app.include_router(photos.router, prefix="/api/v1/photos", tags=["photos"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(advanced.router, prefix="/api/v1/advanced", tags=["advanced"])

# Global exception handler
# EDUCATIONAL: Exception Handling Best Practices
# 
# Why catch exceptions globally?
# 1. Security: Prevents exposing internal error details to users
# 2. Consistency: All errors have the same format
# 3. Logging: Centralized place to log all errors
#
# Bad practice:
#   Letting Python exceptions bubble up → User sees stack traces! (security risk)
#
# Good practice:
#   Catch exceptions → Return generic error message → Log details server-side
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch all unhandled exceptions and return a safe error response.
    
    EDUCATIONAL: This prevents internal errors from being exposed to users.
    Always log the full exception server-side for debugging.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": str(type(exc).__name__)
            # Note: We don't include the full error message for security
        }
    )

# Health check endpoint
# EDUCATIONAL: Health Checks
#
# What they're for:
# - Load balancers check if your service is running
# - Kubernetes uses them to restart unhealthy containers
# - Monitoring systems use them for uptime alerts
#
# Best practice: Return 200 for healthy, 503 for unhealthy
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns:
        Status and version info
    
    EDUCATIONAL: This endpoint should:
    - Return quickly (< 100ms)
    - Not depend on databases (for basic liveness check)
    - Include version info for deployment tracking
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "abandoned-homes-api"
    }

# Startup event
# EDUCATIONAL: Application Lifecycle Events
#
# startup: Runs once when the application starts
# shutdown: Runs once when the application stops
#
# Use cases:
# - Load ML models into memory (expensive, do once)
# - Establish database connection pools
# - Initialize cache connections
@app.on_event("startup")
async def startup_event():
    """
    Initialize resources on app startup.
    
    EDUCATIONAL: This runs before the app starts accepting requests.
    Perfect for one-time initialization tasks.
    """
    logger.info("Starting Abandoned Homes API...")
    # TODO: Load ML models into memory here
    # Example:
    # global model
    # model = load_model('path/to/model.pkl')

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup resources on shutdown.
    
    EDUCATIONAL: This runs when the app is shutting down.
    Use it to:
    - Close database connections
    - Save in-memory state to disk
    - Release file handles
    """
    logger.info("Shutting down API...")
    # TODO: Close connections, save state, etc.

# API Versioning Strategy
# EDUCATIONAL: API Versioning
#
# Why version your API?
# - Allows making breaking changes without breaking existing clients
# - Gives users time to migrate to new versions
#
# Versioning strategies:
# 1. URL versioning: /api/v1/... (what we use - most common)
# 2. Header versioning: X-API-Version: 1
# 3. Query parameter: /api/users?version=1
#
# Best practices:
# - Start with v1 from day one
# - Keep old versions running for 6-12 months
# - Document deprecation timeline
