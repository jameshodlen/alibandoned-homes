"""
Imagery Service for handling Mapillary (street) and Sentinel-2 (satellite) data.

=============================================================================
IMAGERY INTEGRATION CONCEPTS
=============================================================================

1. Street-Level Imagery (Mapillary):
   - Crowdsourced street view data
   - Uses Graph API to find images near coordinates
   - Useful for verifying physical condition (broken windows, overgrowth)

2. Satellite Imagery (Sentinel-2):
   - Free, global, multi-spectral data (ESA)
   - 10m resolution (good enough for large property changes)
   - Revisit time ~5 days
   - Useful for:
     - Vegetation density (NDVI)
     - Roof condition (Visual/RGB)
     - Land use changes over time

3. Data Acquisition Strategy:
   - "Lazy" fetching: Only fetch when requested or during prediction pipeline
   - Caching: Downloaded images are stored locally to prevent re-fetching
   - Rate Limiting: Respect external API limits
=============================================================================
"""

import os
import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

class MapillaryClient:
    """
    Client for Mapillary API v4
    
    Documentation: https://www.mapillary.com/developer/api-documentation/
    """
    
    BASE_URL = "https://graph.mapillary.com"
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        if not self.access_token:
            logger.warning("Mapillary access token not provided. Street view features will be disabled.")

    def search_images(
        self, 
        latitude: float, 
        longitude: float, 
        radius: int = 50,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search for images near coordinates.
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            radius: Search radius in meters
            limit: Max results
            
        Returns:
            List of image metadata objects
        """
        if not self.access_token:
            return []
            
        # Convert radius to bbox (simplified 1 degree ~ 111km)
        # Using a small bounding box centered on point
        offset = radius / 111000.0
        bbox = f"{longitude-offset},{latitude-offset},{longitude+offset},{latitude+offset}"
        
        params = {
            "access_token": self.access_token,
            "fields": "id,captured_at,geometry,thumb_1024_url",
            "bbox": bbox,
            "limit": limit
        }
        
        try:
            response = requests.get(f"{self.BASE_URL}/images", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except requests.RequestException as e:
            logger.error(f"Mapillary API error: {e}")
            return []

    def download_thumbnail(self, image_id: str, url: str, output_dir: Path) -> Optional[Path]:
        """Download image thumbnail to local storage"""
        try:
            response = requests.get(url, stream=True, timeout=15)
            response.raise_for_status()
            
            output_path = output_dir / f"mapillary_{image_id}.jpg"
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return output_path
        except requests.RequestException as e:
            logger.error(f"Failed to download Mapillary image {image_id}: {e}")
            return None


class SentinelClient:
    """
    Client for Sentinel-2 Imagery via Sentinel Hub or Direct Downloader.
    
    For education purposes, we'll demonstrate a simplified interface that would 
    connect to a service like Sentinel Hub (Wms) or standard archives.
    Since Sentinel Hub requires a complex paid/trial setup, we will:
    1. Implement the 'ideal' structure for fetching composite images.
    2. Provide a mock implementation fallback for immediate testing.
    """
    
    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://services.sentinel-hub.com"
        self._token = None
        
        # If credentials aren't provided, we'll run in mock mode
        self.mock_mode = not (client_id and client_secret)

    def _authenticate(self):
        """Get OAuth token for Sentinel Hub"""
        if self.mock_mode:
            return
            
        try:
            resp = requests.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                timeout=10
            )
            resp.raise_for_status()
            self._token = resp.json()["access_token"]
        except Exception as e:
            logger.error(f"Sentinel Hub Auth Error: {e}")
            self.mock_mode = True  # Fallback to mock on auth failure

    def get_latest_satellite_image(
        self, 
        latitude: float, 
        longitude: float, 
        date_start: str,
        date_end: str,
        output_dir: Path
    ) -> Optional[Path]:
        """
        Download recent cloud-free Sentinel-2 RGB image.
        """
        output_path = output_dir / f"sentinel2_{latitude}_{longitude}.jpg"
        
        # MOCK IMPLEMENTATION (for when no keys are present)
        if self.mock_mode:
            logger.info("Running in Mock Mode: Generating placeholder satellite image")
            # In a real app, you might download a static placeholder or fail
            # Here we'll generate a dummy file for testing purposes
            try:
                import numpy as np
                from PIL import Image
                
                # Create a random "satellite-looking" noise image
                arr = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
                img = Image.fromarray(arr)
                img.save(output_path)
                return output_path
            except ImportError:
                return None

        # REAL IMPLEMENTATION SKELETON (Process API)
        # This shows how you WOULD do it with a valid subscription
        if not self._token:
            self._authenticate()
            
        # ... (Implementation of Sentinel Hub Process API request typically goes here)
        # For this educational codebase, we stop here as we don't have secrets.
        return None

class ImageryManager:
    """Facade for managing all imagery sources"""
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.mapillary = MapillaryClient(os.getenv("MAPILLARY_ACCESS_TOKEN", ""))
        self.sentinel = SentinelClient(
            os.getenv("SENTINEL_HUB_CLIENT_ID"),
            os.getenv("SENTINEL_HUB_CLIENT_SECRET")
        )
    
    def fetch_location_imagery(self, location_id: str, lat: float, lon: float) -> Dict[str, List[str]]:
        """
        Fetch all available imagery for a location.
        Steps:
        1. Search street view
        2. Download thumbnails
        3. Fetch latest satellite view
        """
        loc_dir = self.storage_path / location_id
        loc_dir.mkdir(exist_ok=True)
        
        results = {
            "street_view": [],
            "satellite": []
        }
        
        # 1. Street View
        street_images = self.mapillary.search_images(lat, lon, limit=3)
        for img in street_images:
            path = self.mapillary.download_thumbnail(
                img['id'], 
                img['thumb_1024_url'], 
                loc_dir
            )
            if path:
                results["street_view"].append(str(path))
        
        # 2. Satellite (Latest)
        # Look back 30 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        sat_path = self.sentinel.get_latest_satellite_image(
            lat, lon, 
            start_date.isoformat(), 
            end_date.isoformat(), 
            loc_dir
        )
        if sat_path:
            results["satellite"].append(str(sat_path))
            
        return results
