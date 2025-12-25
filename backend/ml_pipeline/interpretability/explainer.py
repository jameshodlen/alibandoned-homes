"""
Model Interpretability Module (Explainable AI)
=============================================

Deep Learning models are often called "Black Boxes".
This module helps us peer inside to see WHY the model made a decision.

Techniques:
- GradCAM (Gradient-weighted Class Activation Mapping):
  Uses the gradients flowing into the final convolutional layer to highlight
  which parts of the image were "activated" by the target class.
"""

import torch
import torch.nn.functional as F
import numpy as np
import cv2
from PIL import Image

class ModelExplainer:
    """
    Tools for visualizing model attention and importance.
    """

    def gradcam_visualization(self, model, image_tensor, target_class=None):
        """
        Generate a GradCAM heatmap.
        
        Result: A heatmap (red=high importance, blue=low) overlaid on the image.
        """
        # Hook into the final convolutional layer
        # For ResNet, this is usually model.backbone.layer4
        target_layer = model.backbone.layer4[-1]
        
        gradients = []
        activations = []
        
        def backward_hook(module, grad_input, grad_output):
            gradients.append(grad_output[0])
            
        def forward_hook(module, input, output):
            activations.append(output)
            
        # Register hooks
        handle_b = target_layer.register_backward_hook(backward_hook)
        handle_f = target_layer.register_forward_hook(forward_hook)
        
        # Forward pass
        model.eval()
        model.zero_grad()
        output = model(image_tensor)
        
        if target_class is None:
            target_class = output.argmax(dim=1).item()
            
        # Backward pass (force gradient calc even in eval mode if needed for this trick)
        score = output[:, target_class]
        score.backward()
        
        # Get gradients and activations
        # Gradients: [1, 2048, 7, 7] -> How much output changes if feature changes
        # Activations: [1, 2048, 7, 7] -> The feature map values themselves
        grads = gradients[0].cpu().data.numpy()[0]
        fmap = activations[0].cpu().data.numpy()[0]
        
        # Global Average Pooling of gradients (Importance weights)
        weights = np.mean(grads, axis=(1, 2)) # [2048]
        
        # Weighted combination of feature maps
        cam = np.zeros(fmap.shape[1:], dtype=np.float32) # [7, 7]
        for i, w in enumerate(weights):
            cam += w * fmap[i, :, :]
            
        # ReLU: We only care about positive influence
        cam = np.maximum(cam, 0)
        
        # Resize to image size (224x224)
        cam = cv2.resize(cam, (image_tensor.shape[3], image_tensor.shape[2]))
        
        # Normalize to 0-1
        cam = cam - np.min(cam)
        cam = cam / np.max(cam)
        
        # Cleanup hooks
        handle_b.remove()
        handle_f.remove()
        
        # Convert to heatmap visualization
        heatmap = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
        heatmap = np.float32(heatmap) / 255
        
        # Reverse image preprocessing for visualization (approx)
        img = image_tensor.cpu().numpy()[0].transpose(1, 2, 0)
        img = (img - np.min(img)) / (np.max(img) - np.min(img))
        
        # Overlay
        cam_img = heatmap + np.float32(img)
        cam_img = cam_img / np.max(cam_img)
        
        return Image.fromarray(np.uint8(255 * cam_img))
