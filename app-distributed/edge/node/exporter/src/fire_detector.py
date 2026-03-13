# exporter/fire_detector.py
"""
Fire Detection Module

This module provides an interface for fire detection AI model.
Currently uses simulation mode with a flag. Replace with actual AI model later.

Usage:
    detector = FireDetector(simulate_fire=True)  # Always detect fire (for testing)
    detector = FireDetector(simulate_fire=False)  # No detection (default)
    detector = FireDetector(model_path="path/to/model")  # Use real AI model (future)

    result = detector.detect(image_bytes)
    # Returns: {"detected": True/False, "class": "fire"/"smoke"/None, "confidence": 0.0-1.0}
"""

import os
import random
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum


class DetectionClass(Enum):
    FIRE = "fire"
    SMOKE = "smoke"
    NONE = None


@dataclass
class DetectionResult:
    """Result from fire detection"""
    detected: bool
    detection_class: Optional[str]  # "fire", "smoke", or None
    confidence: float  # 0.0 - 1.0

    def to_dict(self) -> dict:
        return {
            "detected": self.detected,
            "class": self.detection_class,
            "confidence": self.confidence
        }


class FireDetector:
    """
    Fire detection interface.

    Modes:
    - simulate_fire=True: Always return fire detection (for testing)
    - simulate_fire=False: Never detect fire (default)
    - model_path provided: Use real AI model (future implementation)
    """

    def __init__(
        self,
        simulate_fire: bool = False,
        simulate_smoke: bool = False,
        model_path: Optional[str] = None,
        confidence_min: float = 0.75,
        confidence_max: float = 0.95
    ):
        """
        Initialize fire detector.

        Args:
            simulate_fire: If True, always detect fire (for testing)
            simulate_smoke: If True, always detect smoke (for testing)
            model_path: Path to AI model file (future use)
            confidence_min: Minimum confidence for simulated detections
            confidence_max: Maximum confidence for simulated detections
        """
        self.simulate_fire = simulate_fire
        self.simulate_smoke = simulate_smoke
        self.model_path = model_path
        self.confidence_min = confidence_min
        self.confidence_max = confidence_max
        self.model = None

        # Load model if path provided
        if model_path and os.path.exists(model_path):
            self._load_model(model_path)

        mode = "SIMULATION" if (simulate_fire or simulate_smoke) else "DISABLED"
        if self.model:
            mode = "AI MODEL"
        print(f"[FireDetector] Initialized in {mode} mode")
        if simulate_fire:
            print(f"  - simulate_fire=True (will always detect fire)")
        if simulate_smoke:
            print(f"  - simulate_smoke=True (will always detect smoke)")

    def _load_model(self, model_path: str):
        """
        Load AI model from file using ONNX Runtime.
        """
        print(f"[FireDetector] Loading ONNX model from: {model_path}")
        try:
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 2
            self.session = ort.InferenceSession(model_path, options)
            self.input_name = self.session.get_inputs()[0].name
            self.model = {"path": model_path, "loaded": True}
            print(f"[FireDetector] ONNX Model loaded successfully. Input: {self.input_name}")
        except Exception as e:
            print(f"[FireDetector] Failed to load ONNX model: {e}")
            self.model = None

    def detect(self, image_data: bytes) -> DetectionResult:
        """
        Detect fire/smoke in image.

        Args:
            image_data: Raw image bytes (JPEG, PNG, etc.)

        Returns:
            DetectionResult with detected, class, and confidence
        """
        # If real model is loaded, use it
        if self.model:
            return self._detect_with_model(image_data)

        # Simulation mode
        if self.simulate_fire:
            confidence = self._random_confidence()
            return DetectionResult(
                detected=True,
                detection_class="fire",
                confidence=confidence
            )

        if self.simulate_smoke:
            confidence = self._random_confidence()
            return DetectionResult(
                detected=True,
                detection_class="smoke",
                confidence=confidence
            )

        # No detection
        return DetectionResult(
            detected=False,
            detection_class=None,
            confidence=0.0
        )

    def _detect_with_model(self, image_data: bytes) -> DetectionResult:
        """
        Run actual AI model inference.
        """
        import numpy as np
        from PIL import Image
        import io
        import math

        try:
            # 1. Decode image using Pillow and resize to 224x224 (matching C++ expectations)
            img = Image.open(io.BytesIO(image_data)).convert('RGB')
            img = img.resize((224, 224), Image.Resampling.BILINEAR)

            # 2. Normalize and transpose to PyTorch layout: 1xCxHxW
            img_arr = np.array(img, dtype=np.float32) / 255.0

            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            img_normalized = (img_arr - mean) / std

            # Transpose HWC to CWH (C++ uses CxHxW)
            img_transposed = np.transpose(img_normalized, (2, 0, 1))
            # Expand to batch dimension
            tensor = np.expand_dims(img_transposed, axis=0)

            # 3. ONNX Inference
            results = self.session.run(None, {self.input_name: tensor})
            logits = results[0][0]  # shape (num_classes,)

            # 4. Softmax
            max_val = np.max(logits)
            exp_logits = np.exp(logits - max_val)
            sum_exp = np.sum(exp_logits)
            probs = exp_logits / sum_exp

            best_idx = int(np.argmax(probs))
            confidence = float(probs[best_idx])

            # Class names: 0 -> fire, 1 -> normal
            class_map = {0: "fire", 1: "normal"}
            pred_class = class_map.get(best_idx, "unknown")

            return DetectionResult(
                detected=(pred_class == "fire"),
                detection_class=pred_class if pred_class == "fire" else None,
                confidence=confidence
            )
        except Exception as e:
            print(f"[FireDetector] Error running inference: {e}")
            return DetectionResult(
                detected=False,
                detection_class=None,
                confidence=0.0
            )

    def _random_confidence(self) -> float:
        """Generate random confidence within configured range"""
        return self.confidence_min + random.random() * (self.confidence_max - self.confidence_min)

    def update_simulation_mode(self, simulate_fire: bool = False, simulate_smoke: bool = False):
        """Update simulation mode at runtime"""
        self.simulate_fire = simulate_fire
        self.simulate_smoke = simulate_smoke
        print(f"[FireDetector] Updated: simulate_fire={simulate_fire}, simulate_smoke={simulate_smoke}")
