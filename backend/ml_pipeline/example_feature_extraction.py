"""
Example: Feature Extraction Pipeline
===================================

This script demonstrates how to use the feature engineering service
to extract features for deep learning models.

Key concepts demonstrated:
1. Single point extraction
2. Batch processing
3. Interpretation of results
"""

import sys
import logging
import asyncio
from typing import Dict, Any

# Adjust path to find backend modules
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from backend.ml_pipeline.feature_engineering import FeatureEngineering
from backend.ml_pipeline.batch_processor import BatchProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def interpret_features(features: Dict[str, Any]):
    """
    Print a human-readable interpretation of the features.
    """
    print("\n" + "="*50)
    print("FEATURE INTERPRETATION REPORT")
    print("="*50)
    
    # 1. Economic Health
    # ------------------
    income = features.get('median_household_income', 0)
    poverty = features.get('poverty_rate', 0)
    
    print(f"\n[Economic Indicators]")
    print(f"  Median Income: ${income:,.0f}")
    print(f"  Poverty Rate:  {poverty:.1f}%")
    
    if poverty > 20:
        print("  ⚠️  HIGH POVERTY: Area is economically distressed.")
    elif income < 40000:
        print("  ⚠️  LOW INCOME: Potential financial instability.")
    else:
        print("  ✅  Stable economic indicators.")

    # 2. Housing Stability
    # --------------------
    vacancy = features.get('vacancy_rate', 0)
    
    print(f"\n[Housing Stability]")
    print(f"  Vacancy Rate:  {vacancy:.1f}%")
    
    if vacancy > 15:
        print("  ⚠️  CRITICAL: High vacancy rate indicates abandonment risk.")
    elif vacancy > 8:
        print("  ⚠️  WARNING: Elevated vacancy rate.")
    else:
        print("  ✅  Healthy occupancy levels.")

    # 3. Built Environment
    # --------------------
    road_density = features.get('road_network_density', 0)
    amenities = features.get('amenity_count_total', 0)
    
    print(f"\n[Built Environment]")
    print(f"  Road Density:  {road_density:.2f} km/km²")
    print(f"  Amenities:     {amenities} within 500m")
    
    if road_density < 5:
        print("  ℹ️  Rural/Sparse area context.")
    elif amenities < 2:
        print("  ⚠️  LOW AMENITY: 'Service desert' conditions.")
        
    # 4. Environmental
    # ----------------
    ndvi = features.get('ndvi_mean')
    
    print(f"\n[Environmental]")
    if ndvi is not None:
        print(f"  Vegetation (NDVI): {ndvi:.2f}")
        if ndvi > 0.6:
            print("  ℹ️  Dense vegetation (verify if maintained or overgrown).")
    else:
        print("  ⚪ No satellite data available.")
        
    print("\n" + "="*50 + "\n")

def run_single_example():
    """
    Run extraction for one known location (Detroit, MI).
    """
    print("Initializing Feature Engineering Service...")
    fe = FeatureEngineering()
    
    # Detroit coordinates (approximate neighborhood)
    lat, lon = 42.3314, -83.0458
    
    print(f"Extracting features for Detroit ({lat}, {lon})...")
    features = fe.extract_features_for_location(
        latitude=lat, 
        longitude=lon, 
        radius_meters=500
    )
    
    interpret_features(features)

def run_batch_example():
    """
    Run efficient batch processing.
    """
    print("Running Batch Processing Example...")
    batch_proc = BatchProcessor(max_workers=3)
    
    locations = [
        {'id': 'loc_1', 'lat': 40.7128, 'lon': -74.0060}, # NYC
        {'id': 'loc_2', 'lat': 34.0522, 'lon': -118.2437}, # LA
        {'id': 'loc_3', 'lat': 41.8781, 'lon': -87.6298}, # Chicago
    ]
    
    df = batch_proc.process_locations(locations)
    print(f"\nBatch Result Shape: {df.shape}")
    print("First 5 columns:")
    print(df.iloc[:, :5])

if __name__ == "__main__":
    # Ensure Redis is running or caching will allow fallback (with warning)
    try:
        run_single_example()
        run_batch_example()
    except Exception as e:
        logger.error(f"Execution failed: {e}")
