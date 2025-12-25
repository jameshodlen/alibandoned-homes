"""
API Endpoint Tests

EDUCATIONAL: API Testing Concepts
=================================

Why test APIs?
--------------
1. Verify functionality: Does it work as expected?
2. Catch regressions: Did my change break something?
3. Documentation: Tests show how to use the API
4. Confidence: Deploy changes without fear

Types of tests:
--------------
1. Unit tests: Test individual functions
2. Integration tests: Test API endpoints (what we do here)
3. E2E tests: Test full user workflows
4. Performance tests: Test speed and scalability

FastAPI TestClient:
------------------
- Simulates HTTP requests without running server
- Fast (no network overhead)
- Synchronous (easier to write)
- Based on requests library (familiar API)
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from api.main import app
from database.base import Base, get_async_session
from database.models import Location, create_point

# EDUCATIONAL: Test Database Setup
#
# Use separate database for tests:
# - SQLite in-memory (fast, isolated)
# - PostgreSQL test database (more realistic)
#
# Benefits:
# - Tests don't affect production data
# - Each test starts with clean state
# - Fast (in-memory database)
#
# SQLite limitations:
# - No PostGIS (can't test spatial queries fully)
# - Different SQL dialects (some queries may work differently)
#
# For full testing, use PostgreSQL test database

# Create in-memory SQLite database for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)


# Dependency override for testing
def override_get_db():
    """
    Replace production database with test database.
    
    EDUCATIONAL: Dependency Injection for Testing
    --------------------------------------------
    FastAPI's dependency system makes testing easy:
    1. Define dependencies (get_db, get_current_user)
    2. In tests, replace with test versions
    3. No code changes needed!
    
    Example:
        app.dependency_overrides[get_db] = test_get_db
    """
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Override dependencies
app.dependency_overrides[get_async_session] = override_get_db

# Create test client
# EDUCATIONAL: TestClient
# - Makes requests like: client.get("/api/v1/locations")
# - Returns Response object with .status_code, .json(), etc.
# - No actual HTTP - all in-process
client = TestClient(app)


# =============================================================================
# TEST FIXTURES
# =============================================================================

# EDUCATIONAL: Pytest Fixtures
#
# Fixtures provide reusable setup/teardown:
# - @pytest.fixture decorator
# - Function name becomes fixture name
# - Use as function parameter: def test_something(db_session):
#
# Benefits:
# - DRY (Don't Repeat Yourself)
# - Clean test database for each test
# - Automatic cleanup

@pytest.fixture
def api_key():
    """API key for authenticated requests"""
    return "test-api-key"


@pytest.fixture
def auth_headers(api_key):
    """Headers with API key"""
    return {"X-API-Key": api_key}


@pytest.fixture
def sample_location():
    """Sample location data for tests"""
    return {
        "latitude": 42.3314,
        "longitude": -83.0458,
        "address": "123 Test St, Detroit, MI",
        "confirmed": False,
        "condition": "partial_collapse",
        "accessibility": "moderate",
        "notes": "Test location"
    }


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

def test_health_check():
    """
    Test health endpoint.
    
    EDUCATIONAL: Simple GET Request Test
    ------------------------------------
    1. Make request: client.get(url)
    2. Check status code: assert response.status_code == 200
    3. Check response body: assert data["status"] == "healthy"
    """
    response = client.get("/health")
    
    # Assert status code
    assert response.status_code == 200
    
    # Parse JSON response
    data = response.json()
    
    # Assert response structure
    assert "status" in data
    assert data["status"] == "healthy"
    assert "version" in data


# =============================================================================
# LOCATIONS ENDPOINT TESTS
# =============================================================================

def test_create_location(sample_location, auth_headers):
    """
    Test creating a location.
    
    EDUCATIONAL: POST Request Test
    -----------------------------
    POST requests include:
    - URL: /api/v1/locations/
    - Headers: Authentication
    - Body: JSON data
    - Expected status: 201 Created
    """
    response = client.post(
        "/api/v1/locations/",
        json=sample_location,
        headers=auth_headers
    )
    
    # EDUCATIONAL: Asserting Status Codes
    # 201 = Created (not 200 OK!)
    # This follows REST conventions
    assert response.status_code == 201
    
    data = response.json()
    
    # Verify response includes generated fields
    assert "id" in data
    assert "created_at" in data
    assert data["latitude"] == sample_location["latitude"]
    assert data["longitude"] == sample_location["longitude"]


def test_create_location_invalid_coordinates(auth_headers):
    """
    Test validation of invalid coordinates.
    
    EDUCATIONAL: Testing Validation Errors
    -------------------------------------
    Always test error cases:
    - Invalid input returns 400 Bad Request
    - Error message is helpful
    - No data is created
    """
    invalid_location = {
        "latitude": 91.0,  # Invalid! (max is 90)
        "longitude": -83.0,
        "confirmed": False,
        "condition": "intact",
        "accessibility": "easy"
    }
    
    response = client.post(
        "/api/v1/locations/",
        json=invalid_location,
        headers=auth_headers
    )
    
    # Should return 400 Bad Request
    assert response.status_code == 400
    
    # Error message should be informative
    data = response.json()
    assert "detail" in data
    assert "Latitude" in data["detail"] or "latitude" in data["detail"].lower()


def test_create_location_missing_auth():
    """
    Test authentication requirement.
    
    EDUCATIONAL: Testing Authentication
    ----------------------------------
    - Request without auth → 401 Unauthorized
    - Request with invalid auth → 401 Unauthorized
    - Request with valid auth → Success
    """
    response = client.post(
        "/api/v1/locations/",
        json={"latitude": 42.0, "longitude": -83.0}
        # No headers = no API key
    )
    
    # Should return 401 Unauthorized
    assert response.status_code == 401


def test_list_locations():
    """
    Test listing locations.
    
    EDUCATIONAL: Testing List Endpoints
    ----------------------------------
    Check:
    - Returns list
    - Pagination works
    - Filters work
    """
    response = client.get("/api/v1/locations/")
    
    assert response.status_code == 200
    
    data = response.json()
    
    # Check response structure
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_list_locations_with_filters():
    """Test location filtering"""
    response = client.get(
        "/api/v1/locations/",
        params={"confirmed_only": True, "limit": 10}
    )
    
    assert response.status_code == 200


def test_get_location_not_found():
    """
    Test 404 for non-existent location.
    
    EDUCATIONAL: Testing Not Found
    -----------------------------
    - Invalid ID → 404 Not Found
    - Helpful error message
    """
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/locations/{fake_id}")
    
    assert response.status_code == 404


# =============================================================================
# PREDICTIONS ENDPOINT TESTS
# =============================================================================

def test_predict_area(auth_headers):
    """
    Test area prediction endpoint.
    
    EDUCATIONAL: Testing Async Operations
    ------------------------------------
    For long-running tasks:
    - Initial request returns 202 Accepted
    - Response includes job ID
    - Status endpoint shows progress
    """
    request_data = {
        "center_lat": 42.3314,
        "center_lon": -83.0458,
        "radius_km": 5.0,
        "resolution_meters": 100,
        "threshold": 0.7
    }
    
    response = client.post(
        "/api/v1/predictions/predict-area",
        json=request_data,
        headers=auth_headers
    )
    
    # Should return 202 Accepted (not 200 or 201)
    assert response.status_code == 202
    
    data = response.json()
    
    # Should include job ID
    assert "job_id" in data
    assert "status" in data
    assert data["status"] == "pending"


def test_get_prediction_status(auth_headers):
    """Test checking job status"""
    # First create a job
    request_data = {
        "center_lat": 42.3314,
        "center_lon": -83.0458,
        "radius_km": 5.0
    }
    
    create_response = client.post(
        "/api/v1/predictions/predict-area",
        json=request_data,
        headers=auth_headers
    )
    
    job_id = create_response.json()["job_id"]
    
    # Check status
    status_response = client.get(f"/api/v1/predictions/{job_id}")
    
    assert status_response.status_code == 200
    
    data = status_response.json()
    assert "status" in data
    assert data["status"] in ["pending", "processing", "completed", "failed"]


# =============================================================================
# ADMIN ENDPOINT TESTS
# =============================================================================

def test_admin_stats(auth_headers):
    """Test admin statistics endpoint"""
    response = client.get(
        "/api/v1/admin/stats",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert "total_locations" in data
    assert "confirmed_locations" in data
    assert isinstance(data["total_locations"], int)


# =============================================================================
# RUNNING TESTS
# =============================================================================

# EDUCATIONAL: Running Tests
#
# From command line:
#   pytest tests/test_api.py -v
#
# Options:
#   -v: Verbose (show each test name)
#   -s: Show print statements
#   -k test_create: Only run tests matching name
#   --cov: Show code coverage
#
# Example output:
#   test_health_check PASSED
#   test_create_location PASSED
#   test_create_location_invalid_coordinates PASSED
#   ...
#   10 passed in 0.5s

if __name__ == "__main__":
    # Can run directly: python test_api.py
    pytest.main([__file__, "-v"])
