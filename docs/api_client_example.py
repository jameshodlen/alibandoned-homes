"""
Example API Client

EDUCATIONAL: Building API Clients
=================================

Why Build a Client Library?
--------------------------
1. Easier for developers to integrate
2. Handles authentication consistently
3. Provides type hints and autocompletion
4. Encapsulates error handling
5. Can add retries, caching, logging

Best Practices:
--------------
1. Use requests/httpx for HTTP calls
2. Handle all status codes
3. Parse JSON responses
4. Raise custom exceptions
5. Support async if needed
6. Add comprehensive logging
7. Include retry logic with exponential backoff
"""

import requests
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
from datetime import datetime
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPTIONS
# =============================================================================

class APIError(Exception):
    """Base exception for API errors"""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class AuthenticationError(APIError):
    """401 Unauthorized"""
    pass


class AuthorizationError(APIError):
    """403 Forbidden"""
    pass


class NotFoundError(APIError):
    """404 Not Found"""
    pass


class ValidationError(APIError):
    """400 Bad Request"""
    pass


class RateLimitError(APIError):
    """429 Too Many Requests"""
    def __init__(self, message: str, retry_after: int = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ServerError(APIError):
    """5xx Server Error"""
    pass


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Location:
    """Location data model"""
    id: str
    latitude: float
    longitude: float
    address: Optional[str]
    confirmed: bool
    condition: str
    accessibility: str
    notes: Optional[str]
    confidence_score: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Location':
        """Create Location from API response dict"""
        return cls(
            id=data['id'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            address=data.get('address'),
            confirmed=data.get('confirmed', False),
            condition=data.get('condition', 'unknown'),
            accessibility=data.get('accessibility', 'moderate'),
            notes=data.get('notes'),
            confidence_score=data.get('confidence_score'),
            created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        )


@dataclass
class PredictionJob:
    """Prediction job status"""
    job_id: str
    status: str
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# =============================================================================
# API CLIENT
# =============================================================================

class AbandonedHomesClient:
    """
    Client for the Abandoned Homes Prediction API.
    
    EDUCATIONAL: Client Design Patterns
    -----------------------------------
    This client demonstrates several patterns:
    
    1. Builder Pattern (sort of):
       Configure client once, use many times
       
    2. Retry Pattern:
       Automatic retries with exponential backoff
       
    3. Circuit Breaker (conceptual):
       Could add to prevent hammering failing service
       
    4. Request/Response Logging:
       Log all API calls for debugging
       
    5. Error Mapping:
       Convert HTTP status to specific exceptions
    
    Usage:
        client = AbandonedHomesClient(
            base_url="http://localhost:8000",
            api_key="your-secret-key"
        )
        
        # Create location
        location = client.create_location(
            lat=42.3314,
            lon=-83.0458,
            condition="partial_collapse"
        )
        
        # List locations
        locations = client.list_locations(confirmed_only=True)
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize the API client.
        
        Args:
            base_url: API base URL (e.g., 'http://localhost:8000')
            api_key: Your API key
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            retry_delay: Initial retry delay (doubles each retry)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Create session for connection pooling
        # EDUCATIONAL: Session Benefits
        # - Connection reuse (faster)
        # - Cookie persistence
        # - Default headers for all requests
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        data: dict = None,
        files: dict = None,
        retry: bool = True
    ) -> Dict[str, Any]:
        """
        Make an API request with error handling and retries.
        
        EDUCATIONAL: Robust Request Handling
        -----------------------------------
        Steps:
        1. Build URL and prepare request
        2. Send request with timeout
        3. Check for rate limits (429)
        4. Check for errors (4xx, 5xx)
        5. Retry if appropriate (network errors, 5xx)
        6. Parse and return JSON
        """
        url = f"{self.base_url}/api/v1{endpoint}"
        
        attempts = 0
        last_error = None
        
        while attempts <= self.max_retries:
            try:
                logger.debug(f"Request: {method} {url}")
                
                # Prepare request kwargs
                kwargs = {
                    'timeout': self.timeout
                }
                
                if params:
                    kwargs['params'] = params
                
                if data and not files:
                    kwargs['json'] = data
                elif files:
                    # Remove Content-Type for multipart
                    headers = dict(self.session.headers)
                    del headers['Content-Type']
                    kwargs['headers'] = headers
                    kwargs['files'] = files
                    if data:
                        kwargs['data'] = data
                
                # Make request
                response = self.session.request(method, url, **kwargs)
                
                logger.debug(f"Response: {response.status_code}")
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    if retry and attempts < self.max_retries:
                        logger.warning(f"Rate limited. Waiting {retry_after}s...")
                        time.sleep(retry_after)
                        attempts += 1
                        continue
                    raise RateLimitError(
                        "Rate limit exceeded",
                        status_code=429,
                        retry_after=retry_after
                    )
                
                # Handle errors
                self._handle_error(response)
                
                # Return JSON or empty dict
                if response.status_code == 204:
                    return {}
                return response.json()
                
            except requests.exceptions.RequestException as e:
                # Network error - retry
                last_error = e
                if retry and attempts < self.max_retries:
                    delay = self.retry_delay * (2 ** attempts)  # Exponential backoff
                    logger.warning(f"Request failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                    attempts += 1
                    continue
                raise APIError(f"Network error: {e}")
        
        raise APIError(f"Max retries exceeded: {last_error}")
    
    def _handle_error(self, response: requests.Response):
        """
        Handle HTTP error responses.
        
        EDUCATIONAL: Error Handling Strategy
        -----------------------------------
        Map HTTP status codes to specific exceptions:
        - 400: Validation error (client's fault)
        - 401: Authentication error (missing/invalid key)
        - 403: Authorization error (no permission)
        - 404: Not found
        - 429: Rate limit (handled separately)
        - 5xx: Server error (not client's fault)
        """
        if response.status_code < 400:
            return  # No error
        
        try:
            error_data = response.json()
            message = error_data.get('detail', str(error_data))
        except:
            message = response.text or f"HTTP {response.status_code}"
        
        if response.status_code == 400:
            raise ValidationError(message, status_code=400)
        elif response.status_code == 401:
            raise AuthenticationError(message, status_code=401)
        elif response.status_code == 403:
            raise AuthorizationError(message, status_code=403)
        elif response.status_code == 404:
            raise NotFoundError(message, status_code=404)
        elif response.status_code >= 500:
            raise ServerError(message, status_code=response.status_code)
        else:
            raise APIError(message, status_code=response.status_code)
    
    # =========================================================================
    # HEALTH
    # =========================================================================
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        return self._request('GET', '/../health')  # Health is at root
    
    # =========================================================================
    # LOCATIONS
    # =========================================================================
    
    def create_location(
        self,
        lat: float,
        lon: float,
        confirmed: bool = False,
        condition: str = "unknown",
        accessibility: str = "moderate",
        address: str = None,
        notes: str = None
    ) -> Location:
        """
        Create a new location.
        
        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            confirmed: Whether location is verified
            condition: Building condition
            accessibility: Access difficulty
            address: Street address
            notes: Additional notes
            
        Returns:
            Created Location object
        """
        data = {
            'latitude': lat,
            'longitude': lon,
            'confirmed': confirmed,
            'condition': condition,
            'accessibility': accessibility
        }
        
        if address:
            data['address'] = address
        if notes:
            data['notes'] = notes
        
        response = self._request('POST', '/locations/', data=data)
        return Location.from_dict(response)
    
    def get_location(self, location_id: str) -> Location:
        """Get a single location by ID"""
        response = self._request('GET', f'/locations/{location_id}')
        return Location.from_dict(response)
    
    def list_locations(
        self,
        skip: int = 0,
        limit: int = 100,
        confirmed_only: bool = False,
        condition: str = None,
        min_confidence: float = None,
        bbox: str = None
    ) -> List[Location]:
        """
        List locations with optional filters.
        
        Args:
            skip: Records to skip (pagination)
            limit: Max records to return
            confirmed_only: Only confirmed locations
            condition: Filter by condition
            min_confidence: Minimum confidence score
            bbox: Bounding box (min_lon,min_lat,max_lon,max_lat)
            
        Returns:
            List of Location objects
        """
        params = {'skip': skip, 'limit': limit}
        
        if confirmed_only:
            params['confirmed_only'] = 'true'
        if condition:
            params['condition'] = condition
        if min_confidence:
            params['min_confidence'] = min_confidence
        if bbox:
            params['bbox'] = bbox
        
        response = self._request('GET', '/locations/', params=params)
        return [Location.from_dict(loc) for loc in response.get('items', [])]
    
    def delete_location(self, location_id: str) -> None:
        """Delete a location"""
        self._request('DELETE', f'/locations/{location_id}')
    
    def add_feedback(self, location_id: str, feedback: str) -> Dict[str, Any]:
        """Add feedback to a location"""
        return self._request(
            'PUT',
            f'/locations/{location_id}/feedback',
            params={'feedback': feedback}
        )
    
    # =========================================================================
    # PREDICTIONS
    # =========================================================================
    
    def predict_area(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float,
        resolution_meters: int = 100,
        threshold: float = 0.5
    ) -> str:
        """
        Start area prediction job.
        
        Args:
            center_lat: Center latitude
            center_lon: Center longitude
            radius_km: Search radius in kilometers
            resolution_meters: Grid resolution
            threshold: Probability threshold
            
        Returns:
            str: Job ID for status polling
        """
        data = {
            'center_lat': center_lat,
            'center_lon': center_lon,
            'radius_km': radius_km,
            'resolution_meters': resolution_meters,
            'threshold': threshold
        }
        
        response = self._request('POST', '/predictions/predict-area', data=data)
        return response['job_id']
    
    def get_prediction_status(self, job_id: str) -> PredictionJob:
        """Get prediction job status"""
        response = self._request('GET', f'/predictions/{job_id}')
        return PredictionJob(
            job_id=response['job_id'],
            status=response['status'],
            progress=response.get('progress', 0),
            result=response.get('result'),
            error=response.get('error')
        )
    
    def wait_for_prediction(
        self,
        job_id: str,
        poll_interval: float = 5.0,
        timeout: float = 300.0
    ) -> PredictionJob:
        """
        Wait for prediction job to complete.
        
        EDUCATIONAL: Polling Pattern
        ---------------------------
        For long-running operations:
        1. Start job (returns job_id)
        2. Poll status endpoint periodically
        3. Stop when status is terminal (completed/failed)
        4. Handle timeout
        
        Args:
            job_id: Job ID to wait for
            poll_interval: Seconds between status checks
            timeout: Max seconds to wait
            
        Returns:
            Final job status
        """
        start_time = time.time()
        
        while True:
            status = self.get_prediction_status(job_id)
            
            if status.status in ('completed', 'failed'):
                return status
            
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"Prediction job {job_id} timed out after {timeout}s")
            
            logger.info(f"Job {job_id}: {status.status} ({status.progress:.0%})")
            time.sleep(poll_interval)
    
    # =========================================================================
    # ADMIN
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return self._request('GET', '/admin/stats')
    
    def list_models(self) -> Dict[str, Any]:
        """List trained model versions"""
        return self._request('GET', '/admin/models')


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

if __name__ == "__main__":
    # Example usage
    print("=" * 60)
    print("Abandoned Homes API Client Example")
    print("=" * 60)
    
    # Create client
    client = AbandonedHomesClient(
        base_url="http://localhost:8000",
        api_key="your-api-key-here"
    )
    
    print("\n1. Health Check")
    print("-" * 40)
    try:
        health = client.health_check()
        print(f"Status: {health.get('status')}")
        print(f"Version: {health.get('version')}")
    except APIError as e:
        print(f"Error: {e.message}")
    
    print("\n2. Create Location")
    print("-" * 40)
    try:
        location = client.create_location(
            lat=42.3314,
            lon=-83.0458,
            condition="partial_collapse",
            accessibility="moderate",
            address="123 Test St, Detroit, MI",
            notes="Example location"
        )
        print(f"Created: {location.id}")
        print(f"Coordinates: ({location.latitude}, {location.longitude})")
    except ValidationError as e:
        print(f"Validation Error: {e.message}")
    except AuthenticationError as e:
        print(f"Auth Error: {e.message}")
    
    print("\n3. List Locations")
    print("-" * 40)
    try:
        locations = client.list_locations(limit=5, confirmed_only=False)
        print(f"Found {len(locations)} locations")
        for loc in locations[:3]:
            print(f"  - {loc.id}: ({loc.latitude}, {loc.longitude})")
    except APIError as e:
        print(f"Error: {e.message}")
    
    print("\n4. Start Prediction")
    print("-" * 40)
    try:
        job_id = client.predict_area(
            center_lat=42.3314,
            center_lon=-83.0458,
            radius_km=5.0
        )
        print(f"Job started: {job_id}")
        
        # Wait for completion
        result = client.wait_for_prediction(job_id, timeout=60)
        print(f"Status: {result.status}")
        if result.result:
            print(f"Found {result.result.get('count', 'unknown')} predictions")
    except RateLimitError as e:
        print(f"Rate limited. Retry after {e.retry_after}s")
    except TimeoutError as e:
        print(f"Timeout: {e}")
    
    print("\n5. System Stats")
    print("-" * 40)
    try:
        stats = client.get_stats()
        print(f"Total locations: {stats['locations']['total']}")
        print(f"Confirmed: {stats['locations']['confirmed']}")
    except APIError as e:
        print(f"Error: {e.message}")
    
    print("\n" + "=" * 60)
    print("Example complete!")
