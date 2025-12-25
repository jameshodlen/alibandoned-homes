# Location Prediction System Guide

## Overview

This system predicts where abandoned homes are likely to exist using an ensemble of machine learning models. It combines three distinct "experts":

1.  **Random Forest (The Feature Expert)**: Looks at demographics and infrastructure.
2.  **DBSCAN (The Neighborhood Expert)**: Looks for clusters of existing abandonment.
3.  **KDE (The Hotspot Expert)**: Looks for density gradients.

## 🧠 How It Works

### The Ensemble Logic

No single model is perfect.

- **Random Forest** understands that _"Low Income + High Vacancy = Risk"_, but it doesn't know that the house next door is abandoned.
- **DBSCAN** knows that abandonment is contagious (spatial clustering), but ignores the fact that a new highway was just built.
- **KDE** smooths out the predictions to create "Heatmaps" rather than just dots.

We combine them using a **Weighted Average**:
$$ P*{final} = w*{rf} \cdot P*{rf} + w*{spatial} \cdot P*{spatial} + w*{kde} \cdot P\_{kde} $$

The weights ($w$) are not guessed; they are mathematically optimized to maximize performance on validaton data.

## 🔬 Scientific Validation (Spatial CV)

**The Problem**: "Cheating" with Space.
If you split data randomly, a Training house might be 10 meters from a Test house. They share the exact same environment. The model will just "memorize" the neighbor. This leads to 99% accuracy in testing but 50% in the real world.

**The Solution**: Spatial Blocking with Buffers.
We divide the city into zones.

- **Train** on Zone A, B, C.
- **Test** on Zone D.
- **CRITICAL**: We delete a 2km "Buffer Zone" around Zone D from the training set. This ensures the model has never seen _anything_ near the test data.

## 📊 Interpretation

### SHAP Analysis

We use SHAP (Shapley Additive Explanations) to explain _why_ a specific location was flagged.

- **Waterfall Plot**: Shows how each feature pushed the probability up or down from the baseline.

### Probability Scale

- **0.0 - 0.3**: Low Risk (Stable neighborhood)
- **0.3 - 0.6**: Watchlist (Signs of distress, e.g., declining ownership)
- **0.6 - 1.0**: High Risk (Field verification recommended)

## 🛠️ Usage

### Training

```bash
# Train on confirmed locations in DB
python backend/ml_pipeline/train_location_predictor.py
```

### Area Search

```bash
# Generate heatmap for Detroit area
python backend/ml_pipeline/predict_area.py --center 42.3314,-83.0458 --radius 5
```

Output: `predictions_42.3314_-83.0458.html` (Open in Browser)

## 🔧 Tuning

- **Random Forest**: Increase `n_estimators` for stability.
- **DBSCAN**: Adjust `eps` (epsilon) based on density. 500m for cities, 2km for rural.
- **KDE**: Adjust `bandwidth`. Small = Spiky hotspots, Large = Smooth gradients.
