"""
Compare different training approaches:
1. Baseline: Direct training (existing EfficientNet-B0)
2. Teacher: Heavy model (EfficientNet-B3/B4)
3. Student (Distilled): Lightweight model trained with distillation
4. Student (Baseline): Same lightweight model trained directly (optional)

This script loads all models and compares:
- Accuracy metrics
- Model size
- Inference speed
- Per-class performance
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from pathlib import Path
from tqdm import tqdm
import timm
import time
import sys

sys.path.append(str(Path(__file__).parent))
from config import *

def get_val_loader(data_dir, batch_size=32):
    """Create validation data loader."""
    
    val_transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                           std=[0.229, 0.224, 0.225])
    ])
    
    val_dataset = datasets.ImageFolder(
        root=f'{data_dir}/val',
        transform=val_transform
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=4,
        pin_memory=True
    )
    
    return val_loader, val_dataset.classes

def load_model(checkpoint_path, default_model_name, device):
    """Load a trained model from checkpoint."""
    
    if not Path(checkpoint_path).exists():
        print(f"   ⚠️  Checkpoint not found: {checkpoint_path}")
        return None
    
    checkpoint = torch.load(checkpoint_path, map_location=device)
    
    model_name = checkpoint.get('model_name', default_model_name)
    num_classes = checkpoint.get('num_classes', NUM_CLASSES)
    
    model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
    model.load_state_dict(checkpoint['model_state_dict'])
    model = model.to(device)
    model.eval()
    
    return model, checkpoint

def evaluate_model(model, val_loader, device, model_name):
    """Evaluate model on validation set."""
    
    print(f"\n🔍 Evaluating: {model_name}")
    
    criterion = nn.CrossEntropyLoss()
    running_loss = 0.0
    correct = 0
    total = 0
    
    class_correct = [0, 0]
    class_total = [0, 0]
    
    # Measure inference time
    inference_times = []
    
    with torch.no_grad():
        for images, labels in tqdm(val_loader, desc=f'Testing {model_name}'):
            images, labels = images.to(device), labels.to(device)
            
            # Time inference
            start = time.time()
            outputs = model(images)
            torch.cuda.synchronize() if device.type == 'cuda' else None
            inference_times.append(time.time() - start)
            
            loss = criterion(outputs, labels)
            
            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
            
            for i in range(len(labels)):
                label = labels[i].item()
                class_correct[label] += (predicted[i] == labels[i]).item()
                class_total[label] += 1
    
    val_loss = running_loss / len(val_loader)
    val_acc = 100. * correct / total
    
    class_acc = [100. * class_correct[i] / class_total[i] if class_total[i] > 0 else 0 
                 for i in range(2)]
    
    avg_inference_time = sum(inference_times) / len(inference_times)
    batch_size = val_loader.batch_size
    per_image_time = avg_inference_time / batch_size * 1000  # Convert to ms
    
    return {
        'loss': val_loss,
        'accuracy': val_acc,
        'class_accuracy': class_acc,
        'inference_time_ms': per_image_time
    }

def get_model_size(model):
    """Calculate model size in MB."""
    param_size = sum(p.numel() for p in model.parameters())
    buffer_size = sum(b.numel() for b in model.buffers())
    size_mb = (param_size + buffer_size) * 4 / (1024 ** 2)  # 4 bytes per float32
    return size_mb, param_size

def main():
    print("="*70)
    print("📊 MODEL COMPARISON - Knowledge Distillation Experiment")
    print("="*70)
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n📱 Using device: {device}")
    
    # Load validation data
    print(f"\n📦 Loading validation dataset...")
    val_loader, class_names = get_val_loader(DATA_DIR, BATCH_SIZE)
    print(f"   Validation samples: {len(val_loader.dataset)}")
    print(f"   Classes: {class_names}")
    
    # Define models to compare
    models_to_compare = [
        {
            'name': 'Baseline (EfficientNet-Lite0)',
            'checkpoint': EXISTING_MODEL_CHECKPOINT,
            'default_model': 'efficientnet_lite0',
            'description': 'Direct fine-tuning on fire dataset'
        },
        {
            'name': f'Teacher ({TEACHER_MODEL})',
            'checkpoint': TEACHER_CHECKPOINT,
            'default_model': TEACHER_MODEL,
            'description': 'Heavy model with rich features'
        },
        {
            'name': f'Student Distilled ({STUDENT_MODEL})',
            'checkpoint': STUDENT_DISTILLED_CHECKPOINT,
            'default_model': STUDENT_MODEL,
            'description': 'Lightweight model trained with distillation'
        },
    ]
    
    # Evaluate all models
    results = []
    
    print(f"\n{'='*70}")
    print(f"🧪 EVALUATING MODELS")
    print(f"{'='*70}")
    
    for model_config in models_to_compare:
        print(f"\n{'─'*70}")
        print(f"Model: {model_config['name']}")
        print(f"Description: {model_config['description']}")
        
        model_result = load_model(
            model_config['checkpoint'],
            model_config['default_model'],
            device
        )
        
        if model_result is None:
            print(f"   ⚠️  Skipping (not trained yet)")
            continue
        
        model, checkpoint = model_result
        
        # Get model size
        size_mb, params = get_model_size(model)
        
        # Evaluate
        metrics = evaluate_model(model, val_loader, device, model_config['name'])
        
        results.append({
            'name': model_config['name'],
            'size_mb': size_mb,
            'params': params,
            'metrics': metrics,
            'checkpoint_acc': checkpoint.get('val_acc', 0)
        })
    
    # Print comparison table
    print(f"\n\n{'='*70}")
    print(f"📊 COMPARISON RESULTS")
    print(f"{'='*70}\n")
    
    if not results:
        print("No models available for comparison.")
        print("\nTo run full comparison:")
        print("1. Ensure baseline model exists: fire_detection_best.pth")
        print("2. Train teacher: python experiments/knowledge_distillation/train_teacher.py")
        print("3. Train student: python experiments/knowledge_distillation/train_student_distillation.py")
        return
    
    # Header
    print(f"{'Model':<35} {'Size (MB)':<12} {'Params':<12} {'Accuracy':<12} {'Latency (ms)'}")
    print(f"{'─'*35} {'─'*12} {'─'*12} {'─'*12} {'─'*12}")
    
    # Results
    for result in results:
        print(f"{result['name']:<35} "
              f"{result['size_mb']:>10.2f}  "
              f"{result['params']:>10,}  "
              f"{result['metrics']['accuracy']:>10.2f}%  "
              f"{result['metrics']['inference_time_ms']:>10.2f}")
    
    # Per-class accuracy
    print(f"\n{'='*70}")
    print(f"📊 PER-CLASS ACCURACY")
    print(f"{'='*70}\n")
    
    print(f"{'Model':<35} {class_names[0]:<15} {class_names[1]:<15}")
    print(f"{'─'*35} {'─'*15} {'─'*15}")
    
    for result in results:
        class_acc = result['metrics']['class_accuracy']
        print(f"{result['name']:<35} "
              f"{class_acc[0]:>13.2f}%  "
              f"{class_acc[1]:>13.2f}%")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"💡 INSIGHTS")
    print(f"{'='*70}\n")
    
    if len(results) >= 3:
        baseline = results[0]
        teacher = results[1]
        student = results[2]
        
        print(f"Teacher vs Baseline:")
        acc_diff = teacher['metrics']['accuracy'] - baseline['metrics']['accuracy']
        size_diff = teacher['size_mb'] / baseline['size_mb']
        print(f"  Accuracy: {acc_diff:+.2f}% ({teacher['metrics']['accuracy']:.2f}% vs {baseline['metrics']['accuracy']:.2f}%)")
        print(f"  Model size: {size_diff:.1f}x larger ({teacher['size_mb']:.1f} MB vs {baseline['size_mb']:.1f} MB)")
        
        print(f"\nStudent (Distilled) vs Baseline:")
        acc_diff = student['metrics']['accuracy'] - baseline['metrics']['accuracy']
        size_ratio = student['size_mb'] / baseline['size_mb']
        speed_ratio = baseline['metrics']['inference_time_ms'] / student['metrics']['inference_time_ms']
        print(f"  Accuracy: {acc_diff:+.2f}% ({student['metrics']['accuracy']:.2f}% vs {baseline['metrics']['accuracy']:.2f}%)")
        print(f"  Model size: {size_ratio:.2f}x ({student['size_mb']:.1f} MB vs {baseline['size_mb']:.1f} MB)")
        print(f"  Speed: {speed_ratio:.2f}x {'faster' if speed_ratio > 1 else 'slower'}")
        
        print(f"\nStudent (Distilled) vs Teacher:")
        acc_diff = student['metrics']['accuracy'] - teacher['metrics']['accuracy']
        compression = teacher['size_mb'] / student['size_mb']
        print(f"  Accuracy: {acc_diff:+.2f}% (acceptable if within 2-3%)")
        print(f"  Compression: {compression:.1f}x smaller")
        print(f"  Inference: {student['metrics']['inference_time_ms']:.2f} ms vs {teacher['metrics']['inference_time_ms']:.2f} ms")
        
        print(f"\n🎯 Recommendation:")
        if student['metrics']['accuracy'] > baseline['metrics']['accuracy']:
            print(f"  ✅ Knowledge distillation is EFFECTIVE!")
            print(f"     Student (distilled) achieves {student['metrics']['accuracy']:.2f}% accuracy")
            print(f"     vs {baseline['metrics']['accuracy']:.2f}% with direct training")
            print(f"     Use the distilled student model for deployment.")
        elif abs(student['metrics']['accuracy'] - baseline['metrics']['accuracy']) < 1.0:
            print(f"  ⚖️  Knowledge distillation performs SIMILARLY to direct training")
            print(f"     Consider student if it's smaller/faster, otherwise use baseline")
        else:
            print(f"  ⚠️  Baseline performs better ({baseline['metrics']['accuracy']:.2f}% vs {student['metrics']['accuracy']:.2f}%)")
            print(f"     May need to tune distillation hyperparameters:")
            print(f"     - Increase temperature (current: {DISTILLATION_TEMPERATURE})")
            print(f"     - Adjust alpha (current: {DISTILLATION_ALPHA})")
            print(f"     - Train teacher longer for better soft targets")
    
    print(f"\n{'='*70}\n")

if __name__ == '__main__':
    main()
