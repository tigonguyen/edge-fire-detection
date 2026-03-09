import sys
import torch
print(torch.__version__)
try:
    CKPT = "fire_detection_best.pth"
    print("Loading...")
    ckpt = torch.load(CKPT, map_location=torch.device('cpu'), mmap=True)
    print("Keys:", list(ckpt.keys())[:5])
    print("Success mmap!")
except Exception as e:
    print(f"Error: {e}")
