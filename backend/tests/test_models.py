"""
Unit tests for database models.

=============================================================================
TESTING PYRAMID
=============================================================================

    /\      E2E Tests (10%)
   /  \     - Full system tests
  /----\    - Slow, expensive
 /      \   
/--------\  Integration Tests (20%)
|        |  - Components working together
|--------|  - Test database, API calls
|        |
|--------|  Unit Tests (70%)
|        |  - Individual functions/classes
|________|  - Fast, isolated, specific

Unit Tests:
- Fast (milliseconds)
- Isolated (no external dependencies)
- Specific (test one thing)
- Form the foundation of your test suite

=============================================================================
TEST-DRIVEN DEVELOPMENT (TDD)
=============================================================================

The TDD Cycle (Red-Green-Refactor):
1. RED: Write a failing test first
2. GREEN: Write minimal code to make test pass
3. REFACTOR: Improve code while keeping tests green

Benefits:
- Forces you to think about requirements first
- Produces testable, modular code
- Documentation through tests
- Confidence when refactoring
=============================================================================
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

# Note: In a real project, these would be actual imports from your models
# from database.models import Location, Photo, ModelVersion
# from geoalchemy2.elements import WKTElement

# For demonstration, we'll create mock classes
class Location:
    """Mock Location model for testing demonstration"""
    VALID_CONDITIONS = ['intact', 'partial_collapse', 'full_collapse']
    VALID_ACCESSIBILITY = ['easy', 'moderate', 'difficult', 'dangerous']
    
    def __init__(self, latitude=None, longitude=None, address=None, 
                 confirmed=False, condition='intact', accessibility='easy', notes=None):
        self.id = uuid4()
        self.latitude = latitude
        self.longitude = longitude
        self.address = address
        self.confirmed = confirmed
        self.condition = condition
        self.accessibility = accessibility
        self.notes = notes
        self.created_at = datetime.now(timezone.utc)
        
        # Validation
        if condition and condition not in self.VALID_CONDITIONS:
            raise ValueError(f"Invalid condition: {condition}")
        if accessibility and accessibility not in self.VALID_ACCESSIBILITY:
            raise ValueError(f"Invalid accessibility: {accessibility}")
        if latitude is not None and (latitude < -90 or latitude > 90):
            raise ValueError(f"Invalid latitude: {latitude}")
        if longitude is not None and (longitude < -180 or longitude > 180):
            raise ValueError(f"Invalid longitude: {longitude}")
    
    def is_abandoned(self):
        """Check if location is considered abandoned"""
        return self.condition in ['partial_collapse', 'full_collapse']
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address': self.address,
            'confirmed': self.confirmed,
            'condition': self.condition,
            'accessibility': self.accessibility,
            'notes': self.notes,
        }


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_location():
    """
    Fixture: Reusable test data
    
    Fixtures provide:
    - Consistent test data across tests
    - Setup/teardown automation
    - Code reuse across tests
    - Dependency injection for tests
    
    Scope options:
    - function (default): Run for each test
    - class: Run once per test class
    - module: Run once per file
    - session: Run once for entire test session
    """
    return Location(
        latitude=42.3314,
        longitude=-83.0458,
        address="123 Main St, Detroit, MI",
        confirmed=True,
        condition="partial_collapse",
        accessibility="moderate",
        notes="Test location for unit tests"
    )


@pytest.fixture
def abandoned_location():
    """Fixture for a confirmed abandoned location"""
    return Location(
        latitude=42.3500,
        longitude=-83.0600,
        address="456 Oak Ave, Detroit, MI",
        confirmed=True,
        condition="full_collapse",
        accessibility="dangerous",
        notes="Building condemned 2020"
    )


@pytest.fixture
def intact_location():
    """Fixture for a non-abandoned location"""
    return Location(
        latitude=42.3400,
        longitude=-83.0500,
        address="789 Elm St, Detroit, MI",
        confirmed=True,
        condition="intact",
        accessibility="easy"
    )


# =============================================================================
# BASIC UNIT TESTS
# =============================================================================

class TestLocationCreation:
    """
    Test class: Group related tests together
    
    Benefits:
    - Logical organization
    - Shared fixtures via class scope
    - Easy to run subset of tests
    """
    
    def test_location_instantiation(self, sample_location):
        """Test that Location can be created with valid data"""
        # ASSERT: Check if condition is true, fails test if false
        assert sample_location.address == "123 Main St, Detroit, MI"
        assert sample_location.confirmed == True
        assert sample_location.condition == "partial_collapse"
        assert sample_location.id is not None
    
    def test_location_has_timestamp(self, sample_location):
        """Test that created_at is automatically set"""
        assert sample_location.created_at is not None
        assert isinstance(sample_location.created_at, datetime)
    
    def test_location_coordinates(self, sample_location):
        """Test coordinate values are stored correctly"""
        assert sample_location.latitude == 42.3314
        assert sample_location.longitude == -83.0458
    
    def test_location_to_dict(self, sample_location):
        """Test serialization to dictionary"""
        data = sample_location.to_dict()
        
        assert isinstance(data, dict)
        assert 'id' in data
        assert data['address'] == "123 Main St, Detroit, MI"
        assert data['latitude'] == 42.3314


# =============================================================================
# VALIDATION TESTS (Negative Testing)
# =============================================================================

class TestLocationValidation:
    """
    Negative tests: Verify errors are caught correctly
    
    Testing edge cases and invalid inputs is crucial:
    - Prevents bugs from reaching production
    - Documents expected constraints
    - Protects data integrity
    """
    
    def test_invalid_condition_raises_error(self):
        """Test that invalid condition values are rejected"""
        with pytest.raises(ValueError) as exc_info:
            Location(
                latitude=42.0,
                longitude=-83.0,
                condition="invalid_value"
            )
        
        # Check error message contains useful info
        assert "condition" in str(exc_info.value).lower()
    
    def test_invalid_accessibility_raises_error(self):
        """Test that invalid accessibility values are rejected"""
        with pytest.raises(ValueError):
            Location(
                latitude=42.0,
                longitude=-83.0,
                accessibility="impossible"
            )
    
    def test_latitude_out_of_range_high(self):
        """Test latitude > 90 is rejected"""
        with pytest.raises(ValueError) as exc_info:
            Location(latitude=100, longitude=-83.0)
        
        assert "latitude" in str(exc_info.value).lower()
    
    def test_latitude_out_of_range_low(self):
        """Test latitude < -90 is rejected"""
        with pytest.raises(ValueError):
            Location(latitude=-100, longitude=-83.0)
    
    def test_longitude_out_of_range(self):
        """Test longitude outside -180 to 180 is rejected"""
        with pytest.raises(ValueError):
            Location(latitude=42.0, longitude=200)


# =============================================================================
# PARAMETERIZED TESTS
# =============================================================================

@pytest.mark.parametrize("condition,expected", [
    ("intact", False),
    ("partial_collapse", True),
    ("full_collapse", True),
])
def test_is_abandoned_returns_correct_value(condition, expected):
    """
    Parameterized test: Run same test with different inputs
    
    Benefits:
    - Test multiple cases concisely
    - Easy to add new test cases
    - Clear input/output mapping
    - Reduces code duplication
    
    Each tuple creates a separate test case:
    - test_is_abandoned_returns_correct_value[intact-False]
    - test_is_abandoned_returns_correct_value[partial_collapse-True]
    - test_is_abandoned_returns_correct_value[full_collapse-True]
    """
    location = Location(
        latitude=42.0,
        longitude=-83.0,
        condition=condition,
        confirmed=True
    )
    assert location.is_abandoned() == expected


@pytest.mark.parametrize("lat,lon,should_pass", [
    (0, 0, True),           # Origin
    (90, 180, True),        # Max values
    (-90, -180, True),      # Min values
    (42.3314, -83.0458, True),  # Detroit
    (91, 0, False),         # Invalid lat
    (0, 181, False),        # Invalid lon
])
def test_coordinate_validation(lat, lon, should_pass):
    """Test various coordinate combinations"""
    if should_pass:
        loc = Location(latitude=lat, longitude=lon)
        assert loc.latitude == lat
        assert loc.longitude == lon
    else:
        with pytest.raises(ValueError):
            Location(latitude=lat, longitude=lon)


# =============================================================================
# FIXTURE USAGE EXAMPLES
# =============================================================================

def test_multiple_fixtures(sample_location, abandoned_location, intact_location):
    """
    Tests can use multiple fixtures
    
    Pytest automatically injects fixtures based on parameter names.
    This is called "dependency injection."
    """
    # All three locations should have unique IDs
    ids = {sample_location.id, abandoned_location.id, intact_location.id}
    assert len(ids) == 3
    
    # Different conditions
    assert sample_location.condition == "partial_collapse"
    assert abandoned_location.condition == "full_collapse"
    assert intact_location.condition == "intact"


# =============================================================================
# MARKERS FOR TEST ORGANIZATION
# =============================================================================

@pytest.mark.unit
def test_marked_as_unit():
    """
    Markers help organize and filter tests
    
    Run only unit tests: pytest -m unit
    Skip slow tests: pytest -m "not slow"
    
    Common markers:
    - @pytest.mark.unit
    - @pytest.mark.integration
    - @pytest.mark.slow
    - @pytest.mark.skip(reason="...")
    - @pytest.mark.xfail (expected to fail)
    """
    loc = Location(latitude=42.0, longitude=-83.0)
    assert loc is not None


@pytest.mark.slow
def test_marked_as_slow():
    """
    Mark slow tests to skip during rapid development
    
    Run all tests: pytest
    Skip slow tests: pytest -m "not slow"
    Only slow tests: pytest -m slow
    """
    import time
    time.sleep(0.1)  # Simulate slow operation
    assert True


# =============================================================================
# TESTING BEST PRACTICES
# =============================================================================

"""
TESTING BEST PRACTICES SUMMARY:

1. AAA Pattern (Arrange-Act-Assert):
   - Arrange: Set up test data and conditions
   - Act: Perform the action being tested
   - Assert: Verify the expected outcome

2. One Assertion Per Test:
   - Each test should verify ONE behavior
   - Makes failures easy to diagnose
   - Exception: Related assertions can be grouped

3. Descriptive Test Names:
   - test_<what>_<condition>_<expected_result>
   - Example: test_is_abandoned_when_collapsed_returns_true

4. Test Independence:
   - Tests should not depend on each other
   - Each test should set up its own data
   - Use fixtures for reusable setup

5. Fast Tests:
   - Unit tests should run in milliseconds
   - Mock external dependencies
   - Use in-memory databases for speed

6. Meaningful Assertions:
   - Check what matters, not implementation details
   - Use descriptive error messages

7. Coverage Goals:
   - Aim for 80%+ code coverage
   - 100% is not always necessary or practical
   - Focus on critical paths and edge cases
"""
