# exporter/notification.py
import os
import requests
from typing import Optional
from metrics import FireAlert

class NotificationService:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

    def send_alert(self, alert: FireAlert, image_path: Optional[str] = None):
        """Send alert notification via configured channels"""
        if self.telegram_token and self.telegram_chat_id:
            self._send_telegram(alert, image_path)

    def _send_telegram(self, alert: FireAlert, image_path: Optional[str]):
        """Send notification via Telegram"""
        message = self._format_message(alert)

        # Send to multiple chat IDs if configured
        chat_ids = [cid.strip() for cid in self.telegram_chat_id.split(',')]

        for chat_id in chat_ids:
            try:
                if image_path and os.path.exists(image_path):
                    # Send with photo
                    url = f"https://api.telegram.org/bot{self.telegram_token}/sendPhoto"
                    with open(image_path, 'rb') as photo:
                        files = {'photo': photo}
                        data = {
                            'chat_id': chat_id,
                            'caption': message,
                            'parse_mode': 'HTML'
                        }
                        response = requests.post(url, files=files, data=data, timeout=30)
                else:
                    # Send text only
                    url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                    data = {
                        'chat_id': chat_id,
                        'text': message,
                        'parse_mode': 'HTML'
                    }
                    response = requests.post(url, json=data, timeout=30)

                if response.status_code == 200:
                    print(f"Telegram notification sent to {chat_id}")
                else:
                    print(f"Telegram error: {response.text}")

            except Exception as e:
                print(f"Failed to send Telegram to {chat_id}: {e}")

    def _format_message(self, alert: FireAlert) -> str:
        """Format alert message"""
        google_maps_url = f"https://maps.google.com/?q={alert.latitude},{alert.longitude}"

        return f"""
🔥 <b>CẢNH BÁO PHÁT HIỆN CHÁY RỪNG!</b>

📍 <b>Vị trí:</b> {alert.location}
🌍 <b>Tọa độ:</b> <a href="{google_maps_url}">{alert.latitude:.6f}, {alert.longitude:.6f}</a>
📊 <b>Độ tin cậy:</b> {alert.confidence*100:.1f}%
🔍 <b>Loại:</b> {alert.detection_class}
⏰ <b>Thời gian:</b> {alert.detected_at}

🆔 Alert ID: <code>{alert.alert_id}</code>
📡 Device: <code>{alert.device_id}</code>

⚠️ Vui lòng kiểm tra và xử lý kịp thời!
"""