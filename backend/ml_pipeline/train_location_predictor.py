"""
Complete training script for location prediction ensemble.

This trains all sub-models and combines them into an ensemble predictor.

Usage:
    python train_location_predictor.py --min_samples 20
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path

# Fix paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.ml_pipeline.models.rf_predictor import RandomForestPredictor
from backend.ml_pipeline.models.spatial_clustering import SpatialClusteringPredictor
from backend.ml_pipeline.models.kde_predictor import KernelDensityEstimator
from backend.ml_pipeline.models.ensemble import EnsemblePredictor
from backend.ml_pipeline.feature_engineering import FeatureEngineering
from backend.ml_pipeline.evaluation.spatial_cv import SpatialCrossValidator
import joblib

def main():
    print("="*60)
    print("Location Prediction Model Training")
    print("="*60)
    
    # 1. Load Data (Mock for now, normally from DB)
    print("\n1. Loading location data...")
    # Mocking data for demonstration if DB is empty or for portability
    # In real usage, uncomment DB loading
    
    # Generate Synthetic Data
    # A cluster of 'abandoned' points around (42.33, -83.05)
    n_points = 200
    aband_lat = np.random.normal(42.33, 0.01, 50)
    aband_lon = np.random.normal(-83.05, 0.01, 50)
    
    normal_lat = np.random.uniform(42.30, 42.36, 150)
    normal_lon = np.random.uniform(-83.10, -83.00, 150)
    
    lats = np.concatenate([aband_lat, normal_lat])
    lons = np.concatenate([aband_lon, normal_lon])
    labels = np.concatenate([np.ones(50), np.zeros(150)])
    
    df = pd.DataFrame({'latitude': lats, 'longitude': lons, 'label': labels, 'location_id': range(n_points)})
    print(f"  Total training samples: {len(df)}")
    
    # 2. Extract Features
    print("\n2. Extracting features...")
    # For speed in this script, we'll mock features too
    # Abandoned: Low income, High vacancy
    # Normal: High income, Low vacancy
    
    features_list = []
    for i, row in df.iterrows():
        is_aband = row['label'] == 1
        feat = {
            'population_density': np.random.normal(2000 if is_aband else 5000, 500),
            'median_income': np.random.normal(25000 if is_aband else 60000, 5000),
            'vacancy_rate': np.random.normal(0.20 if is_aband else 0.05, 0.02),
            'distance_to_grocery': np.random.normal(2000 if is_aband else 500, 200),
            'ndvi_mean': np.random.normal(0.4 if is_aband else 0.2, 0.05) # Overgrowth
        }
        features_list.append(feat)
        
    features_df = pd.DataFrame(features_list)
    feature_names = features_df.columns.tolist()
    
    # 3. Spatial Split
    print("\n3. Creating spatial train/validation split...")
    coords = df[['latitude', 'longitude']].values
    spatial_cv = SpatialCrossValidator(n_splits=5, buffer_distance_km=2)
    splits = list(spatial_cv.split(features_df, df['label'], coords))
    
    if not splits:
        print("Warning: Spatial split failed (not enough data?), falling back to random split")
        from sklearn.model_selection import train_test_split
        train_idx, val_idx = train_test_split(range(len(df)), test_size=0.2, random_state=42)
    else:
        train_idx, val_idx = splits[0]
        
    X_train, X_val = features_df.iloc[train_idx], features_df.iloc[val_idx]
    y_train, y_val = df['label'].iloc[train_idx], df['label'].iloc[val_idx]
    coords_train, coords_val = coords[train_idx], coords[val_idx]
    
    # 4. Train Random Forest
    print("\n4. Training Random Forest...")
    rf = RandomForestPredictor()
    rf.train(X_train, y_train, X_val, y_val)
    
    # 5. Train Spatial Models
    print("\n5. Training Spatial Models...")
    # Only train on abandoned points
    aband_train_mask = (y_train == 1)
    aband_coords_train = coords_train[aband_train_mask]
    
    spatial = SpatialClusteringPredictor(eps_meters=500)
    spatial.train(aband_coords_train)
    
    kde = KernelDensityEstimator(bandwidth_meters=1000)
    kde.train(aband_coords_train)
    
    # 6. Ensemble
    print("\n6. Optimizing Ensemble...")
    ensemble = EnsemblePredictor({'rf': rf, 'spatial': spatial, 'kde': kde})
    ensemble.calculate_optimal_weights(X_val, y_val, coords_val)
    
    # 7. Save
    print("\n7. Saving Models...")
    out_dir = Path('backend/ml_pipeline/models/saved/location_predictor')
    out_dir.mkdir(parents=True, exist_ok=True)
    
    joblib.dump(ensemble, out_dir / 'ensemble.pkl')
    with open(out_dir / 'feature_names.txt', 'w') as f:
        f.write('\n'.join(feature_names))
        
    print(f"Done. Saved to {out_dir}")

if __name__ == "__main__":
    main()
