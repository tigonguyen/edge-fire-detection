# Fire Detection Test Guide

## Yeu cau truoc khi chay test

### Services can chay
1. MQTT Broker (localhost:1883)
2. Fire Detection Exporter (localhost:8000)
3. Prometheus (localhost:9090)
4. Alertmanager (localhost:9093)

### Khoi dong services
```bash
cd fire-detection-monitoring
docker-compose up -d
```

---

## Cac Test Case

### 1. Test canh bao chay don le

Gui mot canh bao phat hien chay tai mot khu rung ngau nhien o Viet Nam (co kem hinh anh).

```bash
./test_fire_alerts.py --test single
```

**Loc theo vung:**
```bash
# Mien Bac
./test_fire_alerts.py --test single --region north

# Mien Trung
./test_fire_alerts.py --test single --region central

# Mien Nam
./test_fire_alerts.py --test single --region south
```

**Ket qua mong doi:**
- Canh bao duoc gui qua MQTT topic `wildfire/alerts`
- Prometheus nhan duoc metric `fire_alert_info`
- Alertmanager gui thong bao Telegram

---

### 2. Test canh bao phat hien khoi

Gui canh bao phat hien khoi (do tin cay thap hon chay).

```bash
./test_fire_alerts.py --test smoke
```

**Ket qua mong doi:**
- Canh bao khoi voi confidence 50-80%
- Hinh anh smoke_sample duoc dinh kem

---

### 3. Test chay rung da duoc xu ly (EXTINGUISHED)

Gui canh bao chay, sau do gui thong bao da dap tat.

```bash
./test_fire_alerts.py --test resolve
```

**Quy trinh:**
1. Gui canh bao chay
2. Doi 5 giay
3. Gui thong bao da xu ly (resolution_type: extinguished)

**Ket qua mong doi:**
- Canh bao ban dau duoc gui
- Sau 5 giay, thong bao "resolved" duoc gui qua topic `wildfire/alerts/resolved`
- Trang thai chuyen tu "active" sang "resolved"

---

### 4. Test bao dong gia (FALSE POSITIVE)

Gui canh bao roi danh dau la bao dong gia.

```bash
./test_fire_alerts.py --test false_positive
```

**Quy trinh:**
1. Gui canh bao voi confidence vua phai (65%)
2. Doi 3 giay
3. Danh dau la false positive

**Ket qua mong doi:**
- Canh bao ban dau
- Resolution voi type "false_positive"

---

### 5. Test chay da duoc kiem soat (CONTAINED)

Gui canh bao chay lon, sau do danh dau da kiem soat duoc.

```bash
./test_fire_alerts.py --test contained
```

**Quy trinh:**
1. Gui canh bao voi confidence cao (92%)
2. Doi 5 giay
3. Danh dau la "contained" (da kiem soat)

**Ket qua mong doi:**
- Canh bao critical
- Resolution voi type "contained"

---

### 6. Test nhieu canh bao trong cung vung

Gui 3 canh bao lien tiep trong cung mot vung.

```bash
./test_fire_alerts.py --test multi_region
```

**Ket qua mong doi:**
- 3 canh bao tu cac vi tri khac nhau trong cung vung
- Alertmanager se group cac canh bao theo `device_id`

---

### 7. Test canh bao tu tat ca cac vung

Gui canh bao tu ca 3 mien: Bac, Trung, Nam.

```bash
./test_fire_alerts.py --test all_regions
```

**Ket qua mong doi:**
- 3 canh bao tu 3 vung khac nhau

---

### 8. Test trang thai hoat dong cua thiet bi

Gui trang thai hoat dong (heartbeat/status) cua thiet bi edge.

```bash
./test_fire_alerts.py --test device_status
```

**Tuy chon:**
```bash
# Gui trang thai cho thiet bi cu the
./test_fire_alerts.py --test device_status --device edge_device_001

# Gui trang thai cho nhieu thiet bi
./test_fire_alerts.py --test device_status --count 5
```

**Ket qua mong doi:**
- Thong tin trang thai thiet bi duoc gui qua MQTT topic `wildfire/devices/status`
- Bao gom: device_id, status (online/offline), battery, temperature, uptime

---

### 9. Test gui resolved alert don le

Gui thong bao resolved alert (khong can gui alert truoc).

```bash
./test_fire_alerts.py --test resolved
```

**Tuy chon resolution type:**
```bash
# Da dap tat
./test_fire_alerts.py --test resolved --resolution extinguished

# Bao dong gia
./test_fire_alerts.py --test resolved --resolution false_positive

# Da kiem soat
./test_fire_alerts.py --test resolved --resolution contained
```

**Ket qua mong doi:**
- Thong bao resolved duoc gui qua MQTT topic `wildfire/resolved`
- Alert ID duoc tao tu dong

---

### 10. Test resolved alert cho alert ID cu the

Gui thong bao resolved cho mot alert ID da biet.

```bash
./test_fire_alerts.py --test resolved --alert-id alert_1234567890_123
```

**Vi du su dung:**
```bash
# Buoc 1: Gui canh bao va ghi nho alert_id
./test_fire_alerts.py --test single
# Output: Alert ID: alert_1709123456_789

# Buoc 2: Resolve alert do
./test_fire_alerts.py --test resolved --alert-id alert_1709123456_789 --resolution extinguished
```

**Ket qua mong doi:**
- Thong bao resolved duoc gui voi alert_id chinh xac
- Exporter cap nhat trang thai alert tu "active" sang "resolved"

---

### 11. Chay tat ca test case

Chay tuan tu tat ca cac test case.

```bash
./test_fire_alerts.py --test full
```

---

## Kiem tra ket qua

### Them flag `--verify` de kiem tra Exporter va Prometheus

```bash
./test_fire_alerts.py --test single --verify
```

### Kiem tra thu cong

**Exporter metrics:**
```bash
curl http://localhost:8000/metrics | grep fire_alert
```

**Prometheus query:**
```bash
curl 'http://localhost:9090/api/v1/query?query=fire_alert_info'
```

**Alertmanager alerts:**
```bash
curl http://localhost:9093/api/v1/alerts
```

---

## Cau hinh

### Bien moi truong

| Variable | Default | Mo ta |
|----------|---------|-------|
| `MQTT_BROKER` | localhost | MQTT broker address |
| `MQTT_PORT` | 1883 | MQTT broker port |
| `EXPORTER_URL` | http://localhost:8000 | Fire exporter URL |
| `PROMETHEUS_URL` | http://localhost:9090 | Prometheus URL |

### Vi du cau hinh:
```bash
export MQTT_BROKER=192.168.1.100
export MQTT_PORT=1883
./test_fire_alerts.py --test single
```

---

## Danh sach cac khu rung trong test

### Mien Bac
- Rung quoc gia Hoang Lien - Sa Pa, Lao Cai
- Rung quoc gia Ba Vi - Ha Noi
- Rung quoc gia Tam Dao - Vinh Phuc
- Vuon quoc gia Cat Ba - Hai Phong
- Rung phong ho Soc Son - Ha Noi

### Mien Trung
- Vuon quoc gia Bach Ma - Thua Thien Hue
- Rung dac dung Phong Dien - Thua Thien Hue
- Vuon quoc gia Kon Ka Kinh - Gia Lai
- Vuon quoc gia Bidoup Nui Ba - Lam Dong
- Vuon quoc gia Phong Nha - Ke Bang - Quang Binh

### Mien Nam
- Vuon quoc gia Cat Tien - Dong Nai
- Rung ngap man Can Gio - TP.HCM
- Vuon quoc gia U Minh Thuong - Kien Giang
- Khu bao ton thien nhien Binh Chau - Ba Ria Vung Tau
- Rung thong Da Lat - Lam Dong

---

## Troubleshooting

### MQTT connection failed
```bash
# Kiem tra MQTT broker
docker-compose logs mqtt

# Hoac test ket noi
mosquitto_pub -h localhost -t test -m "hello"
```

### Khong nhan duoc Telegram notification
1. Kiem tra bien moi truong `TELEGRAM_BOT_TOKEN` va `TELEGRAM_CHAT_ID`
2. Kiem tra Alertmanager logs:
```bash
docker-compose logs alertmanager
```

### Prometheus khong co data
1. Kiem tra Exporter hoat dong:
```bash
curl http://localhost:8000/metrics
```
2. Kiem tra Prometheus targets:
   - Truy cap http://localhost:9090/targets

### Kiem tra device status
```bash
# Xem tat ca device status
curl http://localhost:8000/metrics | grep device_status

# Query Prometheus
curl 'http://localhost:9090/api/v1/query?query=device_status_info'
```

### Kiem tra resolved alerts
```bash
# Xem resolved alerts trong exporter
curl http://localhost:8000/metrics | grep fire_alert_resolved

# Hoac kiem tra tren Alertmanager
curl http://localhost:9093/api/v2/alerts | jq '.[] | select(.status.state == "resolved")'
```
