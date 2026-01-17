#include "fire_detector.h"
#include <iostream>
#include <opencv2/opencv.hpp>
#include <chrono>
#include <thread>

void drawDetectionInfo(cv::Mat& frame, const DetectionResult& result) {
    // Determine color based on detection
    cv::Scalar color = result.is_fire ? cv::Scalar(0, 0, 255) : cv::Scalar(0, 255, 0);
    cv::Scalar bg_color = result.is_fire ? cv::Scalar(0, 0, 200) : cv::Scalar(0, 200, 0);
    
    // Draw top banner
    cv::rectangle(frame, cv::Point(0, 0), cv::Point(frame.cols, 120), 
                  cv::Scalar(0, 0, 0), -1);
    
    // Status text
    std::string status = result.is_fire ? "🔥 FIRE DETECTED!" : "✓ Normal";
    cv::putText(frame, status, cv::Point(10, 35), 
                cv::FONT_HERSHEY_BOLD, 1.2, color, 3);
    
    // Confidence
    std::stringstream conf_ss;
    conf_ss << "Confidence: " << std::fixed << std::setprecision(1) 
            << (result.confidence * 100) << "%";
    cv::putText(frame, conf_ss.str(), cv::Point(10, 70), 
                cv::FONT_HERSHEY_SIMPLEX, 0.7, cv::Scalar(255, 255, 255), 2);
    
    // Inference time
    std::stringstream time_ss;
    time_ss << "Inference: " << std::fixed << std::setprecision(1) 
            << result.inference_time_ms << " ms";
    cv::putText(frame, time_ss.str(), cv::Point(10, 100), 
                cv::FONT_HERSHEY_SIMPLEX, 0.6, cv::Scalar(200, 200, 200), 1);
    
    // Draw probabilities on the side
    int y_offset = 150;
    cv::putText(frame, "Probabilities:", cv::Point(10, y_offset), 
                cv::FONT_HERSHEY_SIMPLEX, 0.6, cv::Scalar(255, 255, 255), 2);
    
    y_offset += 30;
    for (const auto& [class_name, prob] : result.class_probabilities) {
        std::stringstream prob_ss;
        prob_ss << class_name << ": " << std::fixed << std::setprecision(1) 
                << (prob * 100) << "%";
        
        cv::Scalar prob_color = (class_name == "fire") ? 
                                cv::Scalar(0, 0, 255) : cv::Scalar(0, 255, 0);
        
        cv::putText(frame, prob_ss.str(), cv::Point(10, y_offset), 
                    cv::FONT_HERSHEY_SIMPLEX, 0.6, prob_color, 2);
        
        // Draw probability bar
        int bar_width = static_cast<int>(prob * 200);
        cv::rectangle(frame, cv::Point(150, y_offset - 15), 
                     cv::Point(150 + bar_width, y_offset - 5), prob_color, -1);
        
        y_offset += 35;
    }
    
    // Frame number
    std::stringstream frame_ss;
    frame_ss << "Frame: " << result.frame_number;
    cv::putText(frame, frame_ss.str(), 
                cv::Point(frame.cols - 150, frame.rows - 20), 
                cv::FONT_HERSHEY_SIMPLEX, 0.6, cv::Scalar(200, 200, 200), 1);
}

void processVideoFile(const std::string& video_path, 
                     const std::string& model_path, 
                     float threshold,
                     bool save_output) {
    
    std::cout << "\n" << std::string(60, '=') << std::endl;
    std::cout << "🔥 Fire Detection Video Stream Processor" << std::endl;
    std::cout << std::string(60, '=') << std::endl;
    std::cout << "Video: " << video_path << std::endl;
    std::cout << "Model: " << model_path << std::endl;
    std::cout << "Threshold: " << threshold << std::endl;
    std::cout << std::string(60, '=') << "\n" << std::endl;
    
    // Initialize detector
    FireDetector detector(model_path, threshold);
    
    // Open video
    cv::VideoCapture cap(video_path);
    if (!cap.isOpened()) {
        std::cerr << "❌ Error opening video file: " << video_path << std::endl;
        return;
    }
    
    // Get video properties
    int frame_width = static_cast<int>(cap.get(cv::CAP_PROP_FRAME_WIDTH));
    int frame_height = static_cast<int>(cap.get(cv::CAP_PROP_FRAME_HEIGHT));
    double fps = cap.get(cv::CAP_PROP_FPS);
    int total_frames = static_cast<int>(cap.get(cv::CAP_PROP_FRAME_COUNT));
    
    std::cout << "Video properties:" << std::endl;
    std::cout << "  Resolution: " << frame_width << "x" << frame_height << std::endl;
    std::cout << "  FPS: " << fps << std::endl;
    std::cout << "  Total frames: " << total_frames << std::endl;
    std::cout << std::endl;
    
    // Setup video writer if saving output
    cv::VideoWriter writer;
    if (save_output) {
        std::string output_path = "output_fire_detection.mp4";
        int codec = cv::VideoWriter::fourcc('m', 'p', '4', 'v');
        writer.open(output_path, codec, fps, cv::Size(frame_width, frame_height), true);
        
        if (writer.isOpened()) {
            std::cout << "💾 Saving output to: " << output_path << std::endl;
        } else {
            std::cerr << "⚠️  Warning: Could not open video writer" << std::endl;
            save_output = false;
        }
    }
    
    // Create window
    cv::namedWindow("Fire Detection", cv::WINDOW_NORMAL);
    cv::resizeWindow("Fire Detection", 1280, 720);
    
    cv::Mat frame;
    int frame_count = 0;
    int fire_alert_count = 0;
    
    std::cout << "▶️  Processing video stream... (Press 'q' to quit, SPACE to pause)" 
              << std::endl;
    std::cout << std::string(60, '-') << std::endl;
    
    bool paused = false;
    auto start_time = std::chrono::high_resolution_clock::now();
    
    while (true) {
        if (!paused) {
            if (!cap.read(frame)) {
                std::cout << "\n✅ End of video stream" << std::endl;
                break;
            }
            
            // Detect fire in frame
            DetectionResult result = detector.detect(frame);
            
            // Draw detection info
            drawDetectionInfo(frame, result);
            
            // Print detection if fire detected
            if (result.is_fire) {
                fire_alert_count++;
                std::cout << "🔥 ALERT [Frame " << result.frame_number 
                          << "]: Fire detected! Confidence: " 
                          << std::fixed << std::setprecision(1) 
                          << (result.confidence * 100) << "%" << std::endl;
            }
            
            // Save frame if output enabled
            if (save_output && writer.isOpened()) {
                writer.write(frame);
            }
            
            frame_count++;
            
            // Print progress every 30 frames
            if (frame_count % 30 == 0) {
                std::cout << "📊 Processed: " << frame_count << "/" << total_frames 
                          << " frames (" 
                          << std::fixed << std::setprecision(1)
                          << (100.0 * frame_count / total_frames) << "%)" 
                          << std::endl;
            }
        }
        
        // Display frame
        cv::imshow("Fire Detection", frame);
        
        // Handle key press
        int key = cv::waitKey(paused ? 0 : 1);
        if (key == 'q' || key == 27) { // 'q' or ESC
            std::cout << "\n⏹️  Stopped by user" << std::endl;
            break;
        } else if (key == ' ') { // SPACE
            paused = !paused;
            std::cout << (paused ? "⏸️  Paused" : "▶️  Resumed") << std::endl;
        }
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration<float>(end_time - start_time).count();
    
    // Cleanup
    cap.release();
    if (writer.isOpened()) {
        writer.release();
    }
    cv::destroyAllWindows();
    
    // Print statistics
    std::cout << std::endl;
    detector.printStatistics();
    
    std::cout << "\n" << std::string(60, '=') << std::endl;
    std::cout << "📈 Processing Summary" << std::endl;
    std::cout << std::string(60, '=') << std::endl;
    std::cout << "Total processing time: " << std::fixed << std::setprecision(2) 
              << duration << " seconds" << std::endl;
    std::cout << "Average FPS: " << std::fixed << std::setprecision(1) 
              << (frame_count / duration) << std::endl;
    std::cout << "Fire alerts: " << fire_alert_count << std::endl;
    std::cout << std::string(60, '=') << std::endl;
}

void printUsage(const char* program_name) {
    std::cout << "Usage: " << program_name << " [OPTIONS]" << std::endl;
    std::cout << "\nOptions:" << std::endl;
    std::cout << "  --video <path>       Path to video file (required)" << std::endl;
    std::cout << "  --model <path>       Path to TorchScript model (required)" << std::endl;
    std::cout << "  --threshold <float>  Confidence threshold (default: 0.8)" << std::endl;
    std::cout << "  --save               Save output video with detections" << std::endl;
    std::cout << "  --help               Show this help message" << std::endl;
    std::cout << "\nExample:" << std::endl;
    std::cout << "  " << program_name 
              << " --video forest.mp4 --model fire_model.pt --threshold 0.85 --save" 
              << std::endl;
}

int main(int argc, char* argv[]) {
    std::string video_path;
    std::string model_path = "fire_detection_scripted.pt";
    float threshold = 0.8;
    bool save_output = false;
    
    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        
        if (arg == "--help" || arg == "-h") {
            printUsage(argv[0]);
            return 0;
        } else if (arg == "--video" && i + 1 < argc) {
            video_path = argv[++i];
        } else if (arg == "--model" && i + 1 < argc) {
            model_path = argv[++i];
        } else if (arg == "--threshold" && i + 1 < argc) {
            threshold = std::stof(argv[++i]);
        } else if (arg == "--save") {
            save_output = true;
        } else {
            std::cerr << "Unknown argument: " << arg << std::endl;
            printUsage(argv[0]);
            return 1;
        }
    }
    
    // Validate required arguments
    if (video_path.empty()) {
        std::cerr << "❌ Error: Video path is required" << std::endl;
        printUsage(argv[0]);
        return 1;
    }
    
    try {
        processVideoFile(video_path, model_path, threshold, save_output);
    } catch (const std::exception& e) {
        std::cerr << "❌ Error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}

