"""
Tests for Canopy Mask Filter
===========================
"""
import pytest
from backend.ml_pipeline.filters.canopy_mask import CanopyMask

def test_classify_vegetation():
    mask = CanopyMask()
    
    # Test strict low NDVI
    assert mask.classify_vegetation(0.1, {}) == 'none'
    assert mask.classify_vegetation(0.3, {}) == 'sparse'
    
    # Test Overgrowth (High anomaly z-score)
    # Pixel 0.8 vs Neigh Mean 0.4 (Std 0.1) -> Z = 4.0
    stats = {'mean_ndvi': 0.4, 'std_ndvi': 0.1}
    assert mask.classify_vegetation(0.8, stats) == 'overgrowth'
    
    # Test Maintained Canopy (Consistent with neighbors)
    # Pixel 0.7 vs Neigh Mean 0.6 (Std 0.1) -> Z = 1.0
    stats_forest = {'mean_ndvi': 0.6, 'std_ndvi': 0.1}
    assert mask.classify_vegetation(0.7, stats_forest) == 'maintained_canopy'

def test_adjust_abandonment_score():
    mask = CanopyMask()
    
    base = 0.5
    
    # Overgrowth boosts score
    assert mask.adjust_abandonment_score(base, 'overgrowth') > base
    
    # Maintained reduces score
    assert mask.adjust_abandonment_score(base, 'maintained_canopy') < base
    
    # Sparse / None stays same
    assert mask.adjust_abandonment_score(base, 'sparse') == base
