"""
Train student model using knowledge distillation from teacher.

This implements the core knowledge distillation algorithm where the student
learns from both:
1. Hard labels (ground truth)
2. Soft labels (teacher's predictions with temperature scaling)

The student aims to match the teacher's output distribution, not just 
the final classification.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from pathlib import Path
from tqdm import tqdm
import timm
import time
import sys

sys.path.append(str(Path(__file__).parent))
from config import *

def get_data_loaders(data_dir, batch_size=32):
    """Create train and validation data loaders."""
    
    train_transform = transforms.Compose([
        transforms.Resize(256),
        transforms.RandomCrop(224),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                           std=[0.229, 0.224, 0.225])
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                           std=[0.229, 0.224, 0.225])
    ])
    
    train_dataset = datasets.ImageFolder(
        root=f'{data_dir}/train',
        transform=train_transform
    )
    
    val_dataset = datasets.ImageFolder(
        root=f'{data_dir}/val',
        transform=val_transform
    )
    
    print(f"Train dataset size: {len(train_dataset)}")
    print(f"Val dataset size: {len(val_dataset)}")
    print(f"Classes: {train_dataset.classes}")
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=4,
        pin_memory=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=4,
        pin_memory=True
    )
    
    return train_loader, val_loader, train_dataset.classes

def distillation_loss(student_logits, teacher_logits, labels, temperature, alpha):
    """
    Compute knowledge distillation loss.
    
    Loss = alpha * hard_loss + (1 - alpha) * distillation_loss
    
    Args:
        student_logits: Raw predictions from student
        teacher_logits: Raw predictions from teacher
        labels: Ground truth labels
        temperature: Temperature for softening predictions
        alpha: Weight for hard loss (0=pure distillation, 1=standard training)
    
    Returns:
        Combined loss value
    """
    # Hard loss: Standard cross-entropy with true labels
    hard_loss = F.cross_entropy(student_logits, labels)
    
    # Soft loss: KL divergence between student and teacher soft predictions
    # Temperature scaling makes predictions softer, revealing teacher's uncertainty
    student_soft = F.log_softmax(student_logits / temperature, dim=1)
    teacher_soft = F.softmax(teacher_logits / temperature, dim=1)
    
    # KL divergence: measures how student's distribution differs from teacher's
    soft_loss = F.kl_div(student_soft, teacher_soft, reduction='batchmean')
    
    # Scale soft loss by T^2 to compensate for temperature scaling
    # (see Hinton et al. 2015: "Distilling the Knowledge in a Neural Network")
    soft_loss = soft_loss * (temperature ** 2)
    
    # Combine losses
    total_loss = alpha * hard_loss + (1 - alpha) * soft_loss
    
    return total_loss, hard_loss, soft_loss

def train_one_epoch(student, teacher, train_loader, optimizer, device, epoch, temperature, alpha):
    """Train student for one epoch with distillation."""
    student.train()
    teacher.eval()  # Teacher is frozen
    
    running_loss = 0.0
    running_hard_loss = 0.0
    running_soft_loss = 0.0
    correct = 0
    total = 0
    
    print(f"\n🔥 Training Epoch {epoch} with Distillation...")
    pbar = tqdm(train_loader, desc=f'Epoch {epoch} [Distill]',
                ncols=100, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}')
    
    for images, labels in pbar:
        images, labels = images.to(device), labels.to(device)
        
        optimizer.zero_grad()
        
        # Get predictions
        student_logits = student(images)
        
        with torch.no_grad():
            teacher_logits = teacher(images)
        
        # Compute distillation loss
        loss, hard_loss, soft_loss = distillation_loss(
            student_logits, teacher_logits, labels, temperature, alpha
        )
        
        loss.backward()
        optimizer.step()
        
        # Statistics
        running_loss += loss.item()
        running_hard_loss += hard_loss.item()
        running_soft_loss += soft_loss.item()
        
        _, predicted = student_logits.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()
        
        pbar.set_postfix({
            'loss': f'{loss.item():.4f}',
            'hard': f'{hard_loss.item():.3f}',
            'soft': f'{soft_loss.item():.3f}',
            'acc': f'{100.*correct/total:.2f}%'
        })
    
    epoch_loss = running_loss / len(train_loader)
    epoch_hard_loss = running_hard_loss / len(train_loader)
    epoch_soft_loss = running_soft_loss / len(train_loader)
    epoch_acc = 100. * correct / total
    
    print(f"✅ Training complete - Loss: {epoch_loss:.4f} (Hard: {epoch_hard_loss:.4f}, Soft: {epoch_soft_loss:.4f}), Acc: {epoch_acc:.2f}%")
    
    return epoch_loss, epoch_hard_loss, epoch_soft_loss, epoch_acc

def validate(model, val_loader, criterion, device, epoch):
    """Validate the student model."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    
    class_correct = [0, 0]
    class_total = [0, 0]
    
    print(f"\n📊 Validating Epoch {epoch}...")
    
    with torch.no_grad():
        pbar = tqdm(val_loader, desc=f'Epoch {epoch} [Val]    ',
                   ncols=100, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]')
        
        for images, labels in pbar:
            images, labels = images.to(device), labels.to(device)
            
            outputs = model(images)
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
    
    print(f"✅ Validation complete - Loss: {val_loss:.4f}, Acc: {val_acc:.2f}%")
    
    return val_loss, val_acc, class_acc

def load_teacher(checkpoint_path, device):
    """Load trained teacher model."""
    print(f"\n🎓 Loading teacher model from {checkpoint_path}...")
    
    if not Path(checkpoint_path).exists():
        print(f"❌ Teacher checkpoint not found!")
        print(f"Please train teacher first: python experiments/knowledge_distillation/train_teacher.py")
        return None
    
    checkpoint = torch.load(checkpoint_path, map_location=device)
    
    teacher_model_name = checkpoint.get('model_name', TEACHER_MODEL)
    teacher = timm.create_model(teacher_model_name, pretrained=False, num_classes=NUM_CLASSES)
    teacher.load_state_dict(checkpoint['model_state_dict'])
    teacher = teacher.to(device)
    teacher.eval()
    
    print(f"✅ Teacher loaded successfully!")
    print(f"   Model: {teacher_model_name}")
    print(f"   Validation accuracy: {checkpoint['val_acc']:.2f}%")
    
    return teacher

def main():
    print("\n" + "="*70)
    print("🎓 STUDENT TRAINING with KNOWLEDGE DISTILLATION")
    print("="*70)
    import sys
    sys.stdout.flush()
    
    # Check if dataset exists
    if not Path(DATA_DIR).exists():
        print(f"❌ Dataset not found at {DATA_DIR}")
        return
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n📱 Using device: {device}")
    if device.type == 'cuda':
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
    
    # Load teacher
    teacher = load_teacher(TEACHER_CHECKPOINT, device)
    if teacher is None:
        return
    
    # Freeze teacher
    for param in teacher.parameters():
        param.requires_grad = False
    
    # Load data
    print(f"\n📦 Loading dataset from {DATA_DIR}...")
    train_loader, val_loader, class_names = get_data_loaders(DATA_DIR, BATCH_SIZE)
    
    print(f"\n📊 Dataset Info:")
    print(f"   Training batches: {len(train_loader)}")
    print(f"   Validation batches: {len(val_loader)}")
    print(f"   Classes: {class_names}")
    
    # Create student model
    print(f"\n🎓 Creating STUDENT model: {STUDENT_MODEL}")
    print(f"   This is a LIGHTWEIGHT model learning from the teacher")
    
    student = timm.create_model(STUDENT_MODEL, pretrained=True, num_classes=NUM_CLASSES)
    student = student.to(device)
    
    total_params = sum(p.numel() for p in student.parameters())
    
    print(f"\n   Total parameters: {total_params:,}")
    print(f"   Model size (FP32): ~{total_params * 4 / (1024**2):.2f} MB")
    
    # Distillation configuration
    print(f"\n🔬 Distillation Configuration:")
    print(f"   Temperature (T): {DISTILLATION_TEMPERATURE}")
    print(f"   Alpha (hard loss weight): {DISTILLATION_ALPHA}")
    print(f"   1-Alpha (soft loss weight): {1-DISTILLATION_ALPHA}")
    
    # Optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(student.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS_STUDENT)
    
    # Training loop
    best_val_acc = 0.0
    start_time = time.time()
    
    print(f"\n{'='*70}")
    print(f"🚀 Starting distillation training for {NUM_EPOCHS_STUDENT} epochs...")
    print(f"{'='*70}\n")
    
    for epoch in range(1, NUM_EPOCHS_STUDENT + 1):
        epoch_start = time.time()
        
        # Train with distillation
        train_loss, hard_loss, soft_loss, train_acc = train_one_epoch(
            student, teacher, train_loader, optimizer, device, epoch,
            DISTILLATION_TEMPERATURE, DISTILLATION_ALPHA
        )
        
        # Validate
        val_loss, val_acc, class_acc = validate(student, val_loader, criterion, device, epoch)
        
        # Update learning rate
        scheduler.step()
        
        epoch_time = time.time() - epoch_start
        
        # Print results
        print(f"\n{'─'*70}")
        print(f"📊 Epoch {epoch}/{NUM_EPOCHS_STUDENT} Results (Time: {epoch_time:.1f}s)")
        print(f"{'─'*70}")
        print(f"  Train Loss: {train_loss:.4f} (Hard: {hard_loss:.4f}, Soft: {soft_loss:.4f})")
        print(f"  Train Acc: {train_acc:.2f}%")
        print(f"  Val Loss:   {val_loss:.4f} | Val Acc:   {val_acc:.2f}%")
        print(f"  Class Accuracy:")
        for i, class_name in enumerate(class_names):
            print(f"    {class_name}: {class_acc[i]:.2f}%")
        print(f"  Learning Rate: {optimizer.param_groups[0]['lr']:.6f}")
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save({
                'epoch': epoch,
                'model_name': STUDENT_MODEL,
                'model_state_dict': student.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_acc': val_acc,
                'val_loss': val_loss,
                'class_names': class_names,
                'num_classes': NUM_CLASSES,
                'teacher_model': TEACHER_MODEL,
                'distillation_temperature': DISTILLATION_TEMPERATURE,
                'distillation_alpha': DISTILLATION_ALPHA,
            }, STUDENT_DISTILLED_CHECKPOINT)
            print(f"  ✅ Saved best student model (val_acc: {val_acc:.2f}%)")
        
        print(f"{'─'*70}\n")
    
    total_time = time.time() - start_time
    
    print(f"\n{'='*70}")
    print(f"✅ Student distillation training completed!")
    print(f"{'='*70}")
    print(f"⏱️  Total training time: {total_time/60:.1f} minutes")
    print(f"🎯 Best validation accuracy: {best_val_acc:.2f}%")
    print(f"💾 Student model saved to: {STUDENT_DISTILLED_CHECKPOINT}")
    print(f"\n🧪 Next step: Compare models")
    print(f"   python experiments/knowledge_distillation/compare_models.py")

if __name__ == '__main__':
    main()
