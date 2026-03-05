#!/bin/bash

# Setup script for knowledge distillation experiment
# Run this before training: bash experiments/knowledge_distillation/setup.sh

set -e

echo "=================================================="
echo "🔧 Knowledge Distillation Experiment Setup"
echo "=================================================="
echo ""

# Check if we're in the right directory
if [ ! -d "experiments/knowledge_distillation" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "   cd /path/to/edge-fire-detection"
    echo "   bash experiments/knowledge_distillation/setup.sh"
    exit 1
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please create one first:"
    echo "   python3 -m venv venv"
    exit 1
fi

echo "✅ Found virtual environment"
echo ""

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Check Python version
echo "🐍 Python version:"
python --version
echo ""

# Install/upgrade required packages
echo "📥 Installing required packages..."
echo "   This may take a few minutes..."
echo ""

pip install --upgrade pip

# Install PyTorch (if not already installed)
if ! python -c "import torch" 2>/dev/null; then
    echo "   Installing PyTorch..."
    pip install torch torchvision
else
    echo "   ✅ PyTorch already installed"
fi

# Install timm (required for EfficientNet models)
if ! python -c "import timm" 2>/dev/null; then
    echo "   Installing timm..."
    pip install timm
else
    echo "   ✅ timm already installed"
fi

# Install tqdm (for progress bars)
if ! python -c "import tqdm" 2>/dev/null; then
    echo "   Installing tqdm..."
    pip install tqdm
else
    echo "   ✅ tqdm already installed"
fi

echo ""
echo "=================================================="
echo "✅ Setup Complete!"
echo "=================================================="
echo ""
echo "📊 Installed packages:"
python -c "import torch; print(f'   PyTorch: {torch.__version__}')"
python -c "import timm; print(f'   timm: {timm.__version__}')"
python -c "import tqdm; print(f'   tqdm: {tqdm.__version__}')"
echo ""
echo "🚀 You're ready to train! Run:"
echo "   source venv/bin/activate"
echo "   python experiments/knowledge_distillation/train_teacher.py"
echo ""
