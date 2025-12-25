"""
Tests for Commercial Imagery Adapter
===================================
"""
import pytest
import numpy as np
from backend.ml_pipeline.adapters.commercial_imagery_adapter import CommercialImageryAdapter

def test_harmonize_dove_values():
    adapter = CommercialImageryAdapter()
    
    # Test inputs (approximate raw reflectance)
    # Green, Red, Nir
    # Coefficients:
    # Green: 0.9306 * val + 0.0018
    input_pixel = np.array([0.1, 0.2, 0.3]) # Green, Red, Nir
    
    harmonized = adapter.harmonize_to_sentinel2(
        input_pixel, 
        'planet_dove', 
        ['green', 'red', 'nir']
    )
    
    # Expected calculations:
    # Green: 0.1 * 0.9306 + 0.0018 = 0.09486
    # Red:   0.2 * 0.7949 + 0.0124 = 0.17138
    # Nir:   0.3 * 0.7526 + 0.0277 = 0.25348
    
    assert np.isclose(harmonized[0], 0.09486)
    assert np.isclose(harmonized[1], 0.17138)
    assert np.isclose(harmonized[2], 0.25348)

def test_harmonize_unknown_source():
    adapter = CommercialImageryAdapter()
    arr = np.array([1, 2, 3])
    # Should return original array
    res = adapter.harmonize_to_sentinel2(arr, 'unknown_sat', ['b1'])
    assert np.array_equal(arr, res)
