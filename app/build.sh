#!/bin/bash
# Build script for Fire Detection C++ Application

set -e  # Exit on error

echo "============================================================"
echo "🔨 Building Fire Detection C++ Application"
echo "============================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "CMakeLists.txt" ]; then
    echo -e "${RED}❌ Error: CMakeLists.txt not found${NC}"
    echo "Please run this script from the app/ directory"
    exit 1
fi

# Check for required dependencies
echo -e "\n${YELLOW}🔍 Checking dependencies...${NC}"

# Check for CMake
if ! command -v cmake &> /dev/null; then
    echo -e "${RED}❌ CMake not found. Please install CMake 3.14+${NC}"
    exit 1
fi
echo -e "${GREEN}✅ CMake found: $(cmake --version | head -n1)${NC}"

# Check for OpenCV
if [ "$(uname)" == "Darwin" ]; then
    # macOS
    OPENCV_PATH="/usr/local/opt/opencv"
    if [ ! -d "$OPENCV_PATH" ]; then
        echo -e "${YELLOW}⚠️  OpenCV not found at $OPENCV_PATH${NC}"
        echo "Install with: brew install opencv"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}✅ OpenCV found at $OPENCV_PATH${NC}"
    fi
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
    # Linux
    if ! pkg-config --exists opencv4; then
        echo -e "${YELLOW}⚠️  OpenCV not found${NC}"
        echo "Install with: sudo apt-get install libopencv-dev"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}✅ OpenCV found: $(pkg-config --modversion opencv4)${NC}"
    fi
fi

# Check for LibTorch
LIBTORCH_PATH="/usr/local/libtorch"
if [ ! -d "$LIBTORCH_PATH" ]; then
    echo -e "${YELLOW}⚠️  LibTorch not found at $LIBTORCH_PATH${NC}"
    echo "Download from: https://pytorch.org/get-started/locally/"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✅ LibTorch found at $LIBTORCH_PATH${NC}"
fi

# Check if TorchScript model exists
echo -e "\n${YELLOW}🔍 Checking for TorchScript model...${NC}"
MODEL_PATH="../fire_detection_scripted.pt"
if [ ! -f "$MODEL_PATH" ]; then
    echo -e "${YELLOW}⚠️  TorchScript model not found at $MODEL_PATH${NC}"
    echo "Export the model first:"
    echo "  cd .."
    echo "  python export_torchscript.py"
    read -p "Continue building anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✅ TorchScript model found${NC}"
fi

# Create build directory
echo -e "\n${YELLOW}📁 Creating build directory...${NC}"
mkdir -p build
cd build

# Configure with CMake
echo -e "\n${YELLOW}⚙️  Configuring with CMake...${NC}"

CMAKE_PREFIX_PATH=""
if [ "$(uname)" == "Darwin" ]; then
    CMAKE_PREFIX_PATH="/usr/local/libtorch;/usr/local/opt/opencv"
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
    CMAKE_PREFIX_PATH="/usr/local/libtorch"
fi

cmake .. \
    -DCMAKE_PREFIX_PATH="$CMAKE_PREFIX_PATH" \
    -DCMAKE_BUILD_TYPE=Release

# Build
echo -e "\n${YELLOW}🔨 Building...${NC}"
cmake --build . --config Release -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

# Check if build succeeded
if [ -f "fire_detector" ]; then
    echo -e "\n${GREEN}============================================================${NC}"
    echo -e "${GREEN}✅ Build completed successfully!${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo -e "\n📝 Executable location: $(pwd)/fire_detector"
    echo -e "\n🚀 Usage:"
    echo "  ./fire_detector --video <video_file> --model ../fire_detection_scripted.pt"
    echo ""
    echo "Example:"
    echo "  ./fire_detector --video ../../'Forest Fire with Drone Support.mp4' \\"
    echo "                  --model ../../fire_detection_scripted.pt \\"
    echo "                  --threshold 0.8 \\"
    echo "                  --save"
    echo ""
else
    echo -e "\n${RED}============================================================${NC}"
    echo -e "${RED}❌ Build failed!${NC}"
    echo -e "${RED}============================================================${NC}"
    exit 1
fi

