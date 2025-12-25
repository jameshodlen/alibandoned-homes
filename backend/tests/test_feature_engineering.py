"""
Tests for Feature Engineering Service
====================================

Educational test suite ensuring the pipeline works as expected.
We mock external APIs to avoid network dependency and costs during testing.
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from backend.ml_pipeline.feature_engineering import FeatureEngineering
from backend.ml_pipeline.feature_validator import FeatureValidator
from backend.ml_pipeline.feature_cache import FeatureCache

@pytest.fixture
def mock_extractors():
    """
    Mock all external data extractors.
    """
    with patch('backend.ml_pipeline.extractors.census_extractor.CensusExtractor') as mock_census, \
         patch('backend.ml_pipeline.extractors.osm_extractor.OSMExtractor') as mock_osm, \
         patch('backend.ml_pipeline.extractors.satellite_extractor.SatelliteExtractor') as mock_sat:
        
        # Setup Census Mock Response
        census_instance = mock_census.return_value
        census_instance.extract_features.return_value = {
            'population_total': 5000,
            'median_household_income': 45000,
            'vacancy_rate': 12.5
        }
        
        # Setup OSM Mock Response
        osm_instance = mock_osm.return_value
        osm_instance.extract_features.return_value = {
            'road_network_density': 15.5,
            'amenity_count_total': 5,
            'distance_to_grocery': 450
        }
        
        # Setup Satellite Mock Response
        sat_instance = mock_sat.return_value
        sat_instance.extract_features.return_value = {
            'ndvi_mean': 0.45,
            'ndbi_mean': -0.1
        }
        
        yield (census_instance, osm_instance, sat_instance)

@pytest.fixture
def feature_engineering(mock_extractors):
    """
    Initialize service with forced mocks.
    """
    # We patch Redis to avoid needing a real server
    with patch('backend.ml_pipeline.feature_cache.redis.Redis'):
        fe = FeatureEngineering()
        # Ensure our specific mocks are attached
        (census, osm, sat) = mock_extractors
        fe.census = census
        fe.osm = osm
        fe.satellite = sat
        return fe

def test_extract_features_aggregates_sources(feature_engineering):
    """
    Verify that the orchestrator correctly combines data from all 3 sources.
    """
    features = feature_engineering.extract_features_for_location(40.0, -74.0)
    
    # Check Census Feature
    assert features['population_total'] == 5000
    # Check OSM Feature
    assert features['road_network_density'] == 15.5
    # Check Satellite Feature
    assert features['ndvi_mean'] == 0.45
    
    # Verify aggregations key count (3 census + 3 osm + 2 sat = 8)
    # Note: Validator might add default imputed keys, so we check >=
    assert len(features) >= 8

def test_validator_cleaning():
    """
    Test that the validator handles missing values.
    """
    validator = FeatureValidator()
    
    dirty_data = {
        'population_total': None,      # Should be imputed
        'median_household_income': 50000,
        'vacancy_rate': 150.0          # Out of bounds!
    }
    
    # 1. Test Imputation
    clean_data = validator.impute_missing_values(dirty_data)
    assert clean_data['population_total'] == 0  # Default fallback
    
    # 2. Test Validation Report
    report = validator.validate_feature_vector(dirty_data)
    assert report['is_valid'] is False
    assert len(report['out_of_bounds']) > 0  # vacancy rate > 100

def test_cache_key_generation():
    """
    Test spatial binning logic in cache keys.
    """
    cache = FeatureCache(host="fake")
    
    # Two very close points (millimeter difference) should have SAME key
    key1 = cache.cache_key_for_location(40.123456, -74.123456, "test", 500)
    key2 = cache.cache_key_for_location(40.123457, -74.123459, "test", 500)
    
    assert key1 == key2, "Cache keys should match for very nearby points"
    
    # Far point should have DIFFERENT key
    key3 = cache.cache_key_for_location(40.12355, -74.12355, "test", 500)
    assert key1 != key3
