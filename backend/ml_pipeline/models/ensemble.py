"""
Ensemble Predictor
=================

Combines the expert opinions of Random Forest, DBSCAN, and KDE.

Combination Strategy:
--------------------
Weighted Average:
Final_P = (w_rf * P_rf) + (w_spatial * P_spatial) + (w_kde * P_kde)

Optimization:
The weights (w) are not guessed. They are "learned" by maximizing performance
on a validation set via Grid Search.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from sklearn.metrics import f1_score, roc_auc_score

class EnsemblePredictor:
    
    def __init__(self, models_dict: Dict[str, Any], weights: Dict[str, float] = None):
        """
        Args:
            models_dict: {'rf': model, 'spatial': model, 'kde': model}
            weights: Dictionary of weights summing to 1.0. If None, equal weights used.
        """
        self.rf_model = models_dict.get('rf')
        self.spatial_model = models_dict.get('spatial')
        self.kde_model = models_dict.get('kde')
        
        if weights:
            self.weights = weights
        else:
            # Default to equal weighting if not specified
            self.weights = {'rf': 0.33, 'spatial': 0.33, 'kde': 0.34}

    def calculate_optimal_weights(self, X_val: pd.DataFrame, y_val: np.ndarray, coords_val: np.ndarray) -> Dict[str, float]:
        """
        Find weights that maximize F1/AUC on validation set.
        Using simple grid search over constrained simplex (w1+w2+w3=1).
        """
        print("Optimizing ensemble weights...")
        
        # 1. Pre-calculate predictions from each model (Outcome cache)
        # This is fast because we just look up scores, then we iterate weights.
        p_rf = self.rf_model.predict_proba(X_val)[:, 1]
        p_spatial = self.spatial_model.predict_proba(coords_val)
        p_kde = self.kde_model.predict_proba(coords_val)
        
        best_score = -1
        best_weights = self.weights
        
        # 2. Grid Search
        # Increment by 0.1 steps
        steps = np.arange(0, 1.1, 0.1)
        
        for w_rf in steps:
            for w_sp in steps:
                w_kde = 1.0 - w_rf - w_sp
                
                # Constraint: w3 must be non-negative and sum roughly to 1
                if w_kde < 0 or not np.isclose(w_rf + w_sp + w_kde, 1.0):
                    continue
                    
                # Calculate Ensemble Score
                p_ensemble = (w_rf * p_rf) + (w_sp * p_spatial) + (w_kde * p_kde)
                
                # Evaluate (AUC is good because it's threshold independent)
                try:
                    score = roc_auc_score(y_val, p_ensemble)
                except ValueError:
                    score = 0
                
                if score > best_score:
                    best_score = score
                    best_weights = {'rf': w_rf, 'spatial': w_sp, 'kde': w_kde}
        
        print(f"Best Ensemble AUC: {best_score:.4f} with weights {best_weights}")
        self.weights = best_weights
        return best_weights

    def predict_proba(self, X: pd.DataFrame, coords: np.ndarray) -> np.ndarray:
        """
        Get combined probability.
        """
        # Handle cases where model might be None (testing)
        p_rf = self.rf_model.predict_proba(X)[:, 1] if self.rf_model else np.zeros(len(X))
        p_spatial = self.spatial_model.predict_proba(coords) if self.spatial_model else np.zeros(len(coords))
        p_kde = self.kde_model.predict_proba(coords) if self.kde_model else np.zeros(len(coords))
        
        ensemble_proba = (
            self.weights['rf'] * p_rf +
            self.weights['spatial'] * p_spatial +
            self.weights['kde'] * p_kde
        )
        
        return ensemble_proba

    def explain_prediction_breakdown(self, X: pd.DataFrame, coords: np.ndarray) -> Dict[str, Any]:
        """
        Detailed breakdown for user interface.
        Show exactly how much each expert contributed.
        """
        p_rf = self.rf_model.predict_proba(X)[:, 1][0]
        p_spatial = self.spatial_model.predict_proba(coords)[0]
        p_kde = self.kde_model.predict_proba(coords)[0]
        
        final = (
            self.weights['rf'] * p_rf +
            self.weights['spatial'] * p_spatial +
            self.weights['kde'] * p_kde
        )
        
        return {
            'final_probability': float(final),
            'contributions': {
                'rf': {
                    'prediction': float(p_rf),
                    'weight': float(self.weights['rf']),
                    'contribution': float(p_rf * self.weights['rf'])
                },
                'spatial': {
                    'prediction': float(p_spatial),
                    'weight': float(self.weights['spatial']),
                    'contribution': float(p_spatial * self.weights['spatial'])
                },
                'kde': {
                    'prediction': float(p_kde),
                    'weight': float(self.weights['kde']),
                    'contribution': float(p_kde * self.weights['kde'])
                }
            }
        }
