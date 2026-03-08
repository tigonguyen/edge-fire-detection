/**
 * Fire detection inference service for edge deployment (C++).
 *
 * Single process:
 *   1. Subscribes to MQTT topic frames/# to receive 224×224 RGB frames
 *   2. Runs ONNX Runtime inference (EfficientNet-Lite0)
 *   3. Serves Prometheus metrics on HTTP :METRICS_PORT /metrics
 *
 * Environment variables:
 *   MQTT_HOST    (default: mqtt-broker.default.svc)
 *   MQTT_PORT    (default: 1883)
 *   MODEL_PATH   (default: /model/fire_detection.onnx)
 *   METRICS_PORT (default: 9090)
 *   CLASS_NAMES  (default: fire,normal)
 *
 * Build: see CMakeLists.txt
 */

#include <onnxruntime_cxx_api.h>
#include <mosquitto.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

// ── Constants ────────────────────────────────────────────────────────

static constexpr int    IMG_H = 224;
static constexpr int    IMG_W = 224;
static constexpr int    IMG_C = 3;
static constexpr size_t FRAME_BYTES = IMG_H * IMG_W * IMG_C; // 150528

static constexpr float MEAN[] = {0.485f, 0.456f, 0.406f};
static constexpr float STD[]  = {0.229f, 0.224f, 0.225f};

// Histogram buckets (same as Python version)
static const double BUCKETS[] = {0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0};
static constexpr int NUM_BUCKETS = 8;

// ── Config (from env) ────────────────────────────────────────────────

static std::string g_mqtt_host;
static int         g_mqtt_port;
static std::string g_model_path;
static int         g_metrics_port;
static std::vector<std::string> g_class_names;

static void load_config() {
    auto env = [](const char* k, const char* d) -> std::string {
        const char* v = std::getenv(k);
        return v ? v : d;
    };
    g_mqtt_host   = env("MQTT_HOST", "mqtt-broker.default.svc");
    g_mqtt_port   = std::stoi(env("MQTT_PORT", "1883"));
    g_model_path  = env("MODEL_PATH", "/model/fire_detection.onnx");
    g_metrics_port = std::stoi(env("METRICS_PORT", "9090"));

    // Parse CLASS_NAMES (comma-separated)
    std::string cn = env("CLASS_NAMES", "fire,normal");
    std::istringstream ss(cn);
    std::string tok;
    while (std::getline(ss, tok, ','))
        if (!tok.empty()) g_class_names.push_back(tok);
    if (g_class_names.empty()) { g_class_names.push_back("fire"); g_class_names.push_back("normal"); }
}

// ── ONNX Runtime globals ────────────────────────────────────────────

static Ort::Env*     g_ort_env     = nullptr;
static Ort::Session* g_ort_session = nullptr;
static std::string   g_input_name;

static void load_model() {
    g_ort_env = new Ort::Env(ORT_LOGGING_LEVEL_WARNING, "fire_inference");
    Ort::SessionOptions opts;
    opts.SetIntraOpNumThreads(2);
    opts.SetInterOpNumThreads(2);
    g_ort_session = new Ort::Session(*g_ort_env, g_model_path.c_str(), opts);

    Ort::AllocatorWithDefaultOptions alloc;
    auto name = g_ort_session->GetInputNameAllocated(0, alloc);
    g_input_name = name.get();
    std::printf("Model loaded: %s | input: %s\n", g_model_path.c_str(), g_input_name.c_str());
}

// ── Preprocessing & inference ────────────────────────────────────────

static void preprocess(const unsigned char* rgb, std::vector<float>& out) {
    out.resize(FRAME_BYTES);
    for (int c = 0; c < IMG_C; ++c)
        for (int i = 0; i < IMG_H * IMG_W; ++i)
            out[c * IMG_H * IMG_W + i] =
                (rgb[i * IMG_C + c] / 255.0f - MEAN[c]) / STD[c];
}

struct InferResult { int cls; float confidence; };

static InferResult infer(const unsigned char* frame) {
    thread_local std::vector<float> tensor_data;
    preprocess(frame, tensor_data);

    std::vector<int64_t> shape = {1, IMG_C, IMG_H, IMG_W};
    auto mem = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    auto tensor = Ort::Value::CreateTensor<float>(
        mem, tensor_data.data(), tensor_data.size(), shape.data(), shape.size());

    const char* in_names[]  = {g_input_name.c_str()};
    Ort::AllocatorWithDefaultOptions alloc;
    auto out_name_alloc = g_ort_session->GetOutputNameAllocated(0, alloc);
    const char* out_names[] = {out_name_alloc.get()};

    auto results = g_ort_session->Run(Ort::RunOptions{}, in_names, &tensor, 1, out_names, 1);
    float* logits = results[0].GetTensorMutableData<float>();
    size_t n = results[0].GetTensorTypeAndShapeInfo().GetElementCount();

    // Softmax
    int best = 0;
    for (size_t i = 1; i < n; ++i)
        if (logits[i] > logits[best]) best = static_cast<int>(i);
    float max_val = logits[best];
    float sum = 0.0f;
    for (size_t i = 0; i < n; ++i) sum += std::exp(logits[i] - max_val);
    float confidence = std::exp(logits[best] - max_val) / sum;

    return {best, confidence};
}

// ── Prometheus metrics store ─────────────────────────────────────────

struct LocationMeta {
    std::string lat = "0";
    std::string lon = "0";
};

struct CounterEntry { uint64_t fire = 0; uint64_t normal = 0; };

struct GaugeEntry {
    std::string lat = "0";
    std::string lon = "0";
    double      value = 0.0;
};

struct HistEntry {
    uint64_t buckets[NUM_BUCKETS] = {};
    uint64_t count = 0;
    double   sum   = 0.0;
};

static std::mutex g_metrics_mu;
static std::unordered_map<std::string, CounterEntry> g_counters;
static std::unordered_map<std::string, GaugeEntry>   g_gauges;
static std::unordered_map<std::string, HistEntry>    g_hists;

static void record_metrics(const std::string& loc, const std::string& lat,
                           const std::string& lon, const std::string& result,
                           double confidence, double latency_s) {
    std::lock_guard<std::mutex> lk(g_metrics_mu);

    // Counter
    auto& ctr = g_counters[loc];
    if (result == "fire") ++ctr.fire; else ++ctr.normal;

    // Gauge
    auto& g = g_gauges[loc];
    g.lat = lat; g.lon = lon; g.value = confidence;

    // Histogram
    auto& h = g_hists[loc];
    for (int i = 0; i < NUM_BUCKETS; ++i)
        if (latency_s <= BUCKETS[i]) ++h.buckets[i];
    ++h.count;
    h.sum += latency_s;
}

static std::string render_metrics() {
    std::lock_guard<std::mutex> lk(g_metrics_mu);
    std::ostringstream o;

    // Counter
    o << "# HELP fire_detection_total Total fire detection inferences\n"
      << "# TYPE fire_detection_total counter\n";
    for (auto& [loc, c] : g_counters) {
        if (c.fire)
            o << "fire_detection_total{location=\"" << loc << "\",result=\"fire\"} " << c.fire << "\n";
        if (c.normal)
            o << "fire_detection_total{location=\"" << loc << "\",result=\"normal\"} " << c.normal << "\n";
    }

    // Gauge
    o << "# HELP fire_detection_confidence Latest detection confidence\n"
      << "# TYPE fire_detection_confidence gauge\n";
    for (auto& [loc, g] : g_gauges)
        o << "fire_detection_confidence{location=\"" << loc
          << "\",lat=\"" << g.lat << "\",lon=\"" << g.lon << "\"} " << g.value << "\n";

    // Histogram
    o << "# HELP fire_detection_latency_seconds ONNX inference latency\n"
      << "# TYPE fire_detection_latency_seconds histogram\n";
    for (auto& [loc, h] : g_hists) {
        uint64_t cumulative = 0;
        for (int i = 0; i < NUM_BUCKETS; ++i) {
            cumulative += h.buckets[i];
            o << "fire_detection_latency_seconds_bucket{location=\"" << loc
              << "\",le=\"" << BUCKETS[i] << "\"} " << cumulative << "\n";
        }
        o << "fire_detection_latency_seconds_bucket{location=\"" << loc << "\",le=\"+Inf\"} " << h.count << "\n";
        o << "fire_detection_latency_seconds_sum{location=\"" << loc << "\"} " << h.sum << "\n";
        o << "fire_detection_latency_seconds_count{location=\"" << loc << "\"} " << h.count << "\n";
    }

    return o.str();
}

// ── Minimal HTTP server (Prometheus /metrics) ────────────────────────

static std::atomic<bool> g_running{true};

static void metrics_server_thread() {
    int srv = socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) { std::perror("socket"); return; }

    int opt = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons(static_cast<uint16_t>(g_metrics_port));

    if (bind(srv, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        std::perror("bind"); close(srv); return;
    }
    listen(srv, 8);
    std::printf("Prometheus metrics on :%d\n", g_metrics_port);

    while (g_running) {
        int cli = accept(srv, nullptr, nullptr);
        if (cli < 0) continue;

        // Read request (we only care that it's HTTP, ignore details)
        char buf[1024];
        ssize_t n = recv(cli, buf, sizeof(buf) - 1, 0);
        (void)n;

        std::string body = render_metrics();
        std::ostringstream resp;
        resp << "HTTP/1.1 200 OK\r\n"
             << "Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
             << "Content-Length: " << body.size() << "\r\n"
             << "Connection: close\r\n\r\n"
             << body;
        std::string r = resp.str();
        send(cli, r.data(), r.size(), 0);
        close(cli);
    }
    close(srv);
}

// ── Minimal JSON helpers ─────────────────────────────────────────────

// Extract string value for a key from a tiny JSON like {"id":"x","lat":11.5,"lon":106.9}
static std::string json_str(const char* json, size_t len, const char* key) {
    std::string needle = std::string("\"") + key + "\"";
    const char* p = std::strstr(json, needle.c_str());
    if (!p) return {};
    p += needle.size();
    while (p < json + len && (*p == ' ' || *p == ':')) ++p;
    if (p >= json + len) return {};
    if (*p == '"') {
        ++p;
        const char* end = static_cast<const char*>(std::memchr(p, '"', json + len - p));
        if (!end) return {};
        return std::string(p, end);
    }
    // Number
    const char* start = p;
    while (p < json + len && *p != ',' && *p != '}' && *p != ' ') ++p;
    return std::string(start, p);
}

// ── MQTT callbacks ───────────────────────────────────────────────────

static std::mutex g_meta_mu;
static std::unordered_map<std::string, LocationMeta> g_location_meta;

static void on_connect(struct mosquitto* /*mosq*/, void* /*obj*/, int rc) {
    std::printf("MQTT connected (rc=%d)\n", rc);
    // Subscribe done in main after connect
}

static void on_message(struct mosquitto* /*mosq*/, void* /*obj*/,
                       const struct mosquitto_message* msg) {
    if (!msg || !msg->topic) return;
    std::string topic(msg->topic);

    // Metadata messages (retained)
    if (topic.size() > 5 && topic.rfind("/meta") == topic.size() - 5) {
        // Extract location id: frames/<loc_id>/meta
        size_t s1 = topic.find('/');
        size_t s2 = topic.rfind('/');
        if (s1 != std::string::npos && s2 != std::string::npos && s2 > s1) {
            std::string loc_id = topic.substr(s1 + 1, s2 - s1 - 1);
            const char* payload = static_cast<const char*>(msg->payload);
            LocationMeta m;
            m.lat = json_str(payload, msg->payloadlen, "lat");
            m.lon = json_str(payload, msg->payloadlen, "lon");
            if (m.lat.empty()) m.lat = "0";
            if (m.lon.empty()) m.lon = "0";
            std::lock_guard<std::mutex> lk(g_meta_mu);
            g_location_meta[loc_id] = m;
        }
        return;
    }

    // Frame messages
    if (msg->payloadlen != static_cast<int>(FRAME_BYTES)) return;

    // Extract location id: frames/<loc_id>
    std::string loc_id = "unknown";
    size_t slash = topic.find('/');
    if (slash != std::string::npos)
        loc_id = topic.substr(slash + 1);

    std::string lat = "0", lon = "0";
    {
        std::lock_guard<std::mutex> lk(g_meta_mu);
        auto it = g_location_meta.find(loc_id);
        if (it != g_location_meta.end()) {
            lat = it->second.lat;
            lon = it->second.lon;
        }
    }

    auto t0 = std::chrono::steady_clock::now();
    auto res = infer(static_cast<const unsigned char*>(msg->payload));
    auto t1 = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(t1 - t0).count();

    const std::string& cls_name =
        (res.cls >= 0 && res.cls < static_cast<int>(g_class_names.size()))
            ? g_class_names[res.cls] : "unknown";

    record_metrics(loc_id, lat, lon, cls_name, res.confidence, elapsed);

    if (cls_name == "fire")
        std::printf("[%s] FIRE  conf=%.3f  latency=%.3fs\n",
                    loc_id.c_str(), res.confidence, elapsed);
}

// ── Main ─────────────────────────────────────────────────────────────

int main() {
    load_config();
    load_model();

    // Start metrics HTTP server thread
    std::thread metrics_th(metrics_server_thread);
    metrics_th.detach();

    // MQTT
    mosquitto_lib_init();
    struct mosquitto* mosq = mosquitto_new("fire-inference", true, nullptr);
    if (!mosq) { std::fprintf(stderr, "mosquitto_new failed\n"); return 1; }

    mosquitto_connect_callback_set(mosq, on_connect);
    mosquitto_message_callback_set(mosq, on_message);

    std::printf("Connecting to MQTT %s:%d\n", g_mqtt_host.c_str(), g_mqtt_port);
    int rc = mosquitto_connect(mosq, g_mqtt_host.c_str(), g_mqtt_port, 60);
    if (rc != MOSQ_ERR_SUCCESS) {
        std::fprintf(stderr, "MQTT connect failed: %s\n", mosquitto_strerror(rc));
        return 1;
    }

    mosquitto_subscribe(mosq, nullptr, "frames/#", 0);
    std::printf("Subscribed to frames/#\n");

    // Blocking loop
    mosquitto_loop_forever(mosq, -1, 1);

    g_running = false;
    mosquitto_destroy(mosq);
    mosquitto_lib_cleanup();
    delete g_ort_session;
    delete g_ort_env;
    return 0;
}
