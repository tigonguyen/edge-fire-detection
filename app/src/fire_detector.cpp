#include "fire_detector.h"
#include <iostream>
#include <chrono>

FireDetector::FireDetector(const std::string& model_path, float threshold)
    : confidence_threshold_(threshold), device_(torch::kCPU) {
    
    // Check if CUDA is available
    if (torch::cuda::is_available()) {
        std::cout << "CUDA is available! Using GPU." << std::endl;
        device_ = torch::kCUDA;
    } else {
        std::cout << "CUDA not available. Using CPU." << std::endl;
    }
    
    // Load the model
    try {
        module_ = torch::jit::load(model_path);
        module_.to(device_);
        module_.eval();
        std::cout << "✅ Model loaded successfully from: " << model_path << std::endl;
    } catch (const c10::Error& e) {
        std::cerr << "❌ Error loading model: " << e.what() << std::endl;
        throw std::runtime_error("Failed to load model");
    }
    
    // ImageNet mean and std for normalization
    mean_ = torch::tensor({0.485, 0.456, 0.406}, torch::TensorOptions().dtype(torch::kFloat32));
    std_ = torch::tensor({0.229, 0.224, 0.225}, torch::TensorOptions().dtype(torch::kFloat32));
    
    class_names_ = {"fire", "normal"};
}

torch::Tensor FireDetector::preprocess(const cv::Mat& frame) {
    // Resize to 224x224
    cv::Mat resized;
    cv::resize(frame, resized, cv::Size(224, 224));
    
    // Convert BGR to RGB
    cv::Mat rgb;
    cv::cvtColor(resized, rgb, cv::COLOR_BGR2RGB);
    
    // Convert to float and normalize to [0, 1]
    rgb.convertTo(rgb, CV_32FC3, 1.0 / 255.0);
    
    // Convert to tensor [H, W, C]
    torch::Tensor tensor = torch::from_blob(
        rgb.data, 
        {rgb.rows, rgb.cols, 3}, 
        torch::TensorOptions().dtype(torch::kFloat32)
    ).clone();
    
    // Normalize with ImageNet mean and std
    tensor = tensor.permute({2, 0, 1}); // [C, H, W]
    tensor = (tensor - mean_.view({3, 1, 1})) / std_.view({3, 1, 1});
    
    // Add batch dimension [1, C, H, W]
    tensor = tensor.unsqueeze(0);
    
    return tensor.to(device_);
}

DetectionResult FireDetector::detect(const cv::Mat& frame) {
    DetectionResult result;
    result.frame_number = frame_count_++;
    
    auto start = std::chrono::high_resolution_clock::now();
    
    // Preprocess frame
    torch::Tensor input = preprocess(frame);
    
    // Run inference
    torch::NoGradGuard no_grad;
    torch::Tensor output = module_.forward({input}).toTensor();
    
    // Apply softmax
    torch::Tensor probabilities = torch::softmax(output, 1);
    
    auto end = std::chrono::high_resolution_clock::now();
    result.inference_time_ms = std::chrono::duration<float, std::milli>(end - start).count();
    
    // Get prediction
    auto [max_prob, predicted_class] = torch::max(probabilities, 1);
    
    result.predicted_class = predicted_class.item<int>();
    result.confidence = max_prob.item<float>();
    result.class_name = class_names_[result.predicted_class];
    result.is_fire = (result.predicted_class == 0 && result.confidence >= confidence_threshold_);
    
    // Get probabilities for all classes
    auto probs_accessor = probabilities[0].cpu();
    for (size_t i = 0; i < class_names_.size(); i++) {
        result.class_probabilities[class_names_[i]] = probs_accessor[i].item<float>();
    }
    
    // Update statistics
    total_inference_time_ += result.inference_time_ms;
    if (result.is_fire) {
        fire_detections_++;
    }
    
    return result;
}

void FireDetector::printStatistics() const {
    std::cout << "\n" << std::string(60, '=') << std::endl;
    std::cout << "📊 Detection Statistics" << std::endl;
    std::cout << std::string(60, '=') << std::endl;
    std::cout << "Total frames processed: " << frame_count_ << std::endl;
    std::cout << "Fire detections: " << fire_detections_ 
              << " (" << (frame_count_ > 0 ? (100.0 * fire_detections_ / frame_count_) : 0) 
              << "%)" << std::endl;
    std::cout << "Average inference time: " 
              << (frame_count_ > 0 ? (total_inference_time_ / frame_count_) : 0) 
              << " ms" << std::endl;
    std::cout << "Frames per second: " 
              << (total_inference_time_ > 0 ? (1000.0 * frame_count_ / total_inference_time_) : 0) 
              << " fps" << std::endl;
    std::cout << std::string(60, '=') << std::endl;
}

