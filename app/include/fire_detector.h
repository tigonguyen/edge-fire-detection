#ifndef FIRE_DETECTOR_H
#define FIRE_DETECTOR_H

#include <torch/script.h>
#include <torch/torch.h>
#include <opencv2/opencv.hpp>
#include <string>
#include <vector>
#include <map>

struct DetectionResult {
    int frame_number;
    int predicted_class;
    std::string class_name;
    float confidence;
    bool is_fire;
    float inference_time_ms;
    std::map<std::string, float> class_probabilities;
};

class FireDetector {
public:
    FireDetector(const std::string& model_path, float threshold = 0.8);
    
    DetectionResult detect(const cv::Mat& frame);
    void printStatistics() const;
    
private:
    torch::jit::script::Module module_;
    torch::Device device_;
    torch::Tensor mean_;
    torch::Tensor std_;
    std::vector<std::string> class_names_;
    float confidence_threshold_;
    
    // Statistics
    int frame_count_ = 0;
    int fire_detections_ = 0;
    float total_inference_time_ = 0.0;
    
    torch::Tensor preprocess(const cv::Mat& frame);
};

#endif // FIRE_DETECTOR_H

