"""
Model Evaluator Module
=====================

This module handles the scientific evaluation of the model.
We can't just trust a single "Accuracy" number. We need deeper insights.

Metrics Explained:
- Precision: "When we say it's abandoned, is it really?" (False Positive avoidance)
- Recall: "Did we find all the abandoned homes?" (False Negative avoidance)
- F1 Score: Harmonic mean of Precision and Recall.
- ROC-AUC: How good is the model at separating the two classes?
"""

import torch
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, roc_curve, precision_recall_curve
)
import json
import os
from typing import Dict, Any, List

class ModelEvaluator:
    """
    Calculates metrics and generates visualizations for model performance.
    """
    
    def evaluate_model(self, model, test_loader, device='cuda') -> Dict[str, Any]:
        """
        Run full evaluation on a test set.
        """
        model.eval()
        y_true = []
        y_pred = []
        y_probs = []
        
        # 1. Collect Predictions
        # ---------------------
        with torch.no_grad():
            for images, labels in test_loader:
                images = images.to(device)
                outputs = model(images) # Logits
                probs = torch.softmax(outputs, dim=1)
                
                _, preds = torch.max(outputs, 1)
                
                y_true.extend(labels.cpu().numpy())
                y_pred.extend(preds.cpu().numpy())
                y_probs.extend(probs.cpu().numpy()[:, 1]) # Prob of class 1 (Abandoned)
                
        # 2. Calculate Metrics
        # -------------------
        metrics = self.calculate_metrics(y_true, y_pred, y_probs)
        
        return metrics

    def calculate_metrics(self, y_true, y_pred, y_probs) -> Dict[str, float]:
        """
        Compute standard classification metrics.
        """
        # Confusion Matrix components
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        
        return {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y_true, y_probs),
            'confusion_matrix': {
                'tn': int(tn), 'fp': int(fp),
                'fn': int(fn), 'tp': int(tp)
            }
        }

    def generate_evaluation_report(self, metrics: Dict, save_path: str):
        """
        Save metrics to a JSON file.
        In a real app, this might generate a PDF or HTML dashboard.
        """
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Determine strictness/bias
        cm = metrics['confusion_matrix']
        total_pos = cm['tp'] + cm['fn']
        total_neg = cm['tn'] + cm['fp']
        
        bias_note = "Model appears balanced."
        if cm['fp'] > cm['fn'] * 2:
            bias_note = "WARNING: High False Positive rate (Model is 'paranoid')."
        elif cm['fn'] > cm['fp'] * 2:
            bias_note = "WARNING: High False Negative rate (Model is missing homes)."
            
        report = {
            'metrics': metrics,
            'analysis': {
                'total_samples': total_pos + total_neg,
                'class_distribution': {
                    'abandoned': total_pos,
                    'normal': total_neg
                },
                'bias_assessment': bias_note
            }
        }
        
        with open(save_path.replace('.pdf', '.json'), 'w') as f:
            json.dump(report, f, indent=4)
            
        print(f"Evaluation report saved to {save_path.replace('.pdf', '.json')}")
