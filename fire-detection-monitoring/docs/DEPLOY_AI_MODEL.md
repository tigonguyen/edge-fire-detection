# Hướng dẫn triển khai Fire Detection với AI Model thật

## Tổng quan

Hệ thống Fire Detection hỗ trợ 2 chế độ:
1. **Simulation Mode**: Giả lập detection để test (không cần AI model)
2. **Production Mode**: Sử dụng AI model thật để phát hiện lửa/khói

Tài liệu này hướng dẫn triển khai với **AI model thật**.

---

## Kiến trúc hệ thống

```
┌─────────────────┐     MQTT (wildfire/images)     ┌──────────────────┐
│   Edge Device   │ ─────────────────────────────► │  Fire Exporter   │
│  (Camera/Drone) │                                │  + AI Model      │
└─────────────────┘                                └────────┬─────────┘
                                                            │
                                                   ┌────────▼─────────┐
                                                   │   Prometheus     │
                                                   │   + Grafana      │
                                                   └──────────────────┘
```

**Luồng xử lý:**
1. Edge device chụp ảnh và gửi qua MQTT topic `wildfire/images`
2. Fire Exporter nhận ảnh và chạy AI model
3. Nếu phát hiện lửa/khói → tạo alert + gửi notification
4. Metrics được cập nhật và hiển thị trên Grafana

---

## Bước 1: Chuẩn bị AI Model

### 1.1. Yêu cầu model

Model cần có khả năng:
- Input: Ảnh RGB (JPEG/PNG)
- Output:
  - `detected`: boolean (có phát hiện lửa/khói không)
  - `class`: string (`fire`, `smoke`, hoặc `none`)
  - `confidence`: float (0.0 - 1.0)

### 1.2. Các loại model được hỗ trợ

| Loại | File extension | Framework |
|------|---------------|-----------|
| ONNX | `.onnx` | ONNX Runtime |
| TensorFlow | `.pb`, `.h5` | TensorFlow/Keras |
| PyTorch | `.pt`, `.pth` | PyTorch |
| TFLite | `.tflite` | TensorFlow Lite |

### 1.3. Download pre-trained model (tùy chọn)

Một số model fire detection có sẵn:

```bash
# Ví dụ: Download YOLO fire detection model
wget https://example.com/fire-detection-yolov8.onnx -O models/fire_detection.onnx
```

Hoặc train model của riêng bạn với dataset:
- [Fire-Smoke-Dataset](https://github.com/DeepQuestAI/Fire-Smoke-Dataset)
- [FLAME Dataset](https://ieee-dataport.org/open-access/flame-dataset)

---

## Bước 2: Implement FireDetector

### 2.1. Cập nhật file `fire_detector.py`

Mở file `exporter/fire_detector.py` và implement method `_detect_with_model()`:

```python
# exporter/fire_detector.py
import numpy as np
from dataclasses import dataclass
from typing import Optional

@dataclass
class DetectionResult:
    detected: bool
    detection_class: str  # 'fire', 'smoke', or 'none'
    confidence: float

class FireDetector:
    def __init__(
        self,
        simulate_fire: bool = False,
        simulate_smoke: bool = False,
        model_path: Optional[str] = None
    ):
        self.simulate_fire = simulate_fire
        self.simulate_smoke = simulate_smoke
        self.model_path = model_path
        self.model = None

        # Load model nếu có path
        if model_path and not (simulate_fire or simulate_smoke):
            self._load_model(model_path)

    def _load_model(self, model_path: str):
        """Load AI model từ file"""
        print(f"[DETECTOR] Loading model: {model_path}")

        if model_path.endswith('.onnx'):
            self._load_onnx_model(model_path)
        elif model_path.endswith('.pt') or model_path.endswith('.pth'):
            self._load_pytorch_model(model_path)
        elif model_path.endswith('.tflite'):
            self._load_tflite_model(model_path)
        else:
            raise ValueError(f"Unsupported model format: {model_path}")

    def _load_onnx_model(self, model_path: str):
        """Load ONNX model"""
        import onnxruntime as ort
        self.model = ort.InferenceSession(model_path)
        self.model_type = 'onnx'
        print(f"[DETECTOR] ONNX model loaded successfully")

    def _load_pytorch_model(self, model_path: str):
        """Load PyTorch model"""
        import torch
        self.model = torch.load(model_path, map_location='cpu')
        self.model.eval()
        self.model_type = 'pytorch'
        print(f"[DETECTOR] PyTorch model loaded successfully")

    def _load_tflite_model(self, model_path: str):
        """Load TFLite model"""
        import tensorflow as tf
        self.model = tf.lite.Interpreter(model_path)
        self.model.allocate_tensors()
        self.model_type = 'tflite'
        print(f"[DETECTOR] TFLite model loaded successfully")

    def detect(self, image_data: bytes) -> DetectionResult:
        """
        Phát hiện lửa/khói trong ảnh.

        Args:
            image_data: Raw bytes của ảnh (JPEG/PNG)

        Returns:
            DetectionResult với detected, class, và confidence
        """
        # Simulation mode
        if self.simulate_fire:
            return DetectionResult(
                detected=True,
                detection_class='fire',
                confidence=0.85 + (hash(image_data[:100]) % 15) / 100
            )

        if self.simulate_smoke:
            return DetectionResult(
                detected=True,
                detection_class='smoke',
                confidence=0.75 + (hash(image_data[:100]) % 20) / 100
            )

        # Real model detection
        if self.model is None:
            print("[DETECTOR] No model loaded, returning no detection")
            return DetectionResult(
                detected=False,
                detection_class='none',
                confidence=0.0
            )

        return self._detect_with_model(image_data)

    def _detect_with_model(self, image_data: bytes) -> DetectionResult:
        """Chạy AI model để detect"""
        import cv2

        # Decode image
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return DetectionResult(False, 'none', 0.0)

        # Preprocess (điều chỉnh theo model của bạn)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_resized = cv2.resize(image_rgb, (224, 224))  # Resize theo input size của model
        image_normalized = image_resized.astype(np.float32) / 255.0
        image_batch = np.expand_dims(image_normalized, axis=0)

        # Run inference
        if self.model_type == 'onnx':
            return self._run_onnx_inference(image_batch)
        elif self.model_type == 'pytorch':
            return self._run_pytorch_inference(image_batch)
        elif self.model_type == 'tflite':
            return self._run_tflite_inference(image_batch)

        return DetectionResult(False, 'none', 0.0)

    def _run_onnx_inference(self, image_batch: np.ndarray) -> DetectionResult:
        """Run ONNX model inference"""
        input_name = self.model.get_inputs()[0].name
        outputs = self.model.run(None, {input_name: image_batch})

        # Giả sử output là [fire_prob, smoke_prob, normal_prob]
        probs = outputs[0][0]

        fire_prob = probs[0]
        smoke_prob = probs[1]

        if fire_prob > 0.5:
            return DetectionResult(True, 'fire', float(fire_prob))
        elif smoke_prob > 0.5:
            return DetectionResult(True, 'smoke', float(smoke_prob))

        return DetectionResult(False, 'none', 0.0)

    def _run_pytorch_inference(self, image_batch: np.ndarray) -> DetectionResult:
        """Run PyTorch model inference"""
        import torch

        # Convert to tensor
        tensor = torch.from_numpy(image_batch).permute(0, 3, 1, 2)

        with torch.no_grad():
            outputs = self.model(tensor)
            probs = torch.softmax(outputs, dim=1)[0]

        fire_prob = probs[0].item()
        smoke_prob = probs[1].item()

        if fire_prob > 0.5:
            return DetectionResult(True, 'fire', fire_prob)
        elif smoke_prob > 0.5:
            return DetectionResult(True, 'smoke', smoke_prob)

        return DetectionResult(False, 'none', 0.0)

    def _run_tflite_inference(self, image_batch: np.ndarray) -> DetectionResult:
        """Run TFLite model inference"""
        input_details = self.model.get_input_details()
        output_details = self.model.get_output_details()

        self.model.set_tensor(input_details[0]['index'], image_batch)
        self.model.invoke()

        probs = self.model.get_tensor(output_details[0]['index'])[0]

        fire_prob = probs[0]
        smoke_prob = probs[1]

        if fire_prob > 0.5:
            return DetectionResult(True, 'fire', float(fire_prob))
        elif smoke_prob > 0.5:
            return DetectionResult(True, 'smoke', float(smoke_prob))

        return DetectionResult(False, 'none', 0.0)
```

### 2.2. Cài đặt dependencies

Thêm vào `requirements.txt`:

```txt
# AI/ML frameworks (chọn framework phù hợp với model)
onnxruntime>=1.16.0        # Cho ONNX model
# torch>=2.0.0             # Cho PyTorch model
# tensorflow>=2.15.0       # Cho TensorFlow model
opencv-python-headless>=4.8.0
numpy>=1.24.0
```

---

## Bước 3: Triển khai với Docker

### 3.1. Cấu trúc thư mục

```
fire-detection-monitoring/
├── models/
│   └── fire_detection.onnx    # <-- Đặt model ở đây
├── exporter/
│   ├── fire_detector.py
│   ├── main.py
│   └── ...
├── docker-compose.yml
└── .env
```

### 3.2. Cập nhật docker-compose.yml

```yaml
services:
  exporter:
    build: ./exporter
    container_name: fire_exporter
    ports:
      - "8000:8000"
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - SIMULATE_FIRE=false          # Tắt simulation
      - SIMULATE_SMOKE=false         # Tắt simulation
      - FIRE_MODEL_PATH=/app/models/fire_detection.onnx
      - ALERT_COOLDOWN_SECONDS=300
    volumes:
      - ./images:/app/images
      - ./models:/app/models:ro      # Mount thư mục models
    depends_on:
      - mosquitto
```

### 3.3. Cập nhật Dockerfile

Thêm vào `exporter/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy và install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create directories
RUN mkdir -p /app/images /app/models

CMD ["python", "main.py"]
```

### 3.4. Khởi động hệ thống

```bash
# Build và start
docker-compose up -d --build

# Kiểm tra logs
docker logs -f fire_exporter
```

---

## Bước 4: Triển khai Local (không Docker)

### 4.1. Cài đặt môi trường

```bash
cd fire-detection-monitoring/exporter

# Tạo virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc: venv\Scripts\activate  # Windows

# Cài đặt dependencies
pip install -r requirements.txt
```

### 4.2. Đặt model vào thư mục

```bash
mkdir -p ../models
cp /path/to/your/fire_detection.onnx ../models/
```

### 4.3. Chạy với model thật

```bash
# Set environment variables
export SIMULATE_FIRE=false
export SIMULATE_SMOKE=false
export FIRE_MODEL_PATH="../models/fire_detection.onnx"
export ALERT_COOLDOWN_SECONDS=300

# Chạy
./run.sh start-local
```

Hoặc một dòng:

```bash
FIRE_MODEL_PATH="../models/fire_detection.onnx" ./run.sh start-local
```

---

## Bước 5: Test hệ thống

### 5.1. Test với ảnh có lửa

```bash
cd fire-detection-monitoring

# Test với 1 ảnh
python test_fire_alerts.py --test image --image /path/to/fire_image.jpg

# Test với video
python test_fire_alerts.py --test video \
    --video /path/to/fire_video.mp4 \
    --interval 2 \
    --max-frames 50
```

### 5.2. Kiểm tra kết quả

```bash
# Xem active alerts
curl http://localhost:8000/alerts | python -m json.tool

# Xem scan history (tất cả ảnh đã scan)
curl http://localhost:8000/scan-history | python -m json.tool

# Xem scan history (chỉ detected)
curl "http://localhost:8000/scan-history?detected_only=true" | python -m json.tool
```

### 5.3. Kiểm tra trên Grafana

1. Mở Grafana: http://localhost:3000
2. Đăng nhập: admin / admin123
3. Vào Dashboard "Fire Detection"
4. Kiểm tra:
   - Geomap có hiển thị vị trí alert không
   - Alert table có thông tin đúng không
   - Confidence gauge có cập nhật không

---

## Bước 6: Cấu hình Production

### 6.1. Environment variables

| Variable | Mô tả | Default |
|----------|-------|---------|
| `SIMULATE_FIRE` | Bật/tắt simulation mode | `false` |
| `SIMULATE_SMOKE` | Bật/tắt simulation mode | `false` |
| `FIRE_MODEL_PATH` | Đường dẫn tới model file | - |
| `ALERT_COOLDOWN_SECONDS` | Cooldown giữa các alert cùng vị trí | `300` |
| `MQTT_BROKER` | MQTT broker hostname | `localhost` |
| `MQTT_PORT` | MQTT broker port | `1883` |

### 6.2. File .env (ví dụ)

```bash
# .env
SIMULATE_FIRE=false
SIMULATE_SMOKE=false
FIRE_MODEL_PATH=/app/models/fire_detection.onnx
ALERT_COOLDOWN_SECONDS=300

TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 6.3. Tối ưu performance

```yaml
# docker-compose.yml - thêm resource limits
services:
  exporter:
    # ...
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

---

## Troubleshooting

### Model không load được

```
[DETECTOR] No model loaded, returning no detection
```

**Giải pháp:**
1. Kiểm tra path model có đúng không
2. Kiểm tra file model có tồn tại không
3. Kiểm tra định dạng model có được hỗ trợ không

### ONNX Runtime error

```
onnxruntime.capi.onnxruntime_pybind11_state.InvalidArgument
```

**Giải pháp:**
1. Kiểm tra input shape của model
2. Điều chỉnh preprocessing (resize, normalize)

### Memory không đủ

```
MemoryError: Unable to allocate array
```

**Giải pháp:**
1. Giảm kích thước ảnh input
2. Sử dụng TFLite thay vì full model
3. Tăng memory limit trong Docker

### Không nhận được ảnh từ MQTT

```
[IMAGE] No image data in payload, skipping
```

**Giải pháp:**
1. Kiểm tra edge device có gửi `image_base64` không
2. Kiểm tra kết nối MQTT
3. Kiểm tra topic có đúng `wildfire/images` không

---

## Tài liệu tham khảo

- [ONNX Runtime Documentation](https://onnxruntime.ai/docs/)
- [OpenCV Python Tutorial](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
- [Fire Detection Dataset](https://github.com/DeepQuestAI/Fire-Smoke-Dataset)
- [YOLO Fire Detection](https://github.com/ultralytics/ultralytics)

---

## Checklist triển khai

- [ ] Chuẩn bị AI model (ONNX/PyTorch/TFLite)
- [ ] Cập nhật `fire_detector.py` với inference code
- [ ] Cài đặt dependencies (onnxruntime, opencv, etc.)
- [ ] Đặt model vào thư mục `models/`
- [ ] Cấu hình environment variables (tắt simulation)
- [ ] Test với ảnh có lửa
- [ ] Test với video
- [ ] Kiểm tra Grafana dashboard
- [ ] Cấu hình Telegram notification
- [ ] Deploy lên production server
