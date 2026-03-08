#!/usr/bin/env python3
import requests
import json
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
import time
import random
import os
import argparse
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
EXPORTER_URL = os.getenv("EXPORTER_URL", "http://localhost:8000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")

# Test images - same folder as this script
SCRIPT_DIR = Path(__file__).parent
TEST_IMAGES_DIR = SCRIPT_DIR / "test_images"


def load_test_images() -> Dict[str, List[Path]]:
    """Load test images from test_images directory"""
    images = {
        "fire": [],
        "smoke": [],
        "general": []
    }

    if not TEST_IMAGES_DIR.exists():
        print(f"  [WARNING] Test image directory not found: {TEST_IMAGES_DIR}")
        return images

    for img_path in TEST_IMAGES_DIR.glob("*"):
        if img_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            # Skip large files (> 1MB) to avoid MQTT issues
            if img_path.stat().st_size > 1024 * 1024:
                print(f"  [INFO] Skipping large image: {img_path.name} ({img_path.stat().st_size // 1024}KB)")
                continue

            name_lower = img_path.stem.lower()
            if "fire" in name_lower:
                images["fire"].append(img_path)
            elif "smoke" in name_lower:
                images["smoke"].append(img_path)
            else:
                images["general"].append(img_path)

    total = sum(len(v) for v in images.values())
    if total > 0:
        print(f"  [INFO] Loaded {total} test images (fire: {len(images['fire'])}, smoke: {len(images['smoke'])}, other: {len(images['general'])})")
    else:
        print(f"  [WARNING] No suitable images found in {TEST_IMAGES_DIR}")

    return images


# Load images at startup
TEST_IMAGES = load_test_images()

# Forest locations in Vietnam
VIETNAM_FOREST_LOCATIONS = [
    # Northern Vietnam
    {"lat": 22.3964, "lon": 103.8200, "name": "Rừng quốc gia Hoàng Liên - Sa Pa, Lào Cai", "region": "north"},
    {"lat": 21.5419, "lon": 105.6089, "name": "Rừng quốc gia Ba Vì - Hà Nội", "region": "north"},
    {"lat": 22.8167, "lon": 105.4833, "name": "Rừng quốc gia Tam Đảo - Vĩnh Phúc", "region": "north"},
    {"lat": 20.8500, "lon": 106.6833, "name": "Vườn quốc gia Cát Bà - Hải Phòng", "region": "north"},
    {"lat": 21.0833, "lon": 105.4167, "name": "Rừng phòng hộ Sóc Sơn - Hà Nội", "region": "north"},

    # Central Vietnam
    {"lat": 16.0167, "lon": 107.8667, "name": "Vườn quốc gia Bạch Mã - Thừa Thiên Huế", "region": "central"},
    {"lat": 15.7500, "lon": 107.8333, "name": "Rừng đặc dụng Phong Điền - Thừa Thiên Huế", "region": "central"},
    {"lat": 14.0500, "lon": 108.1500, "name": "Vườn quốc gia Kon Ka Kinh - Gia Lai", "region": "central"},
    {"lat": 12.2500, "lon": 108.6833, "name": "Vườn quốc gia Bidoup Núi Bà - Lâm Đồng", "region": "central"},
    {"lat": 17.5833, "lon": 106.0500, "name": "Vườn quốc gia Phong Nha - Kẻ Bàng - Quảng Bình", "region": "central"},

    # Southern Vietnam
    {"lat": 11.4333, "lon": 107.4167, "name": "Vườn quốc gia Cát Tiên - Đồng Nai", "region": "south"},
    {"lat": 10.4167, "lon": 107.0500, "name": "Rừng ngập mặn Cần Giờ - TP.HCM", "region": "south"},
    {"lat": 10.0833, "lon": 104.0333, "name": "Vườn quốc gia U Minh Thượng - Kiên Giang", "region": "south"},
    {"lat": 10.9500, "lon": 106.9667, "name": "Khu bảo tồn thiên nhiên Bình Châu - Bà Rịa Vũng Tàu", "region": "south"},
    {"lat": 11.8333, "lon": 108.4333, "name": "Rừng thông Đà Lạt - Lâm Đồng", "region": "south"},
]


def get_image_base64(detection_type: str = "fire") -> Optional[str]:
    """Get a random test image as base64 string (same as test_vietnam_forests.py)"""
    # Try to get image matching detection class
    candidates = TEST_IMAGES.get(detection_type, [])

    # Fallback to general images
    if not candidates:
        candidates = TEST_IMAGES.get("general", [])

    # Fallback to any available image
    if not candidates:
        for img_list in TEST_IMAGES.values():
            if img_list:
                candidates = img_list
                break

    if not candidates:
        return None

    img_path = random.choice(candidates)
    try:
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"  [WARNING] Failed to read image {img_path}: {e}")
        return None


def send_fire_alert(location=None, confidence=None, detection_type="fire",
                    device_id=None, include_image=True, alert_id=None):
    """Send a fire alert via MQTT"""
    # Use CallbackAPIVersion.VERSION2 for newer paho-mqtt (same as test_vietnam_forests.py)
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    client.connect(MQTT_BROKER, MQTT_PORT)

    if location is None:
        location = random.choice(VIETNAM_FOREST_LOCATIONS)

    if confidence is None:
        confidence = 0.7 + random.random() * 0.25  # 0.7 - 0.95

    if device_id is None:
        device_id = f"edge_device_{random.randint(1, 10):03d}"

    if alert_id is None:
        alert_id = f"alert_{int(time.time())}_{random.randint(100, 999)}"

    alert = {
        "alert_id": alert_id,
        "device_id": device_id,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location": {
            "lat": location["lat"],
            "lon": location["lon"],
            "name": location["name"],
        },
        "region": location.get("region", "unknown"),
        "detections": [
            {"class": detection_type, "confidence": confidence}
        ],
        "confidence_max": confidence,
        "status": "active",
    }

    # Add image as base64 if available (same approach as test_vietnam_forests.py)
    has_image = False
    if include_image:
        image_base64 = get_image_base64(detection_type)
        if image_base64:
            alert["image_base64"] = image_base64
            has_image = True
            print(f"  [IMAGE] Attached ({len(image_base64)} chars)")

    payload = json.dumps(alert)
    print(f"  [PAYLOAD] Size: {len(payload)} bytes")

    # Publish alert
    client.publish("wildfire/alerts", payload)
    client.disconnect()

    print(f"[ALERT] Sent {detection_type} alert:")
    print(f"  - Alert ID: {alert_id}")
    print(f"  - Location: {location['name']}")
    print(f"  - Coordinates: {location['lat']}, {location['lon']}")
    print(f"  - Confidence: {confidence*100:.1f}%")
    print(f"  - Detection type: {detection_type}")
    print(f"  - Device: {device_id}")
    print(f"  - Image: {'Yes' if has_image else 'No'}")

    return alert


def send_resolved_alert(original_alert_id, resolution_type="extinguished"):
    """Send a resolution notification for a fire alert"""
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    client.connect(MQTT_BROKER, MQTT_PORT)

    resolution = {
        "alert_id": original_alert_id,
        "status": "resolved",
        "resolution_type": resolution_type,  # extinguished, false_positive, contained
        "resolved_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resolved_by": "fire_response_team",
        "notes": f"Fire {resolution_type} and verified by response team",
    }

    client.publish("wildfire/resolved", json.dumps(resolution))
    client.disconnect()

    print(f"[RESOLVED] Fire alert resolved:")
    print(f"  - Alert ID: {original_alert_id}")
    print(f"  - Resolution: {resolution_type}")
    print(f"  - Time: {resolution['resolved_at']}")

    return resolution


def test_single_fire_alert(region=None):
    """Test a single fire alert"""
    print("\n" + "="*50)
    print("TEST: Single Fire Alert")
    print("="*50)

    if region:
        locations = [loc for loc in VIETNAM_FOREST_LOCATIONS if loc.get("region") == region]
        location = random.choice(locations) if locations else random.choice(VIETNAM_FOREST_LOCATIONS)
    else:
        location = random.choice(VIETNAM_FOREST_LOCATIONS)

    alert = send_fire_alert(location=location, detection_type="fire", include_image=True)
    return alert


def test_single_smoke_alert(region=None):
    """Test a single smoke detection alert"""
    print("\n" + "="*50)
    print("TEST: Single Smoke Alert")
    print("="*50)

    if region:
        locations = [loc for loc in VIETNAM_FOREST_LOCATIONS if loc.get("region") == region]
        location = random.choice(locations) if locations else random.choice(VIETNAM_FOREST_LOCATIONS)
    else:
        location = random.choice(VIETNAM_FOREST_LOCATIONS)

    # Smoke usually has lower confidence initially
    alert = send_fire_alert(location=location, confidence=0.5 + random.random() * 0.3,
                           detection_type="smoke", include_image=True)
    return alert


def test_fire_and_resolve():
    """Test fire alert followed by resolution"""
    print("\n" + "="*50)
    print("TEST: Fire Alert + Resolution")
    print("="*50)

    # Send fire alert
    alert = send_fire_alert(detection_type="fire", include_image=True)

    print("\n[Waiting 5 seconds before resolution...]")
    time.sleep(5)

    # Send resolution
    resolution = send_resolved_alert(alert["alert_id"], resolution_type="extinguished")

    return alert, resolution


def test_false_positive():
    """Test a false positive scenario"""
    print("\n" + "="*50)
    print("TEST: False Positive Alert")
    print("="*50)

    # Send alert with moderate confidence
    alert = send_fire_alert(confidence=0.65, detection_type="fire", include_image=True)

    print("\n[Waiting 3 seconds before marking as false positive...]")
    time.sleep(3)

    # Mark as false positive
    resolution = send_resolved_alert(alert["alert_id"], resolution_type="false_positive")

    return alert, resolution


def test_contained_fire():
    """Test a contained fire scenario"""
    print("\n" + "="*50)
    print("TEST: Contained Fire Alert")
    print("="*50)

    # Send high confidence fire alert
    alert = send_fire_alert(confidence=0.92, detection_type="fire", include_image=True)

    print("\n[Waiting 5 seconds before marking as contained...]")
    time.sleep(5)

    # Mark as contained
    resolution = send_resolved_alert(alert["alert_id"], resolution_type="contained")

    return alert, resolution


def test_multiple_alerts_same_region():
    """Test multiple alerts in the same region"""
    print("\n" + "="*50)
    print("TEST: Multiple Alerts in Same Region")
    print("="*50)

    region = random.choice(["north", "central", "south"])
    locations = [loc for loc in VIETNAM_FOREST_LOCATIONS if loc.get("region") == region]

    alerts = []
    for i, loc in enumerate(locations[:3]):
        print(f"\n--- Alert {i+1}/3 ---")
        alert = send_fire_alert(location=loc, include_image=True)
        alerts.append(alert)
        time.sleep(1)

    return alerts


def test_all_regions():
    """Test alerts from all regions"""
    print("\n" + "="*50)
    print("TEST: Alerts from All Regions")
    print("="*50)

    alerts = []
    for region in ["north", "central", "south"]:
        locations = [loc for loc in VIETNAM_FOREST_LOCATIONS if loc.get("region") == region]
        location = random.choice(locations)

        print(f"\n--- Region: {region.upper()} ---")
        alert = send_fire_alert(location=location, include_image=True)
        alerts.append(alert)
        time.sleep(1)

    return alerts


def send_device_status(device_id: str = None, status: str = "online", location: dict = None):
    """Send device status/heartbeat via MQTT"""
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    client.connect(MQTT_BROKER, MQTT_PORT)

    if device_id is None:
        device_id = f"edge_device_{random.randint(1, 10):03d}"

    # Use provided location or pick a random one from Vietnam forests
    if location is None:
        location = random.choice(VIETNAM_FOREST_LOCATIONS)

    device_status = {
        "device_id": device_id,
        "status": status,  # online, offline
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "battery": random.randint(20, 100),  # percentage
        "temperature": round(25 + random.random() * 20, 1),  # 25-45 celsius
        "uptime": random.randint(3600, 86400 * 30),  # seconds (1h to 30 days)
        "firmware_version": "1.2.3",
        "last_detection": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location": {
            "lat": location["lat"],
            "lon": location["lon"],
            "name": location["name"],
        }
    }

    client.publish("wildfire/devices/status", json.dumps(device_status))
    client.disconnect()

    print(f"[DEVICE STATUS] Sent status update:")
    print(f"  - Device ID: {device_id}")
    print(f"  - Status: {status}")
    print(f"  - Location: {location['name']}")
    print(f"  - Coordinates: {location['lat']}, {location['lon']}")
    print(f"  - Battery: {device_status['battery']}%")
    print(f"  - Temperature: {device_status['temperature']}°C")
    print(f"  - Uptime: {device_status['uptime']} seconds")

    return device_status


def test_device_status(device_id: str = None, count: int = 1):
    """Test device status/heartbeat messages"""
    print("\n" + "="*50)
    print("TEST: Device Status/Heartbeat")
    print("="*50)

    statuses = []
    for i in range(count):
        if count > 1:
            print(f"\n--- Device {i+1}/{count} ---")
            # Generate unique device IDs for multiple devices
            dev_id = device_id if device_id and count == 1 else f"edge_device_{i+1:03d}"
        else:
            dev_id = device_id

        status = send_device_status(device_id=dev_id, status="online")
        statuses.append(status)
        if count > 1 and i < count - 1:
            time.sleep(0.5)

    return statuses


def test_resolved_standalone(alert_id: str = None, resolution_type: str = "extinguished"):
    """Test sending a resolved alert standalone (without sending alert first)"""
    print("\n" + "="*50)
    print("TEST: Resolved Alert (Standalone)")
    print("="*50)

    if alert_id is None:
        alert_id = f"alert_{int(time.time())}_{random.randint(100, 999)}"
        print(f"[INFO] Generated alert_id: {alert_id}")

    resolution = send_resolved_alert(alert_id, resolution_type=resolution_type)
    return resolution


def verify_exporter():
    """Verify exporter is receiving alerts"""
    print("\n--- Verifying Exporter ---")
    try:
        response = requests.get(f"{EXPORTER_URL}/metrics", timeout=5)
        if response.status_code == 200:
            print(f"Exporter OK: {EXPORTER_URL}/metrics")
            return True
        else:
            print(f"Exporter error: {response.status_code}")
            return False
    except Exception as e:
        print(f"Cannot connect to exporter: {e}")
        return False


def verify_prometheus():
    """Verify Prometheus has the alerts"""
    print("\n--- Verifying Prometheus ---")
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": "fire_alert_info"},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get("data", {}).get("result", [])
            print(f"Prometheus OK: {len(results)} fire alerts found")
            return True
        else:
            print(f"Prometheus error: {response.status_code}")
            return False
    except Exception as e:
        print(f"Cannot connect to Prometheus: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Fire Detection Test Suite")
    parser.add_argument("--test", "-t", type=str, default="single",
                       choices=["single", "smoke", "resolve", "false_positive",
                               "contained", "multi_region", "all_regions",
                               "device_status", "resolved", "full"],
                       help="Test case to run")
    parser.add_argument("--region", "-r", type=str, default=None,
                       choices=["north", "central", "south"],
                       help="Region filter for alerts")
    parser.add_argument("--verify", "-v", action="store_true",
                       help="Verify exporter and Prometheus after test")
    parser.add_argument("--device", type=str, default=None,
                       help="Device ID for device_status test")
    parser.add_argument("--count", type=int, default=1,
                       help="Number of devices for device_status test")
    parser.add_argument("--alert-id", type=str, default=None,
                       help="Alert ID for resolved test")
    parser.add_argument("--resolution", type=str, default="extinguished",
                       choices=["extinguished", "false_positive", "contained"],
                       help="Resolution type for resolved test")

    args = parser.parse_args()

    print("="*60)
    print("FIRE DETECTION MONITORING - TEST SUITE")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    if args.test == "single":
        test_single_fire_alert(region=args.region)
    elif args.test == "smoke":
        test_single_smoke_alert(region=args.region)
    elif args.test == "resolve":
        test_fire_and_resolve()
    elif args.test == "false_positive":
        test_false_positive()
    elif args.test == "contained":
        test_contained_fire()
    elif args.test == "multi_region":
        test_multiple_alerts_same_region()
    elif args.test == "all_regions":
        test_all_regions()
    elif args.test == "device_status":
        test_device_status(device_id=args.device, count=args.count)
    elif args.test == "resolved":
        test_resolved_standalone(alert_id=args.alert_id, resolution_type=args.resolution)
    elif args.test == "full":
        print("\n>>> Running all test cases <<<\n")
        test_single_fire_alert()
        time.sleep(2)
        test_single_smoke_alert()
        time.sleep(2)
        test_fire_and_resolve()
        time.sleep(2)
        test_false_positive()
        time.sleep(2)
        test_contained_fire()
        time.sleep(2)
        test_device_status(count=3)
        time.sleep(2)
        test_resolved_standalone()

    if args.verify:
        print("\n" + "="*50)
        print("VERIFICATION")
        print("="*50)
        time.sleep(3)  # Wait for processing
        verify_exporter()
        verify_prometheus()

    print("\n" + "="*60)
    print("TEST COMPLETED")
    print("="*60)


if __name__ == "__main__":
    main()
