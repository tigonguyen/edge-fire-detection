# exporter/main.py
import os
import uvicorn
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading
import time

from metrics import get_metrics, FireAlert
from mqtt_handler import MQTTHandler

# Global instances
mqtt_handler: MQTTHandler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mqtt_handler

    # Startup
    print("Starting Fire Detection Exporter...")

    # Fire detection simulation flags (for testing without real AI model)
    # Set SIMULATE_FIRE=true to always detect fire when receiving images
    # Set SIMULATE_SMOKE=true to always detect smoke when receiving images
    simulate_fire = os.getenv('SIMULATE_FIRE', 'false').lower() == 'true'
    simulate_smoke = os.getenv('SIMULATE_SMOKE', 'false').lower() == 'true'
    model_path = os.getenv('FIRE_MODEL_PATH', None)
    alert_cooldown = int(os.getenv('ALERT_COOLDOWN_SECONDS', '300'))  # 5 minutes default

    if simulate_fire or simulate_smoke:
        print(f"[WARNING] Running in SIMULATION mode: fire={simulate_fire}, smoke={simulate_smoke}")

    print(f"[CONFIG] Alert cooldown: {alert_cooldown} seconds")

    mqtt_handler = MQTTHandler(
        broker=os.getenv('MQTT_BROKER', 'localhost'),
        port=int(os.getenv('MQTT_PORT', 1883)),
        images_dir=os.getenv('IMAGES_DIR', './images'),
        image_base_url=os.getenv('IMAGE_BASE_URL', 'http://localhost:8080/images'),
        simulate_fire=simulate_fire,
        simulate_smoke=simulate_smoke,
        model_path=model_path,
        alert_cooldown_seconds=alert_cooldown
    )
    mqtt_handler.connect()

    yield

    # Shutdown
    print("Shutting down...")
    if mqtt_handler:
        mqtt_handler.disconnect()

app = FastAPI(
    title="Fire Detection Prometheus Exporter",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "running", "service": "Fire Detection Exporter"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_handler.connected if mqtt_handler else False
    }

@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    Grafana sẽ query endpoint này thông qua Prometheus.
    """
    metrics_data = get_metrics().get_metrics()
    return Response(
        content=metrics_data,
        media_type="text/plain; charset=utf-8"
    )

@app.get("/alerts")
async def get_alerts():
    """Get all active alerts (for debugging)"""
    alerts = get_metrics().get_all_alerts()
    return {
        "count": len(alerts),
        "alerts": [
            {
                "alert_id": a.alert_id,
                "device_id": a.device_id,
                "latitude": a.latitude,
                "longitude": a.longitude,
                "location": a.location,
                "confidence": a.confidence,
                "class": a.detection_class,
                "detected_at": a.detected_at,
                "image_url": a.image_url
            }
            for a in alerts
        ]
    }

@app.get("/scan-history")
async def get_scan_history(limit: int = 100, detected_only: bool = False):
    """
    Get scan history for debugging.
    All scanned images are saved and logged, regardless of detection result.

    Query params:
    - limit: max number of records to return (default 100)
    - detected_only: if true, only return records where fire/smoke was detected
    """
    if not mqtt_handler:
        return {"count": 0, "scans": []}

    scans = mqtt_handler.get_scan_history(limit=limit, detected_only=detected_only)
    return {
        "count": len(scans),
        "scans": scans
    }


# For testing: Simulate an alert
@app.post("/test-alert")
async def test_alert():
    """Send a test alert (for development)"""
    import uuid
    from datetime import datetime

    alert = FireAlert(
        alert_id=str(uuid.uuid4())[:8],
        device_id="test_device_001",
        latitude=21.0285 + (hash(str(time.time())) % 100) / 10000,
        longitude=105.8542 + (hash(str(time.time())) % 100) / 10000,
        location="Test Location - Khu vực rừng thử nghiệm",
        confidence=0.85 + (hash(str(time.time())) % 15) / 100,
        detection_class="fire",
        detected_at=datetime.now().isoformat(),
        image_url=""
    )

    get_metrics().add_alert(alert)

    return {"message": "Test alert created", "alert_id": alert.alert_id}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)