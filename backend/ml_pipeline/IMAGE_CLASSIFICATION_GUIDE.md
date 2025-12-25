# Image Classification Guide for Abandoned Homes

## Deep Learning Basics

### What is a Neural Network?

A neural network is inspired by the human brain. It consists of layers of "neurons" that process information:

1. **Input Layer**: Receives the image (224x224x3 = 150,528 numbers)
2. **Hidden Layers**: Process the image through learned transformations
3. **Output Layer**: Produces prediction (2 numbers: probability of each class)

### How Does Learning Work?

**Training Loop:**

1. **Forward Pass**: Show image to network → Get prediction
2. **Loss Calculation**: Compare prediction to true label → Calculate error (loss)
3. **Backpropagation**: Calculate gradients (direction of error)
4. **Optimization**: Adjust network weights to reduce error

## 🔍 How CNNs "See"

We use **ResNet50**, a Convolutional Neural Network (CNN).

- **Layer 1 (Conv1)**: Detects simple edges (vertical, horizontal, diagonal).
- **Layer 2 (Conv2)**: Combines edges to detect shapes (circles, squares, corners).
- **Layer 3 (Conv3)**: Detects textures (brick, grass, shingles).
- **Layer 4 (Conv4)**: Detects parts of objects (windows, doors, roofs).
- **Layer 5 (Conv5)**: Detects entire objects (house, tree, car).

> **Transfer Learning**: Since ResNet50 has already seen 1 million images, it already knows how to detect edges and textures. We just retrain the final layers to understand that "broken windows + overgrown grass = abandoned".

## 🛠️ Components Explained

### 1. Data Augmentation (`augmentation.py`)

Since we have few labeled images of abandoned homes, we cheat by creating variations:

- **Flips**: A house flipped left-to-right is still a house.
- **Color Jitter**: Changes hue to simulate different seasons/times of day.
- **Crops**: Forces the model to recognize "abandoned" from just a window or porch.

### 2. The Model (`image_classifier.py`)

```python
self.backbone = models.resnet50(pretrained=True)
# ^ The expert eye (Frozen)

self.head = nn.Linear(512, 2)
# ^ The decision maker (Trainable)
```

### 3. GradCAM (`explainer.py`)

"Why did you think this was abandoned?"
GradCAM looks at the last convolutional layer. If the "broken window" feature map is highly active, and that feature contributed heavily to the "abandoned" prediction, those pixels light up red.

## 📊 Metrics

- **Accuracy**: % Correct. _Warning: If 90% of homes are normal, a model that says "Normal" every time has 90% accuracy but is useless._
- **Precision**: When it says "abandoned", is it right? (Low precision = false alarms).
- **Recall**: Did it find the abandoned homes? (Low recall = we missed dangerous buildings).
- **F1 Score**: The balance between Precision and Recall.

## 🚀 Running Training

```bash
python backend/ml_pipeline/train.py --epochs 50 --batch_size 32
```
