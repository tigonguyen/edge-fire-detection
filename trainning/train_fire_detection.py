"""
Fine-tune EfficientNet-B0 on fire detection dataset (2 classes: fire and normal).
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from pathlib import Path
from tqdm import tqdm
import timm
import time

# Configuration
DATA_DIR = 'model/data/fire_dataset'
BATCH_SIZE = 32
NUM_EPOCHS = 20
LEARNING_RATE = 0.001
NUM_CLASSES = 2  # fire, normal

def get_data_loaders(data_dir, batch_size=32):
    """Create train and validation data loaders."""
    
    # Data augmentation for training
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
    
    # No augmentation for validation
    val_transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                           std=[0.229, 0.224, 0.225])
    ])
    
    # Load datasets
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
    print(f"Class to index: {train_dataset.class_to_idx}")
    
    # Create data loaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True
    )
    
    return train_loader, val_loader, train_dataset.classes

def train_one_epoch(model, train_loader, criterion, optimizer, device, epoch):
    """Train for one epoch."""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    pbar = tqdm(train_loader, desc=f'Epoch {epoch} [Train]')
    for images, labels in pbar:
        images, labels = images.to(device), labels.to(device)
        
        # Forward pass
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        # Statistics
        running_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()
        
        # Update progress bar
        pbar.set_postfix({
            'loss': f'{loss.item():.4f}',
            'acc': f'{100.*correct/total:.2f}%'
        })
    
    epoch_loss = running_loss / len(train_loader)
    epoch_acc = 100. * correct / total
    return epoch_loss, epoch_acc

def validate(model, val_loader, criterion, device, epoch):
    """Validate the model."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    
    # Track per-class accuracy
    class_correct = [0, 0]  # [normal, fire]
    class_total = [0, 0]
    
    with torch.no_grad():
        for images, labels in tqdm(val_loader, desc=f'Epoch {epoch} [Val]  '):
            images, labels = images.to(device), labels.to(device)
            
            outputs = model(images)
            loss = criterion(outputs, labels)
            
            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
            
            # Per-class accuracy
            for i in range(len(labels)):
                label = labels[i].item()
                class_correct[label] += (predicted[i] == labels[i]).item()
                class_total[label] += 1
    
    val_loss = running_loss / len(val_loader)
    val_acc = 100. * correct / total
    
    # Calculate per-class accuracy
    class_acc = [100. * class_correct[i] / class_total[i] if class_total[i] > 0 else 0 
                 for i in range(2)]
    
    return val_loss, val_acc, class_acc

def main():
    print("="*60)
    print("🔥 Fire Detection Model Training")
    print("="*60)
    
    # Check if dataset exists
    if not Path(DATA_DIR).exists():
        print(f"❌ Dataset not found at {DATA_DIR}")
        print("Please run: python model/organize_dataset.py")
        return
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')
    print(f"\n📱 Using device: {device}")
    if device.type == 'cuda':
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
    elif device.type == 'mps':
        print(f"   GPU: Apple Silicon (MPS)")
    
    # Load data
    print(f"\n📦 Loading dataset from {DATA_DIR}...")
    train_loader, val_loader, class_names = get_data_loaders(DATA_DIR, BATCH_SIZE)
    num_classes = len(class_names)
    
    print(f"\n📊 Dataset Info:")
    print(f"   Training batches: {len(train_loader)}")
    print(f"   Validation batches: {len(val_loader)}")
    print(f"   Batch size: {BATCH_SIZE}")
    print(f"   Classes: {class_names}")
    
    # Create model (EfficientNet-B0)
    print(f"\n🤖 Creating EfficientNet-B0 model...")
    model = timm.create_model('efficientnet_b0', pretrained=True, num_classes=num_classes)
    
    # FREEZE BACKBONE (Transfer Learning Mode)
    for param in model.parameters():
        param.requires_grad = False
    
    # UNFREEZE CLASSIFIER HEAD
    for param in model.get_classifier().parameters():
        param.requires_grad = True

    model = model.to(device)
    
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print(f"   Total parameters: {total_params:,}")
    print(f"   Trainable parameters: {trainable_params:,}")
    print(f"   Model size (FP32): ~{total_params * 4 / (1024**2):.2f} MB")
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS)
    
    # Training loop
    best_val_acc = 0.0
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"🚀 Starting training for {NUM_EPOCHS} epochs...")
    print(f"{'='*60}\n")
    
    for epoch in range(1, NUM_EPOCHS + 1):
        epoch_start = time.time()
        
        # Train
        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device, epoch)
        
        # Validate
        val_loss, val_acc, class_acc = validate(model, val_loader, criterion, device, epoch)
        
        # Update learning rate
        scheduler.step()
        
        epoch_time = time.time() - epoch_start
        
        # Print results
        print(f"\n{'─'*60}")
        print(f"📊 Epoch {epoch}/{NUM_EPOCHS} Results (Time: {epoch_time:.1f}s)")
        print(f"{'─'*60}")
        print(f"  Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.2f}%")
        print(f"  Val Loss:   {val_loss:.4f} | Val Acc:   {val_acc:.2f}%")
        print(f"  Class Accuracy:")
        for i, class_name in enumerate(class_names):
            print(f"    {class_name}: {class_acc[i]:.2f}%")
        print(f"  Learning Rate: {optimizer.param_groups[0]['lr']:.6f}")
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            checkpoint_path = 'fire_detection_b0_best.pth'
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_acc': val_acc,
                'val_loss': val_loss,
                'class_names': class_names,
                'num_classes': num_classes,
                'model_name': 'efficientnet_b0',
            }, checkpoint_path)
            print(f"  ✅ Saved best model (val_acc: {val_acc:.2f}%)")
        
        print(f"{'─'*60}\n")
    
    total_time = time.time() - start_time
    
    print(f"\n{'='*60}")
    print(f"✅ Training completed!")
    print(f"{'='*60}")
    print(f"⏱️  Total training time: {total_time/60:.1f} minutes")
    print(f"🎯 Best validation accuracy: {best_val_acc:.2f}%")
    print(f"💾 Model saved to: fire_detection_b0_best.pth")
    print(f"\n🧪 Next step: Test the model")
    print(f"   python test_trained_model.py")

if __name__ == '__main__':
    main()
