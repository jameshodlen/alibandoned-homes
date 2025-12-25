"""
Enhanced Authentication & Authorization System

EDUCATIONAL: Security Fundamentals
===================================

Authentication vs Authorization:
-------------------------------
- AUTHENTICATION: "Who are you?" - Verify identity
  Example: Logging in with username/password
  
- AUTHORIZATION: "What can you do?" - Verify permissions
  Example: Admin can delete, user can only read

Think of it like a building:
- Authentication = The security guard checking your ID at the door
- Authorization = The keycard that only opens certain rooms

Encryption Types:
----------------
1. Encryption at REST:
   - Data stored encrypted on disk
   - If database is stolen, data is unreadable
   - Example: Encrypted database columns, encrypted files
   
2. Encryption in TRANSIT:
   - Data encrypted while traveling over network
   - Prevents eavesdropping (man-in-the-middle attacks)
   - Example: HTTPS/TLS for API calls

HTTPS/TLS Concepts:
------------------
- TLS (Transport Layer Security): Protocol for secure communication
- HTTPS = HTTP + TLS encryption
- How it works:
  1. Client connects to server
  2. Server sends its certificate (proves identity)
  3. Client verifies certificate with Certificate Authority
  4. Both agree on encryption keys
  5. All data is encrypted from now on
  
- Without HTTPS: Anyone on the network can read your API keys!

Common Authentication Strategies:
---------------------------------
1. API Keys (what we implement):
   - Simple string in header
   - Good for: Single user, server-to-server
   - Cons: Hard to revoke, no user context
   
2. JWT (JSON Web Tokens):
   - Self-contained tokens with user info
   - Good for: Multi-user systems, stateless
   - Cons: Can't revoke until expiration
   
3. OAuth 2.0:
   - Industry standard for third-party access
   - Good for: "Login with Google", delegated access
   - Cons: Complex to implement
   
4. Session Cookies:
   - Server stores session, client gets cookie
   - Good for: Traditional web apps
   - Cons: Requires server-side storage, not stateless
"""

from fastapi import Security, HTTPException, status, Depends, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import os
import secrets
import logging

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# EDUCATIONAL: Environment Variables for Secrets
#
# CRITICAL SECURITY RULE: Never hardcode secrets in source code!
# 
# Why?
# 1. Source code often ends up in Git (public or private repos)
# 2. Logs may contain environment details (if you print config)
# 3. Different environments need different secrets
# 4. Rotating secrets shouldn't require code changes
#
# Best Practices:
# - Development: .env file (in .gitignore)
# - Production: Platform secrets manager (AWS Secrets Manager, GCP Secret Manager)
# - Never: Committed to repository, hardcoded in code

API_KEY = os.getenv("API_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Generate development keys if not set (with warnings)
if not API_KEY:
    API_KEY = secrets.token_urlsafe(32)
    logger.warning(f"⚠️  API_KEY not set! Generated temporary: {API_KEY[:8]}...")
    logger.warning("⚠️  Set API_KEY environment variable for production!")

if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning("⚠️  JWT_SECRET_KEY not set! Generated temporary key.")
    logger.warning("⚠️  Set JWT_SECRET_KEY environment variable for production!")


# =============================================================================
# API KEY AUTHENTICATION
# =============================================================================

# EDUCATIONAL: FastAPI Security Schemes
#
# APIKeyHeader: Expects API key in HTTP header
# - name="X-API-Key": The header name to look for
# - auto_error=False: Don't auto-raise error, let us customize
#
# Alternative schemes:
# - APIKeyCookie: Key stored in browser cookie
# - APIKeyQuery: Key in URL (?api_key=xxx) - NOT RECOMMENDED (logs expose it!)

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API key for authentication. Include as header: X-API-Key: your-key"
)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify API key from request header.
    
    EDUCATIONAL: Timing Attacks
    --------------------------
    A timing attack exploits the time differences in operations:
    
    Vulnerable code:
    ```python
    if api_key == stored_key:  # BAD!
        return True
    ```
    This stops comparing at the first different character.
    Attacker can measure response time to guess correct key:
    - Try "a..." - fails in 0.001ms (first char wrong)
    - Try "x..." - fails in 0.002ms (first char RIGHT, second wrong!)
    - Repeat to eventually guess entire key
    
    Secure code (what we use):
    ```python
    secrets.compare_digest(api_key, stored_key)  # GOOD!
    ```
    This always takes the same time regardless of match position.
    
    Args:
        api_key: API key from X-API-Key header
        
    Returns:
        str: User identifier (or raises 401)
        
    Raises:
        HTTPException: 401 if API key invalid or missing
    """
    if not api_key:
        logger.warning("Authentication failed: No API key provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include header: X-API-Key: your-key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    # CRITICAL: Use constant-time comparison!
    if not secrets.compare_digest(api_key, API_KEY):
        # Log failed attempts (for security monitoring)
        # Don't log the full key - it might be someone's valid key with typo!
        logger.warning(f"Authentication failed: Invalid API key {api_key[:4]}...")
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    # Success! Return user identifier
    # In multi-user system, look up user from API key in database
    return "authenticated_user"


# =============================================================================
# PASSWORD HASHING
# =============================================================================

# EDUCATIONAL: Password Security
#
# NEVER store plaintext passwords!
# If database is breached, all passwords are exposed.
#
# Hashing vs Encryption:
# - Hashing: One-way (can't reverse) - use for passwords
# - Encryption: Two-way (can decrypt) - use for data you need to read
#
# Why bcrypt?
# - SLOW by design (prevents brute force)
# - Salt built-in (each hash is unique)
# - Work factor adjustable (increase as computers get faster)
#
# Cost factor:
# - Higher = slower = more secure
# - 12 = about 0.3 seconds per hash (good balance)
# - Too high? Login takes forever. Too low? Brute force is fast.

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Work factor (2^12 = 4096 iterations)
)


def hash_password(password: str) -> str:
    """
    Hash a password for secure storage.
    
    EDUCATIONAL: Password Hashing Process
    ------------------------------------
    1. Generate random salt (bcrypt does this automatically)
    2. Combine password + salt
    3. Run through bcrypt algorithm (slow, on purpose)
    4. Result: "$2b$12$salt...hash..." (salt embedded in output)
    
    Why salt matters:
    Without salt: All "password123" hash to same value
    With salt: Each "password123" hashes to unique value
    Prevents: Rainbow table attacks (pre-computed hashes)
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password (safe to store in database)
        
    Example:
        >>> hashed = hash_password("mypassword123")
        >>> print(hashed)
        '$2b$12$QeX3lCM1...'  # 60-character hash
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    EDUCATIONAL: Hash Verification
    -----------------------------
    1. Extract salt from stored hash
    2. Hash the provided password with same salt
    3. Compare the two hashes (constant-time)
    
    Even bcrypt.verify uses constant-time comparison internally!
    
    Args:
        plain_password: Password to verify
        hashed_password: Hash from database
        
    Returns:
        bool: True if password matches
        
    Example:
        >>> hashed = hash_password("mypassword123")
        >>> verify_password("mypassword123", hashed)  # True
        >>> verify_password("wrongpassword", hashed)  # False
    """
    return pwd_context.verify(plain_password, hashed_password)


# =============================================================================
# JWT TOKEN AUTHENTICATION
# =============================================================================

# EDUCATIONAL: JWT (JSON Web Tokens)
#
# Structure: header.payload.signature
# - Header: Algorithm and token type {"alg": "HS256", "typ": "JWT"}
# - Payload: User data and claims {"user_id": 123, "exp": 1234567890}
# - Signature: HMAC of header+payload with secret key
#
# How it works:
# 1. User logs in with username/password
# 2. Server verifies credentials, creates JWT with user info
# 3. Client stores JWT (localStorage, cookie)
# 4. Client sends JWT with each request (Authorization header)
# 5. Server verifies signature and extracts user info
#
# Benefits:
# - Stateless: No session storage on server
# - Scalable: Any server can verify (just needs secret key)
# - Self-contained: All user info in token
#
# Risks:
# - Can't revoke until expiration (use short expiration!)
# - If secret key leaks, all tokens can be forged
# - Large payload = larger requests

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token.
    
    EDUCATIONAL: JWT Token Creation
    ------------------------------
    The token contains:
    - sub: Subject (usually user ID)
    - exp: Expiration timestamp
    - iat: Issued at timestamp
    - Custom claims (any data you want)
    
    Algorithm HS256:
    - HMAC with SHA-256
    - Symmetric: Same key for sign and verify
    - Fast, good for single-server or internal APIs
    
    Alternative: RS256
    - RSA with SHA-256
    - Asymmetric: Private key signs, public key verifies
    - Better for: Third-party verification, distributed systems
    
    Args:
        data: Payload data (user_id, roles, etc.)
        expires_delta: Token lifetime (default 24 hours)
        
    Returns:
        str: Encoded JWT token
        
    Example:
        >>> token = create_access_token({"user_id": "123", "role": "admin"})
        >>> print(token)
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    """
    to_encode = data.copy()
    
    # Set expiration
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    # Add standard claims
    to_encode.update({
        "exp": expire,  # Expiration time
        "iat": datetime.utcnow(),  # Issued at
    })
    
    # Encode token
    encoded_jwt = jwt.encode(
        to_encode,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify JWT token.
    
    EDUCATIONAL: Token Verification
    ------------------------------
    Verification checks:
    1. Signature valid (not tampered with)
    2. Not expired (exp > current time)
    3. Issued in past (iat < current time)
    
    Common errors:
    - ExpiredSignatureError: Token too old
    - JWTClaimsError: Invalid claims
    - JWTError: Invalid signature or format
    
    Args:
        token: JWT token string
        
    Returns:
        dict: Decoded payload
        
    Raises:
        HTTPException: 401 if token invalid
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> Dict[str, Any]:
    """
    Verify JWT from Authorization header.
    
    Expected header format:
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5...
    
    Args:
        credentials: Bearer token from header
        
    Returns:
        dict: Decoded token payload
        
    Raises:
        HTTPException: 401 if token missing or invalid
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return decode_access_token(credentials.credentials)


# =============================================================================
# COMBINED AUTHENTICATION
# =============================================================================

async def get_current_user(
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> str:
    """
    Authenticate using either API key or JWT token.
    
    EDUCATIONAL: Multiple Auth Methods
    ---------------------------------
    Supporting multiple auth methods is useful:
    - API Key: For scripts, automation, simple clients
    - JWT: For web apps with user sessions
    - OAuth: For third-party integrations
    
    Priority: Check API key first (simpler), then JWT
    
    Args:
        api_key: API key from X-API-Key header
        bearer: JWT from Authorization: Bearer header
        
    Returns:
        str: User identifier
        
    Raises:
        HTTPException: 401 if both auth methods fail
    """
    # Try API key first
    if api_key:
        try:
            return await verify_api_key(api_key)
        except HTTPException:
            pass  # Try JWT next
    
    # Try JWT
    if bearer:
        try:
            payload = await verify_jwt_token(bearer)
            return payload.get("sub", "jwt_user")
        except HTTPException:
            pass
    
    # Neither worked
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication. Provide X-API-Key or Authorization: Bearer token",
        headers={"WWW-Authenticate": "ApiKey, Bearer"}
    )


# =============================================================================
# AUTHORIZATION (ROLE-BASED ACCESS CONTROL)
# =============================================================================

# EDUCATIONAL: Role-Based Access Control (RBAC)
#
# Common pattern:
# - Users have roles (admin, user, viewer)
# - Roles have permissions (create, read, update, delete)
# - Check: Does user's role have required permission?
#
# Example hierarchy:
# - admin: all permissions
# - user: read, create, update own
# - viewer: read only

class Roles:
    """Role definitions"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class Permissions:
    """Permission definitions"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    ADMIN = "admin"  # Special admin permission


# Role → Permissions mapping
ROLE_PERMISSIONS: Dict[str, set] = {
    Roles.ADMIN: {Permissions.CREATE, Permissions.READ, Permissions.UPDATE, 
                  Permissions.DELETE, Permissions.ADMIN},
    Roles.USER: {Permissions.CREATE, Permissions.READ, Permissions.UPDATE},
    Roles.VIEWER: {Permissions.READ},
}


def require_permission(permission: str):
    """
    Dependency that checks for specific permission.
    
    EDUCATIONAL: Permission Checking
    -------------------------------
    This is a dependency factory - it returns a dependency function.
    
    Usage:
        @router.delete("/locations/{id}")
        async def delete_location(
            user: dict = Depends(require_permission(Permissions.DELETE))
        ):
            # Only users with DELETE permission reach here
            ...
    
    Args:
        permission: Required permission string
        
    Returns:
        Dependency function that checks permission
    """
    async def check_permission(
        request: Request,
        current_user: str = Depends(get_current_user)
    ) -> str:
        # In real app, look up user's role from database
        # For now, assume all authenticated users are "user" role
        user_role = Roles.USER  # Would come from database/JWT
        
        user_permissions = ROLE_PERMISSIONS.get(user_role, set())
        
        if permission not in user_permissions:
            logger.warning(
                f"Authorization failed: User {current_user} lacks {permission}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}"
            )
        
        return current_user
    
    return check_permission


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def generate_api_key() -> str:
    """
    Generate a new secure API key.
    
    EDUCATIONAL: Secure Random Generation
    ------------------------------------
    Use `secrets` module for security-sensitive values:
    - Cryptographically secure random number generator
    - Not predictable (unlike `random` module)
    
    token_urlsafe(32): 32 bytes of randomness = 256 bits
    - Output: URL-safe base64 string (43 characters)
    - Entropy: Enough for cryptographic security
    
    Returns:
        str: New API key (store securely, show once)
    """
    return secrets.token_urlsafe(32)


def generate_jwt_secret() -> str:
    """
    Generate a new JWT secret key.
    
    For HS256, key should be at least 256 bits (32 bytes).
    Using 64 bytes for extra security margin.
    
    Returns:
        str: Hex-encoded secret key
    """
    return secrets.token_hex(64)


# =============================================================================
# EDUCATIONAL: OWASP TOP 10 RELEVANT VULNERABILITIES
# =============================================================================

"""
OWASP Top 10 Security Risks (Relevant to APIs):
----------------------------------------------

1. BROKEN ACCESS CONTROL (What we prevent)
   - Users accessing other users' data
   - Vertical privilege escalation (user → admin)
   - Prevention: Authorization checks on every endpoint

2. CRYPTOGRAPHIC FAILURES (What we prevent)
   - Transmitting data without encryption
   - Weak password storage
   - Prevention: HTTPS, bcrypt password hashing

3. INJECTION (What we prevent)
   - SQL injection via user input
   - Command injection
   - Prevention: Pydantic validation, parameterized queries

4. INSECURE DESIGN (Architectural)
   - Lack of rate limiting (allows brute force)
   - Verbose error messages (info disclosure)
   - Prevention: Rate limiting, generic error messages

5. SECURITY MISCONFIGURATION
   - Default credentials
   - Unnecessary features enabled
   - Prevention: Environment variables, minimal permissions

6. VULNERABLE COMPONENTS
   - Outdated libraries with known issues
   - Prevention: Regular dependency updates, security scanning

7. IDENTIFICATION AND AUTHENTICATION FAILURES (What we prevent)
   - Weak passwords allowed
   - No brute force protection
   - Prevention: Password policies, rate limiting login

8. SOFTWARE AND DATA INTEGRITY FAILURES
   - Unsigned tokens
   - Auto-update without verification
   - Prevention: JWT signatures, dependency verification

9. SECURITY LOGGING AND MONITORING FAILURES (What we prevent)
   - No logging of failed logins
   - Prevention: Comprehensive security logging

10. SERVER-SIDE REQUEST FORGERY (SSRF)
    - Server fetching attacker-controlled URLs
    - Prevention: URL validation, allowlisting

Example Secure vs Insecure Code:

INSECURE - SQL Injection vulnerable:
```python
query = f"SELECT * FROM users WHERE id = {user_id}"  # BAD!
```

SECURE - Parameterized query:
```python
query = select(User).where(User.id == user_id)  # GOOD!
```

INSECURE - Exposes system info:
```python
raise HTTPException(500, f"Database error: {e}")  # BAD! Shows DB errors
```

SECURE - Generic error:
```python
logger.error(f"Database error: {e}")  # Log full error server-side
raise HTTPException(500, "Internal server error")  # Generic message
```
"""
