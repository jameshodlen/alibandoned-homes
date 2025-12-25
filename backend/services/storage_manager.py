"""
Storage Manager for Organized File Storage
===========================================

This module handles file storage and organization for the application,
particularly for photos associated with abandoned property locations.

Why a Storage Manager?
---------------------
Centralized file storage management provides:
1. Consistent directory structure across the application
2. Atomic file operations with proper error handling
3. Easy migration between storage backends (local → S3 → GCS)
4. Clean separation between business logic and file I/O

Directory Structure:
-------------------
We organize files chronologically and by location:

```
/storage/
└── photos/
    └── 2024/                    # Year
        └── 01/                  # Month
            └── abc-123-def/     # Location ID
                ├── ground_uuid1.jpg      # Photo type + UUID
                ├── ground_uuid1_web.jpg  # Web optimized
                ├── ground_uuid1_thumb.jpg # Thumbnail
                └── satellite_uuid2.jpg
```

Benefits of this structure:
- Chronological: Easy to find recent uploads, archive old data
- Location grouping: All photos for a location are together
- Unique filenames: UUID prevents conflicts
- Type prefixes: Easy to identify photo sources

Storage Backends:
----------------
This implementation uses local filesystem storage, but the interface
is designed for easy migration to cloud storage:

TODO: Future implementations:
- AWS S3 backend
- Google Cloud Storage backend
- Azure Blob Storage backend

Example Usage:
-------------
```python
from backend.services.storage_manager import StorageManager

storage = StorageManager(base_path="/app/storage")

# Get path for a new photo
file_path = storage.organize_file_path(
    location_id="abc-123-def",
    photo_type="ground",
    file_extension="jpg"
)
# Returns: /app/storage/photos/2024/01/abc-123-def/ground_uuid.jpg

# Save an image
from PIL import Image
img = Image.open("uploaded.jpg")
file_size = storage.save_image(img, file_path, quality=85)

# Clean up location photos
storage.delete_location_photos("abc-123-def")
```
"""

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Union

# We use Pillow (PIL) for image handling
# It's the most popular Python imaging library
from PIL import Image

# Configure logging for storage operations
logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception for storage-related errors."""
    pass


class DiskSpaceError(StorageError):
    """Raised when there's insufficient disk space."""
    pass


class FileNotFoundStorageError(StorageError):
    """Raised when a requested file doesn't exist."""
    pass


class StorageManager:
    """
    Manages file storage with organized directory structure.
    
    This class handles all file system operations for storing images,
    providing a clean interface that can be adapted to different
    storage backends (local, S3, GCS, etc.).
    
    Why use a dedicated storage manager?
    -----------------------------------
    1. Abstraction: Business logic doesn't care WHERE files are stored
    2. Consistency: All files follow the same organization scheme
    3. Testability: Can mock storage operations in tests
    4. Migration: Easy to switch storage backends later
    
    Attributes:
        base_path: Root directory for all storage operations
        photos_subdir: Subdirectory for photos (default: "photos")
    
    Thread Safety:
        File operations are generally atomic on modern filesystems,
        but this class is NOT thread-safe for directory creation.
        Use proper locking for multi-threaded environments.
    """
    
    def __init__(
        self,
        base_path: Union[str, Path] = "/storage",
        photos_subdir: str = "photos",
    ) -> None:
        """
        Initialize the storage manager.
        
        Args:
            base_path: Root directory for all storage. Will be created
                      if it doesn't exist.
            photos_subdir: Subdirectory name for photos within base_path.
        
        Raises:
            StorageError: If base_path cannot be created.
        
        Example:
            ```python
            # Development
            storage = StorageManager(base_path="./local_storage")
            
            # Production
            storage = StorageManager(base_path="/mnt/data/storage")
            ```
        
        Note:
            Using pathlib.Path instead of string paths because:
            - Cross-platform compatibility (Windows, Linux, macOS)
            - Cleaner path manipulation (/ operator for joining)
            - Better type safety and IDE support
        """
        # Convert to Path object for consistent handling
        # pathlib.Path is preferred over os.path for modern Python
        self.base_path = Path(base_path)
        self.photos_subdir = photos_subdir
        
        # Full path to photos directory
        self.photos_path = self.base_path / photos_subdir
        
        # Ensure base directories exist
        try:
            # parents=True creates parent directories if needed
            # exist_ok=True doesn't error if directory exists
            self.base_path.mkdir(parents=True, exist_ok=True)
            self.photos_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Storage initialized at: {self.base_path}")
        except PermissionError as e:
            raise StorageError(
                f"Cannot create storage directory at {self.base_path}. "
                f"Check permissions. Error: {e}"
            )
        except OSError as e:
            raise StorageError(
                f"Failed to create storage directory: {e}"
            )
    
    def organize_file_path(
        self,
        location_id: str,
        photo_type: str,
        file_extension: str,
        suffix: str = "",
    ) -> Path:
        """
        Generate an organized file path for a new photo.
        
        This method creates a deterministic, organized path structure:
        {base}/photos/{year}/{month}/{location_id}/{type}_{uuid}{suffix}.{ext}
        
        Why this structure?
        ------------------
        
        1. **Chronological organization** (year/month):
           - Easy to find recent uploads
           - Simplifies archival and backup policies
           - Prevents directories from getting too large
        
        2. **Location grouping**:
           - All photos for a location are together
           - Simplifies location deletion (rm -rf)
           - Easy to count photos per location
        
        3. **UUID filenames**:
           - Guaranteed unique (no collisions)
           - No PII in filename (vs. using address)
           - Safe characters (no escaping needed)
        
        4. **Type prefix** (ground_, satellite_):
           - Quick visual identification
           - Easy to filter by type
           - Clear purpose in filename
        
        5. **Suffix** (_web, _thumb):
           - Groups related files visually
           - Easy to identify image versions
           - Simple cleanup of derived files
        
        Args:
            location_id: UUID of the location (as string).
            photo_type: Type of photo (ground, satellite, street).
            file_extension: File extension without dot (jpg, png, webp).
            suffix: Optional suffix for variants (_web, _thumb).
        
        Returns:
            pathlib.Path to the organized file location.
            Directories are created if they don't exist.
        
        Example:
            ```python
            # Original photo
            path = storage.organize_file_path(
                location_id="abc-123",
                photo_type="ground",
                file_extension="jpg"
            )
            # Returns: /storage/photos/2024/01/abc-123/ground_uuid.jpg
            
            # Thumbnail version
            thumb_path = storage.organize_file_path(
                location_id="abc-123",
                photo_type="ground",
                file_extension="jpg",
                suffix="_thumb"
            )
            # Returns: /storage/photos/2024/01/abc-123/ground_uuid_thumb.jpg
            ```
        """
        # Get current date for chronological organization
        now = datetime.now()
        year = str(now.year)
        month = f"{now.month:02d}"  # Zero-padded month (01, 02, ..., 12)
        
        # Build the directory path
        # Using / operator with Path for clean joining
        directory = self.photos_path / year / month / location_id
        
        # Create directory structure if it doesn't exist
        # This is idempotent - safe to call multiple times
        directory.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename using UUID4
        # UUID4 is random and essentially impossible to collide
        unique_id = str(uuid.uuid4())[:12]  # First 12 chars is enough
        
        # Clean the file extension (remove leading dot if present)
        ext = file_extension.lstrip('.')
        
        # Construct filename: {photo_type}_{uuid}{suffix}.{ext}
        # Example: ground_abc123def456_thumb.jpg
        filename = f"{photo_type}_{unique_id}{suffix}.{ext}"
        
        # Full path to the file
        file_path = directory / filename
        
        logger.debug(f"Organized path: {file_path}")
        
        return file_path
    
    def save_image(
        self,
        image: Image.Image,
        file_path: Union[str, Path],
        quality: int = 85,
        optimize: bool = True,
    ) -> int:
        """
        Save a PIL Image to disk with optimization.
        
        This method handles the complexities of saving images:
        - Format detection from file extension
        - Quality vs size tradeoff
        - RGBA to RGB conversion for JPEG
        - Optimization for smaller files
        
        Quality Settings Explained:
        --------------------------
        JPEG/WebP quality (1-100):
        - 100: Maximum quality, large file size
        - 85: High quality, good balance (recommended for originals)
        - 75: Good quality, smaller size (good for web)
        - 60: Noticeable artifacts, much smaller
        
        PNG doesn't have quality setting - it's lossless.
        PNG uses compression level (0-9) in `compress_level` parameter.
        
        Args:
            image: PIL Image object to save.
            file_path: Destination path for the file.
            quality: JPEG/WebP quality (1-100). Higher = better quality.
            optimize: If True, use extra processing for smaller files.
                     Takes longer but reduces file size ~10-20%.
        
        Returns:
            File size in bytes.
        
        Raises:
            StorageError: If saving fails (disk full, permissions, etc.)
        
        Example:
            ```python
            from PIL import Image
            
            img = Image.open("uploaded.jpg")
            file_path = storage.organize_file_path(...)
            
            # Save with high quality (for originals)
            size = storage.save_image(img, file_path, quality=90)
            print(f"Saved {size} bytes")
            
            # Save with web optimization
            thumb_path = file_path.with_suffix('_thumb.jpg')
            storage.save_image(img, thumb_path, quality=75)
            ```
        
        Performance Note:
            optimize=True increases save time by 2-3x but reduces
            file size by 10-20%. Worth it for production.
        """
        file_path = Path(file_path)
        
        # Determine format from extension
        extension = file_path.suffix.lower()
        format_map = {
            '.jpg': 'JPEG',
            '.jpeg': 'JPEG',
            '.png': 'PNG',
            '.webp': 'WebP',
            '.gif': 'GIF',
        }
        
        save_format = format_map.get(extension, 'JPEG')
        
        # Prepare save parameters based on format
        save_kwargs = {}
        
        if save_format == 'JPEG':
            # JPEG doesn't support alpha channel (transparency)
            # Convert RGBA to RGB if needed
            if image.mode == 'RGBA':
                # Create white background and paste image on it
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])  # Use alpha as mask
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            save_kwargs = {
                'quality': quality,
                'optimize': optimize,
                # Progressive JPEG loads "blurry first, then sharp"
                # Better user experience for slow connections
                'progressive': True,
            }
            
        elif save_format == 'PNG':
            # PNG is lossless, no quality setting
            # compress_level: 0 = no compression, 9 = max compression
            save_kwargs = {
                'optimize': optimize,
                'compress_level': 6,  # Good balance of speed and size
            }
            
        elif save_format == 'WebP':
            # WebP supports both lossy and lossless
            # When quality < 100, it's lossy
            save_kwargs = {
                'quality': quality,
                'method': 4,  # Compression effort (0-6), 4 is balanced
            }
        
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the image
            image.save(file_path, format=save_format, **save_kwargs)
            
            # Get file size
            file_size = file_path.stat().st_size
            
            logger.info(f"Saved image: {file_path} ({file_size} bytes)")
            
            return file_size
            
        except OSError as e:
            # OSError includes disk full, permission denied, etc.
            if "No space left" in str(e):
                raise DiskSpaceError(f"Disk full, cannot save: {file_path}")
            raise StorageError(f"Failed to save image: {e}")
    
    def delete_file(self, file_path: Union[str, Path]) -> bool:
        """
        Delete a single file from storage.
        
        Args:
            file_path: Path to the file to delete.
        
        Returns:
            True if file was deleted, False if file didn't exist.
        
        Raises:
            StorageError: If deletion fails (permissions, etc.)
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.warning(f"File not found for deletion: {file_path}")
            return False
        
        try:
            file_path.unlink()  # unlink() is the Path method for deletion
            logger.info(f"Deleted file: {file_path}")
            return True
        except PermissionError:
            raise StorageError(f"Permission denied: cannot delete {file_path}")
        except OSError as e:
            raise StorageError(f"Failed to delete file: {e}")
    
    def delete_location_photos(
        self,
        location_id: str,
        dry_run: bool = False,
    ) -> Tuple[int, int]:
        """
        Delete all photos associated with a location.
        
        This performs a cascade delete of all photo files for a location.
        Use this when deleting a location from the database.
        
        Why cascade delete files?
        ------------------------
        When a Location record is deleted from the database, the associated
        Photo records are also deleted (via FK cascade). But database cascade
        doesn't delete the actual files from disk - we need to do that here.
        
        Order of operations for safe deletion:
        1. Delete files from disk FIRST (this method)
        2. Then delete database records
        
        Why this order? If database delete succeeds but file delete fails,
        you have orphaned files (annoying but not catastrophic). If file
        delete succeeds but database fails, you lose data (catastrophic).
        
        Args:
            location_id: UUID of the location whose photos to delete.
            dry_run: If True, report what would be deleted without deleting.
                    Useful for testing and auditing.
        
        Returns:
            Tuple of (files_deleted, bytes_freed).
        
        Raises:
            StorageError: If deletion fails.
        
        Example:
            ```python
            # Preview what will be deleted
            files, bytes = storage.delete_location_photos(
                location_id="abc-123",
                dry_run=True
            )
            print(f"Would delete {files} files ({bytes} bytes)")
            
            # Actually delete
            files, bytes = storage.delete_location_photos("abc-123")
            print(f"Deleted {files} files, freed {bytes} bytes")
            ```
        """
        files_deleted = 0
        bytes_freed = 0
        
        # Find all directories that might contain photos for this location
        # We need to search across all year/month directories
        pattern = f"**/{location_id}"
        
        location_dirs: List[Path] = []
        
        try:
            # Use glob to find all matching directories
            for dir_path in self.photos_path.glob(pattern):
                if dir_path.is_dir():
                    location_dirs.append(dir_path)
        except Exception as e:
            logger.error(f"Error searching for location directories: {e}")
            raise StorageError(f"Failed to search for location photos: {e}")
        
        if not location_dirs:
            logger.info(f"No photo directories found for location: {location_id}")
            return 0, 0
        
        # Delete each directory and its contents
        for dir_path in location_dirs:
            # Count files and sizes before deleting
            for file_path in dir_path.iterdir():
                if file_path.is_file():
                    bytes_freed += file_path.stat().st_size
                    files_deleted += 1
                    
                    if not dry_run:
                        logger.debug(f"Deleting: {file_path}")
            
            if not dry_run:
                try:
                    # shutil.rmtree deletes directory and all contents
                    shutil.rmtree(dir_path)
                    logger.info(f"Deleted directory: {dir_path}")
                except Exception as e:
                    raise StorageError(
                        f"Failed to delete directory {dir_path}: {e}"
                    )
        
        action = "Would delete" if dry_run else "Deleted"
        logger.info(
            f"{action} {files_deleted} files ({bytes_freed} bytes) "
            f"for location: {location_id}"
        )
        
        return files_deleted, bytes_freed
    
    def get_storage_stats(self) -> dict:
        """
        Get storage usage statistics.
        
        Returns:
            Dictionary with storage statistics:
            - total_files: Number of files stored
            - total_bytes: Total size in bytes
            - by_year: Breakdown by year
            - by_type: Breakdown by photo type
        
        Example:
            ```python
            stats = storage.get_storage_stats()
            print(f"Total: {stats['total_files']} files, "
                  f"{stats['total_bytes'] / 1e9:.2f} GB")
            ```
        """
        stats = {
            'total_files': 0,
            'total_bytes': 0,
            'by_year': {},
            'by_type': {},
        }
        
        try:
            # Walk through all files in photos directory
            for file_path in self.photos_path.rglob('*'):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    stats['total_files'] += 1
                    stats['total_bytes'] += file_size
                    
                    # Extract year from path
                    # Path structure: photos/2024/01/location_id/file.jpg
                    parts = file_path.relative_to(self.photos_path).parts
                    if len(parts) >= 1:
                        year = parts[0]
                        stats['by_year'][year] = stats['by_year'].get(year, 0) + file_size
                    
                    # Extract type from filename
                    # Filename: ground_uuid.jpg
                    photo_type = file_path.stem.split('_')[0]
                    stats['by_type'][photo_type] = stats['by_type'].get(photo_type, 0) + 1
                    
        except Exception as e:
            logger.error(f"Error calculating storage stats: {e}")
        
        return stats
