"""
Tests for Satellite Masking
==========================
"""
import pytest
from backend.ml_pipeline.extractors.satellite_extractor import SatelliteExtractor

def test_mask_clouds_and_shadows():
    extractor = SatelliteExtractor()
    
    mock_bands = {'ndvi_mean': 0.5, 'ndbi_mean': -0.1}
    
    # 1. Clear Pixel (SCL=4 Vegetation)
    res_clear = extractor.mask_clouds_and_shadows(mock_bands.copy(), 4)
    assert res_clear['ndvi_mean'] == 0.5
    assert 'cloud_coverage' not in res_clear or res_clear.get('cloud_coverage') != 1.0
    
    # 2. Cloud Shadow (SCL=3)
    res_shadow = extractor.mask_clouds_and_shadows(mock_bands.copy(), 3)
    assert res_shadow['ndvi_mean'] is None
    assert res_shadow['cloud_coverage'] == 1.0
    
    # 3. High Prob Cloud (SCL=9)
    res_cloud = extractor.mask_clouds_and_shadows(mock_bands.copy(), 9)
    assert res_cloud['ndvi_mean'] is None
    
    # 4. Water (SCL=6)
    res_water = extractor.mask_clouds_and_shadows(mock_bands.copy(), 6)
    assert res_water['ndvi_mean'] is None
