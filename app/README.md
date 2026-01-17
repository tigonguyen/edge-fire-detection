# Fire Detection C++ Application

Real-time fire detection application that processes video streams using a trained PyTorch model.

## Overview

This C++ application simulates receiving a video stream and performs real-time fire detection using the trained EfficientNet-B0 model. It provides:

- 🎥 Video stream processing with real-time inference
- 🔥 Fire detection with confidence scoring
- 📊 Visual overlay with detection results
- 💾 Optional output video saving
- ⚡ GPU acceleration support (CUDA)
- 📈 Performance statistics and metrics

## Features

- **Real-time Detection**: Process video frames and detect fire with low latency
- **Visual Feedback**: Overlay detection results, confidence scores, and probabilities on video
- **Flexible Input**: Support for various video formats and sources
- **Performance Metrics**: Track inference time, FPS, and detection statistics
- **Interactive Controls**: Pause/resume playback, quit on demand
- **Output Recording**: Save processed video with detection overlays

## Architecture

```
┌─────────────────┐
│  Video Stream   │
│   (MP4, AVI)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Frame Capture  │
│   (OpenCV)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Preprocessing  │
│ - Resize 224x224│
│ - Normalize     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Inference     │
│  (LibTorch)     │
│  EfficientNet   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Post-processing │
│ - Softmax       │
│ - Threshold     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Visualization  │
│ - Draw overlay  │
│ - Display       │
└─────────────────┘
```

## Requirements

### System Dependencies

- **C++ Compiler**: GCC 7+ or Clang 5+ with C++17 support
- **CMake**: Version 3.14 or higher
- **OpenCV**: Version 4.x (for video processing and display)
- **LibTorch**: PyTorch C++ API (for model inference)
- **CUDA**: Optional, for GPU acceleration

### Installing Dependencies

#### macOS (using Homebrew)

```bash
# Install OpenCV
brew install opencv

# Install LibTorch
# Download from: https://pytorch.org/get-started/locally/
# Select C++/LibTorch, your platform, and CUDA version (or CPU)
cd ~/Downloads
wget https://download.pytorch.org/libtorch/cpu/libtorch-macos-x86_64-2.1.0.zip
unzip libtorch-macos-x86_64-2.1.0.zip
sudo mv libtorch /usr/local/
```

#### Ubuntu/Linux

```bash
# Install OpenCV
sudo apt-get update
sudo apt-get install libopencv-dev

# Install LibTorch
cd ~/Downloads
wget https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-2.1.0%2Bcpu.zip
unzip libtorch-cxx11-abi-shared-with-deps-2.1.0+cpu.zip
sudo mv libtorch /usr/local/
```

## Building the Application

### Step 1: Export PyTorch Model to TorchScript

Before building the C++ app, you need to convert the PyTorch model to TorchScript format:

```bash
# Create a conversion script
cd /path/to/edge-fire-detection
```

Create `export_torchscript.py`:

```python
import torch
import timm

# Load your trained model
checkpoint = torch.load('fire_detection_best.pth', map_location='cpu')
model = timm.create_model('efficientnet_b0', pretrained=False, num_classes=2)
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()

# Create example input
example_input = torch.rand(1, 3, 224, 224)

# Convert to TorchScript
traced_script_module = torch.jit.trace(model, example_input)

# Save the model
traced_script_module.save("fire_detection_scripted.pt")
print("✅ Model exported to: fire_detection_scripted.pt")
```

Run the conversion:

```bash
python export_torchscript.py
```

### Step 2: Build the C++ Application

```bash
cd app
mkdir -p build
cd build

# Configure with CMake (adjust paths as needed)
cmake .. \
  -DCMAKE_PREFIX_PATH="/usr/local/libtorch;/usr/local/opt/opencv" \
  -DCMAKE_BUILD_TYPE=Release

# Build
cmake --build . --config Release

# The executable will be in build/fire_detector
```

### Build Troubleshooting

If CMake can't find LibTorch or OpenCV:

```bash
# Specify paths explicitly
cmake .. \
  -DCMAKE_PREFIX_PATH="/usr/local/libtorch" \
  -DOpenCV_DIR="/usr/local/opt/opencv/lib/cmake/opencv4" \
  -DCMAKE_BUILD_TYPE=Release
```

## Usage

### Basic Usage

```bash
# Run with video file
./fire_detector --video /path/to/video.mp4 --model /path/to/fire_detection_scripted.pt
```

### Command Line Options

```
Options:
  --video <path>       Path to video file (required)
  --model <path>       Path to TorchScript model (required)
  --threshold <float>  Confidence threshold for fire detection (default: 0.8)
  --save               Save output video with detection overlays
  --help               Show help message
```

### Examples

```bash
# Basic fire detection
./fire_detector --video forest.mp4 --model ../fire_detection_scripted.pt

# With custom threshold
./fire_detector --video forest.mp4 --model ../fire_detection_scripted.pt --threshold 0.85

# Save output video
./fire_detector --video forest.mp4 --model ../fire_detection_scripted.pt --save

# Full example from project root
cd /Users/tigonguyen/Documents/DevOps/repos/personal-projects/edge-fire-detection
./app/build/fire_detector \
  --video "Forest Fire with Drone Support.mp4" \
  --model fire_detection_scripted.pt \
  --threshold 0.8 \
  --save
```

### Interactive Controls

While the application is running:

- **SPACE**: Pause/resume video playback
- **Q** or **ESC**: Quit the application

## Output

### Visual Display

The application displays the video with an overlay showing:

- **Detection Status**: "🔥 FIRE DETECTED!" or "✓ Normal"
- **Confidence Score**: Percentage confidence of the prediction
- **Inference Time**: Time taken for each frame (in milliseconds)
- **Class Probabilities**: Visual bars showing probability for each class
- **Frame Number**: Current frame being processed

### Console Output

```
============================================================
🔥 Fire Detection Video Stream Processor
============================================================
Video: forest.mp4
Model: fire_detection_scripted.pt
Threshold: 0.8
============================================================

CUDA is available! Using GPU.
✅ Model loaded successfully from: fire_detection_scripted.pt

Video properties:
  Resolution: 1920x1080
  FPS: 30.0
  Total frames: 1500

💾 Saving output to: output_fire_detection.mp4
▶️  Processing video stream... (Press 'q' to quit, SPACE to pause)
------------------------------------------------------------
🔥 ALERT [Frame 45]: Fire detected! Confidence: 92.3%
📊 Processed: 30/1500 frames (2.0%)
🔥 ALERT [Frame 67]: Fire detected! Confidence: 89.5%
📊 Processed: 60/1500 frames (4.0%)
...

✅ End of video stream

============================================================
📊 Detection Statistics
============================================================
Total frames processed: 1500
Fire detections: 234 (15.6%)
Average inference time: 23.4 ms
Frames per second: 42.7 fps
============================================================

============================================================
📈 Processing Summary
============================================================
Total processing time: 35.12 seconds
Average FPS: 42.7
Fire alerts: 234
============================================================
```

## Performance

### Typical Performance Metrics

| Configuration | Inference Time | FPS | Notes |
|--------------|----------------|-----|-------|
| CPU (Intel i7) | 40-60 ms | 16-25 | Good for development |
| GPU (NVIDIA RTX 3080) | 8-15 ms | 65-125 | Recommended for production |
| CPU (ARM/M1) | 25-40 ms | 25-40 | Good efficiency |

### Optimization Tips

1. **Use GPU**: Enable CUDA for 3-5x speedup
2. **Batch Processing**: Process multiple frames at once
3. **Resolution**: Lower input resolution for faster inference
4. **Threading**: Use async processing for video I/O

## Code Structure

```
app/
├── CMakeLists.txt           # Build configuration
├── README.md                # This file
├── include/
│   └── fire_detector.h      # FireDetector class header
├── src/
│   ├── main.cpp            # Main application logic
│   └── fire_detector.cpp   # FireDetector implementation
└── build/                   # Build output directory
```

### Key Classes

#### `FireDetector`

Core detection class that handles:
- Model loading and initialization
- Frame preprocessing (resize, normalize)
- Inference with LibTorch
- Result post-processing
- Performance statistics

**Key Methods**:
- `FireDetector(model_path, threshold)`: Constructor
- `detect(frame)`: Perform detection on a frame
- `preprocess(frame)`: Preprocess frame for model input
- `printStatistics()`: Display detection statistics

#### `DetectionResult`

Struct containing detection results:
- `frame_number`: Frame index
- `predicted_class`: Class ID (0=fire, 1=normal)
- `class_name`: Human-readable class name
- `confidence`: Prediction confidence (0-1)
- `is_fire`: Boolean fire detection flag
- `inference_time_ms`: Inference duration
- `class_probabilities`: Map of class names to probabilities

## Extending the Application

### Adding New Features

#### 1. Add Alert System

```cpp
// In main.cpp
if (result.is_fire) {
    sendAlert(result); // Implement MQTT/HTTP alert
}
```

#### 2. Add Multiple Video Sources

```cpp
// Support RTSP streams
cap.open("rtsp://camera-ip:554/stream");

// Support webcam
cap.open(0); // Default camera
```

#### 3. Add Frame Skip for Performance

```cpp
// Process every Nth frame
if (frame_count % 3 == 0) {
    result = detector.detect(frame);
}
```

#### 4. Add Logging

```cpp
#include <fstream>
std::ofstream log_file("detections.log");
if (result.is_fire) {
    log_file << timestamp << "," << result.confidence << std::endl;
}
```

## Troubleshooting

### Common Issues

**Issue**: `error: 'torch/script.h' file not found`
- **Solution**: Ensure LibTorch is installed and CMAKE_PREFIX_PATH includes the libtorch directory

**Issue**: `OpenCV not found`
- **Solution**: Install OpenCV and specify OpenCV_DIR in CMake configuration

**Issue**: Slow inference on CPU
- **Solution**: Install CUDA and use GPU-enabled LibTorch, or reduce video resolution

**Issue**: Model loading fails
- **Solution**: Verify the TorchScript model was exported correctly with `torch.jit.trace()`

**Issue**: Video file not opening
- **Solution**: Ensure OpenCV was built with video codec support (FFMPEG)

## Integration with ESP32 Edge Deployment

This C++ application demonstrates the model inference pipeline that will be deployed on ESP32 devices. Key similarities:

- Same preprocessing steps (resize, normalize)
- Same model architecture (EfficientNet-B0)
- Same confidence threshold logic
- Similar performance metrics

For ESP32 deployment, the model will be:
1. Quantized to INT8
2. Converted to TensorFlow Lite format
3. Integrated with TensorFlow Lite Micro

## License

MIT License - see parent project LICENSE file

## Support

For issues or questions, please open an issue in the main project repository.

---

**Note**: This application is designed for testing and demonstration. For production deployment, consider additional features like error handling, logging, monitoring, and integration with alerting systems.

