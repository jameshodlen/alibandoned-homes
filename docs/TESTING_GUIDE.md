# Testing Guide

## Overview

This guide covers testing strategies, tools, and best practices for the Abandoned Homes application.

## Testing Pyramid

```
        /\      E2E Tests (10%)
       /  \     Full user workflows
      /----\
     /      \   Integration Tests (20%)
    /--------\  Components + database
   /          \
  /------------\  Unit Tests (70%)
 /______________\ Fast, isolated, specific
```

## Quick Start

### Backend Tests (Python)

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov --cov-report=html

# Run only unit tests (fast)
pytest -m unit

# Run specific file
pytest tests/test_models.py

# Run specific test
pytest tests/test_models.py::test_location_creation -v

# Skip slow tests
pytest -m "not slow"

# Verbose output with print statements
pytest -v -s
```

### Frontend Tests (Jest)

```bash
cd frontend

# Run all tests
npm test

# Watch mode (re-run on changes)
npm test -- --watch

# With coverage
npm test -- --coverage

# Specific file
npm test -- MapView.test.jsx
```

### E2E Tests (Cypress)

```bash
cd frontend

# Interactive mode
npm run cypress:open

# Headless mode
npm run cypress:run

# Single spec
npm run cypress:run -- --spec "cypress/e2e/workflow.cy.js"
```

## Writing Tests

### AAA Pattern

```python
def test_example():
    # ARRANGE - Set up data
    location = create_test_location()

    # ACT - Perform action
    result = location.is_abandoned()

    # ASSERT - Check result
    assert result == True
```

### Fixtures

Fixtures provide reusable test data:

```python
@pytest.fixture
def sample_location():
    return Location(
        latitude=42.33,
        longitude=-83.04,
        condition="partial_collapse"
    )

def test_uses_fixture(sample_location):
    assert sample_location.condition == "partial_collapse"
```

### Parameterized Tests

Test multiple inputs with one function:

```python
@pytest.mark.parametrize("condition,expected", [
    ("intact", False),
    ("partial_collapse", True),
    ("full_collapse", True),
])
def test_is_abandoned(condition, expected):
    loc = Location(condition=condition)
    assert loc.is_abandoned() == expected
```

### Mocking

Replace external dependencies:

```python
from unittest.mock import Mock, patch

def test_api_call():
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {"data": "test"}
        result = my_api_function()
        assert result["data"] == "test"
```

## Code Coverage

Coverage measures tested code percentage.

**View coverage report:**

```bash
pytest --cov --cov-report=html
open htmlcov/index.html
```

**Coverage targets:**

- Unit tests: 90%+
- Integration: 70%+
- Overall: 80%+

## Debugging Failed Tests

1. **Read error message** - What assertion failed?
2. **Run single test** - `pytest tests/file.py::test_name -v`
3. **Add print statements** - Use `-s` flag to see output
4. **Use debugger** - `pytest --pdb` drops into debugger on failure
5. **Check fixtures** - Ensure test data is correct

## CI/CD Integration

Tests run automatically on GitHub Actions:

- **Push to main/develop**: Full test suite
- **Pull requests**: All tests + coverage report
- **Nightly**: E2E tests + security scans

See `.github/workflows/test.yml` for configuration.

## Best Practices

1. **Test behavior, not implementation** - Focus on what code does, not how
2. **One assertion per test** - Easier to debug failures
3. **Descriptive names** - `test_invalid_coordinates_rejected`
4. **Independent tests** - Don't rely on test order
5. **Fast feedback** - Run unit tests frequently during development
6. **Mock external services** - Don't hit real APIs in tests
