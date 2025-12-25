"""
Security Middleware - HTTP Security Headers and Request Filtering

EDUCATIONAL: Web Security Headers
=================================

Security headers instruct the browser how to behave, providing defense-in-depth
against various attacks. Even if your application has vulnerabilities, these
headers can prevent exploitation.

Why Add Security Headers?
------------------------
1. Free security layer (just HTTP headers)
2. Browser enforces protection
3. Defense in depth (multiple layers)
4. Industry best practice (security audits check for these)

Common Attack Types These Prevent:
---------------------------------
- XSS (Cross-Site Scripting): Injected malicious scripts
- Clickjacking: Hidden iframes trick users into clicking
- MIME sniffing: Browser guesses content type incorrectly
- Man-in-the-Middle: Eavesdropping on HTTP traffic
- Data injection: Injecting content into responses

HTTPS/TLS In Depth:
------------------
TLS (Transport Layer Security) encrypts all data between client and server.

Without HTTPS:
  Client ----[plain text]----> Server
  Attacker can read: API keys, passwords, personal data

With HTTPS:
  Client ----[encrypted]----> Server
  Attacker sees: Gibberish (encrypted data)

TLS Handshake (simplified):
1. Client Hello: "I want to connect, here are ciphers I support"
2. Server Hello: "Let's use this cipher, here's my certificate"
3. Client Verify: "Certificate is signed by trusted CA? ✓"
4. Key Exchange: Both generate shared secret key
5. Encrypted: All further communication encrypted

Certificate Types:
- DV (Domain Validation): Proves you control domain (cheapest)
- OV (Organization Validation): Proves organization identity
- EV (Extended Validation): Highest trust, green bar in browser
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Callable
import uuid
import time
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all HTTP responses.
    
    EDUCATIONAL: Security Headers Explained
    --------------------------------------
    Each header protects against specific attacks.
    Think of them as browser instructions for security behavior.
    """
    
    def __init__(self, app: ASGIApp, csp_enabled: bool = True):
        super().__init__(app)
        self.csp_enabled = csp_enabled
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Process request
        response = await call_next(request)
        
        # =====================================================================
        # CONTENT SECURITY POLICY (CSP)
        # =====================================================================
        # EDUCATIONAL: CSP - The Most Powerful Security Header
        #
        # Tells browser which sources are allowed for each content type.
        # Prevents XSS by blocking inline scripts and unauthorized sources.
        #
        # Example attack CSP prevents:
        # Attacker injects: <script>steal(document.cookie)</script>
        # With CSP: Browser blocks script (not from allowed source)
        #
        # Directives:
        # - default-src: Fallback for all types
        # - script-src: JavaScript sources
        # - style-src: CSS sources
        # - img-src: Image sources
        # - connect-src: AJAX/fetch destinations
        # - frame-ancestors: Who can embed us (clickjacking protection)
        
        if self.csp_enabled:
            csp_policy = "; ".join([
                "default-src 'self'",  # Only load from same origin
                "script-src 'self'",  # Scripts only from self
                "style-src 'self' 'unsafe-inline'",  # Styles (inline for UI libs)
                "img-src 'self' data: https:",  # Images from self, data URIs, HTTPS
                "connect-src 'self'",  # AJAX only to self
                "frame-ancestors 'none'",  # Don't allow embedding (clickjacking)
                "form-action 'self'",  # Forms only submit to self
                "base-uri 'self'",  # <base> tag only self
            ])
            response.headers["Content-Security-Policy"] = csp_policy
        
        # =====================================================================
        # X-CONTENT-TYPE-OPTIONS
        # =====================================================================
        # EDUCATIONAL: Prevent MIME Sniffing
        #
        # Problem: Browser "helpfully" guesses content type
        # Attack: Upload malicious.txt but browser interprets as HTML/JS
        # 
        # Example attack:
        # 1. Attacker uploads file.txt containing: <script>evil()</script>
        # 2. Server serves as text/plain
        # 3. Browser sniffs content, sees HTML, executes as HTML!
        #
        # Solution: "nosniff" forces browser to respect declared type
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # =====================================================================
        # X-FRAME-OPTIONS
        # =====================================================================
        # EDUCATIONAL: Clickjacking Protection
        #
        # Clickjacking attack:
        # 1. Attacker creates page with invisible iframe containing your site
        # 2. User thinks they're clicking attacker's button
        # 3. Actually clicking button in your (hidden) site!
        #
        # Example: "Click to win prize!" → Actually clicking "Delete Account"
        #
        # Options:
        # - DENY: Never allow framing
        # - SAMEORIGIN: Only allow framing by same origin
        # - ALLOW-FROM uri: Allow specific site to frame
        
        response.headers["X-Frame-Options"] = "DENY"
        
        # =====================================================================
        # X-XSS-PROTECTION
        # =====================================================================
        # EDUCATIONAL: Browser XSS Filter
        #
        # Enables browser's built-in XSS filter (older browsers).
        # Modern browsers use CSP instead, but this helps legacy.
        #
        # "1": Enable filter
        # "mode=block": Block page entirely if attack detected
        #
        # Note: Some security experts argue to disable (0) because
        # the filter itself can have vulnerabilities. CSP is better.
        
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # =====================================================================
        # STRICT-TRANSPORT-SECURITY (HSTS)
        # =====================================================================
        # EDUCATIONAL: Force HTTPS
        #
        # Problem: First request might be HTTP (attacker intercepts, redirects)
        # Solution: Browser remembers "always use HTTPS for this site"
        #
        # max-age=31536000: Remember for 1 year (in seconds)
        # includeSubDomains: Also apply to subdomains
        # preload: Allow inclusion in browser's preload list
        #
        # CRITICAL: Only set this if HTTPS is working!
        # If set incorrectly, site becomes inaccessible.
        
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        
        # =====================================================================
        # REFERRER-POLICY
        # =====================================================================
        # EDUCATIONAL: Control Referrer Header
        #
        # Referrer header tells destination where user came from.
        # Problem: May leak sensitive URLs (tokens, session IDs in URL)
        #
        # Options:
        # - no-referrer: Never send
        # - same-origin: Only to same origin
        # - strict-origin: Only origin (not full path) for HTTPS→HTTPS
        # - strict-origin-when-cross-origin: Full path for same-origin, origin for cross
        
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # =====================================================================
        # PERMISSIONS-POLICY (formerly Feature-Policy)
        # =====================================================================
        # EDUCATIONAL: Disable Dangerous Browser Features
        #
        # Controls access to browser features that could be exploited:
        # - Microphone, camera, geolocation access
        # - Accelerometer, gyroscope (motion tracking)
        # - Payment API, USB access
        #
        # For an API server, we don't need any of these.
        
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        
        # =====================================================================
        # CACHE-CONTROL
        # =====================================================================
        # EDUCATIONAL: Prevent Sensitive Data Caching
        #
        # API responses may contain sensitive data.
        # Don't let browsers/proxies cache them.
        #
        # no-store: Don't cache at all
        # no-cache: Revalidate before using cache
        # private: Only browser can cache (not shared proxies)
        
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, max-age=0"
            response.headers["Pragma"] = "no-cache"  # HTTP/1.0 compat
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all requests for security monitoring.
    
    EDUCATIONAL: Security Logging
    ----------------------------
    Comprehensive logging is crucial for:
    1. Detecting attacks (brute force, scanning)
    2. Forensics (understanding what happened)
    3. Compliance (audit trails)
    
    What to log:
    - Request: method, path, IP, user agent
    - Response: status code, timing
    - Security events: failed auth, rate limits
    
    What NOT to log:
    - Passwords
    - API keys (log masked version)
    - Credit card numbers
    - Personal data (depending on compliance)
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Add request ID to request state (for other middleware/handlers)
        request.state.request_id = request_id
        
        # Record start time
        start_time = time.time()
        
        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Mask API key in logs (show first 4 chars only)
        api_key = request.headers.get("x-api-key", "")
        masked_key = f"{api_key[:4]}..." if api_key else "none"
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "error": str(e)
                }
            )
            raise
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        # Log request (structured logging)
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": client_ip,
            "api_key": masked_key,
            "user_agent": user_agent[:50]  # Truncate long user agents
        }
        
        # Log level based on status
        if response.status_code >= 500:
            logger.error(f"Request: {log_data}")
        elif response.status_code >= 400:
            logger.warning(f"Request: {log_data}")
        else:
            logger.info(f"Request: {log_data}")
        
        return response


class IPFilterMiddleware(BaseHTTPMiddleware):
    """
    IP-based access control.
    
    EDUCATIONAL: IP Filtering
    ------------------------
    Use cases:
    - Admin endpoints only from office IP
    - Block known malicious IPs
    - Geographic restrictions
    
    Limitations:
    - IPs can be spoofed
    - Users behind NAT share IP
    - VPNs/proxies hide real IP
    
    Best used as additional layer, not sole protection.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        allowed_ips: list = None,
        blocked_ips: list = None
    ):
        super().__init__(app)
        self.allowed_ips = set(allowed_ips or [])
        self.blocked_ips = set(blocked_ips or [])
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else None
        
        # Check blocked list
        if client_ip in self.blocked_ips:
            logger.warning(f"Blocked IP attempted access: {client_ip}")
            return Response(
                content='{"detail": "Access denied"}',
                status_code=403,
                media_type="application/json"
            )
        
        # Check allowed list (if configured)
        if self.allowed_ips and client_ip not in self.allowed_ips:
            logger.warning(f"Unlisted IP attempted access: {client_ip}")
            return Response(
                content='{"detail": "Access denied"}',
                status_code=403,
                media_type="application/json"
            )
        
        return await call_next(request)


# =============================================================================
# EDUCATIONAL: Common Web Vulnerabilities
# =============================================================================

"""
XSS (Cross-Site Scripting):
--------------------------
Attack: Injecting malicious JavaScript that runs in users' browsers.

Types:
1. Stored XSS: Script saved in database, served to all users
   Example: Malicious comment on blog that steals cookies
   
2. Reflected XSS: Script in URL parameters, reflected back
   Example: https://site.com/search?q=<script>evil()</script>
   
3. DOM XSS: Script manipulates DOM directly
   Example: document.innerHTML = location.hash

Prevention:
- Escape output (HTML entities)
- Content-Security-Policy header
- HttpOnly cookies (can't access via JS)

---

CSRF (Cross-Site Request Forgery):
---------------------------------
Attack: Trick authenticated user into making unwanted request.

Example:
1. User logged into bank.com
2. User visits evil.com
3. evil.com has: <img src="bank.com/transfer?to=attacker&amount=1000">
4. Browser sends request with user's cookies!

Prevention:
- CSRF tokens (random token in forms)
- SameSite cookie attribute
- Check Referer/Origin headers

---

SQL Injection:
-------------
Attack: Insert SQL code via user input.

Vulnerable:
  query = f"SELECT * FROM users WHERE id = {user_input}"
  # user_input = "1 OR 1=1" → Returns all users!
  # user_input = "1; DROP TABLE users" → Deletes table!

Safe:
  query = select(User).where(User.id == user_input)  # Parameterized

---

Clickjacking:
------------
Attack: Hide malicious actions under legitimate-looking UI.

Example:
1. Attacker page has invisible iframe of bank.com
2. "Click here to win!" button positioned over "Transfer" button
3. User clicks, actually clicking bank's transfer button

Prevention:
- X-Frame-Options: DENY
- CSP frame-ancestors: 'none'
"""
