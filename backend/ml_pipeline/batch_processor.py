"""
Batch Processor
==============

Process large lists of locations efficiently using parallel workers.
"""

import logging
import time
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import pandas as pd

from backend.ml_pipeline.feature_engineering import FeatureEngineering

logger = logging.getLogger(__name__)

class BatchProcessor:
    """
    Handles parallel feature extraction for many locations.
    """
    
    def __init__(self, max_workers: int = 5):
        self.fe = FeatureEngineering()
        self.max_workers = max_workers

    def process_locations(
        self, 
        locations: List[Dict[str, float]], 
        radius: int = 500
    ) -> pd.DataFrame:
        """
        Extract features for a list of coordinates.
        
        Args:
            locations: List of dicts, e.g. [{'lat': 40.0, 'lon': -74.0, 'id': '1'}, ...]
            radius: Analysis radius
            
        Returns:
            DataFrame containing features for all valid locations
        """
        results = []
        errors = []
        
        logger.info(f"Starting batch processing for {len(locations)} locations...")
        
        # Use ThreadPoolExecutor for I/O bound tasks (API calls)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Create a future for each location
            future_to_loc = {
                executor.submit(
                    self.fe.extract_features_for_location,
                    loc['lat'], 
                    loc['lon'], 
                    radius
                ): loc for loc in locations
            }
            
            # usage of tqdm for progress bar
            for future in tqdm(as_completed(future_to_loc), total=len(locations), desc="Extracting Features"):
                loc = future_to_loc[future]
                try:
                    data = future.result()
                    # Add ID back to result
                    data['location_id'] = loc.get('id')
                    results.append(data)
                except Exception as e:
                    logger.error(f"Failed to process {loc}: {e}")
                    errors.append({'location_id': loc.get('id'), 'error': str(e)})
                    
        df = pd.DataFrame(results)
        logger.info(f"Batch complete. Success: {len(results)}, Failed: {len(errors)}")
        return df
