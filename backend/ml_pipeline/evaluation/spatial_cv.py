"""
Spatial Cross-Validation
=======================

Standard Cross-Validation (random split) is dangerous for spatial data.
If you have a home at A and a neighbor at B (10 meters away), and you put A in 
Train and B in Test, the model just "memorizes" the location. This is Data Leakage.

Solution: Spatial Blocking with Buffering.
1. Divide the world into spatial blocks (using K-Means on coordinates).
2. For each fold, take one block as Test.
3. CRITICAL: Remove all training points within X km of the Test block (Buffer).
4. Train on the remaining "safe" points.
"""

import numpy as np
from sklearn.cluster import KMeans
from sklearn.neighbors import BallTree
import matplotlib.pyplot as plt
from typing import Iterator, Tuple, List

class SpatialCrossValidator:
    """
    Generates spatially separated train/test splits with safety buffers.
    """
    
    def __init__(self, n_splits: int = 5, buffer_distance_km: float = 2.0):
        """
        Args:
            n_splits: Number of geographic folds.
            buffer_distance_km: Safety zone size. Points within this distance 
                               of the test set are REMOVED from training.
        """
        self.n_splits = n_splits
        self.buffer_rad = buffer_distance_km / 6371.0 # Earth radius km
        
    def split(self, X, y, coordinates: np.ndarray) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """
        Yields (train_indices, test_indices).
        
        Args:
            coordinates: [[lat, lon], ...] in Degrees.
        """
        # 1. Create Spatial Clusters (Blocks)
        # We use KMeans on coordinates to create rough geographic zones
        kmeans = KMeans(n_clusters=self.n_splits, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(coordinates)
        
        # Convert to radians for distance calculations
        coords_rad = np.radians(coordinates)
        
        # 2. Iterate through folds
        for fold_id in range(self.n_splits):
            # TEST SET: All points in the current cluster
            test_mask = (cluster_labels == fold_id)
            test_indices = np.where(test_mask)[0]
            
            # POTENTIAL TRAIN SET: All other points
            potential_train_indices = np.where(~test_mask)[0]
            
            # 3. Apply Buffer (Remove train points too close to test points)
            if len(test_indices) == 0:
                yield potential_train_indices, test_indices
                continue
                
            # Build search tree of Train points
            train_coords_rad = coords_rad[potential_train_indices]
            test_coords_rad = coords_rad[test_indices]
            
            # We want to find Train points that are neighbors of Test points
            tree = BallTree(test_coords_rad, metric='haversine')
            
            # Query: For each train point, is it within buffer of ANY test point?
            # query_radius returns indices of neighbors. 
            # We query from Train to Test (or vice versa). 
            # Efficient way: count neighbors within radius. If > 0, exclude.
            
            # Let's switch: Build tree of TEST points. Ask for each TRAIN point: "Am I close to a test point?"
            indices_with_neighbors = tree.query_radius(train_coords_rad, r=self.buffer_rad)
            
            # indices_with_neighbors is array of arrays. 
            # If len > 0, it means this train point is close to a test point.
            is_too_close = np.array([len(x) > 0 for x in indices_with_neighbors])
            
            # Final Train Set: Potential Train points NOT in buffer
            final_train_indices = potential_train_indices[~is_too_close]
            
            # Statistics
            n_removed = np.sum(is_too_close)
            # print(f"Fold {fold_id}: Removed {n_removed} points via buffer.")
            
            yield final_train_indices, test_indices

    def visualize_splits(self, coordinates, splits):
        """Generates plots of the folds for verification."""
        fig, axes = plt.subplots(1, self.n_splits, figsize=(20, 4))
        
        for i, (train_idx, test_idx) in enumerate(splits):
            ax = axes[i]
            
            # Plot all points as gray (buffer zone)
            ax.scatter(coordinates[:, 1], coordinates[:, 0], c='lightgray', s=10, label='Buffer')
            
            # Plot Train
            ax.scatter(coordinates[train_idx, 1], coordinates[train_idx, 0], c='blue', s=10, label='Train')
            
            # Plot Test
            ax.scatter(coordinates[test_idx, 1], coordinates[test_idx, 0], c='red', s=20, label='Test')
            
            ax.set_title(f"Fold {i+1}")
            if i == 0: ax.legend()
            ax.axis('off')
            
        return plt
