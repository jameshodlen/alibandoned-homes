"""
Kernel Density Estimator (KDE) Predictor
=======================================

This component estimates a continuous probability "surface" from discrete points.
It is the "Hotspot Expert" in our ensemble.

Algorithm Explained:
------------------
Imagine placing a pile of sand (a "Kernel") on top of every known abandoned home.
If homes are close, the sand piles stack up, creating a large hill (High Density).
If a home is isolated, it's just a small bump (Low Density).

Mathematically: Sum of Gaussian distributions centered at each data point.

Why it's distinct from DBSCAN:
- DBSCAN is binary: You are in a cluster OR you are noise.
- KDE is continuous: You are in a 90% dense zone, or 20% dense zone.
It provides smoother gradients for prediction.
"""

import numpy as np
from sklearn.neighbors import KernelDensity
from sklearn.model_selection import GridSearchCV
import matplotlib.pyplot as plt
from typing import Dict, Any, Tuple

class KernelDensityEstimator:
    """
    Gaussian KDE for identifying probability hotspots.
    """
    
    def __init__(self, bandwidth_meters: int = 1000, kernel: str = 'gaussian'):
        """
        Args:
            bandwidth_meters: Width of the "sand pile". 
                             1000m means influence spreads smoothly over ~1km.
                             Too small = Spiky (overfitting). Too large = Flat (underfitting).
            kernel: Shape of the distribution (gaussian is standard).
        """
        self.bandwidth_meters = bandwidth_meters
        self.kernel = kernel
        self.EARTH_RADIUS_METERS = 6371000.0
        
        # Approximation: at 40 deg latitude, 1 degree ~ 111km
        # We convert meters to degrees slightly roughly here since KDE doesn't support 
        # Haversine natively with fast algorithms efficiently in older sklearn versions,
        # but we use 'haversine' metric with radians if possible.
        # Let's use radians + haversine metric for correctness.
        
        self.bandwidth_rad = bandwidth_meters / self.EARTH_RADIUS_METERS
        
        self.kde = KernelDensity(
            bandwidth=self.bandwidth_rad, 
            metric='haversine',
            kernel=kernel, 
            algorithm='ball_tree'
        )
        
        self.max_log_density = None

    def train(self, coordinates_array: np.ndarray) -> Dict[str, Any]:
        """
        Fit density surface to known locations.
        """
        # Convert to radians
        coords_rad = np.radians(coordinates_array)
        
        self.kde.fit(coords_rad)
        
        # Calculate normalization factor roughly
        # We want to scale output to 0-1 probability relative to the "densest" spot found
        # So we evaluate on the training data itself to find the peak
        log_densities = self.kde.score_samples(coords_rad)
        self.max_log_density = np.max(log_densities)
        
        return {
            'n_samples': len(coordinates_array),
            'max_log_density': self.max_log_density
        }

    def predict_proba(self, coordinates_array: np.ndarray) -> np.ndarray:
        """
        Get normalized density score [0-1].
        """
        if self.max_log_density is None:
            return np.zeros(len(coordinates_array))
            
        coords_rad = np.radians(coordinates_array)
        
        # score_samples returns log(density)
        log_densities = self.kde.score_samples(coords_rad)
        
        # Strategy:
        # We don't want strict probability density (which integrates to 1 over the whole earth).
        # We want a relative risk score.
        # We map the max density seen in training to 1.0 (or close to it).
        
        # exp(log_d - max_log_d) -> scales peak to 1.0
        # If density is effectively zero, this goes to 0.
        probs = np.exp(log_densities - self.max_log_density)
        
        return probs

    def generate_heatmap(self, bounding_box: Dict[str, float], resolution: int = 100):
        """
        Generate a 2D grid for visualization.
        """
        # Create grid
        lats = np.linspace(bounding_box['min_lat'], bounding_box['max_lat'], resolution)
        lons = np.linspace(bounding_box['min_lon'], bounding_box['max_lon'], resolution)
        
        grid_lat, grid_lon = np.meshgrid(lats, lons)
        grid_coords = np.vstack([grid_lat.ravel(), grid_lon.ravel()]).T
        
        probs = self.predict_proba(grid_coords)
        prob_surface = probs.reshape(grid_lat.shape)
        
        return prob_surface, (grid_lat, grid_lon)
