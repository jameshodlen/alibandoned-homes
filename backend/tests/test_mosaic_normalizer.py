"""
Tests for Mosaic Normalizer
==========================
"""
import pytest
import numpy as np
from backend.ml_pipeline.preprocessing.mosaic_normalizer import MosaicNormalizer

def test_histogram_match_shape():
    norm = MosaicNormalizer()
    
    source = np.random.rand(100, 100)
    ref = np.random.rand(100, 100)
    
    matched = norm.histogram_match(source, ref)
    
    assert matched.shape == source.shape
    # Basic check: values should be within ref range
    assert matched.min() >= ref.min() - 0.1 # approximate
    assert matched.max() <= ref.max() + 0.1

def test_normalize_tiles():
    norm = MosaicNormalizer()
    
    t1 = np.ones((10, 10)) * 0.5
    t2 = np.ones((10, 10)) * 0.8 # Brighter
    
    tiles = [t1, t2]
    
    normalized = norm.normalize_tiles(tiles)
    
    # First tile is reference, shouldn't change
    assert np.array_equal(normalized[0], t1)
    
    # Second should be closer to first (0.5)
    # Since t1 is uniform 0.5, t2 should map to 0.5
    assert np.allclose(normalized[1], 0.5)
