"""
Training Loop Module
===================

This module orchestrates the actual training process.
It mirrors the "Study -> Test -> Adjust" loop of human learning.

Concepts:
- Epoch: One full pass through books.
- Batch: Studying one chapter at a time.
- Loss: Quiz score (how wrong were we?).
- Optimizer: Brain adjusting connections based on quiz score.
"""

import torch
import torch.nn as nn
from tqdm import tqdm
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class AbandonedHomesTrainer:
    """
    Manages the training, validation, and checkpointing of the model.
    """
    
    def __init__(self, model, train_loader, val_loader, config):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.config = config
        self.device = config.device
        
        # 1. Setup Loss Function
        # ---------------------
        # CrossEntropyLoss is standard for classification.
        # It combines Softmax (probs) + LogLikelihood (error).
        if config.class_weights:
            # If classes are imbalanced, we tell the loss to penalize 
            # errors on the minority class more heavily.
            # (Assuming weights calculated externally and passed in config - placeholder here)
            # weights = ... 
            # self.criterion = nn.CrossEntropyLoss(weight=weights)
            self.criterion = nn.CrossEntropyLoss() # Default for now
        else:
            self.criterion = nn.CrossEntropyLoss()
            
        # 2. Setup Optimizer
        # -----------------
        # Adam: Good general purpose optimizer
        self.optimizer = torch.optim.Adam(
            model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay
        )
        
        # 3. Setup Scheduler
        # -----------------
        # Reduce LR if validation loss stops decreasing
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=config.scheduler_factor,
            patience=config.scheduler_patience,
            verbose=True
        )

    def train_epoch(self, epoch_idx):
        """
        Run one epoch of training.
        """
        self.model.train() # Enable Dropout and BatchNorm updates
        running_loss = 0.0
        correct_preds = 0
        total_preds = 0
        
        pbar = tqdm(self.train_loader, desc=f"Epoch {epoch_idx}/{self.config.num_epochs}")
        
        for images, labels in pbar:
            images, labels = images.to(self.device), labels.to(self.device)
            
            # A. Zero Gradients
            # Clears old gradients from previous step.
            # If we didn't do this, gradients would accumulate (mix old and new).
            self.optimizer.zero_grad()
            
            # B. Forward Pass
            # Push images through the network -> Get predictions
            outputs = self.model(images)
            
            # C. Calculate Loss
            # Compare predictions to actual labels
            loss = self.criterion(outputs, labels)
            
            # D. Backward Pass (Backpropagation)
            # Calculate how much each weight contributed to the error
            loss.backward()
            
            # E. Optimizer Step
            # Nudge weights in the opposite direction of the gradient
            self.optimizer.step()
            
            # Stats tracking
            running_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total_preds += labels.size(0)
            correct_preds += (predicted == labels).sum().item()
            
            pbar.set_postfix({'loss': running_loss / (total_preds / self.config.batch_size)})
            
        epoch_loss = running_loss / len(self.train_loader)
        epoch_acc = correct_preds / total_preds
        
        return epoch_loss, epoch_acc

    def validate(self):
        """
        Run validation on unseen data.
        """
        self.model.eval() # Disable Dropout
        running_loss = 0.0
        correct_preds = 0
        total_preds = 0
        
        # Turn off gradient calc to save memory/speed
        with torch.no_grad():
            for images, labels in self.val_loader:
                images, labels = images.to(self.device), labels.to(self.device)
                outputs = self.model(images)
                loss = self.criterion(outputs, labels)
                
                running_loss += loss.item()
                _, predicted = torch.max(outputs.data, 1)
                total_preds += labels.size(0)
                correct_preds += (predicted == labels).sum().item()
                
        val_loss = running_loss / len(self.val_loader)
        val_acc = correct_preds / total_preds
        return val_loss, val_acc

    def save_checkpoint(self, path: str, epoch: int, metrics: dict):
        """
        Save the model to disk.
        We save a dictionary so we can resume training later.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'loss': metrics['loss'],
            'config': self.config
        }, path)
        logger.info(f"Model saved to {path}")

    def train(self):
        """
        Main training loop.
        """
        best_val_loss = float('inf')
        
        print(f"Starting training on {self.device}...")
        
        for epoch in range(1, self.config.num_epochs + 1):
            # 1. Train
            train_loss, train_acc = self.train_epoch(epoch)
            
            # 2. Validate
            val_loss, val_acc = self.validate()
            
            # 3. Update Learning Rate
            self.scheduler.step(val_loss)
            
            print(f"Ep {epoch}: Train Loss {train_loss:.4f} Acc {train_acc:.2%} | Val Loss {val_loss:.4f} Acc {val_acc:.2%}")
            
            # 4. Save Best Model
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                self.save_checkpoint(
                    f"models/checkpoints/best_model_{timestamp}.pth", 
                    epoch, 
                    {'loss': val_loss}
                )
