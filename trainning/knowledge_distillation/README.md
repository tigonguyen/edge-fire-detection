# Knowledge Distillation Experiment

This experiment explores whether **knowledge distillation** can produce a better lightweight model than direct training.

## 🎯 Goal

Compare two approaches for training lightweight models:
1. **Direct Training** (Baseline): Fine-tune EfficientNet-B0 directly on fire detection
2. **Knowledge Distillation**: Train a heavy teacher model, then distill to a lightweight student

## 📚 What is Knowledge Distillation?

Knowledge distillation is a technique where a smaller "student" model learns from a larger "teacher" model.

### Key Concepts

**Hard Labels** (Traditional):
- Ground truth: Fire=1, Normal=0
- Binary classification: Just the final answer

**Soft Labels** (Distillation):
- Teacher's predictions: Fire=0.92, Normal=0.08
- Rich information: Confidence, uncertainty, decision boundaries
- Student learns "this image is mostly fire, but has some normal features"

**Temperature Scaling**:
- T=1: Sharp probabilities (standard softmax)
- T>1: Soft probabilities revealing uncertainty
- Example: [0.99, 0.01] at T=1 → [0.75, 0.25] at T=4

**Combined Loss**:
```
Total Loss = α × Hard Loss + (1-α) × Soft Loss

Hard Loss: Student vs Ground Truth (Cross-Entropy)
Soft Loss: Student vs Teacher (KL Divergence)
```

### Why It Works

1. **Teacher encodes knowledge**: Heavy model learns nuanced patterns
2. **Soft targets transfer knowledge**: Student learns decision boundaries, not just classifications
3. **Better generalization**: Student understands "fire-like" features, not just memorization

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Train Heavy Teacher                                │
│                                                              │
│  Fire/Normal Dataset                                         │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                        │
│  │  EfficientNet-B3 │  ← Heavy Model (12M params, 48 MB)    │
│  │     (Teacher)    │  ← Learn rich features                │
│  └──────────────────┘                                        │
│         │                                                    │
│         ▼                                                    │
│    Save teacher_best.pth                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Distill to Lightweight Student                     │
│                                                              │
│  Fire/Normal Dataset                                         │
│         │                                                    │
│         ├─────────────────────────────────┐                 │
│         │                                 │                 │
│         ▼                                 ▼                 │
│  ┌──────────────────┐            ┌──────────────────┐      │
│  │  EfficientNet-B3 │  Frozen    │ EfficientNet-    │      │
│  │     (Teacher)    │ ─────────► │     Lite0        │      │
│  └──────────────────┘  Soft      │   (Student)      │      │
│                       Targets     └──────────────────┘      │
│                                           │                 │
│                        Hard Labels ───────┘                 │
│                                           │                 │
│                                           ▼                 │
│                           Combined Distillation Loss        │
│                                           │                 │
│                                           ▼                 │
│                              Save student_distilled_best.pth │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Files

- **`config.py`**: Hyperparameters for teacher, student, and distillation
- **`train_teacher.py`**: Train heavy teacher model (EfficientNet-B3/B4)
- **`train_student_distillation.py`**: Train student with knowledge distillation
- **`compare_models.py`**: Compare all approaches (baseline, teacher, student)
- **`models/`**: Saved checkpoints

## 🚀 Quick Start

### Step 1: Train Teacher Model

Train a heavy model to learn rich fire detection features:

```bash
cd /Users/tigonguyen/Documents/DevOps/repos/personal-projects/edge-fire-detection

# Train teacher (EfficientNet-B3 by default)
python experiments/knowledge_distillation/train_teacher.py
```

This will:
- Train for 30 epochs (configurable in `config.py`)
- Save best model to `models/teacher_best.pth`
- Take ~30-45 minutes on GPU

### Step 2: Train Student with Distillation

Use teacher to train lightweight student:

```bash
# Train student with knowledge distillation
python experiments/knowledge_distillation/train_student_distillation.py
```

This will:
- Load frozen teacher model
- Train student for 40 epochs with combined loss
- Save best model to `models/student_distilled_best.pth`
- Take ~25-35 minutes on GPU

### Step 3: Compare Results

Compare all approaches:

```bash
# Compare baseline vs teacher vs student (distilled)
python experiments/knowledge_distillation/compare_models.py
```

This shows:
- Accuracy comparison
- Model size comparison
- Inference speed comparison
- Per-class accuracy
- Recommendations

## ⚙️ Configuration

Edit `config.py` to customize:

### Teacher Model Options

```python
TEACHER_MODEL = 'efficientnet_b3'  # Options:
# - 'efficientnet_b3': 12M params, 48 MB (recommended)
# - 'efficientnet_b4': 19M params, 74 MB (more accurate, slower)
# - 'resnet50': 25M params, 98 MB (classic architecture)
```

### Student Model Options

```python
STUDENT_MODEL = 'efficientnet_lite0'  # Options:
# - 'efficientnet_lite0': 4.6M params, 18 MB (recommended for ESP32)
# - 'mobilenetv3_small_100': 2.5M params, 10 MB (faster, less accurate)
```

### Distillation Hyperparameters

```python
# Loss weighting
DISTILLATION_ALPHA = 0.3  # 0.3 = 30% hard labels, 70% soft labels
# Try: 0.1-0.5 (lower = more distillation)

# Temperature
DISTILLATION_TEMPERATURE = 4.0  # Higher = softer predictions
# Try: 2.0-10.0 (higher for complex teachers)

# Training epochs
NUM_EPOCHS_TEACHER = 30   # Train teacher well
NUM_EPOCHS_STUDENT = 40   # Student benefits from more epochs
```

## 📊 Expected Results

### Scenario 1: Distillation Succeeds ✅

```
Model                              Size      Accuracy   Latency
Baseline (EfficientNet-B0)        20 MB      93.5%     25 ms
Teacher (EfficientNet-B3)         48 MB      95.2%     60 ms
Student Distilled (Lite0)         18 MB      94.8%     22 ms  ← Best!
```

**Why use distilled student?**
- Better accuracy than baseline (94.8% vs 93.5%)
- Similar size and speed to baseline
- Learned from teacher's rich features

### Scenario 2: Marginal Improvement ⚖️

```
Model                              Size      Accuracy   Latency
Baseline (EfficientNet-B0)        20 MB      93.5%     25 ms
Student Distilled (Lite0)         18 MB      93.7%     22 ms
```

**Decision**: Use whichever is smaller/faster

### Scenario 3: Distillation Underperforms ⚠️

```
Model                              Size      Accuracy   Latency
Baseline (EfficientNet-B0)        20 MB      93.5%     25 ms
Student Distilled (Lite0)         18 MB      92.1%     22 ms  ← Worse
```

**What to try**:
1. Increase temperature (try T=6 or T=8)
2. Decrease alpha (try α=0.1 for more distillation)
3. Train teacher longer (50 epochs)
4. Use heavier teacher (EfficientNet-B4)

## 🔬 Hyperparameter Tuning Guide

### Temperature (T)

**Low Temperature (T=2):**
- Sharp predictions
- Good when teacher is very confident
- Use when: Teacher accuracy > 96%

**Medium Temperature (T=4):** ✅ Recommended
- Balanced soft/hard predictions
- Good general purpose
- Use when: Teacher accuracy 93-96%

**High Temperature (T=8-10):**
- Very soft predictions
- Reveals teacher's uncertainty
- Use when: Teacher struggles (accuracy < 93%)

### Alpha (α)

**Low Alpha (α=0.1-0.2):**
- Focus on teacher's knowledge
- Good when teacher is much better
- Use when: Teacher >> Baseline

**Medium Alpha (α=0.3-0.5):** ✅ Recommended
- Balanced learning
- Good general purpose
- Standard distillation setup

**High Alpha (α=0.6-0.9):**
- Focus on hard labels
- Use when teacher only marginally better
- Closer to standard training

## 🎯 When to Use Distillation?

**Use Distillation When:**
- ✅ You can afford to train a larger model first
- ✅ Need maximum accuracy in smallest model
- ✅ Dataset is complex with nuanced patterns
- ✅ Have GPU for training (both teacher and student)

**Skip Distillation When:**
- ❌ Limited training time/resources
- ❌ Direct training already performs well
- ❌ Dataset is simple (binary with clear distinction)
- ❌ Only have CPU for training

## 📈 Comparison with Baseline Approach

| Aspect | Baseline (Direct) | Distillation |
|--------|------------------|--------------|
| **Training Time** | ~30 min (1 model) | ~60-75 min (2 models) |
| **Complexity** | Simple | Medium |
| **Accuracy Potential** | Good | Better (if tuned well) |
| **Hyperparameters** | Few | More to tune |
| **Best For** | Quick experiments | Production deployment |

## 🔗 References

1. **Hinton et al. (2015)**: "Distilling the Knowledge in a Neural Network"
   - Original knowledge distillation paper
   - Introduced temperature scaling and soft targets

2. **Gou et al. (2021)**: "Knowledge Distillation: A Survey"
   - Comprehensive survey of distillation techniques

3. **Tan & Le (2019)**: "EfficientNet: Rethinking Model Scaling"
   - EfficientNet architecture design

## 💡 Tips

1. **Always train teacher first**: Good teacher = good student
2. **Monitor both losses**: Hard loss should decrease, soft loss stabilizes
3. **Use validation accuracy**: Not training loss for saving best model
4. **Try different temperatures**: T=4 is a good starting point
5. **Be patient**: Student often needs more epochs than direct training

## 🚀 Next Steps After Experiment

If distillation works well:
1. Export distilled student to ONNX/TFLite
2. Quantize to INT8 for ESP32
3. Compare with baseline quantized model
4. Deploy best model to edge device

## 📞 Need Help?

If distillation doesn't work:
1. Check teacher accuracy (should be > baseline)
2. Visualize predictions (are they reasonable?)
3. Try different hyperparameters
4. Consider using baseline if distillation doesn't help

---

**Note**: This is an experimental approach. The baseline direct training (current `fire_detection_best.pth`) is already effective. Use distillation if you need that extra 1-2% accuracy boost or want to explore advanced techniques.
