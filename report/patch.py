import codecs

with codecs.open('report.tex', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_content = """\\section{Nội dung nghiên cứu}

Phạm vi nghiên cứu của đề tài tập trung vào việc ứng dụng thuật toán học sâu (Deep Learning) để phân loại và phát hiện hình ảnh lửa hoặc khói theo thời gian thực. Hướng tiếp cận này giải quyết bài toán độ trễ bằng cách đưa các mô hình trí tuệ nhân tạo (AI) lên thiết bị biên vốn có những giới hạn khắt khe về sức mạnh phần cứng và mức tiêu thụ năng lượng. Nhóm lựa chọn dòng kiến trúc EfficientNet \\cite{tan2019efficientnet} kết hợp với nền tảng PyTorch trong quá trình xây dựng, cấu hình và huấn luyện mô hình. Nhằm điều chỉnh hệ thống phức tạp này phù hợp cho môi trường nhúng thực tế, đồ án tiến hành tối ưu hóa cấu trúc bộ nhớ và chuyển đổi sang định dạng thực thi trung gian ONNX \\cite{onnxruntime}. Đặc biệt, nghiên cứu này đóng góp trực tiếp bằng việc so sánh ba phương pháp triển khai đa dạng: sử dụng định dạng EfficientNet-Lite0 nguyên bản, vận hành với mạng lưới EfficientNet-B0 tiêu chuẩn, và phương pháp chưng cất tri thức (Knowledge Distillation) \\cite{hinton2015distilling, gou2021survey}. Việc định lượng này sẽ chỉ ra phương án lý thuyết độ cân bằng tối ưu giữa giới hạn cấp phát tài nguyên phần cứng và tỷ lệ độ chuẩn xác nhận diện.

Bên cạnh mảng lõi phân tích hình ảnh cục bộ, nội dung đề tài còn thiết kế cơ chế hạ tầng mạng phân tán cho tin nhắn sự kiện khẩn cấp trên không gian mạng thiết bị lớn. Sau khi ứng dụng nhận được tín hiệu hình ảnh trực tiếp thông qua thư viện OpenCV \\cite{opencv}, thiết bị biên tự động lọc lại, đóng gói siêu dữ liệu định vị và truyền tải thông qua giao thức truyền tải trọng lượng nhẹ MQTT. Về phía trạm quản lý, hệ thống máy chủ vận hành nền móng trung tâm phối hợp được đặt trên nền tảng hạ tầng điều phối mạng Kubernetes. Tại khối đám mây này, dự án áp dụng hệ thống điều khiển quản lý tài nguyên linh hoạt, điển hình là khai báo cơ chế tĩnh nodeSelector nhằm bảo vệ tính toàn vẹn của khả năng đa quy trình để giữ vững luồng mạng ổn định tổng thể.

\\section{Tóm tắt nội dung thực hiện}

Quá trình tiến hành đồ án được cấu trúc thành hai mảng kỹ thuật cốt lõi: xử lý học máy cục bộ tại thiết bị biên và phát triển hệ sinh thái quản lý trung tâm. Ở giai đoạn huấn luyện nhận diện hình ảnh, nhóm nghiên cứu đã tổng hợp tập dữ liệu ảnh đa dạng từ nhiều nguồn, bao gồm các cấu trúc hình ảnh báo cháy, khói và cảnh quan rừng mở tĩnh. Để củng cố chất lượng dữ liệu nhóm, các kỹ thuật tăng cường biểu diễn hình ảnh (Data Augmentation) của thư viện PyTorch đã được áp dụng, làm đa dạng đồ thị biểu diễn và giúp cho mô hình bền bỉ hơn khi nhận diện ngoài môi trường tự nhiên. Các mô hình sau khi huấn luyện đạt hội tụ bắt buộc chuyển đổi sang định dạng nền tảng ONNX Runtime để giảm thiểu đáng kể dung lượng bộ nhớ cũng như tối ưu phần cứng hệ vi nhúng. Tại thiết bị biên, nhóm phát triển bộ thực thi Python thu nhận video băng thông hình ảnh tốc độ thấp, phán đoán sự cố, và nối định tuyến gói mạng cảnh báo định vị vị trí thông qua giao thức rút vắn MQTT.

Phía ở phía đối cực nằm trong phân khối phần mềm trên điều khiển Kubernetes, nhóm sinh viên xây dựng chuỗi ứng dụng giao thức API tạo nền FastAPI tiếp điểm kết nhận đường mạng. Khối giao diện này áp lệnh chuẩn quản lý bằng kiểm soát tần suất gửi thông giới hạn (rate limiting) từ chối rào phân vùng một nguồn sự cố nhiều lần không chủ đích cho trung tâm. Nền tảng hiển thị cảnh báo trung tâm đều giao phó toàn phần thông qua ba giao diện: Prometheus, Grafana, và bộ giao tuyến Alertmanager. Prometheus đóng chức vụ bắt tiến độ báo của API để thành số lọc cho Alertmanager lệnh gửi số liệu độ nguy cấp về trong điện thoại Telegram Bot. Tin nhắn cảnh báo chuyên ngành định rõ phần vĩ độ địa lý và hiện trường cháy từ camera ảnh gửi trong quá trình thiết lập trực tiếp. Hệ thống mạng lưới trực diện lớn này mô hình định vị Geomap hiển hiện tổng đài Grafana, hỗ trợ ứng cứu theo sát các vùng cháy ở những mili-giây thời gian thực chạy.
"""

# Replace lines 101 to 119 (index 101 to 119) with the new text
lines[101:119] = [new_content]

with codecs.open('report.tex', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Patch applied successfully.")
