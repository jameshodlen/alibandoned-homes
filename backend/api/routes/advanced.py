from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import os
import shutil

from database.base import get_db
from database.models import Location
from api.auth import get_current_user
from api.services.imagery import ImageryManager
from api.services.analysis import ImageAnalyzer
from api.services.export import ExportService

router = APIRouter()

# Init services
# In production, use dependency injection
STORAGE_PATH = Path("storage/imagery")
imagery_manager = ImageryManager(STORAGE_PATH)
analyzer = ImageAnalyzer()
export_service = ExportService()

@router.post("/imagery/{location_id}/fetch")
async def fetch_location_imagery(
    location_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger fetching of satellite and street view imagery for a location.
    """
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
        
    # extract lat/lon from geometry in real app
    # For now assuming simple columns or property
    # Mock coordinates for this example as geospatial access varies
    lat, lon = 42.33, -83.04 
    
    results = imagery_manager.fetch_location_imagery(str(location.id), lat, lon)
    
    return {
        "status": "success", 
        "message": f"Fetched {len(results['street_view'])} street views and {len(results['satellite'])} satellite images",
        "data": results
    }

@router.get("/analysis/compare")
async def compare_images(
    img1_path: str,
    img2_path: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Compare two images for changes.
    """
    # Security check: ensure paths are within storage directory
    # (Simplified for example)
    if ".." in img1_path or ".." in img2_path:
        raise HTTPException(status_code=400, detail="Invalid path")
        
    results = analyzer.compare_images(img1_path, img2_path)
    return results

@router.get("/export/{format}")
async def export_data(
    format: str,
    obfuscate: bool = True,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Export location data in specified format (kml, geojson, csv, pdf).
    """
    locations = db.query(Location).all()
    # Convert SQLAlchemy models to dicts
    loc_dicts = []
    for loc in locations:
        loc_dicts.append({
            "id": str(loc.id),
            "status": loc.status.value if loc.status else "unknown",
            "prediction_score": loc.prediction_score,
            "updated_at": loc.updated_at,
            # Hack for coords since we don't have easy geo accessor in this context
            "latitude": 42.33 + (hash(loc.id) % 100) / 1000.0, 
            "longitude": -83.04 + (hash(loc.id) % 100) / 1000.0
        })

    if format == "geojson":
        return export_service.export_geojson(loc_dicts, obfuscate)
    
    elif format == "kml":
        return Response(
            content=export_service.export_kml(loc_dicts, obfuscate),
            media_type="application/vnd.google-earth.kml+xml",
            headers={"Content-Disposition": "attachment; filename=export.kml"}
        )
        
    elif format == "csv":
        return Response(
            content=export_service.export_csv(loc_dicts, obfuscate),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=export.csv"}
        )
        
    elif format == "pdf":
        # Generate to temp file then stream
        output_path = "storage/temp_report.pdf"
        os.makedirs("storage", exist_ok=True)
        export_service.generate_pdf_report(loc_dicts, output_path, obfuscate)
        return FileResponse(
            output_path, 
            media_type="application/pdf", 
            filename="report.pdf"
        )
        
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")

from fastapi.responses import Response, FileResponse
