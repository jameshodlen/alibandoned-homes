"""
Generate probability heatmap for a geographic area.

Usage:
    python predict_area.py --center 42.3314,-83.0458 --radius 5 --resolution 100
"""

import argparse
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import joblib
from pathlib import Path
import sys
import os

# Fix paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.ml_pipeline.models.location_predictor import LocationPredictor
from backend.ml_pipeline.visualization.prediction_viz import PredictionVisualizer

def create_grid(center_lat, center_lon, radius_km, resolution_meters):
    """Create grid of points."""
    radius_deg = radius_km / 111.0
    
    lats = np.arange(
        center_lat - radius_deg, center_lat + radius_deg,
        resolution_meters / 111000
    )
    lons = np.arange(
        center_lon - radius_deg, center_lon + radius_deg,
        resolution_meters / (111000 * np.cos(np.radians(center_lat)))
    )
    
    lat_grid, lon_grid = np.meshgrid(lats, lons)
    return pd.DataFrame({'latitude': lat_grid.flatten(), 'longitude': lon_grid.flatten()})

def main(args):
    print(f"Predicting area around {args.center}...")
    lat, lon = map(float, args.center.split(','))
    
    # 1. Load Model
    model_path = 'backend/ml_pipeline/models/saved/location_predictor'
    try:
        predictor = LocationPredictor.load(model_path)
    except Exception as e:
        print(f"Error loading model from {model_path}: {e}")
        print("Please run train_location_predictor.py first!")
        return

    # 2. Create Grid
    grid = create_grid(lat, lon, args.radius, args.resolution)
    print(f"Created grid with {len(grid)} points.")
    
    # 3. Extracts Features (Mocked here for speed, in real app use BatchProcessor)
    # We create dummy features matching the trained model's expectations
    feature_names = predictor.feature_names
    print(f"Extracting {len(feature_names)} features...")
    
    # Synthesize features based on location (just for demo visualization)
    # Create a fake "hotspot" near center
    dist_to_center = np.sqrt((grid['latitude'] - lat)**2 + (grid['longitude'] - lon)**2)
    
    features_dict = {}
    for f in feature_names:
        if f == 'median_income':
            # Income increases with distance from center
            features_dict[f] = 20000 + (dist_to_center * 1000000) 
        elif f == 'vacancy_rate':
            # Vacancy decreases with distance
            features_dict[f] = 0.2 - (dist_to_center * 2)
        else:
            features_dict[f] = np.random.random(len(grid))
            
    X = pd.DataFrame(features_dict)
    coords = grid[['latitude', 'longitude']].values
    
    # 4. Predict
    print("Running Ensemble Prediction...")
    probs = predictor.ensemble.predict_proba(X, coords)
    grid['probability'] = probs
    
    # 5. Visualize
    print("Generating Heatmap...")
    geometry = [Point(xy) for xy in zip(grid.longitude, grid.latitude)]
    gdf = gpd.GeoDataFrame(grid, geometry=geometry, crs='EPSG:4326')
    
    viz = PredictionVisualizer()
    m = viz.create_probability_heatmap(gdf)
    
    out_file = f'predictions_{lat}_{lon}.html'
    m.save(out_file)
    print(f"Saved interactive map to {out_file}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--center', default="42.33,-83.05")
    parser.add_argument('--radius', type=float, default=2.0)
    parser.add_argument('--resolution', type=int, default=200)
    args = parser.parse_args()
    main(args)
