"""
Tests for Image Classification System
====================================

Verifies the neural network components, data pipeline, and training loop.
"""

import pytest
import torch
import numpy as np
import os
import shutil
from backend.ml_pipeline.models.image_classifier import ImageClassifier
from backend.ml_pipeline.config.training_config import TrainingConfig
from backend.ml_pipeline.data.abandoned_homes_dataset import AbandonedHomesDataset
from backend.ml_pipeline.data.augmentation import get_training_transforms

@pytest.fixture
def mock_image_tensor():
    # Batch of 2 RGB images: [2, 3, 224, 224]
    return torch.randn(2, 3, 224, 224)

@pytest.fixture
def config():
    return TrainingConfig(
        num_epochs=1,
        batch_size=2,
        pretrained=False # Speed up tests
    )

def test_model_initialization():
    """Verify model loads and replaces head correctly."""
    model = ImageClassifier(pretrained=False, num_classes=2)
    
    # Check if head is replaced
    # ResNet fc input is 2048. Our Sequential starts with Linear(2048, 512).
    first_layer = model.backbone.fc[0]
    assert isinstance(first_layer, torch.nn.Linear)
    assert first_layer.in_features == 2048
    assert first_layer.out_features == 512

def test_forward_pass(mock_image_tensor):
    """Verify data can flow through the model."""
    model = ImageClassifier(pretrained=False)
    model.eval()
    
    with torch.no_grad():
        output = model(mock_image_tensor)
        
    # Output should be [Batch Size, Num Classes]
    assert output.shape == (2, 2)
    # Probabilities should sum to 1 (conceptually - logits don't, but softmax does)

def test_dataset_loading(tmp_path):
    """Verify dataset handles images correctly."""
    # 1. Create dummy image
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    img_path = img_dir / "test.jpg"
    
    from PIL import Image
    Image.new('RGB', (100, 100)).save(img_path)
    
    # 2. Create DataFrame
    import pandas as pd
    df = pd.DataFrame([{'image_path': str(img_path), 'label': 1}])
    
    # 3. Test Dataset
    dataset = AbandonedHomesDataset(df, transform=get_training_transforms())
    img_tensor, label = dataset[0]
    
    assert img_tensor.shape == (3, 224, 224) # Should be resized
    assert label == 1
    assert isinstance(img_tensor, torch.Tensor)

def test_config_defaults():
    """Verify configuration defaults are sane."""
    cfg = TrainingConfig()
    assert cfg.learning_rate == 0.001
    assert cfg.batch_size == 32
    assert cfg.model_name == 'resnet50'

def test_model_prediction_shape():
    """Test the predict method wrapper."""
    model = ImageClassifier(pretrained=False)
    # Single image batch [1, 3, 224, 224]
    x = torch.randn(1, 3, 224, 224)
    
    cls, conf = model.predict(x)
    assert isinstance(cls, int)
    assert isinstance(conf, float)
    assert 0 <= conf <= 1.0
