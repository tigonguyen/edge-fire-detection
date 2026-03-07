#pragma once

#include <vector>
#include <cstdint>
#include <cstddef>

namespace fire {

// ImageNet normalization (same as Python training)
constexpr float MEAN[] = {0.485f, 0.456f, 0.406f};
constexpr float STD[]  = {0.229f, 0.224f, 0.225f};
constexpr int INPUT_H = 224;
constexpr int INPUT_W = 224;
constexpr int INPUT_C = 3;
constexpr size_t INPUT_SIZE = INPUT_C * INPUT_H * INPUT_W;

// Raw RGB 224x224 (HWC) -> normalized CHW float for ONNX
inline void preprocess_rgb224(const unsigned char* rgb, std::vector<float>& out) {
  out.resize(INPUT_SIZE);
  for (int c = 0; c < INPUT_C; ++c)
    for (int i = 0; i < INPUT_H * INPUT_W; ++i)
      out[c * INPUT_H * INPUT_W + i] = (rgb[i * INPUT_C + c] / 255.0f - MEAN[c]) / STD[c];
}

} // namespace fire
