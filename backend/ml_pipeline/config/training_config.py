"""
Training Configuration Module
============================

This module defines the hyperparameters for training the image classification model.
Hyperparameters are values we set *before* training that control the learning process.

Finding good hyperparameters is an art - it requires experimentation.
These defaults are chosen based on standard transfer learning practices.
"""

from dataclasses import dataclass
import torch

@dataclass
class TrainingConfig:
    """
    Configuration for training the abandoned homes classifier.
    """
    
    # -------------------------------------------------------------------------
    # Model Architecture
    # -------------------------------------------------------------------------
    model_name: str = 'resnet50'
    # Why ResNet50?
    # - ResNet (Residual Networks) solved the "vanishing gradient" problem allowed deep networks
    # - "50" refers to having 50 layers
    # - It's a standard workhorse: good balance of accuracy (76% top-1 on ImageNet) and speed
    # - Options: 'resnet18' (faster), 'efficientnet_b0' (better accuracy/param)
    
    pretrained: bool = True
    # CRITICAL: Always use True for datasets < 1M images
    # - True: Model starts with weights learned from ImageNet (knows edges, textures, shapes)
    # - False: Model starts with random weights (knows nothing)
    
    num_classes: int = 2
    # Classes: 0 (Not Abandoned), 1 (Abandoned)
    
    # -------------------------------------------------------------------------
    # Training Parameters
    # -------------------------------------------------------------------------
    num_epochs: int = 50
    # Epoch: One complete pass through the entire training dataset
    # - Too few: Underfitting (model hasn't learned enough)
    # - Too many: Overfitting (model memorizes training data)
    
    batch_size: int = 32
    # Batch: Subset of data processed at once
    # - 32 is a safe default for most GPUs
    # - Higher (64, 128): Faster, more stable gradients, needs more VRAM
    # - Lower (8, 16): Slower, noisier gradients, works on small GPUs
    
    learning_rate: float = 0.001
    # Learning Rate (LR): How big a step to take during optimization
    # - Too high (>0.01): Training diverges/explodes
    # - Too low (<0.0001): Training is painfully slow
    # - 0.001 is the standard starting point for Adam optimizer
    
    weight_decay: float = 0.0001
    # L2 Regularization: Penalizes large weights
    # - Prevents the model from relying too heavily on any single feature
    # - Helps prevent overfitting
    
    # -------------------------------------------------------------------------
    # Optimization & Scheduling
    # -------------------------------------------------------------------------
    optimizer: str = 'adam'
    # Adam (Adaptive Moment Estimation):
    # - Adapts learning rate for each parameter individually
    # - Generally converges faster than SGD (Stochastic Gradient Descent)
    
    scheduler: str = 'reduce_on_plateau'
    # Strategy: "If you get stuck, slow down"
    # - Reduces learning rate when validation loss stops improving
    
    scheduler_patience: int = 5
    # Wait 5 epochs with no improvement before reducing LR
    
    scheduler_factor: float = 0.5
    # Reduce LR by 50% when triggered
    
    # -------------------------------------------------------------------------
    # Hard Example Mining / Oversampling
    # -------------------------------------------------------------------------
    class_weights: bool = True
    # If we have 90% normal homes and 10% abandoned:
    # - Without weights: Model ignores abandoned homes (90% accuracy by guessing "Normal")
    # - With weights: Errors on "Abandoned" count 9x more
    
    focal_loss: bool = False
    # Advanced: Dynamically weights "hard" examples more than "easy" ones
    
    # -------------------------------------------------------------------------
    # Hardware & Logging
    # -------------------------------------------------------------------------
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    # Training on CPU is 10-50x slower than GPU
    
    num_workers: int = 4
    # Number of CPU processes loading data in parallel
    # - 0: Main process only (slow)
    # - 4: Good default
    # - Too high: CPU overhead slows things down
    
    log_interval: int = 10
    # Print metrics every 10 batches
    
    early_stopping: bool = True
    early_stopping_patience: int = 10
    # Stop if validation loss doesn't improve for 10 epochs
    
    random_seed: int = 42
    # Ensure reproducibility
