"""
Configuration for knowledge distillation experiments.
"""

# Dataset
DATA_DIR = 'model/data/fire_dataset'
NUM_CLASSES = 2  # fire, normal

# Training hyperparameters
BATCH_SIZE = 32
NUM_EPOCHS_TEACHER = 30  # Train teacher longer for better performance
NUM_EPOCHS_STUDENT = 40  # Student benefits from more distillation epochs
LEARNING_RATE = 0.001

# Teacher model configuration
TEACHER_MODEL = 'efficientnet_b3'  # Options: 'efficientnet_b3', 'efficientnet_b4', 'resnet50'
# Alternative teachers:
# - 'efficientnet_b3': ~12M params, ~48MB, good balance
# - 'efficientnet_b4': ~19M params, ~74MB, more accurate but slower
# - 'resnet50': ~25M params, ~98MB, classic architecture

# Student model configuration  
STUDENT_MODEL = 'efficientnet_lite0'  # Options: 'efficientnet_lite0', 'mobilenetv3_small_100'
# Alternative students:
# - 'efficientnet_lite0': ~4.6M params, ~18MB, optimized for edge
# - 'mobilenetv3_small_100': ~2.5M params, ~10MB, faster but less accurate
# - 'tf_efficientnetv2_b0': ~7M params, newer architecture

# Knowledge distillation hyperparameters
DISTILLATION_ALPHA = 0.3  # Weight for hard loss (cross-entropy with true labels)
# DISTILLATION_ALPHA controls the balance:
# - alpha=0.0: Pure distillation (only learn from teacher)
# - alpha=0.3: Mostly teacher, some true labels (recommended)
# - alpha=0.5: Equal weight
# - alpha=1.0: No distillation (standard training)

DISTILLATION_TEMPERATURE = 4.0  # Temperature for softening predictions
# Temperature controls softness:
# - T=1.0: Sharp probabilities (standard softmax)
# - T=4.0: Soft probabilities (recommended for distillation)
# - T=10.0: Very soft, good for complex teachers
# Higher T makes predictions softer, revealing more about teacher's uncertainty

# Model save paths
TEACHER_CHECKPOINT = 'experiments/knowledge_distillation/models/teacher_best.pth'
STUDENT_DISTILLED_CHECKPOINT = 'experiments/knowledge_distillation/models/student_distilled_best.pth'
STUDENT_BASELINE_CHECKPOINT = 'experiments/knowledge_distillation/models/student_baseline_best.pth'

# Comparison with existing approach
EXISTING_MODEL_CHECKPOINT = 'fire_detection_best.pth'  # Your current EfficientNet-Lite0 (direct training)
