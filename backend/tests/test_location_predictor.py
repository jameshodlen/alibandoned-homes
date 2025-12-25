"""
Tests for Location Prediction System
===================================
"""

import pytest
import numpy as np
import pandas as pd
import shutil
from pathlib import Path

from backend.ml_pipeline.models.rf_predictor import RandomForestPredictor
from backend.ml_pipeline.models.spatial_clustering import SpatialClusteringPredictor
from backend.ml_pipeline.models.ensemble import EnsemblePredictor
from backend.ml_pipeline.evaluation.spatial_cv import SpatialCrossValidator

@pytest.fixture
def mock_data():
    # 20 samples, 5 features
    X = pd.DataFrame(np.random.rand(20, 5), columns=[f'feat_{i}' for i in range(5)])
    y = np.random.randint(0, 2, 20)
    # Coordinates in Detroit
    lats = np.random.uniform(42.30, 42.40, 20)
    lons = np.random.uniform(-83.10, -83.00, 20)
    coords = np.column_stack([lats, lons])
    return X, y, coords

def test_rf_predictor(mock_data):
    X, y, _ = mock_data
    rf = RandomForestPredictor(n_estimators=10)
    
    # Split
    X_train, X_val = X.iloc[:15], X.iloc[15:]
    y_train, y_val = y[:15], y[15:]
    
    metrics = rf.train(X_train, y_train, X_val, y_val)
    assert 'f1_score' in metrics
    
    probs = rf.predict_proba(X_val)
    assert probs.shape == (5, 2)
    
    importances = rf.get_feature_importance()
    assert len(importances) == 5

def test_spatial_clustering(mock_data):
    _, _, coords = mock_data
    # Make a distinct cluster
    coords[0] = [42.35, -83.05]
    coords[1] = [42.3501, -83.0501] # Very close
    coords[2] = [42.3502, -83.0502] 
    
    model = SpatialClusteringPredictor(eps_meters=500, min_samples=2)
    metrics = model.train(coords)
    
    assert metrics['n_clusters'] >= 1
    assert -1 in metrics['labels'] # Likely some noise
    
    # Predict
    probs = model.predict_proba(coords[:5])
    assert len(probs) == 5
    # First 3 should be high probability (part of cluster)
    assert probs[0] > 0.5

def test_ensemble(mock_data):
    X, y, coords = mock_data
    
    # Mock trained sub-models (using real classes but lightweight)
    rf = RandomForestPredictor(n_estimators=5)
    rf.train(X, y, X, y) # Cheating for test speed
    
    sp = SpatialClusteringPredictor(min_samples=2)
    sp.train(coords)
    
    ensemble = EnsemblePredictor({'rf': rf, 'spatial': sp, 'kde': None})
    
    # Test weights optimization
    weights = ensemble.calculate_optimal_weights(X, y, coords)
    assert abs(sum(weights.values()) - 1.0) < 0.001
    
    # Predict
    p = ensemble.predict_proba(X, coords)
    assert len(p) == 20
    assert (p >= 0).all() and (p <= 1).all()

def test_spatial_cv(mock_data):
    X, y, coords = mock_data
    cv = SpatialCrossValidator(n_splits=2, buffer_distance_km=1)
    
    splits = list(cv.split(X, y, coords))
    assert len(splits) == 2
    
    train_idx, test_idx = splits[0]
    assert len(train_idx) > 0
    assert len(test_idx) > 0
    # Intersection must be empty
    assert len(set(train_idx).intersection(set(test_idx))) == 0
