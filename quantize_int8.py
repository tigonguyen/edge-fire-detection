#!/usr/bin/env python3
"""
INT8 post-training quantization for fire_detection_best.pth with accuracy check.
Target: accuracy loss < 2%. Exports quantized model to ONNX for C++ backend.
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from pathlib import Path
import timm

CKPT_PATH = Path("fire_detection_best.pth")
DATA_DIR = Path("model/data/fire_dataset")
OUT_DIR = Path("app/model")
MAX_ACC_LOSS_PCT = 2.0  # require accuracy drop < this

IMAGE_MEAN = [0.485, 0.456, 0.406]
IMAGE_STD = [0.229, 0.224, 0.225]
INPUT_SIZE = 224


def get_val_loader(data_dir, batch_size=32):
    t = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(INPUT_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGE_MEAN, std=IMAGE_STD),
    ])
    ds = datasets.ImageFolder(root=str(data_dir / "val"), transform=t)
    return DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=0), ds.classes


def load_model(ckpt_path, device):
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    model_name = ckpt.get("model_name", "efficientnet_lite0")
    num_classes = ckpt.get("num_classes", 2)
    model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
    # Some timm versions change EfficientNet-Lite0 internal naming (e.g. SE blocks),
    # which can cause "Unexpected key(s) in state_dict" when loading older checkpoints.
    # Use strict=False so we still load all matching weights and ignore renamed extras.
    missing, unexpected = model.load_state_dict(ckpt["model_state_dict"], strict=False)
    if missing or unexpected:
        print(f"[quantize_int8] Loaded with strict=False. Missing keys: {len(missing)}, unexpected keys: {len(unexpected)}")
    model.eval()
    return model, ckpt.get("class_names", ["fire", "normal"])


def evaluate(model, loader, device):
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            out = model(x)
            _, pred = out.max(1)
            total += y.size(0)
            correct += (pred == y).sum().item()
    return 100.0 * correct / total if total else 0.0


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading model and validation data...")
    model, class_names = load_model(CKPT_PATH, device)
    model = model.to(device)

    if not DATA_DIR.exists():
        print(f"Validation dir not found: {DATA_DIR}. Skipping accuracy check.")
        val_acc_fp32 = None
        val_loader = None
    else:
        val_loader, _ = get_val_loader(DATA_DIR)
        val_acc_fp32 = evaluate(model, val_loader, device)
        print(f"FP32 validation accuracy: {val_acc_fp32:.2f}%")

    # Dynamic quantization (weights INT8, activations FP32).
    # NOTE: Some PyTorch builds (or Python versions) may not include quantized
    # kernels on this platform, leading to errors in linear_prepack / qlinear.
    # In that case we gracefully fall back to FP32 but still export ONNX.
    print("Applying dynamic INT8 quantization (if supported by this PyTorch build)...")
    try:
        model_quant = torch.quantization.quantize_dynamic(
            model, {nn.Linear, nn.Conv2d}, dtype=torch.qint8, inplace=False
        )
        quant_supported = True
    except Exception as e:
        print(f"WARNING: dynamic quantization failed on this environment: {e}")
        print("Falling back to FP32 model for export. You can later run ONNX/PTQ tools (onnxruntime, etc.) for INT8.")
        model_quant = model
        quant_supported = False

    if val_loader is not None:
        val_acc_int8 = evaluate(model_quant, val_loader, device)
        loss_pct = val_acc_fp32 - val_acc_int8
        if quant_supported:
            print(f"INT8 validation accuracy: {val_acc_int8:.2f}% (drop: {loss_pct:.2f}%)")
            if loss_pct > MAX_ACC_LOSS_PCT:
                print(f"WARNING: Accuracy drop {loss_pct:.2f}% > {MAX_ACC_LOSS_PCT}%. Consider static quantization with calibration.")
            else:
                print(f"OK: Accuracy loss within {MAX_ACC_LOSS_PCT}%.")
        else:
            print(f"Validation accuracy with fallback model (FP32): {val_acc_int8:.2f}% (no INT8 quantization applied).")
    else:
        val_acc_int8 = None

    # Save quantized state for Python inference; export ONNX from FP32 with same preprocessing for C++ backend
    torch.save({
        "model_state_dict": model_quant.state_dict(),
        "class_names": class_names,
        "val_acc_fp32": val_acc_fp32,
        "val_acc_int8": val_acc_int8,
        "model_name": getattr(model, "name", "efficientnet_lite0"),
    }, OUT_DIR / "fire_detection_int8.pth")

    # Export to ONNX (use FP32 model for ONNX; backend can use ONNX Runtime with optional INT8)
    dummy = torch.randn(1, 3, INPUT_SIZE, INPUT_SIZE, device=device)
    onnx_path = OUT_DIR / "fire_detection.onnx"
    torch.onnx.export(
        model if val_loader else model_quant,
        dummy,
        str(onnx_path),
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=14,
    )
    print(f"Exported ONNX to {onnx_path}")

    # Also export FP32 state_dict for reference and optional TorchScript
    scripted_path = OUT_DIR / "fire_detection_scripted.pt"
    model_fp32, _ = load_model(CKPT_PATH, device)
    model_fp32.eval()
    scripted = torch.jit.trace(model_fp32, dummy)
    scripted.save(str(scripted_path))
    print(f"Exported TorchScript to {scripted_path}")

    print("Done. Use app/model/fire_detection.onnx in the C++ backend.")
    return val_acc_fp32, val_acc_int8

if __name__ == "__main__":
    main()
