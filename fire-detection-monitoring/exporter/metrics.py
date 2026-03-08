# exporter/metrics.py
from prometheus_client import Gauge, Counter, Info, REGISTRY, generate_latest
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import threading
import time

@dataclass
class FireAlert:
    alert_id: str
    device_id: str
    latitude: float
    longitude: float
    location: str
    confidence: float
    detection_class: str
    detected_at: str
    image_url: str
    timestamp: float = field(default_factory=time.time)

class FireDetectionMetrics:
    """
    Custom Prometheus metrics cho Fire Detection system.
    Cung cấp đầy đủ labels cần thiết cho Grafana Geomap.
    """

    def __init__(self, image_base_url: str = "http://localhost:8080/images"):
        self.image_base_url = image_base_url
        self.lock = threading.Lock()

        # Store active alerts (để hiển thị trên map)
        self.active_alerts: Dict[str, FireAlert] = {}

        # Store device status
        self.device_status: Dict[str, dict] = {}

        # Alert history (giữ trong 24h)
        self.alert_history: List[FireAlert] = []
        self.max_history_age = 24 * 3600  # 24 hours

        # ========================================
        # PROMETHEUS METRICS DEFINITIONS
        # ========================================

        # 1. Fire Alert Gauge (CHO GEOMAP)
        # Labels bắt buộc: latitude, longitude
        # Labels tùy chọn: hiển thị trong tooltip
        self.fire_alert_gauge = Gauge(
            'fire_alert_info',
            'Fire detection alert information with location',
            labelnames=[
                'alert_id',
                'device_id',
                'latitude',      # BẮT BUỘC cho Geomap
                'longitude',     # BẮT BUỘC cho Geomap
                'location',
                'class',
                'detected_at',
                'image_url'
            ]
        )

        # 2. Latest confidence per device (CHO GEOMAP)
        self.confidence_gauge = Gauge(
            'fire_confidence_latest',
            'Latest fire detection confidence per device',
            labelnames=[
                'device_id',
                'latitude',      # BẮT BUỘC cho Geomap
                'longitude',     # BẮT BUỘC cho Geomap
                'location'
            ]
        )

        # 3. Device status (CHO GEOMAP - hiển thị devices)
        self.device_status_gauge = Gauge(
            'fire_device_status',
            'Device online status (1=online, 0=offline)',
            labelnames=[
                'device_id',
                'latitude',      # BẮT BUỘC cho Geomap
                'longitude',     # BẮT BUỘC cho Geomap
                'location'
            ]
        )

        # 4. Total alerts counter
        self.alerts_total = Counter(
            'fire_alerts_total',
            'Total number of fire alerts',
            labelnames=['device_id', 'location', 'class']
        )

        # 5. Active alerts count
        self.active_alerts_gauge = Gauge(
            'fire_active_alerts_count',
            'Number of currently active fire alerts'
        )

        # 6. Alert processing time
        self.processing_time = Gauge(
            'fire_alert_processing_seconds',
            'Time to process fire alert'
        )

        # 7. Resolved alerts counter
        self.resolved_total = Counter(
            'fire_resolved_total',
            'Total number of resolved fire alerts',
            labelnames=['resolution_type', 'resolved_by']
        )

        # 8. Resolved alerts count (current)
        self.resolved_count_gauge = Gauge(
            'fire_resolved_count',
            'Number of resolved alerts'
        )

        # Track resolved count
        self._resolved_count = 0

    def add_alert(self, alert: FireAlert):
        """Thêm alert mới và update metrics"""
        with self.lock:
            # Lưu alert
            self.active_alerts[alert.alert_id] = alert
            self.alert_history.append(alert)

            # Cleanup old history
            self._cleanup_old_alerts()

            # Update Prometheus metrics
            self._update_metrics(alert)

            print(f"Added alert: {alert.alert_id} at ({alert.latitude}, {alert.longitude})")

    def _update_metrics(self, alert: FireAlert):
        """Update tất cả Prometheus metrics"""

        # 1. Fire Alert Info (cho Geomap)
        # Note: 'class' is Python reserved keyword, use **{'class': value}
        self.fire_alert_gauge.labels(
            alert_id=alert.alert_id,
            device_id=alert.device_id,
            latitude=str(alert.latitude),      # Phải là string trong labels
            longitude=str(alert.longitude),    # Phải là string trong labels
            location=alert.location,
            detected_at=alert.detected_at,
            image_url=alert.image_url,
            **{'class': alert.detection_class}
        ).set(alert.confidence)

        # 2. Latest confidence per device
        self.confidence_gauge.labels(
            device_id=alert.device_id,
            latitude=str(alert.latitude),
            longitude=str(alert.longitude),
            location=alert.location
        ).set(alert.confidence)

        # 3. Total alerts counter
        self.alerts_total.labels(
            device_id=alert.device_id,
            location=alert.location,
            **{'class': alert.detection_class}
        ).inc()

        # 4. Active alerts count
        self.active_alerts_gauge.set(len(self.active_alerts))

    def update_device_status(self, device_id: str, latitude: float,
                            longitude: float, location: str, is_online: bool):
        """Update device status"""
        with self.lock:
            self.device_status[device_id] = {
                'latitude': latitude,
                'longitude': longitude,
                'location': location,
                'is_online': is_online,
                'last_seen': time.time()
            }

            self.device_status_gauge.labels(
                device_id=device_id,
                latitude=str(latitude),
                longitude=str(longitude),
                location=location
            ).set(1 if is_online else 0)

    def remove_alert(self, alert_id: str, resolution_type: str = "resolved",
                     resolved_by: str = "unknown"):
        """Xóa alert (khi đã acknowledge) và track resolved"""
        with self.lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts.pop(alert_id)

                # Remove from Prometheus
                try:
                    self.fire_alert_gauge.remove(
                        alert.alert_id,
                        alert.device_id,
                        str(alert.latitude),
                        str(alert.longitude),
                        alert.location,
                        alert.detection_class,
                        alert.detected_at,
                        alert.image_url
                    )
                except KeyError:
                    pass

                # Update active alerts count
                self.active_alerts_gauge.set(len(self.active_alerts))

                # Track resolved
                self.resolved_total.labels(
                    resolution_type=resolution_type,
                    resolved_by=resolved_by
                ).inc()

                self._resolved_count += 1
                self.resolved_count_gauge.set(self._resolved_count)

                print(f"Alert {alert_id} resolved: {resolution_type} by {resolved_by}")
            else:
                print(f"Alert {alert_id} not found in active alerts")

    def _cleanup_old_alerts(self):
        """Cleanup alerts cũ hơn max_history_age"""
        current_time = time.time()
        cutoff_time = current_time - self.max_history_age

        # Cleanup history
        self.alert_history = [
            a for a in self.alert_history
            if a.timestamp > cutoff_time
        ]

        # Cleanup active alerts (giữ trong 1 giờ)
        active_cutoff = current_time - 3600
        expired_ids = [
            aid for aid, alert in self.active_alerts.items()
            if alert.timestamp < active_cutoff
        ]

        for alert_id in expired_ids:
            self.remove_alert(alert_id)

    def get_all_alerts(self) -> List[FireAlert]:
        """Lấy tất cả active alerts"""
        with self.lock:
            return list(self.active_alerts.values())

    def get_metrics(self) -> bytes:
        """Generate Prometheus metrics output"""
        return generate_latest(REGISTRY)


# Singleton instance
_metrics_instance: Optional[FireDetectionMetrics] = None

def get_metrics() -> FireDetectionMetrics:
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = FireDetectionMetrics()
    return _metrics_instance