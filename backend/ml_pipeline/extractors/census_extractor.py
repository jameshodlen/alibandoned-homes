"""
Census Data Extractor
====================

This module handles the extraction of demographic and economic data from the 
US Census Bureau using the `cenpy` library.

We rely on the American Community Survey (ACS) 5-year estimates because:
1. It provides data at the detailed 'Census Tract' level
2. It has lower margin of error than 1-year estimates
3. It covers the entire country (unlike 1-year which is only for large metros)

Key Demographic Indicators for Abandonment:
- Population Decline: People voting with their feet
- Poverty Rate: Economic distress
- Vacancy Rate: Direct measure of empty homes
- Low Home Values: Disinvestment
"""

import logging
from typing import Dict, Any, Optional
import cenpy
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

# Mapping of variable codes to human-readable names
# Source: https://api.census.gov/data/2021/acs/acs5/variables.html
CENSUS_VARIABLES = {
    # Population
    'B01003_001E': 'population_total',
    'B01002_001E': 'median_age',
    
    # Income & Economics
    'B19013_001E': 'median_household_income',
    'B17001_002E': 'population_in_poverty',  # Divide by total for rate
    'B23025_005E': 'population_unemployed',  # Civilian labor force unemployed
    'B23025_002E': 'civilian_labor_force',
    
    # Housing
    'B25001_001E': 'housing_units_total',
    'B25002_003E': 'housing_units_vacant',
    'B25003_002E': 'housing_units_owner_occupied',
    'B25077_001E': 'median_home_value',
    
    # Education
    'B15003_022E': 'bachelors_degree_count',
    'B15003_001E': 'education_total_population',
}

class CensusExtractor:
    """
    Extracts variable from US Census API.
    """

    def __init__(self, dataset_name: str = 'ACSDT5Y2021'):
        """
        Initialize the Census API connection.
        
        Args:
            dataset_name: Census dataset identifier. 
                         'ACSDT5Y2021' = ACS 5-year estimates 2021.
        """
        self.dataset_name = dataset_name
        self.conn = None
        
        try:
            # Connect to Census API
            # Note: cenpy handles caching of the variable list automatically
            self.conn = cenpy.products.APIConnection(dataset_name)
            logger.info(f"Connected to Census dataset: {dataset_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Census API: {e}")

    def get_census_tract(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Convert lat/long to FIPS census tract code.
        
        This involves a spatial query to the Census TigerWeb service or 
        using local shapefiles. For simplicity in this demo, we assume 
        external geocoding (e.g. via FCC API or local PostGIS).
        
        For this implementation, we'll return a placeholder or implement
        a mock since we don't have the TigerWeb API wrapper fully set up.
        
        In production: Use `cenpy.remote.APIConnection` to query geography.
        """
        # TODO: Implement actual FIPS geocoding
        # For now, return a Dummy FIPS code for testing structure
        return "12345678901"

    def extract_features(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Main entry point: Get features for a specific point.
        """
        if not self.conn:
            return {}

        tract_fips = self.get_census_tract(latitude, longitude)
        if not tract_fips:
            return {}

        return self.get_tract_data(tract_fips)

    def get_tract_data(self, tract_fips: str) -> Dict[str, Any]:
        """
        Query the Census API for the specific tract.
        """
        # In a real implementation with cenpy:
        # data = self.conn.query(
        #    cols=list(CENSUS_VARIABLES.keys()),
        #    geo_unit='tract:' + tract_fips[-6:],
        #    geo_filter={'state': tract_fips[:2], 'county': tract_fips[2:5]}
        # )
        
        # MOCK IMPLEMENTATION (since we can't hit real API without setup)
        # ----------------------------------------------------------------
        # Return realistic looking data for demonstration
        import random
        
        # Consistent random seed based on fips for repeatability
        random.seed(tract_fips)
        
        total_pop = random.randint(2000, 6000)
        total_housing = int(total_pop / 2.5)
        vacant = int(total_housing * random.uniform(0.05, 0.25))
        
        raw_data = {
            'population_total': total_pop,
            'median_age': random.uniform(30, 45),
            'median_household_income': random.uniform(30000, 80000),
            'population_in_poverty': int(total_pop * random.uniform(0.1, 0.3)),
            'population_unemployed': int(total_pop * random.uniform(0.04, 0.12)),
            'civilian_labor_force': int(total_pop * 0.6),
            'housing_units_total': total_housing,
            'housing_units_vacant': vacant,
            'housing_units_owner_occupied': int((total_housing - vacant) * random.uniform(0.4, 0.7)),
            'median_home_value': random.uniform(100000, 400000),
            'bachelors_degree_count': int(total_pop * random.uniform(0.1, 0.4)),
            'education_total_population': int(total_pop * 0.7),
        }
        # ----------------------------------------------------------------

        return self._calculate_derived_metrics(raw_data)

    def _calculate_derived_metrics(self, raw_data: Dict[str, float]) -> Dict[str, float]:
        """
        Convert raw counts into useful rates and percentages.
        
        Why?
        - '500 vacant homes' means nothing without knowing total homes.
        - '10% vacancy' is comparable across different sized neighborhoods.
        """
        metrics = {}
        
        # Pass through absolute values that are useful
        metrics['population_total'] = raw_data.get('population_total')
        metrics['median_household_income'] = raw_data.get('median_household_income')
        metrics['median_home_value'] = raw_data.get('median_home_value')
        metrics['median_age'] = raw_data.get('median_age')

        # Calculate Rates (avoid division by zero)
        
        # Vacancy Rate: Critical abandonment indicator
        if raw_data.get('housing_units_total', 0) > 0:
            metrics['vacancy_rate'] = (
                raw_data['housing_units_vacant'] / raw_data['housing_units_total']
            ) * 100
        else:
            metrics['vacancy_rate'] = 0.0

        # Poverty Rate
        if raw_data.get('population_total', 0) > 0:
            metrics['poverty_rate'] = (
                raw_data['population_in_poverty'] / raw_data['population_total']
            ) * 100
        else:
            metrics['poverty_rate'] = 0.0
            
        # Unemployment Rate
        if raw_data.get('civilian_labor_force', 0) > 0:
            metrics['unemployment_rate'] = (
                raw_data['population_unemployed'] / raw_data['civilian_labor_force']
            ) * 100
        else:
            metrics['unemployment_rate'] = 0.0
            
        # Education: % Bachelors or higher
        if raw_data.get('education_total_population', 0) > 0:
            metrics['percent_bachelors_degree'] = (
                raw_data['bachelors_degree_count'] / raw_data['education_total_population']
            ) * 100
        else:
            metrics['percent_bachelors_degree'] = 0.0

        return metrics
