# Quick Start Guide - Knowledge Distillation Experiment

## 🚨 Fix the Import Error

You got `ModuleNotFoundError: No module named 'timm'` because you need to activate the virtual environment first.

## ✅ Solution: Run with Virtual Environment

### Option 1: Run Setup Script (Recommended)

```bash
# From project root directory
cd /Users/tigonguyen/Documents/DevOps/repos/personal-projects/edge-fire-detection

# Run setup script (installs dependencies if needed)
bash experiments/knowledge_distillation/setup.sh

# Then activate venv and run training
source venv/bin/activate
python experiments/knowledge_distillation/train_teacher.py
```

### Option 2: Manual Activation

```bash
# Activate virtual environment
cd /Users/tigonguyen/Documents/DevOps/repos/personal-projects/edge-fire-detection
source venv/bin/activate

# Verify packages are installed
python -c "import timm; print('timm is installed')"
python -c "import torch; print('torch is installed')"

# If any package is missing, install it:
pip install timm tqdm torch torchvision

# Now run the training
python experiments/knowledge_distillation/train_teacher.py
```

### Option 3: Use venv Python directly

```bash
# Run with venv's Python directly (no activation needed)
cd /Users/tigonguyen/Documents/DevOps/repos/personal-projects/edge-fire-detection
./venv/bin/python experiments/knowledge_distillation/train_teacher.py
```

## 📋 Full Training Workflow

### Step 1: Setup (One-time)

```bash
cd /Users/tigonguyen/Documents/DevOps/repos/personal-projects/edge-fire-detection
bash experiments/knowledge_distillation/setup.sh
```

### Step 2: Train Teacher (~30-45 min)

```bash
source venv/bin/activate
python experiments/knowledge_distillation/train_teacher.py
```

This will:
- Train EfficientNet-B3 (heavy model)
- Save to `experiments/knowledge_distillation/models/teacher_best.pth`
- Show training progress with accuracy and loss

### Step 3: Train Student with Distillation (~25-35 min)

```bash
source venv/bin/activate
python experiments/knowledge_distillation/train_student_distillation.py
```

This will:
- Load frozen teacher
- Train EfficientNet-Lite0 (lightweight)
- Learn from teacher's soft predictions
- Save to `experiments/knowledge_distillation/models/student_distilled_best.pth`

### Step 4: Compare Models

```bash
source venv/bin/activate
python experiments/knowledge_distillation/compare_models.py
```

This will show:
- Accuracy comparison table
- Model size comparison
- Inference speed
- Recommendations

## 🔧 Troubleshooting

### Error: `ModuleNotFoundError: No module named 'timm'`

**Cause**: Running with system Python instead of virtual environment

**Fix**: Always activate venv first:
```bash
source venv/bin/activate
```

### Error: `No module named 'torch'`

**Cause**: PyTorch not installed in virtual environment

**Fix**: Install PyTorch:
```bash
source venv/bin/activate
pip install torch torchvision
```

### Error: Dataset not found

**Cause**: Training data not organized

**Fix**: Make sure your dataset is at:
```
model/data/fire_dataset/
├── train/
│   ├── fire/
│   └── normal/
└── val/
    ├── fire/
    └── normal/
```

If not, run:
```bash
python model/organize_dataset.py
```

### Error: CUDA out of memory

**Cause**: GPU memory too small or batch size too large

**Fix**: Reduce batch size in `config.py`:
```python
BATCH_SIZE = 16  # or even 8
```

## 💡 Tips

1. **Always activate venv**: Run `source venv/bin/activate` before any Python command
2. **Monitor GPU**: Use `nvidia-smi` to watch GPU usage during training
3. **Save time**: Run teacher training overnight (it's long)
4. **Check config**: Review `experiments/knowledge_distillation/config.py` before training

## 📊 Expected Output

When training starts successfully, you should see:

```
==================================================================
🎓 TEACHER MODEL TRAINING (Knowledge Distillation Experiment)
==================================================================

📱 Using device: cuda
   GPU: NVIDIA GeForce RTX 3080

📦 Loading dataset from model/data/fire_dataset...
Train dataset size: 800
Val dataset size: 200
Classes: ['fire', 'normal']

🎓 Creating TEACHER model: efficientnet_b3
   This is a HEAVY model that will learn rich features
   
   Total parameters: 12,233,232
   Trainable parameters: 12,233,232
   Model size (FP32): ~46.65 MB

==================================================================
🚀 Starting teacher training for 30 epochs...
==================================================================

Epoch 1 [Train]: 100%|████████████████| 25/25 [00:45<00:00]
```

## 🎯 Next Steps

After successful comparison, you'll have:
- `teacher_best.pth` - Heavy model (reference)
- `student_distilled_best.pth` - Lightweight model (for deployment)
- Performance comparison data

Use the best student model for:
1. Quantization to INT8
2. Export to TFLite
3. Deployment on ESP32

---

**Need Help?** Check the full README: `experiments/knowledge_distillation/README.md`
