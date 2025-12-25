"""
Random Forest Predictor
======================

This component uses Random Forest to predict abandonment based on tabular features.
It is the "Feature Expert" in our ensemble.

Algorithm Explained:
------------------
Random Forest is a collection of Decision Trees.
- A single Decision Tree asks a series of questions ("Is income < $30k?", "Is vacancy > 10%?").
- A single tree is prone to overfitting (memorizing the data).
- A Random Forest trains hundreds of trees on random subsets of data and features.
- The final prediction is the average vote of all trees.

Why it's good for this task:
1. Handles non-linear relationships (e.g., income matters differently in cities vs suburbs).
2. Robust to outliers.
3. Provides "Feature Importance" (tells us which data points matter most).
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import shap
import matplotlib.pyplot as plt
import os
from typing import Dict, List, Any, Tuple

class RandomForestPredictor:
    """
    Feature-based predictor using Random Forest Classifier.
    """
    
    def __init__(self, n_estimators: int = 100, max_depth: int = None, class_weight: str = 'balanced'):
        """
        Args:
            n_estimators: Number of trees. More = stable but slower (diminishing returns > 100).
            max_depth: Max questions per tree. None = grow until pure. Limit to prevent overfitting.
            class_weight: 'balanced' automatically ups weight for minority class (abandoned).
        """
        self.feature_names = None
        self.pipeline = Pipeline([
            # 1. Scaler: RF doesn't strictly need this, but good for interpretation & other models
            ('scaler', StandardScaler()),
            
            # 2. Selector: Optional, keeps top k features to reduce noise
            # ('selector', SelectKBest(f_classif, k=30)), 
            
            # 3. Classifier
            ('rf', RandomForestClassifier(
                n_estimators=n_estimators,    # Number of trees (voters)
                max_depth=max_depth,          # Max "questions" per tree
                min_samples_split=20,         # Don't split tiny groups (noise)
                min_samples_leaf=10,          # Leaves must have decent size
                max_features='sqrt',          # Diversity: force trees to look at different features
                class_weight=class_weight,    # Handle imbalance (few abandoned homes)
                bootstrap=True,               # Train on random sample with replacement
                n_jobs=-1,                    # Use all CPU cores
                random_state=42               # Reproducibility
            ))
        ])

    def train(self, X_train: pd.DataFrame, y_train: pd.Series, X_val: pd.DataFrame, y_val: pd.Series) -> Dict[str, float]:
        """
        Train the forest and validate.
        """
        self.feature_names = X_train.columns.tolist()
        
        print(f"Training Random Forest on {len(X_train)} samples with {len(self.feature_names)} features...")
        self.pipeline.fit(X_train, y_train)
        
        # Validation
        print("Validating model...")
        y_pred = self.pipeline.predict(X_val)
        y_probs = self.pipeline.predict_proba(X_val)[:, 1]
        
        metrics = {
            'accuracy': accuracy_score(y_val, y_pred),
            'precision': precision_score(y_val, y_pred, zero_division=0),
            'recall': recall_score(y_val, y_pred, zero_division=0),
            'f1_score': f1_score(y_val, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y_val, y_probs)
        }
        
        return metrics

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get probability predictions [batch_size, 2].
        Returns: 2D array where col 0 is P(Normal), col 1 is P(Abandoned).
        """
        return self.pipeline.predict_proba(X)

    def get_feature_importance(self, feature_names: List[str] = None) -> List[Tuple[str, float]]:
        """
        Extract Gini Importance: How much does each feature clean up the prediction?
        """
        if feature_names is None:
            feature_names = self.feature_names
            
        rf_model = self.pipeline.named_steps['rf']
        importances = rf_model.feature_importances_
        
        # Sort desc
        indices = np.argsort(importances)[::-1]
        sorted_features = [(feature_names[i], importances[i]) for i in indices]
        
        return sorted_features

    def explain_with_shap(self, X: pd.DataFrame, feature_names: List[str] = None) -> Any:
        """
        Use SHAP (Shapley Additive Explanations) for deep interpretability.
        
        Theory:
        Based on Game Theory. It treats each feature as a "player" in a game
        trying to predict the outcome. It calculates the marginal contribution
        of each feature to the final score.
        """
        if feature_names is None:
            feature_names = self.feature_names
            
        # We need the raw model and scaled data for SHAP
        rf_model = self.pipeline.named_steps['rf']
        scaler = self.pipeline.named_steps['scaler']
        X_scaled = scaler.transform(X)
        
        # TreeExplainer is optimized for Random Forests (orders of magnitude faster than generic)
        explainer = shap.TreeExplainer(rf_model)
        shap_values = explainer.shap_values(X_scaled)
        
        # Creates a Plot looking like:
        # P(Abandoned) = Base Rate + Feat1_Effect + Feat2_Effect ...
        
        return explainer, shap_values
