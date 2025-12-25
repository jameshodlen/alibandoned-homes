"""
Feature Validator Module
=======================

This module is responsible for Data Quality Assurance (QA).
Garbage In = Garbage Out. We must ensure extracted features are:
1. Complete (no missing values)
2. Valid (within physical/logical bounds)
3. Normalized (scaled correctly for ML models)

Feature validation happens AFTER extraction but BEFORE model training/prediction.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

class FeatureValidator:
    """
    Validates, cleans, and normalizes feature vectors.
    """

    def __init__(self):
        self.scaler = StandardScaler()
        self.is_fitted = False
        
        # Define logical bounds for features
        # If a feature is outside these bounds, it's likely an error
        self.feature_bounds = {
            # Percentages must be 0-100
            'vacancy_rate': (0, 100),
            'poverty_rate': (0, 100),
            'unemployment_rate': (0, 100),
            'percent_bachelors_degree': (0, 100),
            
            # Indices must be -1 to 1
            'ndvi_mean': (-1, 1),
            'ndbi_mean': (-1, 1),
            'ndwi_mean': (-1, 1),
            
            # Non-negative values
            'median_household_income': (0, 1000000),  # $0 to $1M
            'population_total': (0, None),
            'distance_to_grocery_store': (0, None),
        }

    def validate_feature_vector(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check a single feature vector for quality issues.
        Returns a validation report.
        
        Args:
            features: Dictionary of feature name -> value
            
        Returns:
            Dictionary containing 'is_valid', 'flags', 'missing_keys', 'out_of_bounds'
        """
        report = {
            'is_valid': True,
            'flags': [],
            'missing_keys': [],
            'out_of_bounds': []
        }
        
        # 1. Check for missing values (None or NaN)
        for key, value in features.items():
            if value is None or (isinstance(value, float) and np.isnan(value)):
                report['missing_keys'].append(key)
                report['flags'].append(f"Missing value for {key}")
                report['is_valid'] = False  # Depending on strictness, this might be OK if imputed
        
        # 2. Check for logical bounds
        for key, value in features.items():
            if key in self.feature_bounds and value is not None:
                min_val, max_val = self.feature_bounds[key]
                
                if min_val is not None and value < min_val:
                    report['out_of_bounds'].append(f"{key}: {value} < {min_val}")
                    report['flags'].append(f"{key} too low")
                    report['is_valid'] = False
                    
                if max_val is not None and value > max_val:
                    report['out_of_bounds'].append(f"{key}: {value} > {max_val}")
                    report['flags'].append(f"{key} too high")
                    report['is_valid'] = False
                    
        return report

    def impute_missing_values(self, features: Dict[str, Any], strategy: str = 'median') -> Dict[str, Any]:
        """
        Fill in missing values using a specified strategy.
        
        Strategies:
        - 'zero': Fill with 0 (good for counts)
        - 'median': Fill with a rough median (good for demographics)
        - 'flag': Keep missing but add a binary flag (requires changing schema)
        
        Note: detailed imputation usually requires a dataset statistics file.
        Here we use hardcoded safe defaults for common fields.
        """
        cleaned = features.copy()
        
        # Default fallback values for common fields
        # Ideally these should come from a pre-calculated stats file
        defaults = {
            'population_total': 0,
            'median_household_income': 50000, # National roughly
            'vacancy_rate': 10.0,
            'ndvi_mean': 0.0, # Neutral
            'road_network_density': 0.0,
            'distance_to_grocery_store': 5000, # Assume far if unknown
        }
        
        for key, value in cleaned.items():
            if value is None or (isinstance(value, float) and np.isnan(value)):
                if key in defaults:
                    cleaned[key] = defaults[key]
                else:
                    # Generic fallbacks by type
                    if 'count' in key:
                        cleaned[key] = 0
                    elif 'rate' in key or 'percent' in key:
                        cleaned[key] = 0.0
                    elif 'distance' in key:
                        cleaned[key] = 9999.0 # Max distance
                    else:
                        cleaned[key] = 0.0
                        
        return cleaned

    def fit_scaler(self, training_data: List[Dict[str, Any]]):
        """
        Learn the mean and variance of the training data for normalization.
        
        Args:
            training_data: List of feature dictionaries
        """
        df = pd.DataFrame(training_data)
        # Handle non-numeric cols if any (drop them for scaling)
        numeric_df = df.select_dtypes(include=[np.number])
        self.scaler.fit(numeric_df)
        self.is_fitted = True
        logger.info(f"Scaler fitted on {len(df)} samples")

    def normalize_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scale features to have 0 mean and 1 variance.
        Critical for models like SVM, Neural Networks, K-Means.
        Tree-based models (Random Forest, XGBoost) don't technically need this 
        but it doesn't hurt.
        """
        if not self.is_fitted:
            logger.warning("Scaler not fitted! Returning raw features.")
            return features
            
        # Convert to DF for sklearn compatibility
        df = pd.DataFrame([features])
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if len(numeric_cols) == 0:
            return features
            
        scaled_values = self.scaler.transform(df[numeric_cols])
        
        # Reconstruct dictionary
        result = features.copy()
        for i, col in enumerate(numeric_cols):
            result[col] = float(scaled_values[0][i])
            
        return result
