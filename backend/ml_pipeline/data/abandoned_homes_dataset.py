"""
Abandoned Homes Dataset
======================

A custom PyTorch Dataset class.
The Dataset class is responsible for fetching a single item from the data source
and preparing it for the model.

Key Responsibilities:
1. Load image from disk (Lazy loading)
2. Apply augmentations/transforms
3. Return (image_tensor, label) pair
"""

import torch
from torch.utils.data import Dataset
import numpy as np
import pandas as pd
from PIL import Image
import os 
from typing import Optional, Callable

class AbandonedHomesDataset(Dataset):
    """
    PyTorch Dataset for loading home images.
    """

    def __init__(self, df: pd.DataFrame, transform: Optional[Callable] = None):
        """
        Args:
            df: DataFrame containing 'image_path' and 'label' columns
            transform: Albumentations composition to apply
        """
        self.df = df
        self.transform = transform
        
        # Validate data
        if 'image_path' not in df.columns or 'label' not in df.columns:
            raise ValueError("DataFrame must contain 'image_path' and 'label'")

    def __len__(self):
        """Returns the total number of samples."""
        return len(self.df)

    def __getitem__(self, idx):
        """
        Retrieves the sample at the given index.
        This is called by the DataLoader during training.
        """
        # 1. Get info from dataframe
        row = self.df.iloc[idx]
        image_path = row['image_path']
        label = row['label']
        
        # 2. Load Image
        try:
            # Open as RGB (handles grayscale or RGBA automatically)
            # We use PIL first, then convert to numpy for Albumentations
            image = np.array(Image.open(image_path).convert('RGB'))
            
        except Exception as e:
            # Robustness: If image fails, print error and return a "black" image
            # In production, you might want to log this or skip the index
            print(f"Error loading image {image_path}: {e}")
            image = np.zeros((224, 224, 3), dtype=np.uint8)
            
        # 3. Apply Transforms (Augmentation)
        if self.transform:
            # Albumentations expects named arguments
            augmented = self.transform(image=image)
            image_tensor = augmented['image']
        else:
            # Fallback (shouldn't happen if using our helper)
            image_tensor = torch.from_numpy(image).permute(2, 0, 1).float() / 255.0
            
        # 4. Return pair
        return image_tensor, torch.tensor(label, dtype=torch.long)

    def get_class_weights(self) -> torch.Tensor:
        """
        Calculate weights for handling class imbalance.
        Formula: weight = total_samples / (n_classes * class_samples)
        
        Example: 100 samples (90 neg, 10 pos)
        - Neg weight: 100 / (2 * 90) = 0.55
        - Pos weight: 100 / (2 * 10) = 5.0  (Errors on Pos count 10x more!)
        """
        counts = self.df['label'].value_counts().sort_index()
        weights = len(self.df) / (len(counts) * counts)
        return torch.tensor(weights.values, dtype=torch.float)
