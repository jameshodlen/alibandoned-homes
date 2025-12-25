"""
Pytest conftest.py - Shared fixtures and configuration

=============================================================================
WHAT IS CONFTEST.PY?
=============================================================================

conftest.py is a special pytest file that:
- Provides fixtures available to all tests in the directory
- Configures pytest behavior via hooks
- Shares test configuration without imports

Key features:
- Fixtures defined here are automatically discovered
- No need to import fixtures in test files
- Can have multiple conftest.py at different directory levels
=============================================================================
"""

import pytest
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4
from typing import Generator, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# PYTEST HOOKS
# =============================================================================

def pytest_configure(config):
    """
    Pytest hook: Configure before tests run
    
    Use for:
    - Register custom markers
    - Set up logging
    - Initialize external resources
    """
    # Register custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    
    # Set environment for testing
    os.environ["TESTING"] = "1"
    os.environ["API_KEY"] = "test-api-key"


def pytest_collection_modifyitems(config, items):
    """
    Pytest hook: Modify test collection
    
    Use for:
    - Skip tests based on conditions
    - Add markers dynamically
    - Reorder tests
    """
    # Auto-mark tests based on file path
    for item in items:
        if "integration" in item.fspath.dirname:
            item.add_marker(pytest.mark.integration)
        elif "e2e" in item.fspath.dirname:
            item.add_marker(pytest.mark.e2e)
        elif "unit" in item.fspath.dirname or "test_models" in str(item.fspath):
            item.add_marker(pytest.mark.unit)


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def database_url():
    """
    Database URL for testing
    
    Session scope: Created once for entire test session
    
    Options:
    - SQLite in-memory: Fast, ephemeral (test isolation per fixture)
    - SQLite file: Persistent during test run
    - PostgreSQL test database: Most realistic
    """
    # Use in-memory SQLite for fast testing
    return "sqlite:///./test_db.sqlite"


@pytest.fixture(scope="function")
def mock_db() -> Generator[Dict[str, list], None, None]:
    """
    Mock in-memory database
    
    Function scope: Fresh database for each test
    
    Yields database dict, cleans up after test
    """
    db = {
        "locations": [],
        "photos": [],
        "predictions": [],
        "users": []
    }
    
    yield db
    
    # Cleanup (optional with dict, but good practice)
    db.clear()


# =============================================================================
# API FIXTURES
# =============================================================================

@pytest.fixture
def api_headers() -> Dict[str, str]:
    """Standard API headers for authenticated requests"""
    return {
        "X-API-Key": "test-api-key",
        "Content-Type": "application/json"
    }


@pytest.fixture
def admin_headers() -> Dict[str, str]:
    """Admin API headers with elevated permissions"""
    return {
        "X-API-Key": "admin-api-key",
        "Content-Type": "application/json",
        "X-Admin-Token": "admin-secret"
    }


# =============================================================================
# DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_location_dict() -> Dict[str, Any]:
    """
    Sample location data for creating test locations
    
    Returns dict suitable for API requests
    """
    return {
        "latitude": 42.3314,
        "longitude": -83.0458,
        "address": "123 Test St, Detroit, MI",
        "confirmed": True,
        "condition": "partial_collapse",
        "accessibility": "moderate",
        "notes": "Test location fixture"
    }


@pytest.fixture
def sample_locations() -> list:
    """Multiple sample locations for list/filter tests"""
    return [
        {
            "id": str(uuid4()),
            "latitude": 42.33,
            "longitude": -83.04,
            "address": "100 Main St",
            "confirmed": True,
            "condition": "partial_collapse",
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid4()),
            "latitude": 42.34,
            "longitude": -83.05,
            "address": "200 Oak Ave",
            "confirmed": False,
            "condition": "intact",
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid4()),
            "latitude": 42.35,
            "longitude": -83.06,
            "address": "300 Elm Rd",
            "confirmed": True,
            "condition": "full_collapse",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    ]


@pytest.fixture
def sample_image_bytes() -> bytes:
    """
    Sample image data for upload tests
    
    Creates a minimal valid JPEG file
    """
    # Minimal 1x1 red JPEG
    # In real tests, you'd use a fixture file
    import base64
    jpeg_b64 = (
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
        "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh"
        "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAAR"
        "CAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAA"
        "AAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMB"
        "AAIRAxEAPwCwAB//2Q=="
    )
    return base64.b64decode(jpeg_b64)


# =============================================================================
# ML FIXTURES
# =============================================================================

@pytest.fixture
def sample_features() -> Dict[str, float]:
    """Sample feature vector for ML tests"""
    return {
        "building_count": 15,
        "road_density": 0.75,
        "vegetation_index": 0.3,
        "population_density": 2500.0,
        "median_income": 45000.0,
        "crime_rate": 12.5,
        "vacancy_rate": 0.15,
        "distance_to_downtown": 5000.0,
        "building_age_mean": 65.0,
        "property_value_mean": 85000.0
    }


# =============================================================================
# ASYNC FIXTURES (if using async tests)
# =============================================================================

@pytest.fixture
async def async_client():
    """
    Async HTTP client for async API tests
    
    Usage:
        async def test_async_endpoint(async_client):
            response = await async_client.get('/api/v1/locations')
    """
    try:
        import httpx
        async with httpx.AsyncClient(base_url="http://test") as client:
            yield client
    except ImportError:
        pytest.skip("httpx not installed")


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def temp_directory(tmp_path):
    """
    Temporary directory for file tests
    
    pytest's tmp_path fixture provides a pathlib.Path
    that is automatically cleaned up after the test
    """
    return tmp_path


@pytest.fixture
def mock_current_time():
    """Mock current time for deterministic tests"""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# =============================================================================
# ERROR SIMULATION FIXTURES
# =============================================================================

@pytest.fixture
def network_error():
    """
    Fixture to simulate network errors in tests
    
    Usage:
        def test_handles_network_error(mock_db, network_error):
            with network_error:
                result = api_call_that_might_fail()
            assert result.error == "Network error"
    """
    from unittest.mock import patch
    
    class NetworkErrorContext:
        def __enter__(self):
            self.patcher = patch('requests.get', side_effect=ConnectionError())
            self.patcher.start()
        
        def __exit__(self, *args):
            self.patcher.stop()
    
    return NetworkErrorContext()
