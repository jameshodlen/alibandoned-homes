"""
Complete training script for abandoned homes image classifier.

Run this to train a new model from scratch or fine-tune an existing one.
Example: python train.py --epochs 10 --batch_size 16
"""

import sys
import os
import argparse
import torch
import pandas as pd
from sklearn.model_selection import train_test_split

# Adjust path to find backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.ml_pipeline.models.image_classifier import ImageClassifier
from backend.ml_pipeline.data.abandoned_homes_dataset import AbandonedHomesDataset
from backend.ml_pipeline.data.augmentation import get_training_transforms, get_validation_transforms
from backend.ml_pipeline.training.trainer import AbandonedHomesTrainer
from backend.ml_pipeline.config.training_config import TrainingConfig
from backend.ml_pipeline.evaluation.evaluator import ModelEvaluator

def main(args):
    # 1. Configuration
    config = TrainingConfig()
    if args.epochs: config.num_epochs = args.epochs
    if args.batch_size: config.batch_size = args.batch_size
    
    print(f"Starting training: {config.model_name}, {config.num_epochs} epochs")
    
    # 2. Mock Data Generation (For Demonstration/Portability)
    # In production, query the database: session.query(Photo).all()
    print("Generating mock dataset for demonstration...")
    data = []
    # Create fake "files" if they don't exist
    os.makedirs('mock_data/abandoned', exist_ok=True)
    os.makedirs('mock_data/normal', exist_ok=True)
    
    from PIL import Image
    import numpy as np
    
    # We create dummy images so the script actually runs
    for i in range(50):
        # Abandoned (Label 1)
        path = f'mock_data/abandoned/img_{i}.jpg'
        if not os.path.exists(path):
            img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
            img.save(path)
        data.append({'image_path': path, 'label': 1, 'location_id': f'loc_a_{i}'})
        
        # Normal (Label 0)
        path = f'mock_data/normal/img_{i}.jpg'
        if not os.path.exists(path):
             img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
             img.save(path)
        data.append({'image_path': path, 'label': 0, 'location_id': f'loc_n_{i}'})
            
    df = pd.DataFrame(data)
    
    # 3. Data Splits
    train_df, val_df = train_test_split(df, test_size=0.2, stratify=df['label'])
    
    # 4. Datasets & Loaders
    train_dataset = AbandonedHomesDataset(train_df, transform=get_training_transforms())
    val_dataset = AbandonedHomesDataset(val_df, transform=get_validation_transforms())
    
    train_loader = torch.utils.data.DataLoader(
        train_dataset, batch_size=config.batch_size, shuffle=True
    )
    val_loader = torch.utils.data.DataLoader(
        val_dataset, batch_size=config.batch_size, shuffle=False
    )
    
    # 5. Model
    model = ImageClassifier(
        model_name=config.model_name,
        num_classes=config.num_classes,
        pretrained=config.pretrained
    )
    model = model.to(config.device)
    
    # 6. Train
    trainer = AbandonedHomesTrainer(model, train_loader, val_loader, config)
    trainer.train()
    
    # 7. Evaluate
    evaluator = ModelEvaluator()
    metrics = evaluator.evaluate_model(model, val_loader, device=config.device)
    
    print("\nFinal Metrics:")
    print(metrics)
    
    evaluator.generate_evaluation_report(metrics, 'reports/final_eval.json')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--epochs', type=int)
    parser.add_argument('--batch_size', type=int)
    args = parser.parse_args()
    
    main(args)
