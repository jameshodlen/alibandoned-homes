"""
Augmentation Module
==================

Data Augmentation is the trick to making Deep Learning work with small datasets.
By artificially modifying our training images (rotating, zooming, changing colors),
we teach the model to key on the *structural* features of abandoned homes,
rather than memorizing exact pixel values.

We use `albumentations` library because it's fast and easy to compose.
"""

import albumentations as A
from albumentations.pytorch import ToTensorV2

def get_training_transforms(image_size: int = 224):
    """
    Transforms applied to TRAINING data.
    Random variations to create new "fake" examples.
    """
    return A.Compose([
        # 1. Geometric transforms (Position/Shape)
        # ---------------------------------------
        # Resize larger to allow for random cropping
        A.Resize(int(image_size * 1.15), int(image_size * 1.15)),
        
        # Random Crop: Forces model to look at parts, not just whole
        A.RandomCrop(height=image_size, width=image_size),
        
        # Flips: A house is still a house if flipped left-right
        A.HorizontalFlip(p=0.5),
        
        # Rotation: Simulates imperfect camera leveling
        A.Rotate(limit=15, p=0.5),
        
        # 2. Color/Lighting transforms (Appearance)
        # ----------------------------------------
        # Brightness: Simulate sunny vs overcast days
        A.RandomBrightnessContrast(p=0.2),
        
        # Hue/Sat: Simulate different cameras/seasons
        A.HueSaturationValue(hue_shift_limit=10, sat_shift_limit=20, p=0.2),
        
        # Shadows: Abandoned homes often have trees/debris casting shadows
        A.RandomShadow(p=0.1),
        
        # 3. Quality transforms (Noise)
        # ----------------------------
        # Blur: Simulate out-of-focus or motion blur
        A.GaussianBlur(blur_limit=(3, 5), p=0.1),
        
        # 4. Normalization (CRITICAL)
        # ---------------------------
        # Neural networks like small inputs centered around 0.
        # We subtract mean and divide by std deviation using ImageNet stats.
        A.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ),
        
        # Convert numpy array to PyTorch Tensor
        ToTensorV2()
    ])

def get_validation_transforms(image_size: int = 224):
    """
    Transforms applied to VALIDATION/TEST data.
    NO randomness! We want deterministic evaluation.
    """
    return A.Compose([
        # Deterministic resize (no random crop)
        A.Resize(image_size, image_size),
        
        # Same normalization as training
        A.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ),
        
        ToTensorV2()
    ])
