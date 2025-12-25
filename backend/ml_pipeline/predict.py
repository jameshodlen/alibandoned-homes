"""
Inference script for making predictions on new images.

Usage:
    python predict.py --image path/to/image.jpg --model path/to/model.pth
"""

import sys
import os
import argparse
import torch
import numpy as np
from PIL import Image

# Adjust path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.ml_pipeline.models.image_classifier import ImageClassifier
from backend.ml_pipeline.data.augmentation import get_validation_transforms
from backend.ml_pipeline.interpretability.explainer import ModelExplainer

def predict_single_image(image_path, model_path=None, device='cpu'):
    """
    Predict whether an image shows an abandoned home.
    """
    
    # 1. Load Model
    # ------------
    print("Loading model...")
    model = ImageClassifier(pretrained=False) # No need to download ImageNet weights
    
    if model_path:
        checkpoint = torch.load(model_path, map_location=device)
        model.load_state_dict(checkpoint['model_state_dict'])
    else:
        print("WARNING: No model path provided, using random weights (testing only)")
        
    model = model.to(device)
    model.eval()
    
    # 2. Preprocess Image
    # ------------------
    print(f"Processing {image_path}...")
    try:
        raw_image = Image.open(image_path).convert('RGB')
        
        transform = get_validation_transforms()
        augmented = transform(image=np.array(raw_image))
        image_tensor = augmented['image'].unsqueeze(0).to(device) # Add batch dim
        
    except Exception as e:
        print(f"Error loading image: {e}")
        return

    # 3. Predict
    # ----------
    with torch.no_grad():
        pred_idx, confidence = model.predict(image_tensor)
        
    label = "Abandoned" if pred_idx == 1 else "Normal"
    print(f"\nResult: {label.upper()}")
    print(f"Confidence: {confidence:.2%}")
    
    # 4. Explain
    # ----------
    try:
        print("\nGenerating GradCAM explanation...")
        explainer = ModelExplainer()
        explanation_img = explainer.gradcam_visualization(model, image_tensor)
        
        save_path = image_path + "_gradcam.png"
        explanation_img.save(save_path)
        print(f"Explanation saved to {save_path}")
    except Exception as e:
        print(f"GradCAM failed: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=str, required=True)
    parser.add_argument('--model', type=str)
    args = parser.parse_args()
    
    predict_single_image(args.image, args.model)
