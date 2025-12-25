"""
Integration tests for API endpoints.

=============================================================================
INTEGRATION TESTS
=============================================================================

Integration Tests bridge the gap between unit tests and E2E tests:
- Test multiple components working together
- Use test database (NOT production!)
- Test real API calls and responses
- Slower than unit tests, but faster than E2E

Key Differences from Unit Tests:
- Unit: Test function in isolation with mocked dependencies
- Integration: Test function with real dependencies (DB, other services)

=============================================================================
MOCKING VS REAL DEPENDENCIES
=============================================================================

Mocking: Replace real dependency with fake version
- Use when: External APIs, slow operations, non-deterministic results
- Pro: Fast, reliable, isolated
- Con: May miss integration issues

Real Dependencies: Use actual database, services
- Use when: Testing integration points, data flow
- Pro: Catches real bugs, tests actual behavior
- Con: Slower, needs setup, can be flaky

Strategy: Mock external services, use real internal components
=============================================================================
"""

import pytest
import os
from datetime import datetime, timezone
from uuid import uuid4

# FastAPI testing imports
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional

# =============================================================================
# MOCK APPLICATION FOR TESTING
# =============================================================================
# In a real project, you would import your actual app:
# from api.main import app
# from database.base import Base, get_db, engine

# For demonstration, we create a minimal test app
app = FastAPI(title="Test API")

# Mock database (in-memory list for demonstration)
mock_db = {
    "locations": [],
    "photos": []
}

class LocationCreate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    confirmed: bool = False
    condition: str = "intact"
    accessibility: str = "easy"
    notes: Optional[str] = None

class LocationResponse(BaseModel):
    id: str
    latitude: float
    longitude: float
    confirmed: bool
    condition: str
    accessibility: str
    notes: Optional[str]
    created_at: datetime

def get_api_key(api_key: str = None):
    """Simple API key validation"""
    valid_keys = ["test-key", "admin-key"]
    if api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

@app.post("/api/v1/locations/", status_code=201, response_model=LocationResponse)
def create_location(location: LocationCreate, api_key: str = Depends(get_api_key)):
    """Create a new location"""
    new_location = {
        "id": str(uuid4()),
        "latitude": location.latitude,
        "longitude": location.longitude,
        "confirmed": location.confirmed,
        "condition": location.condition,
        "accessibility": location.accessibility,
        "notes": location.notes,
        "created_at": datetime.now(timezone.utc)
    }
    mock_db["locations"].append(new_location)
    return new_location

@app.get("/api/v1/locations/", response_model=List[LocationResponse])
def list_locations(
    skip: int = 0, 
    limit: int = 10,
    bbox: Optional[str] = None,
    api_key: str = Depends(get_api_key)
):
    """List locations with optional filtering"""
    locations = mock_db["locations"]
    
    # Simple bbox filtering (format: "min_lat,min_lon,max_lat,max_lon")
    if bbox:
        try:
            min_lat, min_lon, max_lat, max_lon = map(float, bbox.split(","))
            locations = [
                loc for loc in locations
                if min_lat <= loc["latitude"] <= max_lat
                and min_lon <= loc["longitude"] <= max_lon
            ]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bbox format")
    
    return locations[skip:skip + limit]

@app.get("/api/v1/locations/{location_id}", response_model=LocationResponse)
def get_location(location_id: str, api_key: str = Depends(get_api_key)):
    """Get a specific location"""
    for loc in mock_db["locations"]:
        if loc["id"] == location_id:
            return loc
    raise HTTPException(status_code=404, detail="Location not found")

@app.delete("/api/v1/locations/{location_id}", status_code=204)
def delete_location(location_id: str, api_key: str = Depends(get_api_key)):
    """Delete a location"""
    for i, loc in enumerate(mock_db["locations"]):
        if loc["id"] == location_id:
            mock_db["locations"].pop(i)
            return
    raise HTTPException(status_code=404, detail="Location not found")


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def test_db():
    """
    Create fresh database state for each test
    
    Scope levels:
    - function: New DB per test (most isolated, recommended)
    - class: New DB per test class
    - module: New DB per file
    - session: One DB for all tests (fastest, least isolated)
    
    Why function scope?
    - Each test starts with clean state
    - Tests cannot affect each other
    - Failures are easy to reproduce
    """
    # Clear mock database before test
    mock_db["locations"] = []
    mock_db["photos"] = []
    
    yield mock_db
    
    # Cleanup after test (optional with mock)
    mock_db["locations"] = []
    mock_db["photos"] = []


@pytest.fixture
def client(test_db):
    """
    FastAPI TestClient
    
    TestClient provides:
    - HTTP client for testing API endpoints
    - Automatic request/response handling
    - No need for running server
    - Synchronous interface for async code
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    """Standard authentication headers for tests"""
    return {"X-API-Key": "test-key"}


@pytest.fixture
def sample_location_data():
    """Sample location data for creating test locations"""
    return {
        "latitude": 42.3314,
        "longitude": -83.0458,
        "confirmed": True,
        "condition": "partial_collapse",
        "accessibility": "moderate",
        "notes": "Test location"
    }


# =============================================================================
# SUCCESSFUL OPERATION TESTS
# =============================================================================

class TestLocationCreation:
    """Tests for POST /api/v1/locations/"""
    
    def test_create_location_success(self, client, auth_headers, sample_location_data):
        """Test successful location creation"""
        response = client.post(
            "/api/v1/locations/",
            json=sample_location_data,
            headers=auth_headers
        )
        
        # Verify response status
        assert response.status_code == 201
        
        # Verify response data
        data = response.json()
        assert "id" in data
        assert data["latitude"] == 42.3314
        assert data["longitude"] == -83.0458
        assert data["confirmed"] == True
        assert data["condition"] == "partial_collapse"
    
    def test_create_location_minimal_data(self, client, auth_headers):
        """Test creation with only required fields"""
        minimal_data = {
            "latitude": 42.0,
            "longitude": -83.0
        }
        
        response = client.post(
            "/api/v1/locations/",
            json=minimal_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        # Default values should be applied
        assert data["confirmed"] == False
        assert data["condition"] == "intact"


class TestLocationRetrieval:
    """Tests for GET /api/v1/locations/"""
    
    def test_list_empty_locations(self, client, auth_headers):
        """Test listing when no locations exist"""
        response = client.get(
            "/api/v1/locations/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_list_locations_returns_created(self, client, auth_headers, sample_location_data):
        """Test that created locations appear in list"""
        # Create a location
        client.post("/api/v1/locations/", json=sample_location_data, headers=auth_headers)
        
        # List should contain it
        response = client.get("/api/v1/locations/", headers=auth_headers)
        
        assert response.status_code == 200
        locations = response.json()
        assert len(locations) == 1
        assert locations[0]["latitude"] == 42.3314
    
    def test_get_single_location(self, client, auth_headers, sample_location_data):
        """Test retrieving a specific location by ID"""
        # Create location
        create_response = client.post(
            "/api/v1/locations/",
            json=sample_location_data,
            headers=auth_headers
        )
        location_id = create_response.json()["id"]
        
        # Retrieve it
        response = client.get(
            f"/api/v1/locations/{location_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["id"] == location_id


# =============================================================================
# VALIDATION AND ERROR TESTS
# =============================================================================

class TestValidation:
    """Tests for input validation"""
    
    def test_invalid_latitude_rejected(self, client, auth_headers):
        """Test that latitude > 90 is rejected"""
        response = client.post(
            "/api/v1/locations/",
            json={"latitude": 100, "longitude": -83.0},
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_invalid_longitude_rejected(self, client, auth_headers):
        """Test that longitude > 180 is rejected"""
        response = client.post(
            "/api/v1/locations/",
            json={"latitude": 42.0, "longitude": 200},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_missing_required_fields(self, client, auth_headers):
        """Test that missing latitude/longitude is rejected"""
        response = client.post(
            "/api/v1/locations/",
            json={"confirmed": True},  # Missing lat/lon
            headers=auth_headers
        )
        
        assert response.status_code == 422


class TestAuthentication:
    """Tests for API authentication"""
    
    def test_missing_api_key_rejected(self, client):
        """Test that requests without API key are rejected"""
        response = client.get("/api/v1/locations/")
        
        assert response.status_code == 401
    
    def test_invalid_api_key_rejected(self, client):
        """Test that invalid API key is rejected"""
        response = client.get(
            "/api/v1/locations/",
            headers={"X-API-Key": "invalid-key"}
        )
        
        assert response.status_code == 401


class TestNotFound:
    """Tests for 404 responses"""
    
    def test_get_nonexistent_location(self, client, auth_headers):
        """Test 404 for non-existent location ID"""
        response = client.get(
            "/api/v1/locations/nonexistent-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_delete_nonexistent_location(self, client, auth_headers):
        """Test 404 when deleting non-existent location"""
        response = client.delete(
            "/api/v1/locations/nonexistent-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404


# =============================================================================
# PAGINATION AND FILTERING TESTS
# =============================================================================

class TestPagination:
    """Tests for pagination functionality"""
    
    def test_pagination_limit(self, client, auth_headers, sample_location_data):
        """Test that limit parameter works"""
        # Create 10 locations
        for i in range(10):
            data = {**sample_location_data, "longitude": -83.0 + i * 0.001}
            client.post("/api/v1/locations/", json=data, headers=auth_headers)
        
        # Request with limit
        response = client.get(
            "/api/v1/locations/?limit=5",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert len(response.json()) == 5
    
    def test_pagination_skip(self, client, auth_headers, sample_location_data):
        """Test that skip parameter works"""
        # Create 10 locations
        for i in range(10):
            data = {**sample_location_data, "longitude": -83.0 + i * 0.001}
            client.post("/api/v1/locations/", json=data, headers=auth_headers)
        
        # Skip first 5
        response = client.get(
            "/api/v1/locations/?skip=5&limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert len(response.json()) == 5  # Only 5 remaining


class TestBoundingBoxFilter:
    """Tests for geographic bounding box filtering"""
    
    def test_bbox_filter_includes_matching(self, client, auth_headers):
        """Test that locations inside bbox are returned"""
        # Create location in Detroit
        client.post(
            "/api/v1/locations/",
            json={"latitude": 42.3, "longitude": -83.0},
            headers=auth_headers
        )
        
        # Query with bbox around Detroit
        bbox = "42.0,-83.5,42.5,-82.5"
        response = client.get(
            f"/api/v1/locations/?bbox={bbox}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert len(response.json()) == 1
    
    def test_bbox_filter_excludes_outside(self, client, auth_headers):
        """Test that locations outside bbox are excluded"""
        # Create location in Chicago (outside Detroit bbox)
        client.post(
            "/api/v1/locations/",
            json={"latitude": 41.8, "longitude": -87.6},
            headers=auth_headers
        )
        
        # Query with bbox around Detroit
        bbox = "42.0,-83.5,42.5,-82.5"
        response = client.get(
            f"/api/v1/locations/?bbox={bbox}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert len(response.json()) == 0  # Chicago excluded


# =============================================================================
# DELETE OPERATION TESTS
# =============================================================================

class TestLocationDeletion:
    """Tests for DELETE /api/v1/locations/{id}"""
    
    def test_delete_location_success(self, client, auth_headers, sample_location_data):
        """Test successful location deletion"""
        # Create location
        create_response = client.post(
            "/api/v1/locations/",
            json=sample_location_data,
            headers=auth_headers
        )
        location_id = create_response.json()["id"]
        
        # Delete it
        delete_response = client.delete(
            f"/api/v1/locations/{location_id}",
            headers=auth_headers
        )
        
        assert delete_response.status_code == 204
        
        # Verify it's gone
        get_response = client.get(
            f"/api/v1/locations/{location_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404


# =============================================================================
# DEBUGGING STRATEGIES
# =============================================================================

"""
DEBUGGING FAILED TESTS

1. READ THE ERROR MESSAGE
   - What assertion failed?
   - What was expected vs actual?
   - What line number?

2. CHECK TEST DATA
   - Is the fixture correct?
   - Is the test database clean?
   - Are dependencies mocked correctly?

3. ADD PRINT STATEMENTS
   ```python
   response = client.post(...)
   print(f"Status: {response.status_code}")
   print(f"Body: {response.json()}")
   assert response.status_code == 201
   ```

4. USE PYTEST -V (VERBOSE)
   pytest tests/test_api.py -v
   
5. RUN SINGLE TEST
   pytest tests/test_api.py::TestLocationCreation::test_create_location_success -v

6. USE DEBUGGER
   pytest tests/test_api.py --pdb  # Drop into debugger on failure
   
7. CHECK TEST ISOLATION
   pytest tests/test_api.py::test_specific --tb=long
"""
