https://docs.docker.com/engine/install/debian/

https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-compose-on-ubuntu-20-04

sudo apt update
sudo apt install python3-venv

python3 -m venv .venv
source .venv/bin/activate
pip3 install requests
pip3 install paho-mqtt
pip3 install opencv-python
pip3 install opencv-python-headless

chmod +x run-all.sh */run.sh */entrypoint.sh 2>/dev/null; echo "Done"

ssh -L 3000:localhost:3000 tu.ngo@34.126.167.11

sudo rm -r */data

./test_fire_alerts.py --test resolved --alert-id alert_1773048569_282 --resolution extinguished


./test_fire_alerts.py --test device_status --count 3


./test_fire_alerts.py --test video --video fire.mp4 --start-frame 500 --max-frames 1


# Kết hợp nhiều options
python test_fire_alerts.py --test video \
    --video patrol.mp4 \
    --device drone_01 \
    --region central \
    --interval 1.5 \
    --max-frames 20 \
    --jpeg-quality 75


ssh -L 8000:localhost:8000 tu.ngo@34.87.189.26



http://localhost:8000/scan-history


Alert đầu tiên: tạo mới, lưu timestamp
Alert tiếp theo (< 5 phút, cùng device, cùng khu vực):
  - Nếu confidence cao hơn → cập nhật
  - Nếu không → bỏ qua
Alert sau 5 phút: tạo alert mới