"""
Compare fire_detection_best.pth (baseline) vs student_distilled_best.pth (distilled).
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from pathlib import Path
from tqdm import tqdm
import timm
import time

# Paths
DATA_DIR = 'model/data/fire_dataset'
BASELINE_PATH = 'fire_detection_best.pth'
STUDENT_PATH = 'experiments/knowledge_distillation/models/student_distilled_best.pth'

def get_val_loader(data_dir, batch_size=32):
    val_transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    val_dataset = datasets.ImageFolder(root=f'{data_dir}/val', transform=val_transform)
    return DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0), val_dataset.classes

def load_checkpoint(path, default_model, device):
    if not Path(path).exists():
        return None, None
    ckpt = torch.load(path, map_location=device)
    model_name = ckpt.get('model_name', default_model)
    num_classes = ckpt.get('num_classes', 2)
    model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
    model.load_state_dict(ckpt['model_state_dict'])
    model = model.to(device)
    model.eval()
    return model, ckpt

def count_params_and_size(model):
    params = sum(p.numel() for p in model.parameters())
    buffers = sum(b.numel() for b in model.buffers())
    size_mb = (params + buffers) * 4 / (1024 ** 2)
    return params, size_mb

def evaluate(model, loader, device):
    correct, total = 0, 0
    times = []
    with torch.no_grad():
        for images, labels in tqdm(loader, desc='Evaluating', leave=False):
            images, labels = images.to(device), labels.to(device)
            start = time.perf_counter()
            out = model(images)
            if device.type == 'cuda':
                torch.cuda.synchronize()
            times.append((time.perf_counter() - start) / images.size(0) * 1000)
            _, pred = out.max(1)
            total += labels.size(0)
            correct += pred.eq(labels).sum().item()
    acc = 100. * correct / total if total else 0
    lat_ms = sum(times) / len(times) if times else 0
    return acc, lat_ms

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print('='*70)
    print('Compare: fire_detection_best.pth vs student_distilled_best.pth')
    print('='*70)
    print(f'Device: {device}\n')

    # Load validation data
    if not Path(DATA_DIR).exists():
        print(f'Validation dir not found: {DATA_DIR}')
        print('Skipping accuracy evaluation; reporting only checkpoint info and model size.\n')
        val_loader, class_names = None, ['fire', 'normal']
    else:
        val_loader, class_names = get_val_loader(DATA_DIR)
        print(f'Validation samples: {len(val_loader.dataset)}, classes: {class_names}\n')

    results = []

    # Baseline: fire_detection_best.pth (EfficientNet-Lite0, direct training)
    print('Loading baseline: fire_detection_best.pth (EfficientNet-Lite0)...')
    model_baseline, ckpt_baseline = load_checkpoint(BASELINE_PATH, 'efficientnet_lite0', device)
    if model_baseline is None:
        print(f'  Not found: {BASELINE_PATH}\n')
    else:
        params_b, size_b = count_params_and_size(model_baseline)
        saved_acc_b = ckpt_baseline.get('val_acc')
        acc_b, lat_b = (evaluate(model_baseline, val_loader, device) if val_loader else (saved_acc_b, None))
        results.append({
            'name': 'fire_detection_best.pth (Baseline)',
            'arch': 'efficientnet_lite0',
            'params': params_b,
            'size_mb': size_b,
            'val_acc': acc_b,
            'saved_val_acc': saved_acc_b,
            'latency_ms': lat_b,
        })
        print(f'  Params: {params_b:,}, Size: {size_b:.2f} MB')
        if val_loader:
            print(f'  Val accuracy: {acc_b:.2f}%')
            print(f'  Latency: {lat_b:.2f} ms/image')
        print()

    # Student distilled: student_distilled_best.pth (EfficientNet-Lite0, knowledge distillation)
    print('Loading student: student_distilled_best.pth (EfficientNet-Lite0, distilled)...')
    model_student, ckpt_student = load_checkpoint(STUDENT_PATH, 'efficientnet_lite0', device)
    if model_student is None:
        print(f'  Not found: {STUDENT_PATH}\n')
    else:
        params_s, size_s = count_params_and_size(model_student)
        saved_acc_s = ckpt_student.get('val_acc')
        acc_s, lat_s = (evaluate(model_student, val_loader, device) if val_loader else (saved_acc_s, None))
        results.append({
            'name': 'student_distilled_best.pth (Distilled)',
            'arch': 'efficientnet_lite0',
            'params': params_s,
            'size_mb': size_s,
            'val_acc': acc_s,
            'saved_val_acc': saved_acc_s,
            'latency_ms': lat_s,
        })
        print(f'  Params: {params_s:,}, Size: {size_s:.2f} MB')
        if val_loader:
            print(f'  Val accuracy: {acc_s:.2f}%')
            print(f'  Latency: {lat_s:.2f} ms/image')
        print()

    # Summary table
    if len(results) == 2:
        b, s = results[0], results[1]
        print('='*70)
        print('Summary')
        print('='*70)
        print(f"{'Metric':<25} {'Baseline (Lite0)':<22} {'Distilled (Lite0)':<22}")
        print('-'*70)
        print(f"{'Architecture':<25} {b['arch']:<22} {s['arch']:<22}")
        print(f"{'Parameters':<25} {b['params']:<22,} {s['params']:<22,}")
        print(f"{'Size (FP32, MB)':<25} {b['size_mb']:.2f}{'':<18} {s['size_mb']:.2f}")
        if b.get('val_acc') is not None and s.get('val_acc') is not None:
            print(f"{'Val accuracy (%)':<25} {b['val_acc']:.2f}{'':<18} {s['val_acc']:.2f}")
        if b.get('latency_ms') is not None and s.get('latency_ms') is not None:
            print(f"{'Latency (ms/img)':<25} {b['latency_ms']:.2f}{'':<18} {s['latency_ms']:.2f}")
        print()
        # Comparison
        size_ratio = b['size_mb'] / s['size_mb']
        param_ratio = b['params'] / s['params']
        print('Distilled (Lite0) vs Baseline (Lite0):')
        print(f'  Size:    {size_ratio:.2f}x smaller ({s["size_mb"]:.1f} MB vs {b["size_mb"]:.1f} MB)')
        print(f'  Params: {param_ratio:.2f}x fewer ({s["params"]:,} vs {b["params"]:,})')
        if b.get('val_acc') is not None and s.get('val_acc') is not None:
            diff = s['val_acc'] - b['val_acc']
            print(f'  Accuracy: {diff:+.2f}% ({s["val_acc"]:.2f}% vs {b["val_acc"]:.2f}%)')
        if b.get('latency_ms') is not None and s.get('latency_ms') is not None:
            speed_ratio = b['latency_ms'] / s['latency_ms']
            print(f'  Speed:   {speed_ratio:.2f}x {"faster" if speed_ratio > 1 else "slower"} ({s["latency_ms"]:.2f} ms vs {b["latency_ms"]:.2f} ms)')
    print('='*70)

if __name__ == '__main__':
    main()
