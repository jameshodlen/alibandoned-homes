"""
Canopy Mask Filter
=================
Distinguishes between maintained maintained tree canopy and unmanaged overgrowth.

Reference: https://github.com/swegmueller/Image_masking_USFS_tree_canopy_cover
"""

import numpy as np
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class CanopyMask:
    """
    Analyzes vegetation structure to classify abandonment risk.
    """
    
    def __init__(self, canopy_threshold: float = 0.5):
        """
        Args:
            canopy_threshold: NDVI threshold for "dense canopy" (default 0.5)
        """
        self.canopy_threshold = canopy_threshold

    def classify_vegetation(self, ndvi_mean: float, neighborhood_stats: Dict[str, float]) -> str:
        """
        Classify the vegetation state based on NDVI and neighborhood context.
        
        Returns:
            str: 'maintained_canopy', 'overgrowth', 'sparse', 'none'
        """
        if ndvi_mean < 0.2:
            return 'none'
        elif ndvi_mean < 0.4:
            return 'sparse'
            
        # High NDVI case: Check context
        avg_neighborhood_ndvi = neighborhood_stats.get('mean_ndvi', 0.4)
        std_neighborhood_ndvi = neighborhood_stats.get('std_ndvi', 0.1)
        
        # Logic: If pixel is significantly higher than neighborhood mean, likely overgrowth
        # If uniform high canopy (low std dev), likely maintained urban forest
        
        z_score = (ndvi_mean - avg_neighborhood_ndvi) / (std_neighborhood_ndvi + 1e-6)
        
        if z_score > 2.0:
            return 'overgrowth'  # Anomaly: much greener than neighbors
        elif ndvi_mean > self.canopy_threshold:
            return 'maintained_canopy' # Consistent with neighbors or just generic dense
            
        return 'sparse'

    def adjust_abandonment_score(self, base_score: float, canopy_classification: str) -> float:
        """
        Adjust prediction score based on vegetation type.
        """
        if canopy_classification == 'overgrowth':
            return min(1.0, base_score * 1.2) # Boost score
        elif canopy_classification == 'maintained_canopy':
            return base_score * 0.8 # Reduce score (healthy street trees)
        
        return base_score
