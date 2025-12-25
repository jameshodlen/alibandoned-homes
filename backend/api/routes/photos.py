"""
Photos API Routes - Upload and manage photos for locations.

EDUCATIONAL: File Upload Handling in FastAPI
============================================

File uploads in web APIs:
-------------------------
1. Multipart form data: Standard for browser file uploads
2. Base64 encoded: Files as JSON strings (not recommended - larger size)
3. Presigned URLs: Client uploads directly to storage (S3, GCS)

We use multipart form data because:
- Standard approach supported by all browsers
- FastAPI makes it easy with UploadFile
- Efficient for binary data
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import os
import uuid
from pathlib import Path

from api.auth import get_current_user
from database.base import get_async_session
from database.models import Photo, Location
from api.schemas import PhotoResponse

router = APIRouter()

# EDUCATIONAL: File Storage Configuration
#
# Where to store uploaded files?
# 1. Local filesystem (development):
#    - Simple, no extra services
#    - Doesn't scale (limited disk space)
#    - Files lost if server crashes
#
# 2. Object storage (production):
#    - AWS S3, Google Cloud Storage, Azure Blob
#    - Scalable, redundant, CDN-ready
#    - Costs money but worth it
#
# 3. Database (NOT recommended):
#    - Bloats database
#    - Slow queries
#    - Hard to serve with CDN

UPLOAD_DIR = Path("uploads/photos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/{location_id}/upload", response_model=List[PhotoResponse])
async def upload_photos(
    location_id: str,
    files: List[UploadFile] = File(..., description="Photos to upload (max 10)"),
    db: AsyncSession = Depends(get_async_session),
    current_user: str = Depends(get_current_user)
):
    """
    Upload photos for a location.
    
    EDUCATIONAL: File Upload Best Practices
    --------------------------------------
    1. Validate file type (only images)
    2. Limit file size (prevent disk fill)
    3. Scan for malware (production)
    4. Generate unique filename (prevent overwrite)
    5. Create thumbnail (faster loading)
    6. Strip EXIF GPS data (privacy)
    7. Store metadata in database
    
    Security considerations:
    - Validate content-type (don't trust client)
    - Check actual file contents (magic bytes)
    - Limit upload rate
    - Scan for malware
    - Don't execute uploaded files!
    
    Args:
        location_id: UUID of location to attach photos to
        files: List of uploaded files
        db: Database session
        current_user: Authenticated user
        
    Returns:
        List of created photo records
        
    Raises:
        400: Invalid file type or size
        404: Location not found
        413: File too large
    """
    # EDUCATIONAL: Validate location exists
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    # EDUCATIONAL: Validate upload count
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files per upload"
        )
    
    photo_records = []
    
    for file in files:
        # EDUCATIONAL: File Type Validation
        #
        # Check both:
        # 1. Content-Type header (can be spoofed!)
        # 2. File extension
        # 3. (Production) Magic bytes check (actual file content)
        
        # Validate content type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File {file.filename} is not an image"
            )
        
        # Validate file extension
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        file_ext = Path(file.filename).suffix.lower() if file.filename else ""
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file_ext} not allowed. Allowed: {allowed_extensions}"
            )
        
# EDUCATIONAL: Generate unique filename
        # Don't use original filename directly:
        # - Could overwrite existing files
        # - Could contain path traversal (../../etc/passwd)
        # - Could have special characters
        #
        # Instead:
        # - Generate UUID
        # - Keep original extension
        # - Store in subfolders by date (helps organization)
        file_id = str(uuid.uuid4())
        filename = f"{file_id}{file_ext}"
        file_path = UPLOAD_DIR / filename
        
        # EDUCATIONAL: Save file to disk
        # 
        # UploadFile.read() loads entire file into memory
        # For large files, use chunks:
        # ```python
        # with open(file_path, "wb") as f:
        #     while chunk := await file.read(1024 * 1024):  # 1MB chunks
        #         f.write(chunk)
        # ```
        contents = await file.read()
        
        # Check file size
        # EDUCATIONAL: File Size Limits
        # - Prevents disk fill attacks
        # - Ensures reasonable upload times
        # - Typical limits: 5MB for photos, 100MB for videos
        max_size = 10 * 1024 * 1024  # 10MB
        if len(contents) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {max_size / 1024 / 1024}MB"
            )
        
        # Write file
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # TODO: Generate thumbnail
        # TODO: Strip EXIF GPS data
        # TODO: Extract safe metadata (camera model, timestamp)
        
        # Create database record
        photo = Photo(
            location_id=location_id,
            file_path=str(file_path),
            thumbnail_path=None,  # TODO: Generate thumbnail
            photo_type="ground"
        )
        db.add(photo)
        photo_records.append(photo)
    
    await db.commit()
    
    # Refresh to load generated IDs
    for photo in photo_records:
        await db.refresh(photo)
    
    return photo_records


@router.get("/{photo_id}/download")
async def download_photo(
    photo_id: str,
    thumbnail: bool = False,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Download a photo file.
    
    EDUCATIONAL: Serving Files from FastAPI
    --------------------------------------
    FileResponse: Stream file to client
    - Efficient (doesn't load entire file into memory)
    - Sets correct Content-Type header
    - Supports range requests (partial downloads)
    
    In production:
    - Serve static files via CDN/reverse proxy (nginx, CloudFront)
    - FastAPI shouldn't serve files (slow, wastes app server resources)
    - Use presigned URLs for direct downloads from S3/GCS
    
    Args:
        photo_id: UUID of photo
        thumbnail: If true, return thumbnail instead of full image
        db: Database session
        
    Returns:
        File stream
        
    Raises:
        404: Photo not found or file missing
    """
    photo = await db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found"
        )
    
    # Choose file path
    file_path = photo.thumbnail_path if thumbnail and photo.thumbnail_path else photo.file_path
    
    # Check file exists
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo file not found on disk"
        )
    
    # EDUCATIONAL: Content-Type Detection
    # Determine MIME type from file extension
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }
    ext = Path(file_path).suffix.lower()
    media_type = content_types.get(ext, "application/octet-stream")
    
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=f"photo_{photo_id}{ext}"
    )


@router.delete("/{photo_id}")
async def delete_photo(
    photo_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: str = Depends(get_current_user)
):
    """
    Delete a photo and its file.
    
    EDUCATIONAL: Deleting Files Safely
    ----------------------------------
    When deleting a record with associated files:
    1. Delete database record first (in transaction)
    2. If successful, delete file from disk
    3. If file deletion fails, log error (don't fail the request)
    
    Why this order?
    - Database is source of truth
    - Orphaned files are okay (can clean up later)
    - Missing files for existing records are problems
    """
    photo = await db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found"
        )
    
    # Store file paths before deleting record
    file_path = photo.file_path
    thumbnail_path = photo.thumbnail_path
    
    # Delete database record
    await db.delete(photo)
    await db.commit()
    
    # Delete files (best effort - don't fail if can't delete)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Warning: Failed to delete file {file_path}: {e}")
    
    try:
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
    except Exception as e:
        print(f"Warning: Failed to delete thumbnail {thumbnail_path}: {e}")
    
    return {"message": "Photo deleted successfully"}
