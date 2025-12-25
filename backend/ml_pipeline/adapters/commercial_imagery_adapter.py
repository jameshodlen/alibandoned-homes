"""
Commercial Imagery Adapter
=========================
Harmonizes commercial satellite imagery (Planet Dove/SuperDove) to 
match Sentinel-2 spectral response for ML model compatibility.

Reference: https://github.com/swegmueller/Dove_image_preprocessing
"""

import numpy as np
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class CommercialImageryAdapter:
    """
    Adapter for harmonizing multi-source imagery.
    """
    
    def __init__(self):
        self.coefficients = {
            # Coefficients from Huang and Roy, 2021 (cited in swegmueller repo)
            'planet_dove': {
                'green': {'slope': 0.9306, 'offset': 0.0018},
                'red':   {'slope': 0.7949, 'offset': 0.0124},
                'nir':   {'slope': 0.7526, 'offset': 0.0277}
            }
        }

    def harmonize_to_sentinel2(self, image: np.ndarray, source: str, bands: List[str]) -> np.ndarray:
        """
        Harmonize input image bands to Sentinel-2 baseline.
        
        Args:
            image: 3D numpy array (channels, height, width) or 1D list of values
            source: 'planet_dove', 'planet_superdove', etc.
            bands: List of band names corresponding to image channels ['blue', 'green', 'red', 'nir']
            
        Returns:
            Harmonized numpy array
        """
        if source not in self.coefficients:
            logger.warning(f"No coefficients for source {source}. Returning raw image.")
            return image
            
        coeffs = self.coefficients[source]
        output = image.copy().astype(float)
        
        # Handle 1D case (single pixel values) vs 3D case (raster)
        is_1d = (image.ndim == 1)
        
        for i, band_name in enumerate(bands):
            if band_name in coeffs:
                c = coeffs[band_name]
                
                # Apply: slope * value + offset
                if is_1d:
                    # Input is scaled 0-1 or 0-10000? 
                    # Reference assumes float scaled 0-1 (after / 10000)
                    # We assume input is reflectance 0.0-1.0
                     output[i] = (c['slope'] * output[i]) + c['offset']
                else:
                     output[i, :, :] = (c['slope'] * output[i, :, :]) + c['offset']
                     
        return output
