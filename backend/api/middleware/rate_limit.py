"""
Advanced Rate Limiting Configuration

EDUCATIONAL: Rate Limiting Deep Dive
====================================

Why Rate Limiting?
-----------------
1. PREVENT ABUSE: Stop API spam and scraping
2. PREVENT DoS: Limit resource consumption per client
3. CONTROL COSTS: Expensive operations (ML) need limits
4. FAIR USAGE: Ensure all users get reasonable access
5. PROTECT INFRASTRUCTURE: Don't overwhelm database/servers

Rate Limiting Algorithms:
------------------------

1. FIXED WINDOW
   - Simple: Count requests per time window
   - Example: 100 requests per hour (resets at hour boundary)
   - Pros: Simple, low memory
   - Cons: Burst at window boundaries (200 requests in 1 minute if timed right)
   
   Timeline:
   [-------- Hour 1 --------][-------- Hour 2 --------]
   User waits →           99 requests here   + 100 here = 199 in 1 min!

2. SLIDING WINDOW
   - Counts requests in rolling time period
   - Example: 100 requests in last 60 minutes
   - Pros: No boundary burst problem
   - Cons: More memory (stores timestamps)
   
3. TOKEN BUCKET
   - Bucket holds tokens, request consumes token
   - Tokens refill at constant rate
   - Allows bursts (up to bucket size)
   - Example: Bucket size 10, refill 1/second
   
   Visualization:
   [🪣 10 tokens]  →  User takes 5  →  [🪣 5 tokens]
         ↑                                    ↓
   Refills 1/sec                      Wait or use 5 more

4. LEAKY BUCKET
   - Requests enter bucket, processed at fixed rate
   - If bucket full, requests rejected
   - Smooths traffic (constant output rate)

Response Headers (Standard):
---------------------------
X-RateLimit-Limit: 100       # Max requests allowed
X-RateLimit-Remaining: 73    # Requests left in window
X-RateLimit-Reset: 1640000   # Unix timestamp when window resets
Retry-After: 60              # Seconds to wait (when limited)
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response, HTTPException
from starlette.responses import JSONResponse
from typing import Callable, Optional
import time
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# RATE LIMIT KEY FUNCTIONS
# =============================================================================

def get_ip_address(request: Request) -> str:
    """
    Get client IP address for rate limiting.
    
    EDUCATIONAL: IP Detection
    ------------------------
    Challenge: Proxies/load balancers hide real client IP.
    
    Request flow:
    Client → Proxy → Load Balancer → API Server
    
    request.client.host = Load balancer IP (wrong!)
    X-Forwarded-For = Real client IP
    
    Trust order:
    1. X-Real-IP (set by trusted proxy)
    2. X-Forwarded-For (first IP if trusted)
    3. request.client.host (fallback)
    
    SECURITY WARNING:
    X-Forwarded-For can be spoofed by clients!
    Only trust it if you control the proxy.
    """
    # Check for proxy headers (only trust if behind known proxy)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For: client, proxy1, proxy2
        # First IP is the client
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    # Direct connection
    return request.client.host if request.client else "unknown"


def get_api_key(request: Request) -> str:
    """
    Get API key for per-user rate limiting.
    
    EDUCATIONAL: Per-User vs Per-IP Limiting
    ----------------------------------------
    Per-IP:
    - Simple
    - Problem: Users behind NAT share limit
    - Problem: Attacker uses multiple IPs
    
    Per-API-Key:
    - Fair per-user limiting
    - Can have tiered limits (free vs paid)
    - Requires authentication
    
    Combined:
    - Per-IP for unauthenticated
    - Per-API-Key for authenticated
    """
    return request.headers.get("x-api-key", "anonymous")


def get_combined_key(request: Request) -> str:
    """
    Combine API key and IP for rate limiting.
    
    This allows:
    - Same API key from different IPs: Each IP counted separately
    - Helps prevent credential sharing abuse
    """
    api_key = get_api_key(request)
    ip = get_ip_address(request)
    return f"{api_key}:{ip}"


def get_endpoint_key(request: Request) -> str:
    """
    Rate limit by endpoint + API key.
    
    Allows different limits per endpoint type:
    - GET endpoints: Higher limit (cheap)
    - POST endpoints: Lower limit (creates data)
    - ML endpoints: Very low limit (expensive)
    """
    api_key = get_api_key(request)
    path = request.url.path
    return f"{api_key}:{path}"


# =============================================================================
# LIMITER CONFIGURATION
# =============================================================================

# EDUCATIONAL: Rate Limit Format
# 
# Format: "count/period"
# Periods: second, minute, hour, day
# Examples:
#   "100/minute" = 100 requests per minute
#   "5/hour" = 5 requests per hour
#   "1000/day" = 1000 requests per day

# Default limiter (per-IP)
limiter = Limiter(
    key_func=get_ip_address,
    default_limits=["100/minute"],
    storage_uri="memory://",  # In-memory (use Redis for production)
)


# =============================================================================
# RATE LIMIT CONFIGURATIONS
# =============================================================================

class RateLimitConfig:
    """
    Centralized rate limit configurations.
    
    EDUCATIONAL: Tiered Rate Limiting
    --------------------------------
    Different operations have different costs:
    
    | Operation        | Cost   | Limit      |
    |-----------------|--------|------------|
    | GET (read)      | Low    | 100/min    |
    | POST (create)   | Medium | 20/min     |
    | PUT (update)    | Medium | 20/min     |
    | DELETE          | Medium | 10/min     |
    | ML Prediction   | High   | 5/hour     |
    | Export/Reports  | High   | 3/hour     |
    | Authentication  | Special| 5/minute   |
    """
    
    # General endpoints
    READ = "100/minute"      # GET requests
    WRITE = "20/minute"      # POST/PUT requests
    DELETE = "10/minute"     # DELETE requests
    
    # Expensive operations
    ML_PREDICTION = "5/hour"     # ML predictions
    EXPORT = "3/hour"            # Large data exports
    BULK_OPERATIONS = "5/hour"   # Bulk create/update
    
    # Security-sensitive
    AUTH_ATTEMPT = "5/minute"    # Login attempts
    PASSWORD_RESET = "3/hour"    # Password reset requests
    API_KEY_GENERATE = "3/day"   # New API key generation
    
    # Admin endpoints
    ADMIN_STATS = "30/minute"    # Dashboard stats
    ADMIN_ACTIONS = "10/minute"  # Admin operations


# =============================================================================
# CUSTOM RATE LIMIT HANDLER
# =============================================================================

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Handle rate limit exceeded errors.
    
    EDUCATIONAL: Rate Limit Response
    --------------------------------
    When limit exceeded:
    1. Return 429 Too Many Requests
    2. Include Retry-After header
    3. Include rate limit headers
    4. Log for monitoring
    
    Headers help clients:
    - Know when they can retry
    - Implement proper backoff
    - Display user-friendly message
    """
    # Log the rate limit hit
    logger.warning(
        f"Rate limit exceeded: {get_ip_address(request)} on {request.url.path}"
    )
    
    # Calculate retry time
    # Note: This is simplified; actual retry time depends on algorithm
    retry_after = 60  # seconds
    
    response = JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded: {exc.detail}",
            "retry_after": retry_after
        }
    )
    
    # Add standard rate limit headers
    response.headers["Retry-After"] = str(retry_after)
    response.headers["X-RateLimit-Limit"] = str(exc.detail.split()[0])
    response.headers["X-RateLimit-Remaining"] = "0"
    
    return response


# =============================================================================
# RATE LIMITING DECORATORS
# =============================================================================

def rate_limit(limit: str = RateLimitConfig.READ):
    """
    Decorator for rate limiting endpoints.
    
    Usage:
        @router.get("/locations")
        @rate_limit("100/minute")
        async def list_locations():
            ...
    """
    return limiter.limit(limit)


def rate_limit_by_user(limit: str = RateLimitConfig.READ):
    """
    Decorator for per-user rate limiting.
    
    Uses API key instead of IP for authenticated users.
    Falls back to IP for unauthenticated requests.
    """
    return limiter.limit(limit, key_func=get_api_key)


def rate_limit_expensive(limit: str = RateLimitConfig.ML_PREDICTION):
    """
    Decorator for expensive operations.
    
    Uses combined key (API key + IP) for stricter limiting.
    """
    return limiter.limit(limit, key_func=get_combined_key)


# =============================================================================
# RATE LIMITING STRATEGIES BY USE CASE
# =============================================================================

"""
EDUCATIONAL: Rate Limiting Strategies

1. PUBLIC API (no auth):
   - Per-IP limiting
   - Generous limits for reads
   - Strict limits for writes
   - Consider: CAPTCHA for abuse

2. AUTHENTICATED API:
   - Per-API-Key limiting
   - Tiered by plan (free/pro/enterprise)
   - Higher limits for paying customers

3. INTERNAL API:
   - Higher limits (trusted services)
   - Monitor for anomalies
   - Still limit to prevent cascading failures

4. ML/COMPUTING ENDPOINTS:
   - Very strict limits
   - Cost-based limiting (tokens, compute time)
   - Queue-based for fairness

5. AUTHENTICATION ENDPOINTS:
   - Very strict (prevent brute force)
   - Temporary lockout after failures
   - Consider: progressive delays

Example Tiered Pricing Model:
----------------------------
| Tier       | Price    | Requests/month | Rate/minute |
|------------|----------|----------------|-------------|
| Free       | $0       | 1,000          | 10          |
| Developer  | $29      | 50,000         | 100         |
| Business   | $99      | 500,000        | 500         |
| Enterprise | Custom   | Unlimited      | 2,000       |

Implementation:
- Store tier in database with user
- Check tier in rate limit key function
- Return appropriate limit
"""


# =============================================================================
# DYNAMIC RATE LIMITING
# =============================================================================

class DynamicRateLimiter:
    """
    Dynamic rate limiting based on system load.
    
    EDUCATIONAL: Adaptive Rate Limiting
    ----------------------------------
    Static limits don't account for:
    - System under heavy load
    - Database slow/unavailable
    - Specific endpoints causing issues
    
    Dynamic limiting adjusts based on:
    - Response times (slow = reduce limits)
    - Error rates (high = reduce limits)
    - CPU/Memory usage
    - Custom metrics
    """
    
    def __init__(self, base_limit: int = 100):
        self.base_limit = base_limit
        self.current_multiplier = 1.0
        self.response_times = []
        self.error_count = 0
        self.last_check = time.time()
    
    def record_response(self, duration_ms: float, is_error: bool = False):
        """Record response metrics for adaptive limiting."""
        self.response_times.append(duration_ms)
        if is_error:
            self.error_count += 1
        
        # Keep only last 100 samples
        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]
    
    def get_current_limit(self) -> int:
        """
        Calculate current limit based on system health.
        
        Logic:
        - Good health (fast, no errors): 100% of base
        - Slow responses: 75% of base
        - Many errors: 50% of base
        - Both problems: 25% of base
        """
        if not self.response_times:
            return self.base_limit
        
        avg_response_time = sum(self.response_times) / len(self.response_times)
        error_rate = self.error_count / max(len(self.response_times), 1)
        
        # Adjust multiplier
        multiplier = 1.0
        
        if avg_response_time > 1000:  # > 1 second average
            multiplier *= 0.75
        if avg_response_time > 2000:  # > 2 seconds
            multiplier *= 0.5
        
        if error_rate > 0.05:  # > 5% errors
            multiplier *= 0.75
        if error_rate > 0.10:  # > 10% errors
            multiplier *= 0.5
        
        self.current_multiplier = multiplier
        return int(self.base_limit * multiplier)
