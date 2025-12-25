"""
Feature Engineering Orchestrator
===============================

This is the main entry point for the Feature Engineering Service.
It orchestrates the extraction of features from all configured sources:
1. Census (Demographics)
2. OpenStreetMap (Spatial/Infrastructure)
3. Satellite (Environmental)

It handles:
- Caching (via Redis)
- concurrency (via AsyncIO)
- Validation
- Aggregation
"""

import logging
import asyncio
import os
import time
from typing import Dict, Any, List, Optional

from backend.ml_pipeline.feature_cache import FeatureCache
from backend.ml_pipeline.feature_validator import FeatureValidator
from backend.ml_pipeline.extractors.census_extractor import CensusExtractor
from backend.ml_pipeline.extractors.osm_extractor import OSMExtractor
from backend.ml_pipeline.extractors.satellite_extractor import SatelliteExtractor
from backend.ml_pipeline.filters.canopy_mask import CanopyMask

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FeatureEngineering:
    """
    Main service class for extracting prediction features.
    """

    def __init__(self):
        """
        Initialize all sub-components.
        """
        # 1. Infrastructure
        self.cache = FeatureCache(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379))
        )
        self.validator = FeatureValidator()
        self.canopy_mask = CanopyMask()
        
        # 2. Extractors
        try:
            self.census = CensusExtractor()
            self.osm = OSMExtractor()
            self.satellite = SatelliteExtractor(
                client_id=os.getenv("SENTINEL_HUB_CLIENT_ID"),
                client_secret=os.getenv("SENTINEL_HUB_CLIENT_SECRET")
            )
        except Exception as e:
            logger.error(f"Error initializing extractors: {e}")
            raise

    def get_feature_names(self) -> List[str]:
        """
        Returns the ordered list of all features produced by this pipeline.
        Crucial for maintaining consistency with the ML model.
        """
        return [
            # Census
            'population_total', 'median_age', 'median_household_income',
            'poverty_rate', 'vacancy_rate', 'unemployment_rate',
            'percent_bachelors_degree', 'median_home_value',
            
            # OSM
            'road_network_density', 'intersection_density',
            'street_connectivity', 'dead_end_count',
            'amenity_count_total', 'grocery_store_count',
            'building_count_200m',
            
            # Satellite
            'ndvi_mean', 'ndbi_mean', 'cloud_coverage',
            
            # Derived / Filters
            'vegetation_class', 'canopy_abandonment_score_adj'
        ]

    def extract_features_for_location(
        self, 
        latitude: float, 
        longitude: float, 
        radius_meters: int = 500,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Extract all features for a single location.
        
        Args:
            latitude: Degree decimal
            longitude: Degree decimal
            radius_meters: Analysis context size
            use_cache: Whether to check Redis first
            
        Returns:
            Dictionary of 50+ features
        """
        start_time = time.time()
        location_id = f"{latitude},{longitude}"
        
        # 1. Check Cache
        # --------------
        cache_key = self.cache.cache_key_for_location(
            latitude, longitude, "all_features", radius_meters
        )
        
        if use_cache:
            cached = self.cache.get_cached_features(cache_key)
            if cached:
                logger.debug(f"Returning cached features for {location_id}")
                return cached

        # 2. Run Extractors
        # -----------------
        # Note: In a real async app, we'd use await asyncio.gather() here.
        # Since our extractors are currently synchronous (blocking), we run them sequentially.
        # Ideally, we would wrap them in run_in_executor for concurrency.
        
        logger.info(f"Extracting features for {location_id}...")
        
        # A. Census Data
        census_data = self.census.extract_features(latitude, longitude)
        
        # B. OSM Data
        osm_data = self.osm.extract_features(latitude, longitude, radius_meters)
        
        # C. Satellite Data
        sat_data = self.satellite.extract_features(latitude, longitude, radius_meters)
        
        # D. Canopy Mask (Vegetation Classification)
        # We need neighborhood stats first, but for now we'll mock them or use what we have.
        # Ideally, we'd fetch neighborhood NDVI stats. 
        # Here we just pass a placeholder or derived stats.
        neighborhood_stats = {
            'mean_ndvi': sat_data.get('ndvi_mean', 0.4), # Self-referential fallback for now
            'std_ndvi': 0.1
        }
        
        veg_class = self.canopy_mask.classify_vegetation(
            sat_data.get('ndvi_mean', 0.0) or 0.0, 
            neighborhood_stats
        )
        
        # Adjust a theoretical base score (e.g. 0.5) to see effect
        score_adj = self.canopy_mask.adjust_abandonment_score(1.0, veg_class)
        
        filter_data = {
            'vegetation_class': veg_class,
            'canopy_abandonment_score_adj': score_adj
        }

        # 3. Aggregate
        # ------------
        features = {
            **census_data,
            **osm_data,
            **sat_data,
            **filter_data
        }
        
        # 4. Validate & Impute
        # --------------------
        # Ensure we have a complete vector
        features = self.validator.impute_missing_values(features)
        
        validation_report = self.validator.validate_feature_vector(features)
        if not validation_report['is_valid']:
            logger.warning(f"Data quality issues for {location_id}: {validation_report['flags']}")
        
        # 5. Cache Result
        # ---------------
        if use_cache:
             self.cache.cache_features(cache_key, features, ttl_seconds=86400 * 7) # 7 days
             
        duration = time.time() - start_time
        logger.info(f"Target {location_id} processed in {duration:.2f}s")
             
        return features

    def get_feature_importance_report(self, model, feature_values: Dict[str, float]) -> str:
        """
        Generate a human-readable explanation of why a location was flagged.
        (Placeholder for when we have a trained model)
        """
        # TODO: Implement SHAP or permutation importance
        return "Feature importance report not yet implemented."
