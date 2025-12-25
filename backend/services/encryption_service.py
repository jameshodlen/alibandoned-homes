"""
Encryption Service for Sensitive Data Protection
=================================================

This module provides secure encryption and decryption capabilities
for sensitive data, particularly EXIF metadata containing GPS coordinates.

Why Encryption?
--------------
Photos often contain EXIF metadata with precise GPS coordinates showing
exactly where and when a photo was taken. This is a serious privacy risk:

1. Location stalking: GPS coordinates reveal where someone was
2. Home address exposure: Photos taken at home reveal where you live  
3. Movement patterns: Multiple photos reveal daily routines
4. Timestamp correlation: Combined with GPS, shows exact movements

We encrypt this sensitive data so:
- It can be recovered if legally required (e.g., subpoena)
- Users can export their own data (GDPR compliance)
- The data is protected from unauthorized access

Encryption Approach:
-------------------
We use Fernet symmetric encryption from the `cryptography` library.

Why Fernet?
- Simple and hard to misuse (unlike raw AES)
- Includes authentication (HMAC) to detect tampering
- Includes timestamp for key rotation policies
- Uses AES-128-CBC with PKCS7 padding
- URL-safe base64 encoding

Key Management Strategy:
-----------------------
1. Master key stored in environment variable (never in code!)
2. Per-location keys derived using PBKDF2 (password-based key derivation)
3. Key IDs stored with encrypted data for key rotation support

SECURITY WARNINGS:
------------------
⚠️  NEVER hardcode the master key in source code
⚠️  NEVER log the master key or derived keys
⚠️  ALWAYS use environment variables or a secrets manager
⚠️  BACKUP the master key securely - if lost, data is unrecoverable

Example Usage:
-------------
```python
from backend.services.encryption_service import EncryptionService

# Initialize service (reads master key from environment)
encryption = EncryptionService()

# Encrypt sensitive EXIF data for a specific location
sensitive_data = {"gps_lat": 30.2672, "gps_lon": -97.7431}
encrypted_bytes, key_id = encryption.encrypt_for_location(
    data=sensitive_data,
    location_id="abc-123-def"
)

# Later, decrypt (e.g., for GDPR data export)
original_data = encryption.decrypt_for_location(
    encrypted_data=encrypted_bytes,
    key_id=key_id,
    location_id="abc-123-def"
)
```
"""

import base64
import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple, Union

# cryptography is the most trusted Python encryption library
# Maintained by the same team that maintains pyopenssl
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Configure logging for security-relevant operations
# IMPORTANT: Never log keys, encrypted data contents, or raw metadata
logger = logging.getLogger(__name__)


class EncryptionServiceError(Exception):
    """Base exception for encryption service errors.
    
    Using a custom exception type allows calling code to catch
    encryption-specific errors separately from other errors.
    """
    pass


class KeyNotFoundError(EncryptionServiceError):
    """Raised when an encryption key cannot be found or derived."""
    pass


class DecryptionError(EncryptionServiceError):
    """Raised when decryption fails (wrong key, corrupted data, etc.)."""
    pass


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.
    
    This service handles all encryption operations for the application,
    with a focus on protecting sensitive EXIF metadata from photos.
    
    Key Concepts:
    -------------
    
    **Symmetric Encryption**: We use the same key to encrypt and decrypt.
    This is faster than asymmetric encryption and suitable for data at rest.
    
    **Key Derivation**: Instead of storing a separate key for each location,
    we derive keys deterministically from a master key + salt (location_id).
    This means we can always regenerate the key without storing it.
    
    **Fernet**: A high-level encryption recipe that combines:
    - AES-128-CBC for encryption (confidentiality)
    - HMAC-SHA256 for authentication (integrity)
    - Base64 encoding for safe storage/transmission
    
    Attributes:
        master_key: The application's master encryption key (from environment)
        _key_cache: Cache of derived keys to avoid repeated PBKDF2 operations
    
    Security Notes:
    ---------------
    - The master key should be at least 32 bytes of random data
    - Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
    - Store in environment variable: ENCRYPTION_MASTER_KEY
    - Never commit the master key to version control!
    """
    
    # Environment variable name for the master key
    # Using a constant ensures consistency across the codebase
    MASTER_KEY_ENV_VAR = "ENCRYPTION_MASTER_KEY"
    
    # PBKDF2 iteration count - higher is slower but more secure
    # 100,000 iterations takes ~100ms on modern hardware
    # This makes brute-force attacks impractical
    PBKDF2_ITERATIONS = 100_000
    
    def __init__(self, master_key: Optional[str] = None) -> None:
        """
        Initialize the encryption service.
        
        The service loads its master key from:
        1. The `master_key` parameter (for testing only!)
        2. The ENCRYPTION_MASTER_KEY environment variable
        
        Args:
            master_key: Optional master key for testing. In production,
                       ALWAYS use the environment variable instead.
        
        Raises:
            EncryptionServiceError: If no master key is found.
        
        Example:
            ```python
            # Production: reads from environment
            service = EncryptionService()
            
            # Testing only: provide key directly (never in production!)
            test_key = Fernet.generate_key().decode()
            service = EncryptionService(master_key=test_key)
            ```
        
        Security Warning:
            ⚠️  Never hardcode the master key in your application code!
            ⚠️  The master_key parameter is for testing only!
        """
        # Try to get master key from parameter or environment
        self._master_key_raw = master_key or os.environ.get(self.MASTER_KEY_ENV_VAR)
        
        if not self._master_key_raw:
            # Provide a helpful error message for developers
            raise EncryptionServiceError(
                f"Encryption master key not found! "
                f"Set the {self.MASTER_KEY_ENV_VAR} environment variable.\n"
                f"Generate a key with: python -c \"from cryptography.fernet import Fernet; "
                f"print(Fernet.generate_key().decode())\""
            )
        
        # Validate the master key format
        # Fernet keys are 32 bytes, URL-safe base64 encoded = 44 characters
        try:
            # Attempt to create a Fernet instance to validate the key
            self._master_fernet = Fernet(self._master_key_raw.encode())
        except Exception as e:
            raise EncryptionServiceError(
                f"Invalid master key format. Key must be a valid Fernet key "
                f"(32 bytes, URL-safe base64 encoded). Error: {e}"
            )
        
        # Cache for derived keys to avoid repeated PBKDF2 operations
        # PBKDF2 is intentionally slow, so caching improves performance
        # Keys are cached by key_id for quick lookup
        self._key_cache: Dict[str, bytes] = {}
        
        logger.info("EncryptionService initialized successfully")
        # SECURITY: Never log the actual key value!
    
    def _derive_key_for_location(self, location_id: str) -> Tuple[bytes, str]:
        """
        Derive a unique encryption key for a specific location.
        
        Why derive keys instead of generating random ones?
        --------------------------------------------------
        If we generated a random key for each location, we'd need to store
        every key securely. That's complex and creates more attack surface.
        
        Instead, we use PBKDF2 (Password-Based Key Derivation Function 2) to
        deterministically derive a key from:
        - Master key (the secret ingredient)
        - Salt (the location_id, making each derived key unique)
        
        Benefits:
        - Deterministic: Same inputs always produce same key
        - Unique per location: Each location_id produces a different key
        - No storage needed: We can regenerate the key anytime
        - Forward secrecy: Compromising one derived key doesn't expose others
        
        How PBKDF2 works:
        ----------------
        1. Take the password (master key) and salt (location_id)
        2. Hash them together repeatedly (100,000 times)
        3. The repetition makes brute-force attacks slow
        4. Output a key of the desired length (32 bytes for Fernet)
        
        Args:
            location_id: Unique identifier for the location.
                        Used as the salt for key derivation.
        
        Returns:
            Tuple of (derived_key_bytes, key_id_string)
            - derived_key_bytes: The 32-byte key for Fernet
            - key_id_string: A hash of the location_id (for key lookup)
        
        Security Notes:
            - The key_id is a hash, not the location_id itself
            - This prevents leaking location_id values in the encrypted data
        """
        # Generate a key_id from hashing the location_id
        # This creates a consistent identifier without exposing location_id
        key_id = hashlib.sha256(location_id.encode()).hexdigest()[:16]
        
        # Check cache first to avoid expensive PBKDF2 operation
        if key_id in self._key_cache:
            return self._key_cache[key_id], key_id
        
        # Create a salt from the location_id
        # Salt should be unique per key but doesn't need to be secret
        salt = location_id.encode('utf-8')
        
        # PBKDF2 key derivation
        # This is intentionally slow to resist brute-force attacks
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),  # Hash algorithm for HMAC
            length=32,  # Output 32 bytes (256 bits) for Fernet
            salt=salt,  # Unique salt per location
            iterations=self.PBKDF2_ITERATIONS,  # Slow = more secure
        )
        
        # Derive the key from the master key
        derived_key = kdf.derive(self._master_key_raw.encode())
        
        # Fernet requires URL-safe base64 encoded key
        fernet_key = base64.urlsafe_b64encode(derived_key)
        
        # Cache the derived key for performance
        self._key_cache[key_id] = fernet_key
        
        logger.debug(f"Derived key for key_id: {key_id}")
        # SECURITY: Never log the actual key value!
        
        return fernet_key, key_id
    
    def encrypt(self, data: bytes, key: bytes) -> bytes:
        """
        Encrypt data using Fernet symmetric encryption.
        
        What Fernet encryption does:
        ---------------------------
        1. Generates a random 128-bit IV (Initialization Vector)
        2. Encrypts data with AES-128 in CBC mode
        3. Computes HMAC-SHA256 over the ciphertext
        4. Combines: version (1 byte) + timestamp (8 bytes) + IV (16 bytes) + ciphertext + HMAC
        5. Base64 encodes the result for safe storage
        
        The HMAC ensures integrity: if anyone modifies the encrypted data,
        decryption will fail. This is called authenticated encryption.
        
        Args:
            data: Raw bytes to encrypt.
            key: Fernet-compatible key (32 bytes, base64 encoded).
        
        Returns:
            Encrypted bytes (base64 encoded, safe for storage/transmission).
        
        Raises:
            EncryptionServiceError: If encryption fails.
        
        Example:
            ```python
            key = Fernet.generate_key()
            encrypted = service.encrypt(b"secret data", key)
            ```
        
        Performance Note:
            Fernet encryption is fast: ~10MB/s on typical hardware.
            For EXIF metadata (usually < 100KB), this is negligible.
        """
        try:
            # Create a Fernet instance with the provided key
            fernet = Fernet(key)
            
            # Fernet.encrypt() handles IV generation, padding, encryption,
            # and HMAC computation all in one call
            encrypted = fernet.encrypt(data)
            
            return encrypted
            
        except Exception as e:
            # Log the error type but NOT the data content
            logger.error(f"Encryption failed: {type(e).__name__}")
            raise EncryptionServiceError(f"Failed to encrypt data: {e}")
    
    def decrypt(self, encrypted_data: bytes, key: bytes) -> bytes:
        """
        Decrypt data that was encrypted with Fernet.
        
        What Fernet decryption does:
        ---------------------------
        1. Base64 decodes the ciphertext
        2. Extracts version, timestamp, IV, ciphertext, and HMAC
        3. Verifies the HMAC (ensures data wasn't tampered with)
        4. Decrypts the ciphertext using AES-128-CBC
        5. Removes padding and returns the original data
        
        If ANY step fails (wrong key, corrupted data, modified ciphertext),
        decryption fails with InvalidToken. This is a security feature!
        
        Args:
            encrypted_data: Data that was encrypted with Fernet.
            key: The same key that was used for encryption.
        
        Returns:
            Original decrypted bytes.
        
        Raises:
            DecryptionError: If decryption fails for any reason:
                - Wrong key
                - Corrupted data
                - Tampered ciphertext
                - Expired token (if TTL is used)
        
        Example:
            ```python
            decrypted = service.decrypt(encrypted_data, key)
            original_string = decrypted.decode('utf-8')
            ```
        
        Security Note:
            The error message intentionally doesn't distinguish between
            wrong key vs corrupted data. This prevents attackers from
            using error messages to guess keys.
        """
        try:
            # Create a Fernet instance with the provided key
            fernet = Fernet(key)
            
            # Fernet.decrypt() handles all validation automatically:
            # - Checks version byte
            # - Verifies HMAC (integrity check)
            # - Decrypts and removes padding
            decrypted = fernet.decrypt(encrypted_data)
            
            return decrypted
            
        except InvalidToken:
            # InvalidToken covers: wrong key, tampered data, or corruption
            # We don't distinguish to prevent information leakage
            logger.warning("Decryption failed: invalid token")
            raise DecryptionError(
                "Failed to decrypt data. This could mean: "
                "wrong key, corrupted data, or tampered ciphertext."
            )
        except Exception as e:
            logger.error(f"Unexpected decryption error: {type(e).__name__}")
            raise DecryptionError(f"Failed to decrypt data: {e}")
    
    def encrypt_for_location(
        self,
        data: Union[Dict[str, Any], str, bytes],
        location_id: str,
    ) -> Tuple[bytes, str]:
        """
        Encrypt data associated with a specific location.
        
        This is the main method for encrypting sensitive EXIF metadata.
        It handles:
        1. Key derivation from location_id
        2. Data serialization (if dict or string)
        3. Encryption with derived key
        4. Returning both encrypted data and key_id
        
        The key_id should be stored alongside the encrypted data so we
        know which key to use for decryption later.
        
        Args:
            data: Data to encrypt. Can be:
                - dict: Will be JSON serialized
                - str: Will be UTF-8 encoded
                - bytes: Used as-is
            location_id: The location this data belongs to.
                        Used for key derivation.
        
        Returns:
            Tuple of (encrypted_bytes, key_id)
            - encrypted_bytes: The encrypted data
            - key_id: Store this to enable decryption later
        
        Example:
            ```python
            sensitive_metadata = {
                "gps_latitude": 30.2672,
                "gps_longitude": -97.7431,
                "gps_timestamp": "2024-01-15T14:30:00Z"
            }
            
            encrypted, key_id = encryption.encrypt_for_location(
                data=sensitive_metadata,
                location_id="abc-123-def"
            )
            
            # Store in database
            photo.original_metadata_encrypted = encrypted
            photo.encryption_key_id = key_id
            ```
        """
        # Derive the encryption key for this location
        key, key_id = self._derive_key_for_location(location_id)
        
        # Serialize the data to bytes
        if isinstance(data, dict):
            # JSON encode dictionaries for safe storage
            # Using ensure_ascii=False allows Unicode characters
            data_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
        elif isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            raise EncryptionServiceError(
                f"Unsupported data type: {type(data)}. "
                f"Expected dict, str, or bytes."
            )
        
        # Encrypt the serialized data
        encrypted = self.encrypt(data_bytes, key)
        
        logger.info(f"Encrypted {len(data_bytes)} bytes for key_id: {key_id}")
        
        return encrypted, key_id
    
    def decrypt_for_location(
        self,
        encrypted_data: bytes,
        key_id: str,
        location_id: str,
    ) -> Dict[str, Any]:
        """
        Decrypt data associated with a specific location.
        
        This method is typically used for:
        1. GDPR data export (user requests their data)
        2. Legal requirements (subpoena for original metadata)
        3. Administrative access for debugging
        
        The location_id must match what was used during encryption,
        or decryption will fail with DecryptionError.
        
        Args:
            encrypted_data: The encrypted bytes from the database.
            key_id: The key_id stored with the encrypted data.
                   Used for validation (optional in current implementation).
            location_id: The location this data belongs to.
                        Must match the original encryption location_id.
        
        Returns:
            The decrypted data as a dictionary (assumes JSON).
        
        Raises:
            DecryptionError: If decryption fails (wrong location_id, etc.)
        
        Example:
            ```python
            # Retrieve from database
            encrypted = photo.original_metadata_encrypted
            key_id = photo.encryption_key_id
            location_id = photo.location_id
            
            # Decrypt
            original_metadata = encryption.decrypt_for_location(
                encrypted_data=encrypted,
                key_id=key_id,
                location_id=str(location_id)
            )
            
            print(f"GPS: {original_metadata['gps_latitude']}, "
                  f"{original_metadata['gps_longitude']}")
            ```
        """
        # Derive the key again using the same location_id
        # If location_id doesn't match, we'll get a different key and decryption fails
        key, derived_key_id = self._derive_key_for_location(location_id)
        
        # Optional: Verify key_id matches (extra validation)
        # This catches bugs where location_id doesn't match encrypted data
        if derived_key_id != key_id:
            logger.warning(
                f"Key ID mismatch! Expected: {key_id}, Got: {derived_key_id}"
            )
            # We still try to decrypt - it will fail if truly mismatched
        
        # Decrypt the data
        decrypted_bytes = self.decrypt(encrypted_data, key)
        
        # Parse JSON back to dictionary
        try:
            data = json.loads(decrypted_bytes.decode('utf-8'))
        except json.JSONDecodeError as e:
            # Data was encrypted but isn't valid JSON
            # This could mean it was encrypted as raw bytes/string
            logger.warning(f"Decrypted data is not JSON: {e}")
            raise DecryptionError(
                "Decrypted data is not valid JSON. "
                "The data may have been encrypted in a different format."
            )
        
        logger.info(f"Decrypted data for key_id: {key_id}")
        
        return data
    
    def rotate_master_key(
        self,
        old_key: str,
        new_key: str,
        location_ids: list[str],
    ) -> Dict[str, Tuple[bytes, str]]:
        """
        Re-encrypt data with a new master key during key rotation.
        
        Key rotation is a security best practice:
        - Limits exposure if a key is compromised
        - Complies with security policies (e.g., rotate annually)
        - Allows transitioning to stronger algorithms
        
        This method is complex in production because you need to:
        1. Fetch all encrypted data for given locations
        2. Decrypt with old key
        3. Re-encrypt with new key
        4. Update database records
        5. Handle failures gracefully (partial migration)
        
        Args:
            old_key: The current master key.
            new_key: The new master key to migrate to.
            location_ids: List of location IDs to migrate.
        
        Returns:
            Dict mapping location_id to (new_encrypted_data, new_key_id)
        
        Raises:
            EncryptionServiceError: If rotation fails.
        
        TODO: Implement proper key rotation with database integration.
        
        Security Note:
            ⚠️  Key rotation should be done during a maintenance window
            ⚠️  Always backup data before rotating keys
            ⚠️  Test thoroughly in staging first
        """
        # TODO: Implement full key rotation with database integration
        # This is a placeholder showing the concept
        raise NotImplementedError(
            "Key rotation requires database integration. "
            "See documentation for manual rotation process."
        )


# =============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# =============================================================================

# Singleton instance for easy access throughout the application
# Created lazily on first use
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get the singleton EncryptionService instance.
    
    This provides a convenient way to access the encryption service
    without creating new instances everywhere.
    
    Returns:
        The shared EncryptionService instance.
    
    Example:
        ```python
        from backend.services.encryption_service import get_encryption_service
        
        encryption = get_encryption_service()
        encrypted, key_id = encryption.encrypt_for_location(data, location_id)
        ```
    """
    global _encryption_service
    
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    
    return _encryption_service


def generate_master_key() -> str:
    """
    Generate a new Fernet master key.
    
    Use this once to create your master key, then store it securely
    in your environment variables or secrets manager.
    
    Returns:
        A new Fernet key as a string.
    
    Example:
        ```bash
        $ python -c "from backend.services.encryption_service import generate_master_key; print(generate_master_key())"
        YWtzaW5hc2RrZmp...  # Your key here
        ```
    
    Security Warning:
        ⚠️  Generate only once and store securely
        ⚠️  Never regenerate in production (will lose all encrypted data!)
        ⚠️  Backup the key in multiple secure locations
    """
    return Fernet.generate_key().decode('utf-8')
