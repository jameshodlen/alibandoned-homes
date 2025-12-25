# API Testing Guide

Comprehensive testing guide for the Abandoned Homes Prediction API.

## Testing Philosophy

**Test Pyramid:**

```
        /\
       /  \      E2E Tests (few, slow, high confidence)
      /----\
     /      \    Integration Tests (API endpoints)
    /--------\
   /          \  Unit Tests (many, fast, low confidence)
  --------------
```

**What to Test:**

- ✅ Happy paths (success cases)
- ✅ Error cases (validation, not found)
- ✅ Edge cases (empty data, max limits)
- ✅ Security (authentication, authorization)
- ✅ Rate limiting

---

## Unit Tests

### Setup

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=api --cov-report=html
```

### Example Test Structure

```python
# tests/test_locations.py
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

# Fixtures
@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-api-key"}

@pytest.fixture
def sample_location():
    return {
        "latitude": 42.3314,
        "longitude": -83.0458,
        "condition": "partial_collapse",
        "accessibility": "moderate"
    }
```

### Testing Success Cases

```python
def test_create_location_success(auth_headers, sample_location):
    """Test successful location creation"""
    response = client.post(
        "/api/v1/locations/",
        json=sample_location,
        headers=auth_headers
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["latitude"] == sample_location["latitude"]
    assert data["longitude"] == sample_location["longitude"]


def test_list_locations_success(auth_headers):
    """Test listing locations"""
    response = client.get(
        "/api/v1/locations/",
        params={"limit": 10},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
```

### Testing Validation Errors

```python
def test_create_location_invalid_latitude(auth_headers):
    """Test validation rejects invalid latitude"""
    response = client.post(
        "/api/v1/locations/",
        json={
            "latitude": 100,  # Invalid: > 90
            "longitude": -83.0458,
            "condition": "intact",
            "accessibility": "easy"
        },
        headers=auth_headers
    )

    assert response.status_code == 400
    assert "latitude" in response.json()["detail"].lower()


def test_create_location_missing_required_field(auth_headers):
    """Test validation requires mandatory fields"""
    response = client.post(
        "/api/v1/locations/",
        json={"latitude": 42.0},  # Missing longitude
        headers=auth_headers
    )

    assert response.status_code == 422  # Pydantic validation error
```

### Testing Authentication

```python
def test_create_location_missing_auth():
    """Test 401 when API key missing"""
    response = client.post(
        "/api/v1/locations/",
        json={"latitude": 42.0, "longitude": -83.0}
    )

    assert response.status_code == 401


def test_create_location_invalid_auth():
    """Test 401 when API key invalid"""
    response = client.post(
        "/api/v1/locations/",
        json={"latitude": 42.0, "longitude": -83.0},
        headers={"X-API-Key": "invalid-key"}
    )

    assert response.status_code == 401
```

### Testing Not Found

```python
def test_get_location_not_found(auth_headers):
    """Test 404 for non-existent location"""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(
        f"/api/v1/locations/{fake_id}",
        headers=auth_headers
    )

    assert response.status_code == 404
```

---

## Integration Tests

### Testing Full Workflows

```python
def test_full_location_workflow(auth_headers):
    """Test complete workflow: create → list → update → delete"""

    # 1. Create
    create_resp = client.post(
        "/api/v1/locations/",
        json={
            "latitude": 42.3314,
            "longitude": -83.0458,
            "condition": "partial_collapse",
            "accessibility": "moderate"
        },
        headers=auth_headers
    )
    assert create_resp.status_code == 201
    location_id = create_resp.json()["id"]

    # 2. Read
    get_resp = client.get(
        f"/api/v1/locations/{location_id}",
        headers=auth_headers
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == location_id

    # 3. List (should include new location)
    list_resp = client.get(
        "/api/v1/locations/",
        headers=auth_headers
    )
    assert any(loc["id"] == location_id for loc in list_resp.json()["items"])

    # 4. Add feedback
    feedback_resp = client.put(
        f"/api/v1/locations/{location_id}/feedback",
        params={"feedback": "confirmed"},
        headers=auth_headers
    )
    assert feedback_resp.status_code == 200

    # 5. Delete
    delete_resp = client.delete(
        f"/api/v1/locations/{location_id}",
        headers=auth_headers
    )
    assert delete_resp.status_code == 204

    # 6. Verify deleted
    verify_resp = client.get(
        f"/api/v1/locations/{location_id}",
        headers=auth_headers
    )
    assert verify_resp.status_code == 404


def test_prediction_workflow(auth_headers):
    """Test prediction job workflow"""

    # 1. Start prediction
    start_resp = client.post(
        "/api/v1/predictions/predict-area",
        json={
            "center_lat": 42.3314,
            "center_lon": -83.0458,
            "radius_km": 5.0
        },
        headers=auth_headers
    )
    assert start_resp.status_code == 202
    job_id = start_resp.json()["job_id"]

    # 2. Check status
    status_resp = client.get(
        f"/api/v1/predictions/{job_id}",
        headers=auth_headers
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] in ["pending", "processing", "completed"]
```

---

## Load Testing

### Using Apache Bench

```bash
# Simple load test: 1000 requests, 10 concurrent
ab -n 1000 -c 10 -H "X-API-Key: test-key" \
   http://localhost:8000/api/v1/locations/
```

### Using Locust

```python
# tests/load_test.py
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 5)

    def on_start(self):
        self.headers = {"X-API-Key": "test-key"}

    @task(10)
    def list_locations(self):
        self.client.get(
            "/api/v1/locations/",
            headers=self.headers
        )

    @task(3)
    def create_location(self):
        self.client.post(
            "/api/v1/locations/",
            json={
                "latitude": 42.3314,
                "longitude": -83.0458,
                "condition": "intact",
                "accessibility": "easy"
            },
            headers=self.headers
        )

    @task(1)
    def predict_area(self):
        self.client.post(
            "/api/v1/predictions/predict-area",
            json={
                "center_lat": 42.3314,
                "center_lon": -83.0458,
                "radius_km": 5.0
            },
            headers=self.headers
        )
```

**Run Locust:**

```bash
locust -f tests/load_test.py --host=http://localhost:8000
# Open http://localhost:8089 in browser
```

---

## Security Testing

### Test Rate Limiting

```python
def test_rate_limiting():
    """Test that rate limits are enforced"""
    headers = {"X-API-Key": "test-key"}

    # Make many rapid requests
    responses = []
    for _ in range(150):  # Exceed limit
        resp = client.get("/api/v1/locations/", headers=headers)
        responses.append(resp.status_code)

    # Should eventually get 429
    assert 429 in responses
```

### Test Input Validation

```python
def test_sql_injection_prevention(auth_headers):
    """Test SQL injection is prevented"""
    malicious_input = "'; DROP TABLE locations; --"

    response = client.post(
        "/api/v1/locations/",
        json={
            "latitude": 42.0,
            "longitude": -83.0,
            "notes": malicious_input,
            "condition": "intact",
            "accessibility": "easy"
        },
        headers=auth_headers
    )

    # Should either sanitize or reject, not crash
    assert response.status_code in [201, 400]


def test_path_traversal_prevention(auth_headers):
    """Test path traversal in file uploads"""
    malicious_filename = "../../../etc/passwd"

    # Create test file
    files = {"files": (malicious_filename, b"test content", "image/jpeg")}

    response = client.post(
        "/api/v1/photos/test-location-id/upload",
        files=files,
        headers=auth_headers
    )

    # Should sanitize filename or reject
    if response.status_code == 200:
        result = response.json()
        # Filename should be sanitized
        assert ".." not in result[0].get("file_path", "")
```

---

## Test Configuration

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
asyncio_mode = auto
addopts = -v --tb=short
```

### conftest.py

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from database.base import Base

# Test database
TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture(scope="session")
def test_db():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-api-key"}
```

---

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgis/postgis:15-3.3
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost/test_db
          API_KEY: test-key
        run: |
          pytest tests/ --cov=api --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Best Practices

1. **Isolate tests**: Each test should be independent
2. **Clean up**: Reset state after each test
3. **Use fixtures**: Share common setup/teardown
4. **Test edge cases**: Empty inputs, max values, Unicode
5. **Test errors**: Don't just test happy paths
6. **Fast tests**: Unit tests should run in milliseconds
7. **Meaningful names**: `test_create_location_with_invalid_latitude`
8. **Single assertion focus**: One concept per test
9. **Mock external services**: Don't hit real APIs in tests
10. **Run automatically**: CI/CD on every commit
