/**
 * Minimal fire detection backend: load ONNX model, expose HTTP POST /predict.
 * Body: raw RGB 224x224 (150528 bytes) or base64-encoded RGB 224x224.
 * Response: JSON { "class": "fire"|"normal", "confidence": float }
 */

#include <onnxruntime_cxx_api.h>
#include "preprocess.h"
#include <iostream>
#include <string>
#include <vector>
#include <cstring>
#include <sstream>
#include <cmath>
#include <algorithm>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <arpa/inet.h>

static void b64_decode(const std::string& in, std::vector<unsigned char>& out) {
  out.clear();
  int val = 0, bits = -8;
  for (unsigned char c : in) {
    if (c == '=') break;
    int d = (c >= 'A' && c <= 'Z') ? c - 'A' : (c >= 'a' && c <= 'z') ? c - 'a' + 26 : (c >= '0' && c <= '9') ? c - '0' + 52 : (c == '+') ? 62 : (c == '/') ? 63 : -1;
    if (d < 0) continue;
    val = (val << 6) + d; bits += 6;
    if (bits >= 0) { out.push_back(static_cast<unsigned char>((val >> bits) & 0xff)); bits -= 8; }
  }
}

const char* CLASS_NAMES[] = {"normal", "fire"};
constexpr int PORT = 8080;
constexpr size_t BODY_LIMIT = 1024 * 1024; // 1MB max

std::string json_response(const char* cls, float conf) {
  std::ostringstream o;
  o << "{\"class\":\"" << cls << "\",\"confidence\":" << conf << "}";
  return o.str();
}

int main(int argc, char** argv) {
  std::string model_path = "model/fire_detection.onnx";
  if (argc >= 2) model_path = argv[1];

  Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "fire_backend");
  Ort::SessionOptions opts;
  opts.SetIntraOpNumThreads(1);
  Ort::Session session(env, model_path.c_str(), opts);

  Ort::AllocatorWithDefaultOptions allocator;
  auto input_name_ptr = session.GetInputNameAllocated(0, allocator);
  auto output_name_ptr = session.GetOutputNameAllocated(0, allocator);
  std::string input_name_str(input_name_ptr.get());
  std::string output_name_str(output_name_ptr.get());
  const char* input_name = input_name_str.c_str();
  const char* output_name = output_name_str.c_str();

  int sock = socket(AF_INET, SOCK_STREAM, 0);
  if (sock < 0) { std::cerr << "socket failed\n"; return 1; }
  int one = 1;
  setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(PORT);
  addr.sin_addr.s_addr = INADDR_ANY;
  if (bind(sock, (sockaddr*)&addr, sizeof(addr)) < 0) { std::cerr << "bind failed\n"; return 1; }
  if (listen(sock, 5) < 0) { std::cerr << "listen failed\n"; return 1; }
  std::cout << "Listening on 0.0.0.0:" << PORT << " (model: " << model_path << ")\n";

  while (true) {
    int client = accept(sock, nullptr, nullptr);
    if (client < 0) continue;
    std::string req;
    char buf[4096];
    ssize_t n;
    size_t content_len = 0;
    while ((n = recv(client, buf, sizeof(buf), 0)) > 0) {
      req.append(buf, n);
      if (req.find("\r\n\r\n") != std::string::npos) {
        auto cl = req.find("Content-Length: ");
        if (cl != std::string::npos)
          content_len = std::stoul(req.substr(cl + 16, req.find("\r\n", cl) - cl - 16));
        break;
      }
    }
    size_t header_end = req.find("\r\n\r\n");
    std::string body = header_end != std::string::npos ? req.substr(header_end + 4) : "";
    while (body.size() < content_len && (n = recv(client, buf, sizeof(buf), 0)) > 0)
      body.append(buf, n);
    if (body.size() > content_len) body.resize(content_len);

    std::string response = "HTTP/1.1 500 Internal Error\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"error\":\"internal\"}";
    do {
      const unsigned char* rgb = nullptr;
      size_t rgb_len = 0;
      if (body.size() == fire::INPUT_SIZE) {
        rgb = reinterpret_cast<const unsigned char*>(body.data());
        rgb_len = body.size();
      } else if (body.size() > 100) {
        std::vector<unsigned char> decoded;
        b64_decode(body, decoded);
        if (decoded.size() == fire::INPUT_SIZE) {
          rgb = decoded.data();
          rgb_len = decoded.size();
        }
      }
      if (!rgb || rgb_len != fire::INPUT_SIZE) {
        response = "HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"error\":\"body must be 150528 raw bytes or base64\"}";
        break;
      }

      std::vector<float> input_vec;
      fire::preprocess_rgb224(rgb, input_vec);

      std::vector<const char*> input_names = {input_name};
      std::vector<const char*> output_names = {output_name};
      std::vector<int64_t> dims = {1, 3, fire::INPUT_H, fire::INPUT_W};
      Ort::MemoryInfo mem_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
      Ort::Value input_tensor = Ort::Value::CreateTensor<float>(mem_info, input_vec.data(), input_vec.size(), dims.data(), dims.size());

      auto run_options = Ort::RunOptions{};
      auto outputs = session.Run(run_options, input_names.data(), &input_tensor, 1, output_names.data(), 1);
      float* logits = outputs[0].GetTensorMutableData<float>();
      size_t num_classes = outputs[0].GetTensorTypeAndShapeInfo().GetElementCount();
      int pred = 0;
      for (size_t i = 1; i < num_classes; ++i) if (logits[i] > logits[pred]) pred = (int)i;
      float max_val = logits[pred];
      float sum = 0;
      for (size_t i = 0; i < num_classes; ++i) sum += std::exp(logits[i] - max_val);
      float conf = std::exp(logits[pred] - max_val) / sum;

      std::string json = json_response(CLASS_NAMES[pred], conf);
      response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: " + std::to_string(json.size()) + "\r\n\r\n" + json;
    } while (0);

    send(client, response.data(), response.size(), 0);
    close(client);
  }
  close(sock);
  return 0;
}
