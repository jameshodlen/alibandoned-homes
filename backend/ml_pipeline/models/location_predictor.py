"""
Location Predictor (Main Interface)
==================================

High-level facade for the location prediction system.
This is the class that the API or Training Script interacts with.

It orchestrates:
1. Feature Extraction (optional, can pass pre-computed)
2. Ensemble Prediction
3. Explanation Generation
"""

from typing import Dict, Any, Union
import pandas as pd
import numpy as np
import joblib
from feature_engineering import FeatureEngineering

class LocationPredictor:
    
    def __init__(self, ensemble_model=None, feature_names=None):
        self.ensemble = ensemble_model
        self.feature_names = feature_names
        self.fe = FeatureEngineering() # For live prediction

    @classmethod
    def load(cls, model_dir: str):
        """
        Factory method to load trained system from disk.
        """
        import os
        from pathlib import Path
        path = Path(model_dir)
        
        print(f"Loading ensemble from {path}...")
        ensemble = joblib.load(path / 'ensemble.pkl')
        
        # Load feature names list (critical for DF column ordering)
        with open(path / 'feature_names.txt', 'r') as f:
            feature_names = f.read().strip().split('\n')
            
        return cls(ensemble_model=ensemble, feature_names=feature_names)

    def predict_single_location(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        End-to-end prediction for a single coordinate.
        """
        # 1. Extract Features Live
        print(f"Extracting features for ({latitude}, {longitude})...")
        features = self.fe.extract_features_for_location(latitude, longitude)
        
        # 2. Prepare Dataframes
        # DataFrame must span only the columns expecting by RF, in correct order
        features_df = pd.DataFrame([features])
        
        # Ensure columns match training
        X = features_df[self.feature_names] 
        coords = np.array([[latitude, longitude]])
        
        # 3. Predict
        prob = self.ensemble.predict_proba(X, coords)[0]
        
        # 4. Explain
        explanation = self.ensemble.explain_prediction_breakdown(X, coords)
        
        return {
            'coordinates': {'lat': latitude, 'lon': longitude},
            'probability': prob,
            'is_high_risk': prob > 0.65,
            'explanation': explanation
        }
