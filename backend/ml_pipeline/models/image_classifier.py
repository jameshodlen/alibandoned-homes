"""
Image Classification Model
=========================

This module implements a transfer learning model for identifying abandoned homes.
We use a pre-trained ResNet50 as a "feature extractor" and train a custom
"classification head" for our specific task.

Deep Learning Concepts Explained:
-------------------------------
1. CNN (Convolutional Neural Network): 
   - A type of network designed for images.
   - It uses "filters" that slide over the image to detect features.
   - Layer 1 detects edges/colors. Layer 2 detects textures. Layer 3 objects.

2. Transfer Learning:
   - Training a deep network from scratch needs 100k+ images.
   - Instead, we take a model trained on ImageNet (1.2M images).
   - This model already knows how to "see" (detect edges, shapes).
   - We just teach it what an "abandoned home" looks like using those features.
"""

import torch
import torch.nn as nn
from torchvision import models
import numpy as np
import cv2
from typing import Tuple, Dict, Any

class ImageClassifier(nn.Module):
    """
    Binary classifier for abandoned homes using Transfer Learning.
    """
    
    def __init__(self, model_name: str = 'resnet50', num_classes: int = 2, pretrained: bool = True):
        super(ImageClassifier, self).__init__()
        
        # 1. Load Pre-trained Backbone
        # ---------------------------
        # We assume ResNet50 for this implementation
        # Weights='DEFAULT' downloads the best available ImageNet weights
        weights = models.ResNet50_Weights.DEFAULT if pretrained else None
        self.backbone = models.resnet50(weights=weights)
        
        # 2. Freeze Early Layers
        # ---------------------
        # We don't want to change the feature extraction layers
        # (they are already good at detecting edges/shapes).
        # We only want to train the final decision layers.
        if pretrained:
            for param in self.backbone.parameters():
                param.requires_grad = False
                
        # 3. Create Custom Classification Head
        # -----------------------------------
        # The original ResNet has a last layer for 1000 ImageNet classes.
        # We replace it with our own layers for 2 classes.
        
        # Get number of input features to the last layer (2048 for ResNet50)
        num_features = self.backbone.fc.in_features
        
        self.backbone.fc = nn.Sequential(
            # Layer 1: Compress 2048 features down to 512
            nn.Linear(num_features, 512),
            
            # Activation: ReLU (Rectified Linear Unit)
            # Adds "non-linearity" allowing the model to learn complex patterns
            # Formula: f(x) = max(0, x)
            nn.ReLU(),
            
            # Regularization: Dropout
            # Randomly zeroes out 50% of neurons during training.
            # Prevents the model from memorizing specific training examples (overfitting).
            nn.Dropout(0.5),
            
            # Layer 2: 512 features down to num_classes (2)
            # These are the "logits" (raw scores)
            nn.Linear(512, num_classes)
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward Pass: The journey of an image through the network.
        
        Args:
            x: Input tensor of shape [Batch, Channels, Height, Width]
               e.g. [32, 3, 224, 224]
               
        Returns:
            Logits: Raw prediction scores [Batch, 2]
        """
        # Pass through the ResNet layers (Conv -> BatchNorm -> ReLU -> Pool)
        return self.backbone(x)
        
    def predict(self, x: torch.Tensor) -> Tuple[int, float]:
        """
        Make a prediction for a single image tensor.
        
        Args:
            x: Input tensor [1, 3, 224, 224]
            
        Returns:
            (predicted_class, confidence_score)
        """
        self.eval() # Set to evaluation mode (disable Dropout)
        
        with torch.no_grad(): # Disable gradient calculation (save memory/speed)
            logits = self.forward(x)
            
            # Convert logits to probabilities using Softmax
            # Softmax forces values to sum to 1.0 (e.g. [0.1, 0.9])
            probs = torch.softmax(logits, dim=1)
            
            # Get the class with highest probability
            confidence, predicted_class = torch.max(probs, dim=1)
            
        return predicted_class.item(), confidence.item()

    def explain_prediction(self, x_tensor: torch.Tensor) -> Any:
        """
        Explain WHY the model made a prediction using GradCAM.
        (Placeholder for full implementation in separate module)
        """
        # GradCAM requires hooking into the gradients of the last coord layer
        # This logic is complex and usually handled by a helper class
        pass

    def unfreeze_all_layers(self):
        """
        Fine-tuning strategy: Unfreeze the whole model.
        
        Usually done after training the head for a few epochs.
        Allows the feature extractor to slightly adapt to our specific data
        (e.g. detecting "boarded windows" instead of generic "rectangles").
        """
        for param in self.backbone.parameters():
            param.requires_grad = True
