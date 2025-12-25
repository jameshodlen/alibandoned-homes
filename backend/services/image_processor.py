"""
Image Processor - Main Image Processing Pipeline
=================================================

This module provides the primary image processing functionality for the
Abandoned Homes Prediction application. It handles the complete lifecycle
of an uploaded photo:

1. Validate the uploaded file (security)
2. Extract EXIF metadata (for analysis and privacy handling)
3. Strip all EXIF data from the image (privacy protection)
4. Encrypt sensitive metadata (GPS, timestamps)
5. Generate multiple image versions (original, web, thumbnail)
6. Organize and save to storage

Why is EXIF Data a Privacy Concern?
-----------------------------------
EXIF (Exchangeable Image File Format) metadata is automatically embedded
in photos by cameras and smartphones. It can include:

**Highly Sensitive:**
- GPS coordinates (exactly where the photo was taken)
- Date/time (when it was taken)
- Device serial numbers (identifies the camera owner)

**Moderately Sensitive:**
- Camera make/model (can identify likely owner)
- Software version (identifies phone type)
- Thumbnail (may show cropped-out content)

**Generally Safe:**
- Image dimensions, color space
- Orientation
- Basic camera settings (ISO, aperture, shutter speed)

Real-world privacy risks:
- Photos of your home → reveals your address
- Photos over time → reveals your routine
- Photos of sensitive locations → reveals involvement

Our approach:
- Strip ALL metadata from stored images
- Encrypt GPS and timestamp data separately
- Keep only non-sensitive metadata for ML training

Example Usage:
-------------
```python
from backend.services.image_processor import ImageProcessor

processor = ImageProcessor(storage_base_path="/app/storage")

# Process an uploaded photo
with open("uploaded.jpg", "rb") as f:
    result = processor.process_image(
        image_file=f,
        location_id="abc-123-def",
        photo_type="ground"
    )

# Result contains:
# - original_path: Path to EXIF-stripped original
# - web_path: Web-optimized version (1920px max)
# - thumbnail_path: Small thumbnail (400px max)
# - safe_metadata: Camera model, dimensions, etc.
# - encrypted_metadata: Encrypted GPS and timestamps
# - key_id: For decrypting the metadata later
```

Dependencies:
------------
- Pillow (PIL): Image processing
- piexif: EXIF reading/manipulation (optional, we also support exifread)
- cryptography: Encryption of sensitive metadata

Performance Notes:
-----------------
Processing a 12MP JPEG typically takes:
- EXIF extraction: ~50ms
- EXIF stripping: ~100ms  
- Web version generation: ~200ms
- Thumbnail generation: ~50ms
- Total: ~400-500ms per image

For batch processing, consider using a worker queue (Celery, RQ).
"""

import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

from PIL import Image, ExifTags

# Import our other services
from backend.services.encryption_service import EncryptionService, EncryptionServiceError
from backend.services.storage_manager import StorageManager, StorageError
from backend.services.image_utils import (
    convert_heic_to_jpeg,
    get_image_hash,
    validate_image_file,
    ImageValidationError,
)

# Configure logging
logger = logging.getLogger(__name__)


class ImageProcessingError(Exception):
    """Base exception for image processing errors."""
    pass


class MetadataExtractionError(ImageProcessingError):
    """Raised when EXIF metadata extraction fails."""
    pass


class ImageProcessor:
    """
    Main service for processing uploaded images.
    
    This class orchestrates the complete image processing pipeline,
    from upload to storage. It handles privacy protection, multiple
    format support, and organized storage.
    
    Processing Pipeline:
    -------------------
    ```
    Upload → Validate → Extract EXIF → Strip EXIF → Encrypt Sensitive
       ↓
    Generate Versions → Save to Storage → Return Metadata
    ```
    
    Image Versions Generated:
    ------------------------
    1. **Original**: Full resolution, EXIF stripped, high quality
       - Use case: Archival, ML training
       - Quality: 95%
    
    2. **Web**: 1920px max dimension, optimized
       - Use case: Full-screen viewing in browser
       - Quality: 85%
    
    3. **Thumbnail**: 400px max dimension
       - Use case: Gallery grids, previews
       - Quality: 80%
    
    Attributes:
        storage: StorageManager for file operations
        encryption: EncryptionService for sensitive metadata
        web_max_dimension: Maximum pixels for web version (default 1920)
        thumbnail_max_dimension: Maximum pixels for thumbnail (default 400)
    
    Thread Safety:
        This class is NOT thread-safe for write operations to the same
        location. Use locks or process one image at a time per location.
    """
    
    # Default dimensions for generated versions
    WEB_MAX_DIMENSION = 1920  # Good for 1080p displays
    THUMBNAIL_MAX_DIMENSION = 400  # Good for gallery grids
    
    # Quality settings (1-100, higher = better quality + larger file)
    ORIGINAL_QUALITY = 95  # Near-lossless for archival
    WEB_QUALITY = 85  # Good balance for web viewing
    THUMBNAIL_QUALITY = 80  # Acceptable for small images
    
    # EXIF tag IDs for GPS data (standard EXIF specification)
    # These tags contain location information we must protect
    GPS_TAGS = {
        'GPSInfo',  # Container tag for all GPS data
        'GPSLatitude',
        'GPSLatitudeRef',
        'GPSLongitude', 
        'GPSLongitudeRef',
        'GPSAltitude',
        'GPSAltitudeRef',
        'GPSTimeStamp',
        'GPSDateStamp',
    }
    
    # EXIF tags that are safe to keep (no PII)
    SAFE_TAGS = {
        'Make',  # Camera manufacturer (e.g., Apple, Canon)
        'Model',  # Camera model (e.g., iPhone 12 Pro)
        'Orientation',  # Image rotation
        'XResolution',
        'YResolution',
        'ResolutionUnit',
        'ColorSpace',
        'ExifImageWidth',
        'ExifImageHeight',
        'FocalLength',
        'FNumber',  # Aperture
        'ExposureTime',
        'ISOSpeedRatings',
        'Flash',
        'WhiteBalance',
    }
    
    def __init__(
        self,
        storage_base_path: Union[str, Path] = "/storage",
        encryption_service: Optional[EncryptionService] = None,
    ) -> None:
        """
        Initialize the image processor.
        
        Args:
            storage_base_path: Root directory for file storage.
            encryption_service: Optional EncryptionService instance.
                              If None, a new one will be created.
        
        Raises:
            EncryptionServiceError: If encryption service fails to initialize
                                   (usually missing ENCRYPTION_MASTER_KEY).
        
        Example:
            ```python
            # Basic initialization
            processor = ImageProcessor(storage_base_path="./storage")
            
            # With custom encryption service (for testing)
            from backend.services.encryption_service import EncryptionService
            enc = EncryptionService(master_key=test_key)
            processor = ImageProcessor(
                storage_base_path="./storage",
                encryption_service=enc
            )
            ```
        """
        # Initialize storage manager for file operations
        self.storage = StorageManager(base_path=storage_base_path)
        
        # Initialize or use provided encryption service
        # Encryption is required for secure metadata storage
        if encryption_service:
            self.encryption = encryption_service
        else:
            self.encryption = EncryptionService()
        
        logger.info(f"ImageProcessor initialized with storage at: {storage_base_path}")
    
    def process_image(
        self,
        image_file: Union[BinaryIO, Path, str],
        location_id: str,
        photo_type: str,
    ) -> Dict[str, Any]:
        """
        Process an uploaded image through the complete pipeline.
        
        This is the main method you'll use. It handles everything:
        1. Validates the image (security check)
        2. Extracts and categorizes EXIF metadata
        3. Strips all metadata from the image
        4. Encrypts sensitive metadata (GPS, timestamps)
        5. Generates multiple size versions
        6. Saves everything to organized storage
        7. Returns paths and metadata for database storage
        
        Args:
            image_file: The uploaded image. Can be:
                - File-like object (from FastAPI UploadFile.file)
                - Path to a file on disk
                - String path to a file
            location_id: UUID of the location this photo belongs to.
                        Used for encryption key derivation and storage organization.
            photo_type: Type of photo - "ground", "satellite", or "street".
                       Used for file naming and organization.
        
        Returns:
            Dictionary containing:
            ```python
            {
                "original_path": "/storage/photos/2024/01/abc/.../ground_uuid.jpg",
                "web_path": "/storage/photos/2024/01/abc/.../ground_uuid_web.jpg",
                "thumbnail_path": "/storage/photos/2024/01/abc/.../ground_uuid_thumb.jpg",
                "safe_metadata": {
                    "make": "Apple",
                    "model": "iPhone 12 Pro",
                    "width": 4032,
                    "height": 3024,
                    ...
                },
                "encrypted_metadata": b"...",  # Encrypted bytes
                "key_id": "abc123def456",  # For later decryption
                "original_size_bytes": 2500000,
                "web_size_bytes": 500000,
                "thumbnail_size_bytes": 50000,
                "perceptual_hash": "d4f3e2a1b0c9d8e7",  # For duplicate detection
                "taken_at": "2024-01-15T14:30:00Z",  # From EXIF or None
            }
            ```
        
        Raises:
            ImageValidationError: If the file is not a valid image.
            ImageProcessingError: If processing fails at any stage.
        
        Example:
            ```python
            # FastAPI endpoint
            @app.post("/upload-photo/{location_id}")
            async def upload_photo(
                location_id: str,
                file: UploadFile,
            ):
                processor = ImageProcessor()
                
                # Process the uploaded file
                result = processor.process_image(
                    image_file=file.file,
                    location_id=location_id,
                    photo_type="ground"
                )
                
                # Save to database
                photo = Photo(
                    location_id=location_id,
                    file_path=result["original_path"],
                    thumbnail_path=result["thumbnail_path"],
                    stripped_metadata_json=result["safe_metadata"],
                    original_metadata_encrypted=result["encrypted_metadata"],
                    encryption_key_id=result["key_id"],
                    width=result["safe_metadata"]["width"],
                    height=result["safe_metadata"]["height"],
                    taken_at=result["taken_at"],
                )
                session.add(photo)
                await session.commit()
                
                return {"success": True, "photo_id": str(photo.id)}
            ```
        
        Security Notes:
            ⚠️  Always validate user input (location_id, photo_type)
            ⚠️  The returned paths are relative - don't expose full paths
            ⚠️  Logs do not contain sensitive metadata
        """
        logger.info(f"Processing image for location: {location_id}, type: {photo_type}")
        
        # =====================================================================
        # Step 1: Validate the image file
        # =====================================================================
        # This is our first line of defense against malicious uploads.
        # See image_utils.validate_image_file for security details.
        
        is_valid, error_msg = validate_image_file(image_file)
        if not is_valid:
            logger.warning(f"Image validation failed: {error_msg}")
            raise ImageValidationError(error_msg)
        
        # =====================================================================
        # Step 2: Open the image with Pillow
        # =====================================================================
        # Reset file position if it's a file-like object (after validation read it)
        
        try:
            if hasattr(image_file, 'seek'):
                image_file.seek(0)
            
            # Check if it's HEIC format and convert if needed
            if isinstance(image_file, (str, Path)):
                file_path = Path(image_file)
                if file_path.suffix.lower() in ('.heic', '.heif'):
                    logger.info("Converting HEIC to JPEG compatible format")
                    image = convert_heic_to_jpeg(image_file)
                else:
                    image = Image.open(image_file)
            else:
                # For file objects, we'll try to open directly
                # HEIC files need special handling (see convert_heic_to_jpeg)
                image = Image.open(image_file)
            
        except Exception as e:
            logger.error(f"Failed to open image: {e}")
            raise ImageProcessingError(f"Could not open image file: {e}")
        
        # =====================================================================
        # Step 3: Extract EXIF metadata before stripping
        # =====================================================================
        # We need to extract metadata BEFORE stripping because once stripped,
        # it's gone forever from the image file.
        
        metadata = self.extract_metadata(image)
        safe_metadata = metadata['safe']
        sensitive_metadata = metadata['sensitive']
        taken_at = metadata.get('taken_at')
        
        logger.debug(f"Extracted metadata - Safe: {len(safe_metadata)} fields, "
                    f"Sensitive: {len(sensitive_metadata)} fields")
        
        # =====================================================================
        # Step 4: Calculate perceptual hash for duplicate detection
        # =====================================================================
        # We do this BEFORE stripping EXIF because some hash algorithms
        # might use EXIF orientation data.
        
        perceptual_hash = get_image_hash(image)
        
        # =====================================================================
        # Step 5: Strip ALL EXIF data from the image
        # =====================================================================
        # This is critical for privacy. After this, the image has NO metadata.
        
        clean_image = self.strip_exif_data(image)
        
        # =====================================================================
        # Step 6: Encrypt sensitive metadata
        # =====================================================================
        # Even though we stripped it from the image, we encrypt and store
        # the original metadata for potential legal/compliance needs.
        
        encrypted_metadata = None
        key_id = None
        
        if sensitive_metadata:
            try:
                encrypted_metadata, key_id = self.encryption.encrypt_for_location(
                    data=sensitive_metadata,
                    location_id=location_id
                )
                logger.debug(f"Encrypted sensitive metadata with key_id: {key_id}")
            except EncryptionServiceError as e:
                logger.error(f"Failed to encrypt metadata: {e}")
                # Continue processing - encryption failure shouldn't stop the upload
                # But we should log this as a compliance concern
        
        # =====================================================================
        # Step 7: Generate multiple image versions
        # =====================================================================
        # We create multiple sizes to optimize for different use cases.
        
        # Determine output format (prefer JPEG for photos, preserve PNG for graphics)
        # Note: We use JPEG for most photos because it's much smaller than PNG
        # for photographic content and widely supported.
        original_format = image.format or 'JPEG'
        if original_format in ('PNG', 'GIF'):
            output_extension = original_format.lower()
        else:
            output_extension = 'jpg'
        
        # Generate file paths for all versions
        original_path = self.storage.organize_file_path(
            location_id=location_id,
            photo_type=photo_type,
            file_extension=output_extension,
            suffix=""  # No suffix for original
        )
        
        web_path = self.storage.organize_file_path(
            location_id=location_id,
            photo_type=photo_type,
            file_extension=output_extension,
            suffix="_web"
        )
        
        thumbnail_path = self.storage.organize_file_path(
            location_id=location_id,
            photo_type=photo_type,
            file_extension=output_extension,
            suffix="_thumb"
        )
        
        # Generate the web version (1920px max)
        web_image = self.generate_thumbnail(
            clean_image,
            max_size=self.WEB_MAX_DIMENSION
        )
        
        # Generate the thumbnail (400px max)
        thumbnail_image = self.generate_thumbnail(
            clean_image,
            max_size=self.THUMBNAIL_MAX_DIMENSION
        )
        
        # =====================================================================
        # Step 8: Save all versions to storage
        # =====================================================================
        
        try:
            original_size = self.storage.save_image(
                clean_image,
                original_path,
                quality=self.ORIGINAL_QUALITY
            )
            
            web_size = self.storage.save_image(
                web_image,
                web_path,
                quality=self.WEB_QUALITY
            )
            
            thumbnail_size = self.storage.save_image(
                thumbnail_image,
                thumbnail_path,
                quality=self.THUMBNAIL_QUALITY
            )
            
        except StorageError as e:
            logger.error(f"Failed to save images: {e}")
            raise ImageProcessingError(f"Failed to save images: {e}")
        
        logger.info(
            f"Saved images: original={original_size}B, "
            f"web={web_size}B, thumb={thumbnail_size}B"
        )
        
        # =====================================================================
        # Step 9: Prepare result dictionary for database storage
        # =====================================================================
        
        result = {
            # File paths (relative to storage root)
            "original_path": str(original_path),
            "web_path": str(web_path),
            "thumbnail_path": str(thumbnail_path),
            
            # Metadata
            "safe_metadata": safe_metadata,
            "encrypted_metadata": encrypted_metadata,
            "key_id": key_id,
            
            # File sizes (for storage tracking)
            "original_size_bytes": original_size,
            "web_size_bytes": web_size,
            "thumbnail_size_bytes": thumbnail_size,
            
            # Analysis data
            "perceptual_hash": perceptual_hash,
            "taken_at": taken_at,
        }
        
        logger.info(f"Image processing complete for location: {location_id}")
        
        return result
    
    def extract_metadata(
        self,
        image: Image.Image,
    ) -> Dict[str, Any]:
        """
        Extract and categorize EXIF metadata from an image.
        
        This method reads all available EXIF tags and separates them into:
        - **safe**: Metadata that can be stored in plain text (no PII)
        - **sensitive**: Metadata that must be encrypted (location, time)
        
        EXIF Structure:
        --------------
        EXIF data is organized into IFDs (Image File Directories):
        - IFD0: Main image tags (Make, Model, Orientation)
        - EXIF IFD: Camera settings (FocalLength, ExposureTime)
        - GPS IFD: Location data (Latitude, Longitude, Altitude)
        - IFD1: Thumbnail tags
        
        How GPS is Stored in EXIF:
        -------------------------
        GPS coordinates are stored as rational numbers in a specific format:
        ```
        GPSLatitude: ((40, 1), (43, 1), (567, 100))  # 40° 43' 5.67"
        GPSLatitudeRef: 'N'  # North or South
        GPSLongitude: ((74, 1), (0, 1), (2134, 100))  # 74° 0' 21.34"
        GPSLongitudeRef: 'W'  # West or East
        ```
        
        We convert this to decimal degrees:
        - 40° 43' 5.67" N = 40.71825
        - 74° 0' 21.34" W = -74.00593
        
        Args:
            image: PIL Image with potential EXIF data.
        
        Returns:
            Dictionary with structure:
            ```python
            {
                "safe": {
                    "make": "Apple",
                    "model": "iPhone 12 Pro",
                    "width": 4032,
                    "height": 3024,
                    "orientation": 1,
                    "focal_length": 4.2,
                    "f_number": 1.6,
                    "iso": 100,
                    ...
                },
                "sensitive": {
                    "gps_latitude": 40.71825,
                    "gps_longitude": -74.00593,
                    "gps_altitude": 10.5,
                    "datetime_original": "2024:01:15 14:30:00",
                    ...
                },
                "taken_at": datetime(2024, 1, 15, 14, 30, 0),  # Parsed or None
                "raw": {...}  # All raw EXIF data
            }
            ```
        
        Example:
            ```python
            image = Image.open("photo.jpg")
            metadata = processor.extract_metadata(image)
            
            print(f"Camera: {metadata['safe'].get('make')} "
                  f"{metadata['safe'].get('model')}")
            
            if metadata['sensitive'].get('gps_latitude'):
                print(f"Location: {metadata['sensitive']['gps_latitude']}, "
                      f"{metadata['sensitive']['gps_longitude']}")
            ```
        """
        safe_metadata: Dict[str, Any] = {}
        sensitive_metadata: Dict[str, Any] = {}
        raw_metadata: Dict[str, Any] = {}
        taken_at: Optional[datetime] = None
        
        # Always include basic image properties (these aren't from EXIF)
        safe_metadata['width'], safe_metadata['height'] = image.size
        safe_metadata['mode'] = image.mode  # RGB, RGBA, L, etc.
        safe_metadata['format'] = image.format
        
        # Try to get EXIF data
        # Pillow provides _getexif() for JPEG images
        try:
            exif_data = image._getexif()
        except AttributeError:
            # Some image formats don't have _getexif method
            exif_data = None
        except Exception as e:
            logger.warning(f"Failed to extract EXIF data: {e}")
            exif_data = None
        
        if not exif_data:
            logger.debug("No EXIF data found in image")
            return {
                'safe': safe_metadata,
                'sensitive': sensitive_metadata,
                'taken_at': None,
                'raw': {},
            }
        
        # Build a reverse mapping from tag ID to tag name
        # ExifTags.TAGS maps ID -> name (e.g., 271 -> 'Make')
        tag_names = {v: k for k, v in ExifTags.TAGS.items()}
        
        # Process each EXIF tag
        for tag_id, value in exif_data.items():
            # Get human-readable tag name
            tag_name = ExifTags.TAGS.get(tag_id, f"Unknown_{tag_id}")
            
            # Store raw value (might be bytes, need to handle encoding)
            try:
                if isinstance(value, bytes):
                    raw_metadata[tag_name] = value.decode('utf-8', errors='ignore')
                else:
                    raw_metadata[tag_name] = value
            except Exception:
                pass  # Skip problematic values
            
            # Categorize the tag
            if tag_name in self.GPS_TAGS or tag_name == 'GPSInfo':
                # GPS data is sensitive - handle specially
                if tag_name == 'GPSInfo':
                    # GPSInfo is a nested dictionary with GPS sub-tags
                    gps_coords = self._parse_gps_info(value)
                    if gps_coords:
                        sensitive_metadata.update(gps_coords)
            elif tag_name in ('DateTimeOriginal', 'DateTimeDigitized', 'DateTime'):
                # Datetime tags are sensitive (reveal when photo was taken)
                sensitive_metadata[tag_name.lower()] = value
                
                # Try to parse the datetime
                if taken_at is None and value:
                    taken_at = self._parse_exif_datetime(value)
            elif tag_name in self.SAFE_TAGS:
                # Add to safe metadata with lowercase keys
                safe_metadata[self._normalize_tag_name(tag_name)] = value
        
        logger.debug(
            f"Extracted EXIF: {len(safe_metadata)} safe, "
            f"{len(sensitive_metadata)} sensitive tags"
        )
        
        return {
            'safe': safe_metadata,
            'sensitive': sensitive_metadata,
            'taken_at': taken_at,
            'raw': raw_metadata,
        }
    
    def _parse_gps_info(
        self,
        gps_info_dict: Dict[int, Any],
    ) -> Dict[str, float]:
        """
        Parse GPS IFD data into decimal degrees.
        
        EXIF GPS Format:
        ---------------
        GPS coordinates in EXIF are stored as:
        - Degrees, minutes, seconds (three rational numbers)
        - Reference (N/S for latitude, E/W for longitude)
        
        Example raw data:
        ```
        1: 'N'                           # GPSLatitudeRef
        2: ((40, 1), (43, 1), (2854, 100))  # GPSLatitude
        3: 'W'                           # GPSLongitudeRef  
        4: ((74, 1), (0, 1), (2134, 100))   # GPSLongitude
        5: 0                             # GPSAltitudeRef (0=above sea level)
        6: (105, 10)                     # GPSAltitude (10.5 meters)
        ```
        
        Args:
            gps_info_dict: GPS IFD dictionary from EXIF data.
        
        Returns:
            Dictionary with decimal coordinates:
            ```python
            {
                "gps_latitude": 40.71904,
                "gps_longitude": -74.00593,
                "gps_altitude": 10.5
            }
            ```
        """
        result = {}
        
        # GPS tag IDs within the GPS IFD
        GPS_LAT_REF = 1  # 'N' or 'S'
        GPS_LAT = 2  # Latitude in DMS
        GPS_LON_REF = 3  # 'E' or 'W'
        GPS_LON = 4  # Longitude in DMS
        GPS_ALT_REF = 5  # 0=above sea level, 1=below
        GPS_ALT = 6  # Altitude in meters
        
        try:
            # Parse latitude
            if GPS_LAT in gps_info_dict and GPS_LAT_REF in gps_info_dict:
                lat_dms = gps_info_dict[GPS_LAT]
                lat_ref = gps_info_dict[GPS_LAT_REF]
                
                lat_decimal = self._dms_to_decimal(lat_dms)
                if lat_ref == 'S':
                    lat_decimal = -lat_decimal
                
                result['gps_latitude'] = lat_decimal
            
            # Parse longitude
            if GPS_LON in gps_info_dict and GPS_LON_REF in gps_info_dict:
                lon_dms = gps_info_dict[GPS_LON]
                lon_ref = gps_info_dict[GPS_LON_REF]
                
                lon_decimal = self._dms_to_decimal(lon_dms)
                if lon_ref == 'W':
                    lon_decimal = -lon_decimal
                
                result['gps_longitude'] = lon_decimal
            
            # Parse altitude
            if GPS_ALT in gps_info_dict:
                alt = gps_info_dict[GPS_ALT]
                if isinstance(alt, tuple):
                    altitude = alt[0] / alt[1] if alt[1] else 0
                else:
                    altitude = float(alt)
                
                # Check if below sea level
                if gps_info_dict.get(GPS_ALT_REF, 0) == 1:
                    altitude = -altitude
                
                result['gps_altitude'] = altitude
                
        except Exception as e:
            logger.warning(f"Failed to parse GPS data: {e}")
        
        return result
    
    def _dms_to_decimal(
        self,
        dms: Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]],
    ) -> float:
        """
        Convert degrees/minutes/seconds to decimal degrees.
        
        Math:
        ----
        decimal = degrees + minutes/60 + seconds/3600
        
        EXIF stores DMS as rationals: ((degrees_num, degrees_den), ...)
        
        Args:
            dms: Tuple of three rationals ((d_num, d_den), (m_num, m_den), (s_num, s_den))
        
        Returns:
            Decimal degrees as float.
        
        Example:
            40° 43' 5.67" = 40 + 43/60 + 5.67/3600 = 40.71825
        """
        try:
            # Each component is a tuple (numerator, denominator)
            degrees = dms[0][0] / dms[0][1] if dms[0][1] else 0
            minutes = dms[1][0] / dms[1][1] if dms[1][1] else 0
            seconds = dms[2][0] / dms[2][1] if dms[2][1] else 0
            
            return degrees + (minutes / 60) + (seconds / 3600)
        except (IndexError, TypeError, ZeroDivisionError):
            return 0.0
    
    def _parse_exif_datetime(self, datetime_str: str) -> Optional[datetime]:
        """
        Parse EXIF datetime string to Python datetime.
        
        EXIF uses format: "YYYY:MM:DD HH:MM:SS"
        Note the colons in the date part (not standard ISO format).
        
        Args:
            datetime_str: EXIF datetime string like "2024:01:15 14:30:00"
        
        Returns:
            Python datetime object, or None if parsing fails.
        """
        if not datetime_str:
            return None
        
        # EXIF datetime format
        exif_format = "%Y:%m:%d %H:%M:%S"
        
        try:
            return datetime.strptime(datetime_str.strip(), exif_format)
        except ValueError:
            # Try alternate formats
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(datetime_str.strip(), fmt)
                except ValueError:
                    continue
        
        return None
    
    def _normalize_tag_name(self, tag_name: str) -> str:
        """Convert CamelCase EXIF tag names to snake_case."""
        # Simple conversion: FNumber -> f_number
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', tag_name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    def strip_exif_data(self, image: Image.Image) -> Image.Image:
        """
        Remove ALL EXIF metadata from an image.
        
        Why Strip EXIF?
        --------------
        Even if we encrypt sensitive data, leaving metadata in the image
        creates unnecessary risk:
        
        1. **Defense in depth**: If encryption fails, data is still exposed
        2. **Accidental sharing**: Stripped images are safe to share
        3. **Smaller files**: EXIF can add 10-100KB to file size
        4. **Consistency**: All stored images have uniform structure
        
        How EXIF Stripping Works:
        ------------------------
        EXIF data is stored in specific segments of JPEG/TIFF files.
        Pillow can strip it by:
        1. Loading the image data (pixels)
        2. Saving without EXIF (by not including the exif parameter)
        
        For JPEG specifically:
        - App1 marker (FFE1) contains EXIF
        - We save without it
        
        For PNG:
        - PNG uses "chunks" for metadata (iTXt, tEXt, zTXt)
        - We strip these during save
        
        Args:
            image: PIL Image potentially containing EXIF data.
        
        Returns:
            New PIL Image with all metadata removed.
            Original image is not modified.
        
        Example:
            ```python
            original = Image.open("photo_with_gps.jpg")
            print(original._getexif())  # Shows EXIF data
            
            clean = processor.strip_exif_data(original)
            print(clean._getexif())  # None - no EXIF
            ```
        
        Performance Note:
            This operation recompresses the image, which takes time
            and may slightly alter the image (for lossy formats).
            For lossless metadata removal, consider piexif library.
        """
        # Get image data (color mode, size, pixel data)
        # We're essentially creating a copy without metadata
        
        # Handle orientation BEFORE stripping EXIF
        # EXIF orientation tag tells us how to rotate the image for correct display
        # If we strip EXIF without applying orientation, image may appear rotated
        try:
            from PIL import ImageOps
            # ExifTranspose applies any rotation specified in EXIF
            image = ImageOps.exif_transpose(image) or image
        except Exception as e:
            logger.debug(f"Could not apply EXIF orientation: {e}")
        
        # Method 1: Save to buffer and reload (most reliable)
        # This creates a new image without any metadata
        buffer = io.BytesIO()
        
        # Determine format for saving
        # We need to handle RGBA -> RGB conversion for JPEG
        if image.mode == 'RGBA':
            # JPEG doesn't support alpha channel
            # Create white background and paste image
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            save_image = background
            format_to_use = 'JPEG'
        elif image.mode in ('P', 'PA'):
            # Palette modes need conversion
            save_image = image.convert('RGB')
            format_to_use = 'JPEG'
        elif image.mode == 'RGB':
            save_image = image
            format_to_use = 'JPEG'
        else:
            # For other modes (L, LA, etc.), convert to RGB
            save_image = image.convert('RGB')
            format_to_use = 'JPEG'
        
        # Save without EXIF
        # By not passing exif parameter, Pillow won't include EXIF data
        save_image.save(
            buffer,
            format=format_to_use,
            quality=95,  # High quality to minimize re-compression artifacts
        )
        
        # Reload from buffer
        buffer.seek(0)
        clean_image = Image.open(buffer)
        
        # Force loading the image data
        # Otherwise it's still linked to the buffer
        clean_image.load()
        
        # Verify EXIF is gone
        try:
            remaining_exif = clean_image._getexif()
            if remaining_exif:
                logger.warning("EXIF data still present after stripping!")
        except AttributeError:
            pass  # No _getexif method means no EXIF
        
        logger.debug(f"Stripped EXIF from image: {image.size}")
        
        return clean_image
    
    def generate_thumbnail(
        self,
        image: Image.Image,
        max_size: int = 400,
    ) -> Image.Image:
        """
        Generate a thumbnail/resized version of an image.
        
        Why Thumbnails?
        --------------
        Full-resolution images are large (3-10MB for photos). Loading them:
        - Wastes bandwidth for small UI elements
        - Causes slow page loads
        - Uses unnecessary memory on client devices
        
        Thumbnails solve this by providing appropriately-sized versions:
        - Gallery grid: 200-400px thumbnails
        - Full-screen preview: 1920px web version
        - Print/download: Full resolution original
        
        Aspect Ratio Preservation:
        -------------------------
        We maintain the original aspect ratio to prevent distortion.
        The max_size parameter limits the LARGEST dimension.
        
        Examples (max_size=400):
        - 4000x3000 → 400x300 (landscape)
        - 3000x4000 → 300x400 (portrait)
        - 3000x3000 → 400x400 (square)
        
        Why LANCZOS Filter?
        ------------------
        Pillow offers several resampling filters:
        - NEAREST: Fastest, worst quality (pixelated)
        - BILINEAR: Fast, fair quality
        - BICUBIC: Slow, good quality
        - LANCZOS: Slowest, best quality (no aliasing)
        
        For thumbnails, quality matters more than speed,
        so we use LANCZOS.
        
        Args:
            image: PIL Image to resize.
            max_size: Maximum dimension in pixels (width or height).
        
        Returns:
            Resized PIL Image maintaining aspect ratio.
        
        Example:
            ```python
            # Create a gallery thumbnail
            thumb = processor.generate_thumbnail(full_image, max_size=400)
            thumb.save("thumbnail.jpg")
            
            # Create a web-optimized version
            web = processor.generate_thumbnail(full_image, max_size=1920)
            web.save("web_version.jpg", quality=85)
            ```
        
        Performance Note:
            LANCZOS resampling for a 4000x3000 → 400x300 takes ~50ms.
            For bulk processing, consider BILINEAR for 3x speedup.
        """
        # Get current dimensions
        width, height = image.size
        
        # Check if resize is needed
        if width <= max_size and height <= max_size:
            logger.debug(f"Image {width}x{height} already smaller than {max_size}")
            return image.copy()
        
        # Calculate new dimensions maintaining aspect ratio
        # The larger dimension will be set to max_size
        if width > height:
            # Landscape orientation
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            # Portrait or square orientation
            new_height = max_size
            new_width = int(width * (max_size / height))
        
        # Create a copy to avoid modifying the original
        # Use .copy() because thumbnail() modifies in place
        thumbnail = image.copy()
        
        # Pillow's thumbnail method is optimized for downscaling
        # It modifies the image in place
        # LANCZOS provides the best quality for downscaling
        thumbnail.thumbnail(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )
        
        logger.debug(f"Generated thumbnail: {width}x{height} → {thumbnail.size}")
        
        return thumbnail
    
    def encrypt_metadata(
        self,
        metadata_dict: Dict[str, Any],
        location_id: str,
    ) -> Tuple[bytes, str]:
        """
        Encrypt metadata dictionary for secure storage.
        
        This is a convenience wrapper around EncryptionService.encrypt_for_location.
        
        When Would We Decrypt This?
        --------------------------
        1. **GDPR data export**: User requests their data
        2. **Legal subpoena**: Law enforcement requires original metadata
        3. **Internal audit**: Verifying data integrity
        4. **Migration**: Moving data to a new system
        
        Args:
            metadata_dict: Dictionary of metadata to encrypt.
            location_id: Location ID for key derivation.
        
        Returns:
            Tuple of (encrypted_bytes, key_id).
        
        Raises:
            EncryptionServiceError: If encryption fails.
        """
        return self.encryption.encrypt_for_location(
            data=metadata_dict,
            location_id=location_id
        )
    
    def decrypt_metadata(
        self,
        encrypted_data: bytes,
        key_id: str,
        location_id: str,
    ) -> Dict[str, Any]:
        """
        Decrypt previously encrypted metadata.
        
        Security: This method should only be called for legitimate purposes:
        - User data export requests
        - Legal requirements
        - System administration
        
        Consider adding audit logging for decryption operations.
        
        Args:
            encrypted_data: Encrypted bytes from database.
            key_id: Key ID stored with the encrypted data.
            location_id: Location ID (must match original encryption).
        
        Returns:
            Original metadata dictionary.
        
        Raises:
            DecryptionError: If decryption fails.
        """
        # TODO: Add audit logging for compliance
        logger.info(f"Decrypting metadata for location: {location_id}")
        
        return self.encryption.decrypt_for_location(
            encrypted_data=encrypted_data,
            key_id=key_id,
            location_id=location_id
        )
