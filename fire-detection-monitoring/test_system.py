import requests
import json
import paho.mqtt.client as mqtt
import time
import random

MQTT_BROKER = "localhost"
EXPORTER_URL = "http://localhost:8000"
PROMETHEUS_URL = "http://localhost:9090"

def test_mqtt_alert():
    """Send test alert via MQTT"""
    client = mqtt.Client()
    client.connect(MQTT_BROKER, 1883)

    # Locations in Vietnam for testing
    locations = [
        {"lat": 21.0285, "lon": 105.8542, "name": "Hà Nội - Khu vực rừng 1"},
        {"lat": 16.0544, "lon": 108.2022, "name": "Đà Nẵng - Khu vực rừng 2"},
        {"lat": 10.8231, "lon": 106.6297, "name": "TP.HCM - Khu vực rừng 3"},
        {"lat": 21.3891, "lon": 103.0169, "name": "Lào Cai - Khu vực rừng 4"},
    ]

    location = random.choice(locations)
    confidence = 0.7 + random.random() * 0.25  # 0.7 - 0.95

    alert = {
        "alert_id": f"test_{int(time.time())}",
        "device_id": f"edge_device_{random.randint(1, 5):03d}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location": location,
        "detections": [
            {"class": "fire", "confidence": confidence}
        ],
        "confidence_max": confidence
    }

    client.publish("wildfire/alerts", json.dumps(alert))
    client.disconnect()

    print(f"Sent alert: {alert['alert_id']} at {location['name']}")
    return alert

def test_exporter_metrics():
    """Verify exporter metrics"""
    response = requests.get(f"{EXPORTER_URL}/metrics")
    assert response.status_code == 200

    metrics_text = response.text
    assert "fire_alert_info" in metrics_text
    print("Exporter metrics OK")

def test_prometheus_query():
    """Query Prometheus for fire alerts"""
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": "fire_alert_info"}
    )
    assert response.status_code == 200

    data = response.json()
    results = data.get("data", {}).get("result", [])
    print(f"Prometheus has {len(results)} fire alerts")

def main():
    print("=== Testing Fire Detection System ===\n")

    # Send multiple test alerts
    print("1. Sending test alerts...")
    for i in range(3):
        test_mqtt_alert()
        time.sleep(1)

    # Wait for processing
    time.sleep(5)

    # Test exporter
    print("\n2. Testing exporter...")
    test_exporter_metrics()

    # Test Prometheus
    print("\n3. Testing Prometheus...")
    test_prometheus_query()

    print("\n=== All tests passed! ===")
    print("\nOpen Grafana at http://localhost:3000 to view the dashboard")

if __name__ == "__main__":
    main()