# Quick Start Guide - C++ Fire Detection App

## 🚀 Quick Setup (5 minutes)

### Step 1: Export Model to TorchScript

```bash
cd /Users/tigonguyen/Documents/DevOps/repos/personal-projects/edge-fire-detection

# Activate virtual environment
source venv/bin/activate

# Export the trained model
python export_torchscript.py
```

**Output**: `fire_detection_scripted.pt` (TorchScript model for C++)

### Step 2: Install Dependencies (if not already installed)

#### macOS:
```bash
# Install OpenCV
brew install opencv

# Download LibTorch (CPU version)
cd ~/Downloads
curl -o libtorch.zip https://download.pytorch.org/libtorch/cpu/libtorch-macos-x86_64-2.1.0.zip
unzip libtorch.zip
sudo mv libtorch /usr/local/
```

#### Linux:
```bash
# Install OpenCV
sudo apt-get update
sudo apt-get install libopencv-dev

# Download LibTorch (CPU version)
cd ~/Downloads
wget https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-2.1.0%2Bcpu.zip
unzip libtorch-cxx11-abi-shared-with-deps-2.1.0+cpu.zip
sudo mv libtorch /usr/local/
```

### Step 3: Build the Application

```bash
cd app
./build.sh
```

This will:
- Check dependencies
- Configure with CMake
- Build the executable

### Step 4: Run Fire Detection

```bash
cd build

# Basic usage
./fire_detector \
  --video "../../Forest Fire with Drone Support.mp4" \
  --model ../../fire_detection_scripted.pt

# With options
./fire_detector \
  --video "../../Forest Fire with Drone Support.mp4" \
  --model ../../fire_detection_scripted.pt \
  --threshold 0.8 \
  --save
```

## 🎮 Controls

- **SPACE**: Pause/Resume
- **Q** or **ESC**: Quit

## 📊 What You'll See

The app displays:
- 🔥 **Fire Detection Status** with confidence
- ⚡ **Inference Time** per frame
- 📈 **Class Probabilities** with visual bars
- 🎯 **Real-time Video** with overlays

## 🎥 Expected Output

```
============================================================
🔥 Fire Detection Video Stream Processor
============================================================
Video: Forest Fire with Drone Support.mp4
Model: fire_detection_scripted.pt
Threshold: 0.8
============================================================

CUDA is available! Using GPU.
✅ Model loaded successfully

Video properties:
  Resolution: 1920x1080
  FPS: 30.0
  Total frames: 1500

▶️  Processing video stream...
------------------------------------------------------------
🔥 ALERT [Frame 45]: Fire detected! Confidence: 92.3%
📊 Processed: 30/1500 frames (2.0%)
...
```

## 🐛 Troubleshooting

### Build Errors

**"OpenCV not found"**
```bash
# macOS
brew install opencv

# Linux
sudo apt-get install libopencv-dev
```

**"Torch not found"**
```bash
# Make sure LibTorch is in /usr/local/libtorch
# Or specify custom path in CMakeLists.txt
```

### Runtime Errors

**"Error loading model"**
- Make sure you ran `python export_torchscript.py`
- Check that `fire_detection_scripted.pt` exists

**"Error opening video file"**
- Verify the video file path is correct
- Ensure OpenCV was built with FFMPEG support

**Slow performance**
- Use GPU version of LibTorch if available
- Reduce video resolution
- Increase frame skip interval

## 📝 Manual Build (if build.sh fails)

```bash
cd app
mkdir -p build
cd build

# Configure
cmake .. \
  -DCMAKE_PREFIX_PATH="/usr/local/libtorch;/usr/local/opt/opencv" \
  -DCMAKE_BUILD_TYPE=Release

# Build
cmake --build . --config Release

# Run
./fire_detector --help
```

## 🔗 Next Steps

- Test on different videos
- Adjust confidence threshold
- Integrate with alert system
- Deploy on edge devices

## 📚 Full Documentation

See `app/README.md` for complete documentation.

