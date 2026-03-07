/**
 * Minimal fire detection CLI using ONNX Runtime.
 *
 * Usage:  ./fire_detect <model.onnx> <image_224x224.rgb>
 *
 * The image file must be raw RGB bytes: 224 x 224 x 3 = 150528 bytes.
 * Use the helper script (prepare_input.py) to convert JPEG/PNG to raw.
 */

#include <onnxruntime_cxx_api.h>
#include "preprocess.h"
#include <fstream>
#include <iostream>
#include <vector>
#include <cmath>

static const char* CLASS_NAMES[] = {"fire", "normal"};

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " <model.onnx> <image.rgb>\n";
        return 1;
    }

    const char* model_path = argv[1];
    const char* image_path = argv[2];

    // Read raw image
    std::ifstream fin(image_path, std::ios::binary);
    if (!fin) { std::cerr << "Cannot open " << image_path << "\n"; return 1; }
    std::vector<unsigned char> rgb(fire::INPUT_SIZE);
    fin.read(reinterpret_cast<char*>(rgb.data()), fire::INPUT_SIZE);
    if (fin.gcount() != static_cast<std::streamsize>(fire::INPUT_SIZE)) {
        std::cerr << "Expected " << fire::INPUT_SIZE << " bytes, got " << fin.gcount() << "\n";
        return 1;
    }

    // Preprocess: HWC uint8 → CHW float32 (ImageNet normalize)
    std::vector<float> input_tensor_data;
    fire::preprocess_rgb224(rgb.data(), input_tensor_data);

    // ONNX Runtime session
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "fire_detect");
    Ort::SessionOptions opts;
    opts.SetIntraOpNumThreads(2);
    Ort::Session session(env, model_path, opts);

    Ort::AllocatorWithDefaultOptions alloc;
    auto in_name  = session.GetInputNameAllocated(0, alloc);
    auto out_name = session.GetOutputNameAllocated(0, alloc);
    const char* input_names[]  = {in_name.get()};
    const char* output_names[] = {out_name.get()};

    // Create input tensor
    std::vector<int64_t> shape = {1, fire::INPUT_C, fire::INPUT_H, fire::INPUT_W};
    auto mem = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    auto tensor = Ort::Value::CreateTensor<float>(
        mem, input_tensor_data.data(), input_tensor_data.size(),
        shape.data(), shape.size());

    // Run
    auto results = session.Run(Ort::RunOptions{}, input_names, &tensor, 1, output_names, 1);
    float* logits = results[0].GetTensorMutableData<float>();
    size_t n = results[0].GetTensorTypeAndShapeInfo().GetElementCount();

    // Softmax → prediction
    int best = 0;
    for (size_t i = 1; i < n; ++i)
        if (logits[i] > logits[best]) best = static_cast<int>(i);

    float max_val = logits[best];
    float sum = 0;
    for (size_t i = 0; i < n; ++i) sum += std::exp(logits[i] - max_val);
    float confidence = std::exp(logits[best] - max_val) / sum;

    std::cout << "class:      " << CLASS_NAMES[best] << "\n"
              << "confidence: " << confidence << "\n";
    return 0;
}
