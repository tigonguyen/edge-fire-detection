# Edge Device Evaluation: Baseline vs Distilled (Both EfficientNet-Lite0)

Comparison of **fire_detection_best.pth** (EfficientNet-Lite0, direct training) and **student_distilled_best.pth** (EfficientNet-Lite0, knowledge distillation) for deployment on edge devices such as **ESP32-S3**.

Both models use the **same architecture (EfficientNet-Lite0)**. The only difference is training:
- **Baseline:** Direct fine-tuning on the fire dataset.
- **Distilled:** Trained with knowledge distillation from a larger teacher (EfficientNet-B3).

---

## 1. Criteria for Edge Deployment

| Criterion | Why it matters on edge |
|-----------|------------------------|
| **Model size (flash)** | ESP32-S3 often has 4–16 MB flash; model must fit with app and TFLite runtime. |
| **RAM at inference** | Single-frame buffers + activations must fit in ~8 MB PSRAM. |
| **Inference latency** | Target ~20–40 ms per frame for near real-time. |
| **Accuracy** | Must stay high; false negatives are critical in fire detection. |
| **TFLite / INT8 support** | Lite0 is designed for TFLite and quantizes with minimal accuracy drop. |

---

## 2. Architecture: Same for Both

| Aspect | fire_detection_best.pth (Baseline) | student_distilled_best.pth (Distilled) |
|--------|------------------------------------|----------------------------------------|
| **Architecture** | EfficientNet-**Lite0** | EfficientNet-**Lite0** |
| **Training** | Direct fine-tuning on fire dataset | Knowledge distillation from EfficientNet-B3 teacher |
| **Params (typical)** | ~4.6 M | ~4.6 M |
| **FP32 size** | ~18 MB | ~18 MB |
| **INT8 size** | ~5.3 MB | ~5.3 MB |
| **RAM (INT8)** | ~1.5 MB | ~1.5 MB |
| **TFLite / edge** | ✅ Designed for edge | ✅ Same |

For edge devices, **size, RAM, and latency are the same**; the only differentiator is **accuracy** (and possibly robustness from distillation).

---

## 3. Which Is Better for Edge?

Because both are Lite0:

1. **Deployment cost (flash, RAM, latency)**  
   **Tie.** Use whichever checkpoint you prefer; resource usage is the same.

2. **Accuracy**  
   Run `experiments/knowledge_distillation/compare_models.py` (or `compare_two_models.py`) on your validation set:
   - If **distilled** has **higher (or equal) validation accuracy** → prefer **student_distilled_best.pth** for edge.
   - If **baseline** has **higher accuracy** → prefer **fire_detection_best.pth** for edge.

3. **Robustness / generalization**  
   Distillation often helps the student generalize better (soft labels from the teacher). If your comparison shows similar accuracy, the distilled model can still be slightly better on edge in the wild; prefer it unless the baseline clearly wins on your metrics.

---

## 4. Summary Table

| Criterion | Baseline (Lite0) | Distilled (Lite0) | Better for edge |
|-----------|------------------|-------------------|------------------|
| Flash (INT8) | ~5.3 MB | ~5.3 MB | Tie |
| RAM (inference) | ~1.5 MB | ~1.5 MB | Tie |
| Latency (ESP32-S3) | ~22–40 ms | ~22–40 ms | Tie |
| TFLite / INT8 | ✅ | ✅ | Tie |
| Accuracy | From your eval | From your eval | **Whichever scores higher** |

---

## 5. Recommendation for Edge Devices

- **Same architecture** → choose the checkpoint with **better validation accuracy** (and, if similar, consider the distilled one for potential better generalization).
- To get numbers: from repo root with your training env (e.g. `venv`):

  ```bash
  python experiments/knowledge_distillation/compare_models.py
  ```
  or

  ```bash
  python compare_two_models.py
  ```

- If you have not run distillation yet, **fire_detection_best.pth** (direct Lite0) is already a good edge model; you can add the distilled one later and switch if it performs better.
