# Fire Detection — C++ ONNX Runtime

Minimal CLI that loads an EfficientNet-Lite0 ONNX model and classifies a single image as `fire` or `normal`.

## Prerequisites

1. **ONNX model** — export from the trained checkpoint:
   ```bash
   python quantize_int8.py
   ```
   Produces `fire_detection.onnx`.

2. **ONNX Runtime** — download the C++ package:
   ```bash
   wget https://github.com/microsoft/onnxruntime/releases/download/v1.16.3/onnxruntime-linux-x64-1.16.3.tgz
   tar xzf onnxruntime-linux-x64-1.16.3.tgz
   export ONNXRUNTIME_ROOT=$(pwd)/onnxruntime-linux-x64-1.16.3
   ```

## Build

```bash
cd app
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make
```

## Run

```bash
# Convert any image to raw 224x224 RGB
python app/prepare_input.py photo.jpg test_input.rgb

# Inference
./build/fire_backend fire_detection.onnx test_input.rgb
```

Output:
```
class:      fire
confidence: 0.973
```

## Files

- `src/main.cpp` — load model, read raw image, inference, print result
- `include/preprocess.h` — ImageNet normalization (HWC uint8 → CHW float32)
- `prepare_input.py` — convert JPEG/PNG to raw 224×224 RGB
- `CMakeLists.txt` — CMake build with ONNX Runtime
- `Dockerfile` — multi-stage build for container deployment
