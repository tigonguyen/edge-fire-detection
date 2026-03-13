import os
import time
import torch
import timm
from pathlib import Path
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
from tqdm import tqdm

# Configuration: Dynamically find root structure so it runs from anywhere
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT_DIR / 'models'
DATA_DIR = ROOT_DIR / 'data' / 'fire_dataset' / 'val'
BATCH_SIZE = 32

def get_model_size_mb(path):
    size_bytes = os.path.getsize(path)
    return size_bytes / (1024 * 1024)

def evaluate_model(model_path, val_loader, device):
    # Pass weights_only=False to fix future warnings when loading timm models
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    model_name = checkpoint.get('model_name', 'efficientnet_lite0')
    num_classes = checkpoint.get('num_classes', 2)
    
    model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
    model.load_state_dict(checkpoint['model_state_dict'])
    model = model.to(device)
    model.eval()
    
    tp = fp = tn = fn = 0
    total_time = 0.0
    num_samples = 0
    
    with torch.no_grad():
        for images, labels in tqdm(val_loader, desc=f"Evaluating {model_path.name:30}"):
            images, labels = images.to(device), labels.to(device)
            
            start_t = time.time()
            outputs = model(images)
            end_t = time.time()
            
            total_time += (end_t - start_t)
            num_samples += images.size(0)
            
            _, predicted = outputs.max(1)
            
            # Assuming fire=0, normal=1 (standard ImageFolder alphabetical mapping)
            for p, y in zip(predicted, labels):
                p, y = p.item(), y.item()
                if p == 0 and y == 0: tp += 1
                elif p == 0 and y == 1: fp += 1
                elif p == 1 and y == 1: tn += 1
                elif p == 1 and y == 0: fn += 1

    accuracy = (tp + tn) / (tp + tn + fp + fn) * 100 if (tp + tn + fp + fn) else 0
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * (precision * recall) / (precision + recall) * 100 if (precision + recall) else 0
    fps = num_samples / total_time if total_time > 0 else 0
            
    return accuracy, f1, fps

def main():
    if not DATA_DIR.exists():
        print(f"Validation data not found at {DATA_DIR}.")
        return
        
    val_transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    val_dataset = datasets.ImageFolder(root=DATA_DIR, transform=val_transform)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
    
    # We enforce CPU for script stability to prevent Mac initialization hangs on MPS
    device = torch.device('cpu')
    print(f"Using device: {device}\n")
    
    print(f"{'Model Name':<35} | {'Size (MB)':<10} | {'Accuracy':<10} | {'F1-Score':<10} | {'FPS':<6}")
    print("-" * 85)
    
    if not MODELS_DIR.exists():
        print(f"Models directory not found at {MODELS_DIR}")
        return
        
    for model_path in sorted(MODELS_DIR.glob('*.pth')):
        size_mb = get_model_size_mb(model_path)
        try:
            acc, f1, fps = evaluate_model(model_path, val_loader, device)
            print(f"{model_path.name:<35} | {size_mb:<10.2f} | {acc:<9.2f}% | {f1:<9.2f}% | {fps:<5.1f}")
        except Exception as e:
            print(f"{model_path.name:<35} | {size_mb:<10.2f} | Failed: {str(e)}")

if __name__ == '__main__':
    main()
