"""
Hyperparameter Optimizer
=======================

Systematically finds the best settings for our models.
Uses Spatial CV to ensure the "best" settings actually work on new areas.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import make_scorer, f1_score, silhouette_score

class HyperparameterOptimizer:
    
    def __init__(self, spatial_cv):
        self.cv = spatial_cv

    def optimize_random_forest(self, model, X, y, coordinates) -> Dict[str, Any]:
        """
        Tune RF parameters using Randomized Search + Spatial CV.
        """
        print("Optimizing Random Forest...")
        
        param_dist = {
            'rf__n_estimators': [100, 200, 300],
            'rf__max_depth': [None, 10, 20, 30],
            'rf__min_samples_split': [10, 20, 50],
            'rf__max_features': ['sqrt', 'log2', 0.5]
        }
        
        # We need to create a custom CV iterator because standard sklearn
        # Cross-validators don't accept 'coordinates' as a third arg to split().
        # So we pre-generate the splits based on coordinates.
        spatial_splits = list(self.cv.split(X, y, coordinates))
        
        search = RandomizedSearchCV(
            model.pipeline, 
            param_distributions=param_dist,
            n_iter=10, 
            scoring='f1',
            cv=spatial_splits,
            n_jobs=-1,
            random_state=42,
            verbose=1
        )
        
        search.fit(X, y)
        print(f"Best RF F1: {search.best_score_:.3f}")
        return search.best_params_

    def optimize_dbscan(self, model_class, coordinates, max_eps_km=2.0) -> Dict[str, Any]:
        """
        Find best EPS for DBSCAN.
        Metric: Silhouette score (how well separated are the clusters?)
        """
        print("Optimizing DBSCAN EPS...")
        
        best_score = -1
        best_eps = 500
        best_min_samples = 3
        
        # Grid Search
        # Try eps from 100m to max_km
        eps_range = np.linspace(100, max_eps_km * 1000, 10)
        
        for eps in eps_range:
            model = model_class(eps_meters=eps, min_samples=3)
            try:
                metrics = model.train(coordinates)
                labels = metrics['labels']
                
                # Check validity
                if metrics['n_clusters'] < 1: continue 
                if metrics['n_clusters'] == len(coordinates): continue # All noise
                
                # Calculate Silhouette (only on non-noise points if possible, or all)
                # Usually calculate on all, treating noise as a 'cluster' or excluding it
                mask = (labels != -1)
                if np.sum(mask) < 3: continue 
                
                score = silhouette_score(coordinates[mask], labels[mask])
                
                if score > best_score:
                    best_score = score
                    best_eps = eps
                    
            except Exception as e:
                continue
                
        print(f"Best DBSCAN EPS: {best_eps:.0f}m (Silhouette: {best_score:.2f})")
        return {'eps_meters': best_eps, 'min_samples': 3}

    def optimize_kde_bandwidth(self, model_class, coordinates) -> Dict[str, Any]:
        """
        Use Silverman's Rule of Thumb for initial bandwidth.
        """
        # A simple heuristic often works better than complex CV for 2D geographic data
        # Bandwidth ~ n^(-1/6) * std_dev
        n = len(coordinates)
        std_lat = np.std(coordinates[:, 0]) * 111000 # meters
        std_lon = np.std(coordinates[:, 1]) * 111000 # roughly
        
        mean_std = (std_lat + std_lon) / 2
        bw = mean_std * (n ** (-1.0/6.0))
        
        print(f"Heuristic KDE Bandwidth: {bw:.0f}m")
        return {'bandwidth_meters': int(bw)}
