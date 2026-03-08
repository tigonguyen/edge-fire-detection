/**
 * Frame Extractor service for edge devices (C++).
 *
 * Single process, multi-threaded:
 *   1. Parses /config/sources.json to find simulated video cameras.
 *   2. Spawns one thread per camera.
 *   3. Reads frames using OpenCV, converts to 224x224 RGB.
 *   4. Publishes raw frame bytes to MQTT topic: frames/<location_id>
 *   5. Publishes static metadata to: frames/<location_id>/meta (retained)
 *   6. Publishes heartbeat to: wildfire/heartbeat (for Grafana UI)
 *
 * Environment variables:
 *   MQTT_HOST      (default: mqtt-broker.default.svc)
 *   MQTT_PORT      (default: 1883)
 *   FRAME_INTERVAL (default: 2.0 seconds)
 *   SOURCES_JSON   (default: /config/sources.json)
 *   VIDEO_DIR      (default: /videos)
 *   HEARTBEAT_INT  (default: 30 seconds)
 *
 * Build: see CMakeLists.txt
 */

#include <mosquitto.h>
#include <opencv2/opencv.hpp>
#include <nlohmann/json.hpp>
#include <curl/curl.h>

#include <atomic>
#include <chrono>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
#include <mutex>
#include <cstdlib>

using json = nlohmann::json;

// ── Constants & Configuration ────────────────────────────────────────

static constexpr int IMG_SIZE = 224;

struct CameraSource {
    std::string id;
    std::string file;
    std::string url;
    double lat;
    double lon;
    std::string description;
};

static std::string g_mqtt_host;
static int         g_mqtt_port;
static double      g_frame_interval;
static std::string g_sources_json;
static std::string g_video_dir;
static int         g_heartbeat_interval;

static std::vector<CameraSource> g_sources;
static std::atomic<bool> g_running{true};

static void load_config() {
    auto env = [](const char* k, const char* d) -> std::string {
        const char* v = std::getenv(k);
        return v ? v : d;
    };
    g_mqtt_host          = env("MQTT_HOST", "mqtt-broker.default.svc");
    g_mqtt_port          = std::stoi(env("MQTT_PORT", "1883"));
    g_frame_interval     = std::stod(env("FRAME_INTERVAL", "2.0"));
    g_sources_json       = env("SOURCES_JSON", "/config/sources.json");
    g_video_dir          = env("VIDEO_DIR", "/videos");
    g_heartbeat_interval = std::stoi(env("HEARTBEAT_INTERVAL", "30"));
}

static void parse_sources() {
    std::ifstream f(g_sources_json);
    if (!f.is_open()) {
        std::cerr << "Failed to open sources JSON: " << g_sources_json << std::endl;
        std::exit(1);
    }
    json data = json::parse(f);
    for (const auto& item : data) {
        CameraSource src;
        src.id          = item.value("id", "unknown");
        src.file        = item.value("file", "");
        src.url         = item.value("url", "");
        src.lat         = item.value("lat", 0.0);
        src.lon         = item.value("lon", 0.0);
        src.description = item.value("description", "");
        g_sources.push_back(src);
    }
}

// ── File Download (libcurl) ──────────────────────────────────────────

static size_t write_data(void* ptr, size_t size, size_t nmemb, FILE* stream) {
    size_t written = fwrite(ptr, size, nmemb, stream);
    return written;
}

static bool download_file(const std::string& url, const std::string& out_path) {
    CURL* curl = curl_easy_init();
    if (!curl) return false;

    FILE* fp = fopen(out_path.c_str(), "wb");
    if (!fp) {
        curl_easy_cleanup(curl);
        return false;
    }

    std::cout << "Downloading GCP Bucket Object: " << url << " -> " << out_path << std::endl;
    
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_data);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, fp);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_FAILONERROR, 1L);
    
    // Ignore SSL varification for simplicity if needed (or keep strict based on environment)
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);

    CURLcode res = curl_easy_perform(curl);
    
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    
    fclose(fp);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        std::cerr << "curl_easy_perform() failed: " << curl_easy_strerror(res) << std::endl;
        std::remove(out_path.c_str());
        return false;
    }
    
    if (http_code >= 400) {
        std::cerr << "HTTP Error downloading file. Code: " << http_code << std::endl;
        std::remove(out_path.c_str());
        return false;
    }
    
    return true;
}

// ── Thread Tasks ─────────────────────────────────────────────────────

// Global MQTT client pointer (protected by mutex if needed, but mosquitto_publish is thread-safe)
static struct mosquitto* g_mosq = nullptr;

static void stream_source(const CameraSource& src) {
    std::string video_path = g_video_dir + "/" + src.file;

    // 1. Publish retained metadata for inference tier
    json meta;
    meta["id"] = src.id;
    meta["lat"] = src.lat;
    meta["lon"] = src.lon;
    std::string meta_str = meta.dump();
    std::string meta_topic = "frames/" + src.id + "/meta";
    
    mosquitto_publish(g_mosq, nullptr, meta_topic.c_str(), meta_str.size(), meta_str.c_str(), 1, true);

    // 2. Download from GCP if file is missing locally and URL is provided
    std::ifstream f(video_path);
    if (!f.good()) {
        f.close();
        if (!src.url.empty()) {
            if (!download_file(src.url, video_path)) {
                std::cerr << "[" << src.id << "] Failed to download from: " << src.url << "\n";
                return;
            }
        } else {
            std::cerr << "[" << src.id << "] Local mp4 not found & no URL given: " << video_path << "\n";
            return;
        }
    } else {
        f.close();
    }

    cv::VideoCapture cap(video_path);
    if (!cap.isOpened()) {
        std::cerr << "[" << src.id << "] Cannot open " << video_path << std::endl;
        return;
    }

    std::cout << "[" << src.id << "] Streaming (lat=" << src.lat << ", lon=" << src.lon << ")\n";
    
    std::string frame_topic = "frames/" + src.id;

    while (g_running) {
        cv::Mat frame;
        if (!cap.read(frame) || frame.empty()) {
            // Loop video
            cap.set(cv::CAP_PROP_POS_FRAMES, 0);
            continue;
        }

        // BGR to RGB
        cv::Mat rgb;
        cv::cvtColor(frame, rgb, cv::COLOR_BGR2RGB);

        // Resize 224x224
        cv::Mat resized;
        cv::resize(rgb, resized, cv::Size(IMG_SIZE, IMG_SIZE));

        // Note: OpenCV Mat data is continuous after resize
        if (!resized.isContinuous()) {
            resized = resized.clone();
        }

        // Publish raw bytes
        size_t size_in_bytes = resized.total() * resized.elemSize();
        mosquitto_publish(g_mosq, nullptr, frame_topic.c_str(), size_in_bytes, resized.data, 0, false);

        int wait_ms = static_cast<int>(g_frame_interval * 1000);
        std::this_thread::sleep_for(std::chrono::milliseconds(wait_ms));
    }
    cap.release();
}

static void heartbeat_thread() {
    while (g_running) {
        for (const auto& src : g_sources) {
            // Publish to wildfire/heartbeat so monitoring Exporter marks it Online
            json hb;
            hb["device_id"] = src.id;
            hb["location"]["lat"] = src.lat;
            hb["location"]["lon"] = src.lon;
            hb["location"]["name"] = src.description;
            hb["timestamp"] = std::time(nullptr);

            std::string hb_str = hb.dump();
            mosquitto_publish(g_mosq, nullptr, "wildfire/heartbeat", hb_str.size(), hb_str.c_str(), 0, false);
        }
        std::this_thread::sleep_for(std::chrono::seconds(g_heartbeat_interval));
    }
}

// ── MQTT Callbacks ───────────────────────────────────────────────────

static void on_connect(struct mosquitto* mosq, void* obj, int rc) {
    if (rc == 0) {
        std::cout << "Connected to MQTT broker safely.\n";
    } else {
        std::cerr << "MQTT connection failed rc=" << rc << "\n";
    }
}

// ── Main ─────────────────────────────────────────────────────────────

int main() {
    load_config();
    parse_sources();

    // Init Mosquitto
    mosquitto_lib_init();
    g_mosq = mosquitto_new(nullptr, true, nullptr);
    if (!g_mosq) {
        std::cerr << "Failed to init Mosquitto\n";
        return 1;
    }

    mosquitto_connect_callback_set(g_mosq, on_connect);

    std::cout << "Connecting to MQTT " << g_mqtt_host << ":" << g_mqtt_port << "\n";
    int rc = mosquitto_connect(g_mosq, g_mqtt_host.c_str(), g_mqtt_port, 60);
    if (rc != MOSQ_ERR_SUCCESS) {
        std::cerr << "MQTT connect failed: " << mosquitto_strerror(rc) << "\n";
        return 1;
    }

    // Start background thread for MQTT loops
    mosquitto_loop_start(g_mosq);

    std::vector<std::thread> workers;
    
    // 1. Thread cho Heartbeats
    workers.emplace_back(heartbeat_thread);

    // 2. Thread cho từng camera
    for (const auto& src : g_sources) {
        workers.emplace_back(stream_source, src);
    }

    std::cout << "All streams started. Interval: " << g_frame_interval << "s, Heartbeat: " << g_heartbeat_interval << "s\n";

    // Wait until killed (e.g. SIGINT/SIGTERM, though Docker will just stop container)
    for (auto& t : workers) {
        if (t.joinable()) {
            t.join();
        }
    }

    g_running = false;
    mosquitto_loop_stop(g_mosq, true);
    mosquitto_destroy(g_mosq);
    mosquitto_lib_cleanup();

    return 0;
}
