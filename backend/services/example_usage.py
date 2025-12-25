"""
Example Usage - Image Processing Pipeline
==========================================

This module demonstrates how to use the image processing service
in a real application. Each step is heavily commented to explain
what's happening and why.

This is meant to be read as a tutorial, not just run as code.

Prerequisites:
-------------
1. Set ENCRYPTION_MASTER_KEY environment variable:
   ```bash
   # Generate a key
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   
   # Set in your environment (Linux/Mac)
   export ENCRYPTION_MASTER_KEY="your-generated-key-here"
   
   # Or in .env file
   echo "ENCRYPTION_MASTER_KEY=your-key" >> .env
   ```

2. Install dependencies:
   ```bash
   pip install pillow cryptography imagehash pillow-heif
   ```

3. Create a storage directory:
   ```bash
   mkdir -p ./storage/photos
   ```

Running this example:
-------------------
```bash
python -m backend.services.example_usage
```
"""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Set up logging so we can see what's happening
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_environment():
    """
    Set up environment variables for the example.
    
    In production, these would be set in your deployment configuration.
    For this example, we generate a temporary key.
    """
    # Check if ENCRYPTION_MASTER_KEY is already set
    if not os.environ.get('ENCRYPTION_MASTER_KEY'):
        # Generate a temporary key for demonstration
        # ⚠️ In production, NEVER generate keys at runtime!
        from cryptography.fernet import Fernet
        temp_key = Fernet.generate_key().decode()
        os.environ['ENCRYPTION_MASTER_KEY'] = temp_key
        logger.warning(
            "Generated temporary encryption key. "
            "In production, set ENCRYPTION_MASTER_KEY in environment!"
        )


def example_basic_processing():
    """
    Example 1: Basic image processing workflow.
    
    This shows the most common use case: processing a user-uploaded photo.
    """
    print("\n" + "=" * 60)
    print("Example 1: Basic Image Processing")
    print("=" * 60 + "\n")
    
    # Import the processor
    from backend.services.image_processor import ImageProcessor
    
    # Initialize the processor
    # storage_base_path: Where to store processed images
    processor = ImageProcessor(storage_base_path="./storage")
    
    # For this example, we'll create a test image
    # In a real app, this would be an uploaded file
    from PIL import Image
    
    # Create a simple test image (red square)
    test_image = Image.new('RGB', (1000, 1000), color='red')
    
    # Save it temporarily to simulate an upload
    test_path = Path("./test_upload.jpg")
    test_image.save(test_path, format='JPEG')
    
    try:
        # Process the image through our pipeline
        result = processor.process_image(
            image_file=test_path,
            location_id="example-location-123",  # UUID in real app
            photo_type="ground"  # ground, satellite, or street
        )
        
        # Let's examine what we got back
        print("Processing complete! Results:")
        print("-" * 40)
        print(f"Original saved to:  {result['original_path']}")
        print(f"Web version saved:  {result['web_path']}")
        print(f"Thumbnail saved:    {result['thumbnail_path']}")
        print(f"\nFile sizes:")
        print(f"  Original:   {result['original_size_bytes']:,} bytes")
        print(f"  Web:        {result['web_size_bytes']:,} bytes")
        print(f"  Thumbnail:  {result['thumbnail_size_bytes']:,} bytes")
        print(f"\nSafe metadata (can store in plain text):")
        for key, value in result['safe_metadata'].items():
            print(f"  {key}: {value}")
        print(f"\nSensitive metadata encrypted: {result['encrypted_metadata'] is not None}")
        print(f"Encryption key ID: {result['key_id']}")
        print(f"Perceptual hash: {result['perceptual_hash']}")
        
    finally:
        # Clean up test file
        if test_path.exists():
            test_path.unlink()


def example_exif_extraction():
    """
    Example 2: Manually extracting and examining EXIF metadata.
    
    This shows how to use the metadata extraction independently,
    useful for analysis without full processing.
    """
    print("\n" + "=" * 60)
    print("Example 2: EXIF Metadata Extraction")
    print("=" * 60 + "\n")
    
    from backend.services.image_processor import ImageProcessor
    from PIL import Image
    
    processor = ImageProcessor(storage_base_path="./storage")
    
    # Create a test image (real photos would have EXIF data)
    test_image = Image.new('RGB', (500, 500), color='blue')
    
    # Extract metadata
    metadata = processor.extract_metadata(test_image)
    
    print("Extracted Metadata Structure:")
    print("-" * 40)
    print("\n1. SAFE metadata (no privacy concerns):")
    for key, value in metadata['safe'].items():
        print(f"   {key}: {value}")
    
    print("\n2. SENSITIVE metadata (encrypted before storage):")
    if metadata['sensitive']:
        for key, value in metadata['sensitive'].items():
            print(f"   {key}: {value}")
    else:
        print("   (None found - test image has no EXIF)")
    
    print(f"\n3. Date taken: {metadata['taken_at']}")


def example_encryption_workflow():
    """
    Example 3: Working with encrypted metadata.
    
    Shows how to encrypt sensitive data and later decrypt it
    (e.g., for GDPR data export requests).
    """
    print("\n" + "=" * 60)
    print("Example 3: Encryption Workflow")
    print("=" * 60 + "\n")
    
    from backend.services.encryption_service import EncryptionService
    
    # Initialize encryption service
    encryption = EncryptionService()
    
    # Simulate sensitive EXIF data with GPS coordinates
    sensitive_metadata = {
        "gps_latitude": 40.7128,
        "gps_longitude": -74.0060,
        "gps_altitude": 10.5,
        "datetime_original": "2024:01:15 14:30:00",
    }
    
    location_id = "test-location-456"
    
    print("Original sensitive metadata:")
    for key, value in sensitive_metadata.items():
        print(f"  {key}: {value}")
    
    # Encrypt the data
    encrypted_bytes, key_id = encryption.encrypt_for_location(
        data=sensitive_metadata,
        location_id=location_id
    )
    
    print(f"\nEncrypted data (first 50 bytes): {encrypted_bytes[:50]}...")
    print(f"Key ID (store this in database): {key_id}")
    
    # Simulate database storage
    print("\n[Simulating database storage...]")
    database_record = {
        "original_metadata_encrypted": encrypted_bytes,
        "encryption_key_id": key_id,
        "location_id": location_id,
    }
    
    # Later... user requests GDPR data export
    print("\n[User requests data export...]")
    
    # Decrypt the data
    decrypted_metadata = encryption.decrypt_for_location(
        encrypted_data=database_record["original_metadata_encrypted"],
        key_id=database_record["encryption_key_id"],
        location_id=database_record["location_id"],
    )
    
    print("\nDecrypted metadata (matches original):")
    for key, value in decrypted_metadata.items():
        print(f"  {key}: {value}")


def example_validation():
    """
    Example 4: Image validation for security.
    
    Shows how to validate uploaded files before processing.
    """
    print("\n" + "=" * 60)
    print("Example 4: Image Validation")
    print("=" * 60 + "\n")
    
    from backend.services.image_utils import validate_image_file
    from PIL import Image
    import io
    
    # Test 1: Valid JPEG image
    print("Test 1: Valid JPEG image")
    valid_image = Image.new('RGB', (100, 100), color='green')
    buffer = io.BytesIO()
    valid_image.save(buffer, format='JPEG')
    buffer.seek(0)
    
    is_valid, error = validate_image_file(buffer)
    print(f"  Valid: {is_valid}")
    print(f"  Error: {error}")
    
    # Test 2: Invalid file (not an image)
    print("\nTest 2: Invalid file (text file)")
    fake_image = io.BytesIO(b"This is not an image!")
    
    is_valid, error = validate_image_file(fake_image)
    print(f"  Valid: {is_valid}")
    print(f"  Error: {error}")
    
    # Test 3: Empty file
    print("\nTest 3: Empty file")
    empty_file = io.BytesIO(b"")
    
    is_valid, error = validate_image_file(empty_file)
    print(f"  Valid: {is_valid}")
    print(f"  Error: {error}")


def example_storage_organization():
    """
    Example 5: Understanding the storage structure.
    
    Shows how files are organized by date and location.
    """
    print("\n" + "=" * 60)
    print("Example 5: Storage Organization")
    print("=" * 60 + "\n")
    
    from backend.services.storage_manager import StorageManager
    
    storage = StorageManager(base_path="./storage_example")
    
    # Generate paths for different scenarios
    print("Path generation examples:")
    print("-" * 40)
    
    # Original photo
    path1 = storage.organize_file_path(
        location_id="loc-123",
        photo_type="ground",
        file_extension="jpg"
    )
    print(f"\nOriginal: {path1}")
    
    # Web version
    path2 = storage.organize_file_path(
        location_id="loc-123",
        photo_type="ground",
        file_extension="jpg",
        suffix="_web"
    )
    print(f"Web:      {path2}")
    
    # Thumbnail
    path3 = storage.organize_file_path(
        location_id="loc-123",
        photo_type="ground",
        file_extension="jpg",
        suffix="_thumb"
    )
    print(f"Thumb:    {path3}")
    
    # Different photo type
    path4 = storage.organize_file_path(
        location_id="loc-123",
        photo_type="satellite",
        file_extension="png"
    )
    print(f"Satellite: {path4}")
    
    print("\nNotice:")
    print("- Files are organized by year/month/location")
    print("- Each file has a unique UUID to prevent conflicts")
    print("- Related files (original, web, thumb) are in same directory")


def example_fastapi_integration():
    """
    Example 6: How to integrate with FastAPI.
    
    This is pseudo-code showing the typical integration pattern.
    """
    print("\n" + "=" * 60)
    print("Example 6: FastAPI Integration Pattern")
    print("=" * 60 + "\n")
    
    code_example = '''
# In your FastAPI endpoint file:

from fastapi import APIRouter, UploadFile, HTTPException
from backend.services.image_processor import ImageProcessor
from backend.services.image_utils import ImageValidationError

router = APIRouter()
processor = ImageProcessor(storage_base_path="/app/storage")

@router.post("/locations/{location_id}/photos")
async def upload_photo(
    location_id: str,
    photo_type: str,  # ground, satellite, street
    file: UploadFile,
):
    """
    Upload a photo for a location.
    
    The image will be:
    1. Validated for security
    2. EXIF data extracted and encrypted
    3. All metadata stripped from stored image
    4. Multiple versions generated (original, web, thumbnail)
    """
    try:
        # Process the uploaded image
        result = processor.process_image(
            image_file=file.file,
            location_id=location_id,
            photo_type=photo_type,
        )
        
        # Create database record
        photo = Photo(
            location_id=uuid.UUID(location_id),
            file_path=result["original_path"],
            thumbnail_path=result["thumbnail_path"],
            stripped_metadata_json=result["safe_metadata"],
            original_metadata_encrypted=result["encrypted_metadata"],
            encryption_key_id=result["key_id"],
            photo_type=PhotoType(photo_type),
            width=result["safe_metadata"]["width"],
            height=result["safe_metadata"]["height"],
        )
        
        session.add(photo)
        await session.commit()
        
        return {
            "photo_id": str(photo.id),
            "thumbnail_url": f"/media/{result['thumbnail_path']}",
            "message": "Photo uploaded successfully",
        }
        
    except ImageValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Photo upload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to process image")
'''
    
    print(code_example)


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("IMAGE PROCESSING SERVICE EXAMPLES")
    print("=" * 60)
    
    # Set up environment
    setup_environment()
    
    # Run examples
    example_basic_processing()
    example_exif_extraction()
    example_encryption_workflow()
    example_validation()
    example_storage_organization()
    example_fastapi_integration()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
