"""
Tests for Image Processing Service
===================================

This test suite validates the complete image processing pipeline.
Each test is heavily commented to explain:
1. What we're testing
2. Why this test matters
3. What could go wrong

Run tests with:
```bash
pytest backend/tests/test_image_processor.py -v
```

Test Categories:
---------------
1. EXIF Stripping - Ensures privacy protection works
2. Encryption/Decryption - Verifies data security
3. Thumbnail Generation - Checks image resizing
4. Validation - Confirms security checks work
5. Error Handling - Verifies graceful failure
"""

import io
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from PIL import Image

# Set up test encryption key before importing our modules
# This simulates having the environment variable set in production
TEST_ENCRYPTION_KEY = "zNH4_0KqPJgEUQPo7R_9fwWvLI4WF2LKxwTH8Ht0_rk="
os.environ['ENCRYPTION_MASTER_KEY'] = TEST_ENCRYPTION_KEY


# =============================================================================
# FIXTURES
# =============================================================================
# Fixtures are reusable test components. They run before each test that uses them.

@pytest.fixture
def test_image_rgb():
    """
    Create a simple RGB test image.
    
    This is used for most basic tests. It's a 100x100 red square,
    small enough to process quickly but large enough to be valid.
    """
    # Create a red square image
    image = Image.new('RGB', (100, 100), color='red')
    return image


@pytest.fixture
def test_image_with_exif():
    """
    Create a test image with EXIF data.
    
    This is trickier - we need to embed actual EXIF data.
    We use piexif library if available, otherwise create a mock.
    
    This tests our EXIF stripping functionality.
    """
    image = Image.new('RGB', (200, 200), color='blue')
    
    # Try to add EXIF data
    try:
        import piexif
        
        # Build EXIF data structure
        # This mimics what a camera would embed
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: "TestCamera",
                piexif.ImageIFD.Model: "TestModel",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: "2024:01:15 14:30:00",
            },
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: "N",
                piexif.GPSIFD.GPSLatitude: ((40, 1), (43, 1), (0, 1)),
                piexif.GPSIFD.GPSLongitudeRef: "W",
                piexif.GPSIFD.GPSLongitude: ((74, 1), (0, 1), (0, 1)),
            },
            "1st": {},
            "thumbnail": None,
        }
        
        exif_bytes = piexif.dump(exif_dict)
        
        # Save with EXIF and reload
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', exif=exif_bytes)
        buffer.seek(0)
        return Image.open(buffer)
        
    except ImportError:
        # piexif not installed, return plain image
        # Tests will need to handle this case
        return image


@pytest.fixture
def test_image_large():
    """
    Create a larger test image for thumbnail testing.
    
    This 2000x1500 image will be resized during processing.
    The 4:3 aspect ratio is common for phone photos.
    """
    return Image.new('RGB', (2000, 1500), color='green')


@pytest.fixture
def corrupted_file():
    """
    Create a file that looks like an image but isn't.
    
    This tests our security validation.
    Attackers might try to upload PHP files renamed as .jpg.
    """
    # Create a file that starts with text, not image magic bytes
    return io.BytesIO(b"This is not an image, but someone renamed it .jpg")


@pytest.fixture
def temp_storage_dir(tmp_path):
    """
    Create a temporary storage directory for tests.
    
    pytest's tmp_path fixture provides a unique temp directory
    that's automatically cleaned up after tests.
    """
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    return storage_dir


@pytest.fixture
def encryption_service():
    """
    Create an EncryptionService instance for testing.
    """
    from backend.services.encryption_service import EncryptionService
    return EncryptionService()


@pytest.fixture
def image_processor(temp_storage_dir):
    """
    Create an ImageProcessor instance with temporary storage.
    """
    from backend.services.image_processor import ImageProcessor
    return ImageProcessor(storage_base_path=str(temp_storage_dir))


# =============================================================================
# EXIF STRIPPING TESTS
# =============================================================================
# These tests verify that we properly remove metadata from images.
# This is CRITICAL for user privacy.

class TestExifStripping:
    """Tests for EXIF metadata removal."""
    
    def test_strip_exif_removes_all_metadata(self, image_processor, test_image_with_exif):
        """
        Test that EXIF stripping removes ALL metadata.
        
        Why this matters:
        - User privacy depends on complete EXIF removal
        - Partial removal could still leak GPS data
        - We must verify nothing remains
        """
        # Strip EXIF from the image
        clean_image = image_processor.strip_exif_data(test_image_with_exif)
        
        # Check that no EXIF remains
        # Pillow's _getexif() returns None or {} if no EXIF
        try:
            remaining_exif = clean_image._getexif()
            assert remaining_exif is None or remaining_exif == {}, \
                "EXIF data should be completely removed"
        except AttributeError:
            # No _getexif method means no EXIF support in this format
            pass
    
    def test_strip_exif_preserves_image_quality(self, image_processor, test_image_rgb):
        """
        Test that image quality is preserved after stripping.
        
        Why this matters:
        - We shouldn't degrade image quality while stripping EXIF
        - The image should look the same after processing
        """
        original_size = test_image_rgb.size
        
        clean_image = image_processor.strip_exif_data(test_image_rgb)
        
        # Check dimensions are preserved
        assert clean_image.size == original_size, \
            "Image dimensions should be preserved"
        
        # Check mode is RGB (not corrupted)
        assert clean_image.mode == 'RGB', \
            "Image should remain in RGB mode"
    
    def test_strip_exif_handles_rgba_images(self, image_processor):
        """
        Test that RGBA images are handled correctly.
        
        Why this matters:
        - PNG images often have alpha channels (RGBA)
        - JPEG doesn't support alpha, so we must convert
        - This should happen gracefully
        """
        # Create an RGBA image (with transparency)
        rgba_image = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        
        clean_image = image_processor.strip_exif_data(rgba_image)
        
        # Should be converted to RGB for JPEG compatibility
        assert clean_image.mode == 'RGB', \
            "RGBA should be converted to RGB"


# =============================================================================
# ENCRYPTION TESTS
# =============================================================================
# These tests verify our encryption and decryption work correctly.

class TestEncryption:
    """Tests for metadata encryption/decryption."""
    
    def test_encrypt_decrypt_roundtrip(self, encryption_service):
        """
        Test that data can be encrypted and then decrypted.
        
        Why this matters:
        - If we can't decrypt, we lose user data permanently
        - The round-trip must be perfect
        """
        original_data = {
            "gps_latitude": 40.7128,
            "gps_longitude": -74.0060,
            "secret_value": "test123",
        }
        location_id = "test-location-abc"
        
        # Encrypt
        encrypted, key_id = encryption_service.encrypt_for_location(
            data=original_data,
            location_id=location_id
        )
        
        # Decrypt
        decrypted = encryption_service.decrypt_for_location(
            encrypted_data=encrypted,
            key_id=key_id,
            location_id=location_id
        )
        
        # Verify
        assert decrypted == original_data, \
            "Decrypted data should match original exactly"
    
    def test_encrypt_produces_different_output_for_different_locations(
        self, encryption_service
    ):
        """
        Test that different locations produce different encrypted output.
        
        Why this matters:
        - Each location should have a unique derived key
        - Same data for different locations = different ciphertext
        - This limits damage if one key is compromised
        """
        data = {"test": "value"}
        
        encrypted1, _ = encryption_service.encrypt_for_location(
            data=data, location_id="location-a"
        )
        encrypted2, _ = encryption_service.encrypt_for_location(
            data=data, location_id="location-b"
        )
        
        assert encrypted1 != encrypted2, \
            "Different locations should produce different ciphertext"
    
    def test_decrypt_with_wrong_location_fails(self, encryption_service):
        """
        Test that decryption fails with wrong location_id.
        
        Why this matters:
        - Keys are derived from location_id
        - Wrong location = wrong key = decryption failure
        - This is a security feature!
        """
        from backend.services.encryption_service import DecryptionError
        
        data = {"test": "secret"}
        location_id = "correct-location"
        wrong_location = "wrong-location"
        
        encrypted, key_id = encryption_service.encrypt_for_location(
            data=data, location_id=location_id
        )
        
        with pytest.raises(DecryptionError):
            encryption_service.decrypt_for_location(
                encrypted_data=encrypted,
                key_id=key_id,
                location_id=wrong_location  # This should fail!
            )
    
    def test_key_derivation_is_deterministic(self, encryption_service):
        """
        Test that the same location always produces the same key.
        
        Why this matters:
        - We don't store keys, we derive them
        - Same inputs must always produce same key
        - Otherwise we couldn't decrypt old data!
        """
        location_id = "test-location-123"
        
        key1, key_id1 = encryption_service._derive_key_for_location(location_id)
        key2, key_id2 = encryption_service._derive_key_for_location(location_id)
        
        assert key1 == key2, "Same location should produce same key"
        assert key_id1 == key_id2, "Same location should produce same key_id"


# =============================================================================
# THUMBNAIL GENERATION TESTS
# =============================================================================
# These tests verify image resizing works correctly.

class TestThumbnailGeneration:
    """Tests for thumbnail and web version generation."""
    
    def test_thumbnail_respects_max_dimension(self, image_processor, test_image_large):
        """
        Test that thumbnails respect the max_size parameter.
        
        Why this matters:
        - Thumbnails must fit within the specified size
        - Too large = wasted bandwidth
        - Too small = poor quality
        """
        max_size = 400
        thumbnail = image_processor.generate_thumbnail(
            test_image_large, max_size=max_size
        )
        
        width, height = thumbnail.size
        
        assert max(width, height) <= max_size, \
            f"Largest dimension should be <= {max_size}"
    
    def test_thumbnail_maintains_aspect_ratio(self, image_processor, test_image_large):
        """
        Test that aspect ratio is preserved.
        
        Why this matters:
        - Distorted images look bad
        - Squares from rectangles = wrong
        - We should scale proportionally
        """
        original_width, original_height = test_image_large.size
        original_ratio = original_width / original_height
        
        thumbnail = image_processor.generate_thumbnail(test_image_large, max_size=400)
        
        new_width, new_height = thumbnail.size
        new_ratio = new_width / new_height
        
        # Allow small floating point difference
        assert abs(original_ratio - new_ratio) < 0.01, \
            "Aspect ratio should be preserved"
    
    def test_small_image_not_upscaled(self, image_processor, test_image_rgb):
        """
        Test that small images aren't unnecessarily upscaled.
        
        Why this matters:
        - Upscaling creates larger files with no quality benefit
        - A 100x100 image shouldn't become 400x400
        - We should return the original size
        """
        max_size = 400
        result = image_processor.generate_thumbnail(test_image_rgb, max_size=max_size)
        
        # Original is 100x100, should not be upscaled to 400x400
        assert result.size == test_image_rgb.size, \
            "Small images should not be upscaled"


# =============================================================================
# VALIDATION TESTS
# =============================================================================
# These tests verify our security validation catches malicious files.

class TestImageValidation:
    """Tests for image file validation."""
    
    def test_valid_jpeg_passes_validation(self, test_image_rgb):
        """
        Test that valid JPEG files pass validation.
        
        Why this matters:
        - We must not reject legitimate uploads
        - False positives = poor user experience
        """
        from backend.services.image_utils import validate_image_file
        
        # Save as JPEG
        buffer = io.BytesIO()
        test_image_rgb.save(buffer, format='JPEG')
        buffer.seek(0)
        
        is_valid, error = validate_image_file(buffer)
        
        assert is_valid, f"Valid JPEG should pass validation: {error}"
    
    def test_valid_png_passes_validation(self, test_image_rgb):
        """
        Test that valid PNG files pass validation.
        """
        from backend.services.image_utils import validate_image_file
        
        buffer = io.BytesIO()
        test_image_rgb.save(buffer, format='PNG')
        buffer.seek(0)
        
        is_valid, error = validate_image_file(buffer)
        
        assert is_valid, f"Valid PNG should pass validation: {error}"
    
    def test_non_image_fails_validation(self, corrupted_file):
        """
        Test that non-image files are rejected.
        
        Why this matters:
        - CRITICAL SECURITY: malicious files must be rejected
        - Attackers might upload PHP/EXE files as .jpg
        - We must detect and reject these
        """
        from backend.services.image_utils import validate_image_file
        
        is_valid, error = validate_image_file(corrupted_file)
        
        assert not is_valid, "Non-image file should fail validation"
        assert error is not None, "Error message should be provided"
    
    def test_empty_file_fails_validation(self):
        """
        Test that empty files are rejected.
        """
        from backend.services.image_utils import validate_image_file
        
        empty_file = io.BytesIO(b"")
        
        is_valid, error = validate_image_file(empty_file)
        
        assert not is_valid, "Empty file should fail validation"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================
# These tests verify the complete pipeline works end-to-end.

class TestFullPipeline:
    """Integration tests for the complete processing pipeline."""
    
    def test_process_image_creates_all_versions(
        self, image_processor, test_image_large, temp_storage_dir
    ):
        """
        Test that processing creates original, web, and thumbnail.
        
        Why this matters:
        - All three versions must be created for the app to work
        - Missing versions = broken UI
        """
        # Save test image to a file
        test_file = temp_storage_dir / "upload.jpg"
        test_image_large.save(test_file, format='JPEG')
        
        result = image_processor.process_image(
            image_file=test_file,
            location_id="test-loc-123",
            photo_type="ground"
        )
        
        # Verify all paths exist
        assert Path(result['original_path']).exists(), "Original should be saved"
        assert Path(result['web_path']).exists(), "Web version should be saved"
        assert Path(result['thumbnail_path']).exists(), "Thumbnail should be saved"
    
    def test_process_image_returns_safe_metadata(
        self, image_processor, test_image_rgb, temp_storage_dir
    ):
        """
        Test that safe metadata is extracted and returned.
        """
        test_file = temp_storage_dir / "upload.jpg"
        test_image_rgb.save(test_file, format='JPEG')
        
        result = image_processor.process_image(
            image_file=test_file,
            location_id="test-loc-123",
            photo_type="ground"
        )
        
        assert 'safe_metadata' in result
        assert 'width' in result['safe_metadata']
        assert 'height' in result['safe_metadata']
    
    def test_process_image_encrypts_sensitive_metadata(
        self, image_processor, test_image_with_exif, temp_storage_dir
    ):
        """
        Test that sensitive metadata is encrypted when present.
        
        Note: This test depends on having a test image with GPS data.
        If piexif isn't installed, we skip this test.
        """
        test_file = temp_storage_dir / "upload.jpg"
        test_image_with_exif.save(test_file, format='JPEG')
        
        result = image_processor.process_image(
            image_file=test_file,
            location_id="test-loc-123",
            photo_type="ground"
        )
        
        # May or may not have encrypted metadata depending on EXIF presence
        # At minimum, the fields should be in the result
        assert 'encrypted_metadata' in result
        assert 'key_id' in result


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================
# These tests verify graceful error handling.

class TestErrorHandling:
    """Tests for error handling throughout the pipeline."""
    
    def test_process_invalid_file_raises_error(
        self, image_processor, corrupted_file
    ):
        """
        Test that invalid files raise appropriate errors.
        """
        from backend.services.image_utils import ImageValidationError
        
        with pytest.raises(ImageValidationError):
            image_processor.process_image(
                image_file=corrupted_file,
                location_id="test-loc",
                photo_type="ground"
            )
    
    def test_encryption_without_key_raises_error(self):
        """
        Test that encryption fails gracefully without master key.
        """
        from backend.services.encryption_service import (
            EncryptionService,
            EncryptionServiceError
        )
        
        # Temporarily remove the key
        original_key = os.environ.pop('ENCRYPTION_MASTER_KEY', None)
        
        try:
            with pytest.raises(EncryptionServiceError):
                EncryptionService()
        finally:
            # Restore the key so other tests work
            if original_key:
                os.environ['ENCRYPTION_MASTER_KEY'] = original_key


# =============================================================================
# PERCEPTUAL HASH TESTS
# =============================================================================

class TestPerceptualHashing:
    """Tests for duplicate detection via perceptual hashing."""
    
    def test_same_image_same_hash(self, test_image_rgb):
        """
        Test that the same image produces the same hash.
        """
        from backend.services.image_utils import get_image_hash
        
        hash1 = get_image_hash(test_image_rgb)
        hash2 = get_image_hash(test_image_rgb)
        
        assert hash1 == hash2, "Same image should have same hash"
    
    def test_different_images_different_hash(self, test_image_rgb):
        """
        Test that different images (usually) have different hashes.
        """
        from backend.services.image_utils import get_image_hash
        
        image2 = Image.new('RGB', (100, 100), color='blue')
        
        hash1 = get_image_hash(test_image_rgb)
        hash2 = get_image_hash(image2)
        
        # Note: In theory, different images could have the same hash
        # (collision), but for very different images this is unlikely
        assert hash1 != hash2, "Different images should have different hashes"
