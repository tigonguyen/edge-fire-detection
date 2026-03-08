# exporter/notification.py
import os
import requests
from typing import Optional
from metrics import FireAlert

class NotificationService:
    """
    Send fire alert notifications via Telegram.

    Strategy:
    - This service sends IMMEDIATE notification with photo when fire is detected
    - Alertmanager is used for REMINDERS only (if alert not resolved after X minutes)
    - This avoids duplicate notifications while still supporting photos
    """

    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

    def send_alert(self, alert: FireAlert, image_path: Optional[str] = None):
        """Send immediate alert notification with photo via Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print(f"Telegram not configured, skipping notification for {alert.alert_id}")
            return

        # Always send full notification with photo (Alertmanager will only remind later)
        self._send_telegram_notification(alert, image_path)

    def _send_telegram_notification(self, alert: FireAlert, image_path: Optional[str]):
        """Send full notification with photo via Telegram"""
        message = self._format_message(alert)
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
                    msg_type = "with photo"
                else:
                    # Send text only (no image available)
                    url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                    data = {
                        'chat_id': chat_id,
                        'text': message,
                        'parse_mode': 'HTML'
                    }
                    response = requests.post(url, json=data, timeout=30)
                    msg_type = "text only"

                if response.status_code == 200:
                    print(f"Telegram notification sent ({msg_type}) to {chat_id} for alert {alert.alert_id}")
                else:
                    print(f"Telegram error: {response.text}")

            except Exception as e:
                print(f"Failed to send Telegram to {chat_id}: {e}")

    def send_resolution(self, alert_id: str, resolution_type: str,
                        resolved_by: str, notes: str):
        """Send resolution notification via Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print(f"Telegram not configured, skipping resolution notification")
            return

        # Format resolution message
        resolution_emoji = {
            'resolved': '✅',
            'extinguished': '🚒',
            'contained': '🛡️',
            'false_positive': '❌',
            'false_alarm': '❌',
            'acknowledged': '👁️',
        }
        emoji = resolution_emoji.get(resolution_type, '✅')

        message = f"""
{emoji} <b>CẢNH BÁO ĐÃ ĐƯỢC XỬ LÝ</b>

🆔 Alert ID: <code>{alert_id}</code>
📋 <b>Trạng thái:</b> {resolution_type.upper()}
👤 <b>Xử lý bởi:</b> {resolved_by}
"""
        if notes:
            message += f"📝 <b>Ghi chú:</b> {notes}\n"

        message += "\n✅ Alert đã được đóng, không còn nhận reminder."

        chat_ids = [cid.strip() for cid in self.telegram_chat_id.split(',')]

        for chat_id in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                data = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                response = requests.post(url, json=data, timeout=30)

                if response.status_code == 200:
                    print(f"Resolution notification sent to {chat_id} for alert {alert_id}")
                else:
                    print(f"Telegram error: {response.text}")

            except Exception as e:
                print(f"Failed to send resolution notification to {chat_id}: {e}")

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