"""
Image Analysis Service for change detection and property assessment.

=============================================================================
COMPUTER VISION CONCEPTS FOR ABANDONMENT
=============================================================================

1. Structural Similarity Index (SSIM):
   - Measures similarity between two images
   - Used to detect changes in building structure over time (e.g., roof collapse)
   - Range: -1 to 1 (1 = identical)

2. Histogram Analysis:
   - Compares color distributions
   - Useful for detecting vegetation overgrowth (increase in green channel)
   - Useful for detecting fire damage (increase in charcoal/black)

3. Change Detection:
   - Image Differencing: |Image1 - Image2|
   - Thresholding: Identifying significant changes above noise level
=============================================================================
"""

import logging
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Dict, Tuple, Optional

# Try to import scikit-image for advanced metrics, fallback if missing
try:
    from skimage.metrics import structural_similarity as ssim
    from skimage.color import rgb2gray
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False

logger = logging.getLogger(__name__)

class ImageAnalyzer:
    """
    Tools for analyzing and comparing property images.
    """

    @staticmethod
    def load_image(path: str) -> Optional[np.ndarray]:
        """Load image as numpy array"""
        try:
            img = Image.open(path).convert('RGB')
            return np.array(img)
        except Exception as e:
            logger.error(f"Failed to load image {path}: {e}")
            return None

    def compare_images(self, path1: str, path2: str) -> Dict[str, float]:
        """
        Compare two images (e.g., historical vs current) to detect change.
        """
        img1 = self.load_image(path1)
        img2 = self.load_image(path2)
        
        if img1 is None or img2 is None:
            return {"error": "Failed to load one or both images"}

        # Resize img2 to match img1 for comparison
        if img1.shape != img2.shape:
            img2_pil = Image.fromarray(img2).resize((img1.shape[1], img1.shape[0]))
            img2 = np.array(img2_pil)

        results = {
            "histogram_similarity": self._compare_histograms(img1, img2)
        }

        if HAS_SKIMAGE:
            results["ssim"] = self._calculate_ssim(img1, img2)
            results["change_detected"] = results["ssim"] < 0.85
        else:
            results["note"] = "Install scikit-image for SSIM analysis"
            # Fallback simple difference
            diff = np.mean(np.abs(img1 - img2))
            results["difference_score"] = float(diff)
            results["change_detected"] = diff > 30.0

        return results

    def _compare_histograms(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """
        Compare color histograms (correlation).
        Returns 0..1 where 1 is identical distribution.
        """
        # Simple implementation using numpy
        # Flatten and calculate histogram for each channel
        score = 0
        for i in range(3): # R, G, B
            hist1, _ = np.histogram(img1[:,:,i], bins=256, range=(0,256))
            hist2, _ = np.histogram(img2[:,:,i], bins=256, range=(0,256))
            
            # Normalize
            hist1 = hist1 / (hist1.sum() + 1e-10)
            hist2 = hist2 / (hist2.sum() + 1e-10)
            
            # Intersection/Correlation-like metric
            score += np.minimum(hist1, hist2).sum()
            
        return float(score / 3.0)

    def _calculate_ssim(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Calculate Structural Similarity Index"""
        # Convert to grayscale usually needed for SSIM
        gray1 = rgb2gray(img1)
        gray2 = rgb2gray(img2)
        
        score, _ = ssim(gray1, gray2, full=True, data_range=1.0)
        return float(score)

    def analyze_abandonment_indicators(self, path: str) -> Dict[str, float]:
        """
        Analyze a single image for signs of abandonment.
        Simple heuristics for vegetation and boarded windows.
        """
        img = self.load_image(path)
        if img is None:
            return {}

        # 1. Vegetation Index (Greenery check)
        # Ratio of Green channel to Red/Blue
        r, g, b = img[:,:,0], img[:,:,1], img[:,:,2]
        
        # Simple Green-Red vegetation index
        # Avoid division by zero
        denominator = (g.astype(float) + r.astype(float)) + 1e-10
        grvi = (g.astype(float) - r.astype(float)) / denominator
        vegetation_score = np.mean(grvi > 0.1) # Threshold for "green"

        # 2. Boarded Window Simulator (Brown/Beige detection)
        # Detect wood-like colors (higher Red/Green, low Blue)
        # This is very heuristic and prone to false positives
        wood_mask = (r > 100) & (g > 80) & (b < 80) & (r > b + 30)
        boarding_score = np.mean(wood_mask)

        return {
            "vegetation_coverage": float(vegetation_score),
            "boarding_likelihood": float(boarding_score),
            "is_overgrown": bool(vegetation_score > 0.3)
        }
