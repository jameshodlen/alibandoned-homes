"""
Image Utility Functions for Validation and Processing
======================================================

This module provides utility functions for image validation, format
conversion, and analysis. These functions are used throughout the
image processing pipeline.

Security Focus:
--------------
Image validation is CRITICAL for security because:
1. Users upload untrusted files that may be malicious
2. "JPEG" files might actually be PHP scripts or executables
3. Oversized images can cause denial of service (memory exhaustion)
4. Corrupted images can crash processing libraries

This module implements defense-in-depth validation:
1. File extension check (weak - can be spoofed)
2. Magic bytes verification (strong - checks actual file content)
3. PIL open test (definitive - actually parses the file)
4. Size limits (prevents resource exhaustion)

Example Usage:
-------------
```python
from backend.services.image_utils import (
    validate_image_file,
    get_image_hash,
    convert_heic_to_jpeg,
)

# Validate an uploaded file
is_valid, error_message = validate_image_file(uploaded_file)
if not is_valid:
    raise HTTPException(400, error_message)

# Check for duplicate images
hash1 = get_image_hash(image1)
hash2 = get_image_hash(image2)
if hash1 == hash2:
    print("These images are visually identical!")

# Convert Apple HEIC to web-compatible JPEG
if file_path.suffix.lower() == '.heic':
    jpeg_image = convert_heic_to_jpeg(file_path)
```
"""

import hashlib
import io
import logging
from pathlib import Path
from typing import BinaryIO, Optional, Tuple, Union

from PIL import Image, UnidentifiedImageError

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# FILE SIGNATURE (MAGIC BYTES) DEFINITIONS
# =============================================================================
# Magic bytes are the first few bytes of a file that identify its type.
# Unlike file extensions, these can't be easily spoofed.
# 
# Reference: https://en.wikipedia.org/wiki/List_of_file_signatures

# Dictionary mapping format names to their magic byte signatures
# Some formats have multiple possible signatures
IMAGE_MAGIC_BYTES = {
    'JPEG': [
        b'\xFF\xD8\xFF',  # Standard JPEG signature
    ],
    'PNG': [
        b'\x89PNG\r\n\x1a\n',  # PNG signature (8 bytes)
    ],
    'GIF': [
        b'GIF87a',  # GIF87a format
        b'GIF89a',  # GIF89a format (more common)
    ],
    'WebP': [
        b'RIFF',  # WebP uses RIFF container format
        # Full WebP signature is: RIFF????WEBP but we check RIFF first
    ],
    'BMP': [
        b'BM',  # Windows bitmap
    ],
    'TIFF': [
        b'II\x2a\x00',  # TIFF little-endian
        b'MM\x00\x2a',  # TIFF big-endian
    ],
    'HEIC': [
        b'\x00\x00\x00',  # HEIC starts with size box (first 3 bytes are usually 0)
        b'ftypheic',     # HEIC file type box (found after size)
        b'ftypmif1',     # HEIF image format
    ],
}

# Allowed extensions (normalized to lowercase without dot)
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'heic', 'heif'}

# Maximum file size in bytes (50 MB default)
# This prevents memory exhaustion attacks with huge images
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

# Maximum image dimensions
# Very large dimensions can cause memory issues even with small file sizes
# (e.g., a huge sparse PNG could be small on disk but huge in memory)
MAX_DIMENSION = 25000  # 25,000 pixels in either direction


class ImageValidationError(Exception):
    """Raised when image validation fails."""
    pass


def validate_image_file(
    file: Union[BinaryIO, Path, str],
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
    allowed_extensions: Optional[set] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a file is a legitimate image.
    
    This function implements defense-in-depth validation:
    
    1. **Extension Check** (Weak Security)
       - Checks the file extension matches allowed types
       - Easy to bypass by renaming files
       - We still check because most attacks don't bother renaming
    
    2. **Size Check** (DoS Prevention)
       - Prevents processing of extremely large files
       - Protects against memory exhaustion attacks
       - Speeds up processing by rejecting early
    
    3. **Magic Bytes Check** (Medium Security)
       - Reads first few bytes and compares to known signatures
       - Much harder to bypass than extension check
       - Attacker would need to craft a polyglot file
    
    4. **PIL Open Test** (Strong Security)
       - Actually parses the image file
       - Catches corrupted or malformed files
       - Most reliable validation method
    
    5. **Dimension Check** (Resource Protection)
       - Prevents decompression bombs (small file, huge dimensions)
       - A 1x1 billion pixel image = 4GB+ in memory
    
    Args:
        file: File-like object, Path, or string path to validate.
        max_size_bytes: Maximum allowed file size.
        allowed_extensions: Set of allowed extensions (without dot).
                           If None, uses default set.
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
        - If valid: (True, None)
        - If invalid: (False, "Description of why invalid")
    
    Example:
        ```python
        # Validate an uploaded file from FastAPI
        is_valid, error = validate_image_file(uploaded_file.file)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        
        # Validate a file path
        is_valid, error = validate_image_file(Path("/path/to/image.jpg"))
        ```
    
    Security Notes:
        ⚠️  This validation is necessary but not sufficient for security
        ⚠️  Always process images in a sandboxed environment if possible
        ⚠️  Consider running antivirus scans on uploaded files
        ⚠️  Store uploads outside the web root to prevent execution
    """
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS
    
    # Handle different input types
    file_path: Optional[Path] = None
    file_obj: Optional[BinaryIO] = None
    
    if isinstance(file, (str, Path)):
        file_path = Path(file)
        if not file_path.exists():
            return False, f"File not found: {file_path}"
    else:
        file_obj = file
    
    # -------------------------------------------------------------------------
    # Step 1: Extension Check (Weak but fast)
    # -------------------------------------------------------------------------
    if file_path:
        extension = file_path.suffix.lower().lstrip('.')
        if extension not in allowed_extensions:
            logger.warning(f"Rejected file with extension: {extension}")
            return False, f"File extension '.{extension}' not allowed. Allowed: {allowed_extensions}"
    
    # -------------------------------------------------------------------------
    # Step 2: Size Check (DoS Prevention)
    # -------------------------------------------------------------------------
    try:
        if file_path:
            file_size = file_path.stat().st_size
        else:
            # For file-like objects, seek to end and back
            current_pos = file_obj.tell()
            file_obj.seek(0, 2)  # Seek to end
            file_size = file_obj.tell()
            file_obj.seek(current_pos)  # Restore position
        
        if file_size > max_size_bytes:
            size_mb = file_size / (1024 * 1024)
            max_mb = max_size_bytes / (1024 * 1024)
            return False, f"File too large: {size_mb:.1f}MB (max: {max_mb:.1f}MB)"
        
        if file_size == 0:
            return False, "File is empty"
            
    except Exception as e:
        return False, f"Could not determine file size: {e}"
    
    # -------------------------------------------------------------------------
    # Step 3: Magic Bytes Check (Medium Security)
    # -------------------------------------------------------------------------
    try:
        if file_path:
            with open(file_path, 'rb') as f:
                header = f.read(16)  # Read first 16 bytes
        else:
            current_pos = file_obj.tell()
            file_obj.seek(0)
            header = file_obj.read(16)
            file_obj.seek(current_pos)
        
        # Check if header matches any known image format
        is_known_format = False
        for format_name, signatures in IMAGE_MAGIC_BYTES.items():
            for sig in signatures:
                if header.startswith(sig):
                    is_known_format = True
                    logger.debug(f"Detected format: {format_name}")
                    break
            if is_known_format:
                break
        
        if not is_known_format:
            logger.warning(f"Unknown file format. Header: {header[:8].hex()}")
            return False, "File does not appear to be a valid image (unknown format)"
            
    except Exception as e:
        return False, f"Could not read file header: {e}"
    
    # -------------------------------------------------------------------------
    # Step 4: PIL Open Test (Strong Security)
    # -------------------------------------------------------------------------
    try:
        if file_path:
            img = Image.open(file_path)
        else:
            file_obj.seek(0)
            img = Image.open(file_obj)
        
        # Force PIL to actually load the image data
        # Some attacks hide malicious data that only appears when loading
        img.verify()  # Verify the image is valid
        
        # Need to reopen after verify() as it closes the file
        if file_path:
            img = Image.open(file_path)
        else:
            file_obj.seek(0)
            img = Image.open(file_obj)
        
        # Get dimensions
        width, height = img.size
        
    except UnidentifiedImageError:
        return False, "File is not a recognized image format"
    except Exception as e:
        return False, f"Failed to open image: {e}"
    
    # -------------------------------------------------------------------------
    # Step 5: Dimension Check (Resource Protection)
    # -------------------------------------------------------------------------
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        return False, (
            f"Image dimensions too large: {width}x{height}. "
            f"Maximum: {MAX_DIMENSION}x{MAX_DIMENSION}"
        )
    
    # Check for potential decompression bomb
    # A small compressed file could expand to huge dimensions
    pixel_count = width * height
    MAX_PIXELS = 178956970  # ~178 million pixels (similar to Pillow's default)
    if pixel_count > MAX_PIXELS:
        return False, (
            f"Image has too many pixels: {pixel_count:,}. "
            f"Maximum: {MAX_PIXELS:,}"
        )
    
    logger.debug(f"Image validated: {width}x{height}, {file_size} bytes")
    return True, None


def get_image_hash(
    image: Union[Image.Image, Path, str, BinaryIO],
    algorithm: str = 'phash',
) -> Optional[str]:
    """
    Calculate a perceptual hash of an image for duplicate detection.
    
    What is Perceptual Hashing?
    --------------------------
    Unlike cryptographic hashes (SHA256), perceptual hashes produce
    similar output for visually similar images. This is useful for:
    - Detecting duplicate uploads (even if resized or recompressed)
    - Finding near-duplicate images
    - Content-based image retrieval
    
    Hash Types:
    ----------
    - **aHash** (Average Hash): Fast but less accurate
      Resizes to 8x8, converts to grayscale, compares to mean
    
    - **pHash** (Perceptual Hash): Good balance (recommended)
      Uses DCT (Discrete Cosine Transform) for better accuracy
    
    - **dHash** (Difference Hash): Good for simple comparisons
      Compares adjacent pixels for gradient patterns
    
    - **wHash** (Wavelet Hash): Best for photographs
      Uses wavelet transform for multi-resolution analysis
    
    How pHash Works:
    ---------------
    1. Resize image to 32x32
    2. Convert to grayscale
    3. Apply Discrete Cosine Transform (like JPEG compression)
    4. Keep low-frequency components (overall structure)
    5. Threshold to binary (0s and 1s)
    6. Return as hex string
    
    Comparison:
    ----------
    Two hashes can be compared using Hamming distance:
    ```python
    import imagehash
    distance = hash1 - hash2  # Returns number of different bits
    if distance <= 5:  # Threshold (experiment with this)
        print("Images are similar!")
    ```
    
    Args:
        image: PIL Image, path to image, or file-like object.
        algorithm: Hash algorithm - 'ahash', 'phash', 'dhash', 'whash'.
    
    Returns:
        Hex string representation of the hash, or None on error.
    
    Example:
        ```python
        # Check if two images are similar
        hash1 = get_image_hash("photo1.jpg")
        hash2 = get_image_hash("photo2.jpg")
        
        # Compare (using simple string comparison for exact match)
        if hash1 == hash2:
            print("These images are perceptually identical!")
        
        # For similarity threshold, use imagehash library directly:
        # import imagehash
        # if abs(imagehash.hex_to_hash(hash1) - imagehash.hex_to_hash(hash2)) <= 5:
        #     print("These images are similar!")
        ```
    
    Limitations:
        ⚠️  Perceptual hashes are NOT suitable for security purposes
        ⚠️  They can produce false positives (similar != same)
        ⚠️  They can produce false negatives (same != detected)
        ⚠️  Cropping may change the hash significantly
    """
    try:
        # Import imagehash (optional dependency)
        import imagehash
    except ImportError:
        logger.warning(
            "imagehash library not installed. Install with: pip install imagehash"
        )
        # Fall back to simple MD5 hash (not perceptual, but works)
        return _get_simple_hash(image)
    
    # Open image if needed
    try:
        if isinstance(image, Image.Image):
            img = image
        elif isinstance(image, (str, Path)):
            img = Image.open(image)
        else:
            image.seek(0)
            img = Image.open(image)
    except Exception as e:
        logger.error(f"Failed to open image for hashing: {e}")
        return None
    
    # Calculate hash based on algorithm
    try:
        if algorithm == 'ahash':
            # Average Hash: Simple and fast
            hash_obj = imagehash.average_hash(img)
        elif algorithm == 'phash':
            # Perceptual Hash: Best general-purpose option
            hash_obj = imagehash.phash(img)
        elif algorithm == 'dhash':
            # Difference Hash: Good for gradient patterns
            hash_obj = imagehash.dhash(img)
        elif algorithm == 'whash':
            # Wavelet Hash: Best for photographs
            hash_obj = imagehash.whash(img)
        else:
            logger.warning(f"Unknown hash algorithm: {algorithm}, using phash")
            hash_obj = imagehash.phash(img)
        
        return str(hash_obj)
        
    except Exception as e:
        logger.error(f"Failed to calculate image hash: {e}")
        return None


def _get_simple_hash(image: Union[Image.Image, Path, str, BinaryIO]) -> Optional[str]:
    """
    Calculate a simple MD5 hash of image bytes (fallback when imagehash unavailable).
    
    Note: This is NOT a perceptual hash - it will be different for
    resized or recompressed versions of the same image.
    """
    try:
        if isinstance(image, Image.Image):
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            data = buffer.getvalue()
        elif isinstance(image, (str, Path)):
            with open(image, 'rb') as f:
                data = f.read()
        else:
            image.seek(0)
            data = image.read()
        
        return hashlib.md5(data).hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate simple hash: {e}")
        return None


def convert_heic_to_jpeg(
    heic_file: Union[Path, str, BinaryIO],
    quality: int = 90,
) -> Image.Image:
    """
    Convert Apple HEIC/HEIF format to JPEG-compatible PIL Image.
    
    What is HEIC?
    ------------
    HEIC (High Efficiency Image Container) is a container format using
    HEVC (H.265) compression. Apple uses it as the default photo format
    on iPhones since iOS 11.
    
    Benefits of HEIC:
    - 40-50% smaller than JPEG at similar quality
    - Supports 16-bit color depth
    - Can store multiple images (e.g., live photos)
    
    Why Convert?
    -----------
    - Not supported by most web browsers (2024)
    - Not supported by many image processing tools
    - JPEG has universal compatibility
    
    Dependencies:
    ------------
    This function requires one of these libraries:
    - pillow-heif (recommended): `pip install pillow-heif`
    - pyheif: `pip install pyheif` (requires libheif)
    
    Args:
        heic_file: Path to HEIC file or file-like object.
        quality: JPEG quality for the conversion (1-100).
    
    Returns:
        PIL Image in RGB format (ready to save as JPEG).
    
    Raises:
        ImageValidationError: If conversion fails or dependency is missing.
    
    Example:
        ```python
        # Convert and save as JPEG
        if file_path.suffix.lower() in ('.heic', '.heif'):
            img = convert_heic_to_jpeg(file_path)
            img.save("converted.jpg")
        
        # Process converted image
        img = convert_heic_to_jpeg(uploaded_file)
        thumbnail = img.copy()
        thumbnail.thumbnail((400, 400))
        ```
    
    Performance Note:
        HEIC conversion is CPU-intensive. For a 12MP image:
        - Decode time: ~200-500ms
        - Memory: ~50MB peak
        Consider limiting concurrent conversions in production.
    """
    try:
        # Try pillow-heif first (most compatible)
        import pillow_heif
        
        # Register HEIF opener with Pillow
        pillow_heif.register_heif_opener()
        
        # Now PIL can open HEIC directly
        if isinstance(heic_file, (str, Path)):
            img = Image.open(heic_file)
        else:
            heic_file.seek(0)
            img = Image.open(heic_file)
        
        # Convert to RGB (HEIC might be RGBA or other mode)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        logger.info(f"Converted HEIC image: {img.size}")
        return img
        
    except ImportError:
        pass  # Try alternative library
    
    try:
        # Try pyheif as fallback
        import pyheif
        
        if isinstance(heic_file, (str, Path)):
            heif_file = pyheif.read(heic_file)
        else:
            heic_file.seek(0)
            heif_file = pyheif.read(heic_file.read())
        
        # Create PIL Image from decoded data
        img = Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw",
            heif_file.mode,
            heif_file.stride,
        )
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        logger.info(f"Converted HEIC image (pyheif): {img.size}")
        return img
        
    except ImportError:
        raise ImageValidationError(
            "HEIC conversion requires pillow-heif or pyheif library. "
            "Install with: pip install pillow-heif"
        )
    except Exception as e:
        raise ImageValidationError(f"Failed to convert HEIC image: {e}")


def get_image_dimensions(
    file: Union[BinaryIO, Path, str],
) -> Tuple[int, int]:
    """
    Get image dimensions without fully loading the image.
    
    This is faster and uses less memory than Image.open().size
    because Pillow can read dimensions from header without
    decoding the entire image.
    
    Args:
        file: File-like object or path to image.
    
    Returns:
        Tuple of (width, height) in pixels.
    
    Raises:
        ImageValidationError: If file is not a valid image.
    """
    try:
        if isinstance(file, (str, Path)):
            with Image.open(file) as img:
                return img.size
        else:
            file.seek(0)
            with Image.open(file) as img:
                return img.size
    except Exception as e:
        raise ImageValidationError(f"Failed to get image dimensions: {e}")


def estimate_jpeg_size(
    image: Image.Image,
    quality: int = 85,
) -> int:
    """
    Estimate the file size of an image if saved as JPEG.
    
    Useful for predicting storage requirements before saving.
    The estimate is approximate - actual size may vary by 10-20%.
    
    Args:
        image: PIL Image to estimate.
        quality: JPEG quality setting (1-100).
    
    Returns:
        Estimated file size in bytes.
    """
    # Save to buffer to get actual compressed size
    buffer = io.BytesIO()
    
    # Convert to RGB if needed (JPEG doesn't support alpha)
    if image.mode != 'RGB':
        img = image.convert('RGB')
    else:
        img = image
    
    img.save(buffer, format='JPEG', quality=quality)
    return buffer.tell()
