# Knowledge Distillation Experiment

This directory contains an alternative training approach using **knowledge distillation** to potentially improve the student model's performance compared to direct training.

## 📚 What is Knowledge Distillation?

Knowledge distillation is a technique where:
1. A large, accurate **teacher model** is trained first
2. A smaller **student model** learns from both:
   - Hard labels (ground truth)
   - Soft predictions from the teacher (containing richer information)

## 🎯 Experiment Setup

### Teacher Model
- **Architecture**: EfficientNet-B3 (~12M parameters)
- **Purpose**: Achieve highest possible accuracy
- **Size**: ~47 MB (FP32)
- **Training**: Standard transfer learning on fire dataset

### Student Model
- **Architecture**: EfficientNet-B0 (~5M parameters)
- **Purpose**: Lightweight model for ESP32 deployment
- **Size**: ~20 MB (FP32), ~5 MB (INT8 quantized)
- **Training**: Knowledge distillation from teacher

### Distillation Loss

The student is trained with a combined loss:

```
Total Loss = α × CE(student_output, hard_labels) + 
             (1-α) × KL(soft_student, soft_teacher)

where:
- CE = Cross-Entropy Loss
- KL = Kullback-Leibler Divergence
- α = 0.3 (weight for hard labels)
- soft = softmax(logits / temperature)
- temperature = 4.0
```

## 📁 Directory Structure

```
distillation_experiment/
├── README.md                          # This file
├── teacher/
│   ├── train_teacher.py              # Train large teacher model
│   └── teacher_best.pth              # Trained teacher checkpoint
├── student/
│   ├── distill_student.py            # Distillation training
│   └── student_distilled_best.pth    # Distilled student model
└── comparison/
    ├── compare_models.py             # Compare all approaches
    └── results.txt                   # Comparison results
```

## 🚀 Usage

### Step 1: Train Teacher Model

```bash
# Train the large teacher model (EfficientNet-B3)
python distillation_experiment/teacher/train_teacher.py
```

This will:
- Train EfficientNet-B3 on the fire dataset
- Save the best model to `teacher/teacher_best.pth`
- Take ~30-45 minutes on GPU

### Step 2: Distill Student Model

```bash
# Train student using knowledge distillation
python distillation_experiment/student/distill_student.py
```

This will:
- Load the trained teacher model
- Train EfficientNet-B0 using distillation
- Save the best model to `student/student_distilled_best.pth`
- Take ~20-30 minutes on GPU

### Step 3: Compare Results

```bash
# Compare all three approaches
python distillation_experiment/comparison/compare_models.py
```

This compares:
1. **Direct training**: Current approach (`fire_detection_best.pth`)
2. **Teacher model**: Large model (`teacher_best.pth`)
3. **Distilled student**: Distillation approach (`student_distilled_best.pth`)

## 📊 Expected Results

| Model | Parameters | Size (FP32) | Size (INT8) | Accuracy | ESP32 Compatible |
|-------|-----------|-------------|-------------|----------|-----------------|
| **Teacher (B3)** | 12M | 47 MB | 12 MB | ~95-97% | ❌ Too large |
| **Student Direct** | 5M | 20 MB | 5 MB | ~93-94% | ✅ Yes |
| **Student Distilled** | 5M | 20 MB | 5 MB | ~94-96% | ✅ Yes |

**Expected improvement**: Distilled student should achieve **1-3% higher accuracy** than direct training while maintaining the same model size.

## 🔬 Key Differences from Direct Training

### Direct Training (Current Approach)
- Student learns only from hard labels (fire=1, normal=0)
- Simple and fast to train
- Good baseline performance

### Knowledge Distillation (This Experiment)
- Student learns from both hard labels and teacher's soft predictions
- Teacher provides "dark knowledge" (e.g., "this is 85% fire, 15% normal")
- Student learns more nuanced decision boundaries
- Better generalization to edge cases

## 📈 Benefits of Distillation

1. **Higher accuracy**: 1-3% improvement expected
2. **Better generalization**: Learns from teacher's uncertainty
3. **Same deployment size**: Student remains ~5 MB (INT8)
4. **Edge case handling**: Better performance on ambiguous images
5. **Proven technique**: Used in production AI systems

## 🔍 When to Use Each Approach

### Use Direct Training When:
- Quick experiments needed
- Limited computational resources
- Simple binary classification sufficient
- Training time is critical

### Use Knowledge Distillation When:
- Maximum accuracy required
- Have GPU resources for teacher training
- Deployment on edge devices (size constrained)
- Worth 2x training time for 1-3% accuracy boost

## 📝 Notes

- This experiment is completely separate from the main training pipeline
- Original model at `fire_detection_best.pth` is unchanged
- Can compare both approaches side-by-side
- Choose best model based on accuracy/complexity trade-off

## 🔗 References

- [Distilling the Knowledge in a Neural Network](https://arxiv.org/abs/1503.02531) (Hinton et al., 2015)
- [Knowledge Distillation: A Survey](https://arxiv.org/abs/2006.05525)
