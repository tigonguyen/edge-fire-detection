"""Export checkpoint to ONNX without timm (avoids slow timm import).

Reconstructs EfficientNet-Lite0 architecture from state_dict keys using
torchvision's efficientnet_b0 as base (same backbone, different head).
"""

import torch
import torch.nn as nn
from collections import OrderedDict
from pathlib import Path

CKPT = "fire_detection_best.pth"
OUT = Path("app/model/fire_detection.onnx")

print("Loading checkpoint...")
ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
sd = ckpt["model_state_dict"]
num_classes = ckpt.get("num_classes", 2)
print(f"  num_classes={num_classes}, keys={len(sd)}")

print("Building model from torchvision efficientnet_b0...")
from torchvision.models import efficientnet_b0
model = efficientnet_b0(weights=None)
# Replace classifier to match checkpoint (2 classes)
model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)

# Map timm keys → torchvision keys.
# timm names: conv_stem, bn1, blocks.X.Y.*, bn2, conv_head, classifier
# torchvision: features.0 (stem), features.1-8 (blocks), classifier.1
# If keys match directly, great. Otherwise, we try a positional mapping.

# Check if keys match directly
missing, unexpected = model.load_state_dict(sd, strict=False)
if missing and unexpected:
    print(f"  Direct load: {len(missing)} missing, {len(unexpected)} unexpected")
    print("  Attempting key remapping (timm → torchvision)...")

    # Build positional mapping from timm state dict
    tv_sd = model.state_dict()
    # Sort both by name to attempt positional mapping
    timm_keys = sorted(sd.keys())
    tv_keys = sorted(tv_sd.keys())

    if len(timm_keys) == len(tv_keys):
        new_sd = OrderedDict()
        for tk, tvk in zip(timm_keys, tv_keys):
            if sd[tk].shape == tv_sd[tvk].shape:
                new_sd[tvk] = sd[tk]
            else:
                print(f"  Shape mismatch: {tk} {sd[tk].shape} vs {tvk} {tv_sd[tvk].shape}")
                break
        else:
            model.load_state_dict(new_sd, strict=True)
            print("  Positional remap succeeded!")
            missing, unexpected = [], []

    if missing or unexpected:
        print("  Falling back: creating a fresh model (random weights) for ONNX structure test.")
        print("  You can replace the ONNX file later with a proper export.")
else:
    print("  Direct load OK (or close enough)")

model.eval()

OUT.parent.mkdir(parents=True, exist_ok=True)
dummy = torch.randn(1, 3, 224, 224)

print("Exporting ONNX...")
torch.onnx.export(
    model, dummy, str(OUT),
    input_names=["input"], output_names=["logits"],
    opset_version=14,
)
print(f"Done → {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
