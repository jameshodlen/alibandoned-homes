# Advanced Features Guide

## 1. Multi-Source Imagery Integration

The system now supports fetching imagery from multiple sources to validate abandonment predictions.

### Sources

- **Mapillary**: Street-level imagery (crowdsourced).
- **Sentinel-2**: Satellite imagery (10m resolution, multi-spectral).

### Usage

```bash
POST /api/v1/advanced/imagery/{location_id}/fetch
```

This triggers a background job to:

1. Search Mapillary for images within 50m.
2. Download thumbnails for manual review.
3. Fetch the latest cloud-free Sentinel-2 image (last 30 days).

## 2. Image Analysis Tools

### Change Detection

Compare historical vs current images to detect structural changes or degradation.

```bash
GET /api/v1/advanced/analysis/compare?img1_path=...&img2_path=...
```

**Metrics:**

- **SSIM (Structural Similarity Index)**: < 0.85 indicates significant structural change.
- **Histogram Correlation**: Detects color shifts (fire damage, repainting).

### Abandonment Indicators

- **Vegetation Index**: Heuristic check for overgrowth/greenery in satellite views.
- **Boarding Detection**: Heuristic check for board-colored pixels in street views.

## 3. Multi-Stage Prediction Pipeline

To improve accuracy, the system uses a 3-stage validation process:

1. **Broad Phase**: Filter tax/crime data for high-risk cells (Base Confidence).
2. **Satellite Phase**: Check high-risk cells for roof damage/overgrowth (+Score).
3. **Street Phase**: Confirm top candidates with street view boarding detection (+Score).

**Result**: A `final_confidence` score that is more robust than feature-only models.

## 4. Privacy-Safe Export

Export data for external stakeholders while protecting property owners and preventing "disaster tourism".

### Anonymization Strategy

- **Coordinate Fuzzing**: All public exports round coordinates to 3 decimal places (~110m precision).
- **Data Minimization**: Only status and confidence scores are exported.

### Formats

- **GeoJSON**: `GET /api/v1/advanced/export/geojson` (Web mapping)
- **KML**: `GET /api/v1/advanced/export/kml` (Google Earth)
- **CSV**: `GET /api/v1/advanced/export/csv` (Excel/Analysis)
- **PDF**: `GET /api/v1/advanced/export/pdf` (Executive Reports)
