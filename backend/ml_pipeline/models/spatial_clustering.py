"""
Spatial Clustering Predictor (DBSCAN)
====================================

This component predicts abandonment based purely on proximity to known clusters.
It is the "Neighborhood Expert" in our ensemble.

Algorithm Explained:
------------------
DBSCAN (Density-Based Spatial Clustering of Applications with Noise).
Unlike K-Means, it doesn't need to know the number of clusters (K) in advance.
It groups points that are close together and marks isolated points as "Noise".

Logic: "Birds of a feather flock together."
Abandoned homes rarely happen in isolation; they cluster in distressed neighborhoods.
If a location is near an existing cluster of abandoned homes, it's high risk.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Tuple

class SpatialClusteringPredictor:
    """
    DBSCAN-based spatial clustering for location risk assessment.
    """
    
    def __init__(self, eps_meters: float = 500, min_samples: int = 3):
        """
        Args:
            eps_meters: Max distance to be considered a "neighbor". 
                       500m is roughly a neighborhood scale.
            min_samples: Min points to form a dense region (Core Point).
        """
        self.eps_meters = eps_meters
        self.min_samples = min_samples
        
        # Earth radius in meters (for Haversine metric conversion)
        self.EARTH_RADIUS_METERS = 6371000.0
        
        # Convert eps to radians (required for sklearn haversine)
        self.eps_radians = self.eps_meters / self.EARTH_RADIUS_METERS
        
        self.dbscan = DBSCAN(
            eps=self.eps_radians, 
            min_samples=min_samples, 
            metric='haversine',
            algorithm='ball_tree'
        )
        
        self.cluster_centroids = None
        self.cluster_sizes = None

    def train(self, coordinates_array: np.ndarray) -> Dict[str, Any]:
        """
        Fit clusters to known abandoned locations.
        
        Args:
            coordinates_array: [[lat, lon], [lat, lon], ...] (Degrees)
        """
        # Convert to Radians for Haversine
        coords_rad = np.radians(coordinates_array)
        
        # Fit
        self.labels = self.dbscan.fit_predict(coords_rad)
        
        # Analyze Clusters
        # Label -1 is Noise (scattered homes)
        unique_labels = set(self.labels)
        n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
        n_noise = list(self.labels).count(-1)
        
        # Calculate centroids (mean lat/lon of each cluster)
        self.cluster_centroids = []
        self.cluster_sizes = []
        
        for k in unique_labels:
            if k == -1: continue # Skip noise
            
            # Get points in this cluster
            cluster_mask = (self.labels == k)
            cluster_points = coordinates_array[cluster_mask]
            
            # Centroid
            centroid = np.mean(cluster_points, axis=0)
            self.cluster_centroids.append(centroid)
            self.cluster_sizes.append(len(cluster_points))
            
        self.cluster_centroids = np.array(self.cluster_centroids)
        
        return {
            'n_clusters': n_clusters,
            'n_noise': n_noise,
            'noise_ratio': n_noise / len(self.labels),
            'labels': self.labels
        }

    def predict_proba(self, coordinates_array: np.ndarray) -> np.ndarray:
        """
        Predict probability based on distance to nearest cluster.
        
        Logic: Exponential decay.
        P = exp(-distance / decay_rate)
        
        Args:
            coordinates_array: [[lat, lon], ...] (Degrees)
        """
        if self.cluster_centroids is None or len(self.cluster_centroids) == 0:
            # If no clusters found, return zeroes (or base rate)
            return np.zeros(len(coordinates_array))
            
        # Convert query points to radians
        query_rad = np.radians(coordinates_array)
        centroids_rad = np.radians(self.cluster_centroids)
        
        # Use NearestNeighbors to find closest cluster center quickly
        nn = NearestNeighbors(n_neighbors=1, metric='haversine')
        nn.fit(centroids_rad)
        
        distances_rad, indices = nn.kneighbors(query_rad)
        
        # Convert back to meters
        distances_meters = distances_rad * self.EARTH_RADIUS_METERS
        distances_meters = distances_meters.flatten()
        
        # Calculate probability logic
        # 0m -> 1.0 probability
        # 500m (eps) -> 0.5 probability (arbitrary choice for decay)
        # Decay constant lambda: 0.5 = exp(-500 * lambda) => lambda ~ 0.00138
        decay_const = np.log(2) / self.eps_meters
        
        probs = np.exp(-distances_meters * decay_const)
        
        # Optional: Boost probability if nearest cluster is HUGE?
        # For now, keep it simple based on distance.
        
        return probs

    def visualize_clusters(self, coordinates: np.ndarray, labels: np.ndarray):
        """Generates a quick matplotlib plot of the clusters."""
        plt.figure(figsize=(10, 8))
        
        # Plot noise
        noise_mask = (labels == -1)
        plt.scatter(coordinates[noise_mask, 1], coordinates[noise_mask, 0], 
                   c='gray', s=10, label='Noise (Isolated)')
        
        # Plot clusters
        unique_labels = set(labels)
        colors = plt.cm.rainbow(np.linspace(0, 1, len(unique_labels)))
        
        for k, col in zip(unique_labels, colors):
            if k == -1: continue
            
            mask = (labels == k)
            plt.scatter(coordinates[mask, 1], coordinates[mask, 0], 
                       c=[col], s=20, label=f'Cluster {k}')
                       
        plt.title(f'DBSCAN Spatial Clusters (eps={self.eps_meters}m)')
        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        return plt
