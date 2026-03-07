# Fire detection backend (C++ / ONNX Runtime)

Minimal HTTP service that runs EfficientNet-Lite0 (ONNX) for fire/normal classification. Accepts a single image per request and returns JSON.

## Prerequisites

1. **Export the ONNX model** (from repo root):
   ```bash
   python quantize_int8.py
   ```
   This produces `app/model/fire_detection.onnx` (and checks INT8 accuracy if validation data exists).

2. **ONNX Runtime** (for local build): set `ONNXRUNTIME_ROOT` to the unpacked Linux x64 package, or install system-wide.

## Build (local)

```bash
cd app
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DONNXRUNTIME_ROOT=/path/to/onnxruntime-linux-x64-* ..
make
```

Binary: `fire_backend`.

## Run (local)

```bash
./fire_backend /path/to/fire_detection.onnx
```

Listens on `0.0.0.0:8080`. Send POST to `/predict` with body either:
- **Raw**: 150528 bytes (RGB 224×224), or  
- **Base64**: same image encoded as base64.

Response: `{"class":"fire"|"normal","confidence":<float>}`.

## Docker

Build (from repo root; ensure `app/model/fire_detection.onnx` exists or mount it at run time):

```bash
docker build -f app/Dockerfile -t fire-backend ./app
```

Run with model mounted:

```bash
docker run -p 8080:8080 -v "$(pwd)/app/model:/app/model" fire-backend
```

Or copy the model into the image by adding to the Dockerfile before `EXPOSE`:  
`COPY model/ /app/model/` (when building with context `app/` and `app/model/` present).

## Layout

- `CMakeLists.txt` — build with ONNX Runtime
- `include/preprocess.h` — ImageNet normalization, `preprocess_rgb224()`
- `src/main.cpp` — HTTP server, ONNX inference, JSON response
- `Dockerfile` — multi-stage build for a small runtime image
