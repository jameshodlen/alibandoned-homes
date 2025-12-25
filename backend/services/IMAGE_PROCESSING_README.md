# Image Processing Service

A comprehensive image processing pipeline for the Abandoned Homes Prediction application, with a focus on **privacy protection** and **security**.

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         IMAGE PROCESSING PIPELINE                           │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │  Upload  │────▶│ Validate │────▶│  Extract │────▶│  Strip   │
    │   File   │     │ Security │     │   EXIF   │     │   EXIF   │
    └──────────┘     └──────────┘     └──────────┘     └──────────┘
                           │                │               │
                           ▼                ▼               ▼
                     Check magic       GPS, datetime    Remove ALL
                     bytes + size      + camera info    metadata
                                            │
                                            ▼
                     ┌──────────────────────────────────────┐
                     │     Encrypt Sensitive Metadata       │
                     │  (GPS coords, timestamps, etc.)      │
                     └──────────────────────────────────────┘
                                            │
         ┌──────────────────────────────────┼──────────────────────────────┐
         ▼                                  ▼                              ▼
    ┌──────────┐                      ┌──────────┐                   ┌──────────┐
    │ Original │                      │   Web    │                   │Thumbnail │
    │  95% Q   │                      │ 1920px   │                   │  400px   │
    │          │                      │  85% Q   │                   │  80% Q   │
    └──────────┘                      └──────────┘                   └──────────┘
         │                                  │                              │
         └──────────────────────────────────┼──────────────────────────────┘
                                            ▼
                     ┌──────────────────────────────────────┐
                     │     Store in Organized Structure     │
                     │  /storage/photos/{year}/{month}/...  │
                     └──────────────────────────────────────┘
```

## Why EXIF Stripping Matters

**EXIF metadata can reveal:**
| Data Type | Privacy Risk | Example |
|-----------|--------------|---------|
| GPS Coordinates | Exact location | Home address exposed |
| Timestamps | When you were somewhere | Daily routines revealed |
| Device ID | Identifies owner | Links photos to person |
| Thumbnails | Original content | Cropped-out content visible |

**Our approach:**

1. Extract ALL metadata before processing
2. Encrypt sensitive fields (GPS, timestamps)
3. Strip ALL metadata from stored images
4. Keep only camera model/settings for ML training

## Quick Start

```python
from backend.services.image_processor import ImageProcessor

processor = ImageProcessor(storage_base_path="/app/storage")

result = processor.process_image(
    image_file=uploaded_file,
    location_id="abc-123-def",
    photo_type="ground"
)

# Result contains paths to all versions + encrypted metadata
```

## Files

| File                    | Purpose                                      | Size  |
| ----------------------- | -------------------------------------------- | ----- |
| `encryption_service.py` | Fernet encryption with PBKDF2 key derivation | ~15KB |
| `storage_manager.py`    | Organized file storage and cleanup           | ~12KB |
| `image_utils.py`        | Validation, hashing, format conversion       | ~14KB |
| `image_processor.py`    | Main processing pipeline                     | ~20KB |
| `example_usage.py`      | Tutorial with all examples                   | ~8KB  |

## Security Features

- **Magic bytes validation** - Prevents malicious files
- **Size limits** - Prevents DoS attacks
- **EXIF stripping** - Privacy protection
- **Fernet encryption** - AES-128-CBC + HMAC
- **PBKDF2 key derivation** - Per-location keys

## Dependencies

```
pillow>=10.0.0           # Image processing
cryptography>=41.0.0     # Encryption
imagehash>=4.3.1         # Perceptual hashing (optional)
pillow-heif>=0.13.0      # HEIC support (optional)
```

## Environment Variables

```bash
# Required for encryption
ENCRYPTION_MASTER_KEY=<your-fernet-key>

# Generate with:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
